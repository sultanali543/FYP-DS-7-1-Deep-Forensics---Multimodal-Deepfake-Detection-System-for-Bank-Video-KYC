"""Small synthetic fixtures test correctness, never deepfake model accuracy."""

from collections import defaultdict
import json
from pathlib import Path
import zipfile

import numpy as np
import pytest

from ml.common import read_json
from ml.data import add_source_groups, assign_splits, audit_splits, import_dfdc, metadata_rows, open_video
from ml.faces import create_crop_review, frame_positions, square_box
from ml.metrics import aggregate_scores, classification_metrics, grouped_bootstrap, select_threshold
from ml.train import fit_head, training_weights, video_arrays


def synthetic_metadata(groups=15):
    metadata = {}
    for index in range(groups):
        original = f"real_{index:03d}.mp4"
        metadata[original] = {"label": "REAL", "split": "train"}
        metadata[f"fake_{index:03d}.mp4"] = {"label": "FAKE", "original": original, "split": "train"}
    return metadata


def synthetic_features():
    generator = np.random.default_rng(7)
    rows = assign_splits(add_source_groups(metadata_rows(synthetic_metadata())), seed=42)
    entries = []
    for row in rows:
        for _ in range(2):
            entries.append((row, generator.normal(loc=2 * row["label"] - 1, scale=0.2, size=3)))
    return {
        "features": np.array([vector for _, vector in entries], dtype=np.float32),
        "video_ids": np.array([row["video_id"] for row, _ in entries]),
        "labels": np.array([row["label"] for row, _ in entries]),
        "splits": np.array([row["split"] for row, _ in entries]),
        "groups": np.array([row["group_id"] for row, _ in entries]),
    }


def test_source_pairs_never_cross_splits_and_seed_is_reproducible():
    first = assign_splits(add_source_groups(metadata_rows(synthetic_metadata())), seed=42)
    second = assign_splits(add_source_groups(metadata_rows(synthetic_metadata())), seed=42)
    assert first == second
    memberships = defaultdict(set)
    for row in first:
        memberships[row["group_id"]].add(row["split"])
    assert all(len(splits) == 1 for splits in memberships.values())
    assert sum(part["total"] for part in audit_splits(first).values()) == 30


def test_chained_original_references_stay_in_one_connected_group():
    rows = [
        {"video_id": "a.mp4", "original": "a.mp4"},
        {"video_id": "b.mp4", "original": "a.mp4"},
        {"video_id": "c.mp4", "original": "b.mp4"},
    ]
    assert len({row["group_id"] for row in add_source_groups(rows)}) == 1


def test_explicit_split_leakage_is_rejected():
    rows = assign_splits(add_source_groups(metadata_rows(synthetic_metadata())))
    related = [row for row in rows if row["group_id"] == rows[0]["group_id"]]
    related[0]["split"] = "val" if related[1]["split"] != "val" else "test"
    with pytest.raises(ValueError, match="leakage"):
        audit_splits(rows)


def test_missing_original_and_unsafe_metadata_names_are_rejected():
    with pytest.raises(ValueError, match="original-video reference"):
        metadata_rows({"a.mp4": {"label": "REAL"}, "b.mp4": {"label": "FAKE"}})
    with pytest.raises(ValueError, match="path"):
        metadata_rows({"../escape.mp4": {"label": "REAL"}})


def test_zip_processing_streams_one_member_and_cleans_its_own_temporary_file(tmp_path):
    archive = tmp_path / "sample.zip"
    metadata = synthetic_metadata()
    with zipfile.ZipFile(archive, "w") as handle:
        handle.writestr("train_sample_videos/metadata.json", json.dumps(metadata))
        for name in metadata:
            handle.writestr("train_sample_videos/" + name, b"synthetic-video-fixture")
        handle.writestr("test_videos/unlabeled.mp4", b"not-used")
    manifest = import_dfdc(archive, tmp_path / "manifest.json")
    assert len(manifest["rows"]) == 30
    assert all("unlabeled" not in row["video_id"] for row in manifest["rows"])
    with open_video(manifest, manifest["rows"][0]) as video:
        temporary = video
        assert video.read_bytes() == b"synthetic-video-fixture"
    assert not temporary.exists()


def test_uniform_frame_sampling_and_boundary_crop_remain_valid():
    assert frame_positions(100, 4) == [0, 33, 66, 99]
    assert frame_positions(2, 12) == [0, 1]
    left, top, right, bottom = square_box([-10, -10, 60, 60], 100, 80, 0.25)
    assert 0 <= left < right <= 100
    assert 0 <= top < bottom <= 80
    assert right - left == bottom - top


def test_frame_aggregation_gives_each_video_one_evaluation_record():
    scores = aggregate_scores(["a", "a", "a", "b"], [0.9, 0.9, 0.3, 0.1])
    assert scores["a"] == pytest.approx(0.7)
    assert scores["b"] == pytest.approx(0.1)


def test_training_weights_balance_videos_instead_of_counting_crops_as_independent():
    ids = np.array(["real"] * 8 + ["fake1"] * 2 + ["fake2"] * 3)
    labels = np.array([0] * 8 + [1] * 5)
    weights = training_weights(ids, labels)
    assert weights[labels == 0].sum() == pytest.approx(weights[labels == 1].sum())
    assert weights[ids == "fake1"].sum() == pytest.approx(weights[ids == "fake2"].sum())


def test_scaling_and_selection_do_not_use_test_labels_or_values():
    cache = synthetic_features()
    best, _ = fit_head(cache, [0.1, 1.0])
    changed = {key: value.copy() for key, value in cache.items()}
    changed["features"][changed["splits"] == "test"] = 10000
    changed["labels"][changed["splits"] == "test"] = 1 - changed["labels"][changed["splits"] == "test"]
    other, _ = fit_head(changed, [0.1, 1.0])
    np.testing.assert_allclose(best["scaler"].mean_, other["scaler"].mean_)
    np.testing.assert_allclose(best["classifier"].coef_, other["classifier"].coef_)
    assert best["summary"] == {**other["summary"], "fit_seconds": best["summary"]["fit_seconds"]}


def test_threshold_and_metrics_handle_class_imbalance_and_missing_classes():
    labels = [0, 0, 1, 1]
    scores = [0.1, 0.2, 0.6, 0.9]
    threshold = select_threshold(labels, scores)
    result = classification_metrics(labels, scores, threshold)
    assert result["confusion_matrix"] == [[2, 0], [0, 2]]
    assert result["balanced_accuracy"] == 1
    assert result["majority_class_accuracy"] == 0.5
    with pytest.raises(ValueError, match="both classes"):
        classification_metrics([0, 0], [0.1, 0.2], 0.5)
    with pytest.raises(ValueError, match="finite"):
        select_threshold(labels, [0.1, np.nan, 0.6, 0.9])


def test_conflicting_video_labels_cannot_silently_enter_metrics():
    cache = synthetic_features()
    indices = np.flatnonzero(cache["splits"] == "val")
    cache["labels"][indices[0]] = 1 - cache["labels"][indices[0]]
    with pytest.raises(ValueError, match="Conflicting"):
        video_arrays(cache, np.full(len(cache["labels"]), 0.5), "val")


def test_checkpoint_linear_head_matches_sklearn_without_pickled_estimators():
    import torch
    cache = synthetic_features()
    best, _ = fit_head(cache, [0.1])
    scaler, classifier = best["scaler"], best["classifier"]
    standardized = (torch.tensor(cache["features"]) - torch.tensor(scaler.mean_, dtype=torch.float32)) / torch.tensor(scaler.scale_, dtype=torch.float32)
    logits = standardized @ torch.tensor(classifier.coef_[0], dtype=torch.float32) + float(classifier.intercept_[0])
    actual = torch.sigmoid(logits).numpy()
    expected = classifier.predict_proba(scaler.transform(cache["features"]))[:, 1]
    np.testing.assert_allclose(actual, expected, rtol=1e-5, atol=1e-6)


def test_group_bootstrap_is_reproducible():
    result = grouped_bootstrap([0, 1, 0, 1], [0.1, 0.8, 0.3, 0.7], ["a", "a", "b", "b"], 0.5, repeats=20)
    assert result["valid_repeats"] == 20
    assert result["intervals_95"]["balanced_accuracy"] == [1.0, 1.0]


def test_changed_archive_is_rejected_before_video_processing(tmp_path):
    archive = tmp_path / "sample.zip"
    metadata = synthetic_metadata()
    with zipfile.ZipFile(archive, "w") as handle:
        handle.writestr("metadata.json", json.dumps(metadata))
        for name in metadata:
            handle.writestr(name, b"video")
    manifest = import_dfdc(archive, tmp_path / "manifest.json")
    with archive.open("ab") as handle:
        handle.write(b"changed")
    with pytest.raises(ValueError, match="changed"):
        with open_video(manifest, manifest["rows"][0]):
            pytest.fail("Changed archive must not be used.")


def test_crop_review_never_reads_validation_or_test_images(tmp_path):
    from PIL import Image
    from ml.common import write_json

    directory = tmp_path / "train"
    directory.mkdir()
    Image.new("RGB", (224, 224), "grey").save(directory / "frame.jpg")
    write_json(directory / "audit.json", {"status": "usable", "crops": [{"filename": "frame.jpg"}]})
    rows = [{"video_id": "train.mp4", "split": "train", "label": 0},
            {"video_id": "absent_test.mp4", "split": "test", "label": 1},
            {"video_id": "absent_val.mp4", "split": "val", "label": 1}]
    result = create_crop_review({"rows": rows}, tmp_path, tmp_path / "review.jpg")
    assert result["training_videos_shown"] == 1
    assert (tmp_path / "review.jpg").exists()


def test_feature_extraction_rejects_crops_from_another_manifest(tmp_path):
    from ml.common import load_settings, write_json
    from ml.features import extract_features

    write_json(tmp_path / "summary.json", {"manifest_fingerprint": "old-dataset"})
    with pytest.raises(ValueError, match="different data"):
        extract_features({"fingerprint": "new-dataset"}, load_settings(), tmp_path,
                         tmp_path / "features", "efficientnet_b0")


def test_training_export_and_held_out_evaluation_work_together(tmp_path, monkeypatch):
    """A software integration fixture, not a deepfake accuracy experiment."""
    import torch
    from ml import train as training
    from ml.common import file_sha256, load_settings, write_json
    from ml.evaluate import evaluate_baseline
    from ml.faces import FACE_KEYS

    settings = load_settings()
    settings["backbones"] = ["efficientnet_b0"]
    rows = assign_splits(add_source_groups(metadata_rows(synthetic_metadata())))
    manifest = {"fingerprint": "synthetic-software-test", "rows": rows, "seed": 42,
                "counts": audit_splits(rows), "label_limitation": "synthetic fixture",
                "identity_limitation": "synthetic fixture"}
    feature_path = tmp_path / "efficientnet_b0.npz"
    np.savez_compressed(feature_path, **synthetic_features())
    write_json(feature_path.with_suffix(".json"), {
        "signature": "synthetic-feature-fixture", "detector_sha256": "synthetic-detector",
        "face_settings": {key: settings[key] for key in FACE_KEYS},
    })
    monkeypatch.setattr(training, "extract_features", lambda *args: feature_path)
    monkeypatch.setattr(training, "make_encoder", lambda *args, **kwargs: (torch.nn.Identity(), None, 3))
    run = tmp_path / "run"
    summary = training.train_baseline(manifest, settings, tmp_path, tmp_path, run)
    assert summary["test_evaluated"] is False
    assert not (run / "test_metrics.json").exists()
    checkpoint = torch.load(run / "model.pt", map_location="cpu", weights_only=True)
    assert checkpoint["class_mapping"] == {"REAL": 0, "FAKE": 1}
    assert summary["checkpoint_sha256"] == file_sha256(run / "model.pt")
    assert not (run / "model.pt.tmp").exists()
    report = evaluate_baseline(manifest, run, tmp_path, "test", bootstrap_repeats=5)
    assert report["evaluation_unit"] == "video"
    assert report["coverage"]["analyzed_videos"] == manifest["counts"]["test"]["total"]
    assert (run / "test_evaluation.png").exists()
    assert read_json(run / "training_summary.json")["test_evaluated"] is True
