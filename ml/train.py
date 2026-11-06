"""Train a regularized binary head; use validation videos for every selection."""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
import time

import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler

from .common import configure_torch, file_sha256, fingerprint, read_json, runtime_versions, write_json
from .data import audit_splits
from .features import extract_features, make_encoder
from .metrics import aggregate_scores, classification_metrics, select_threshold


def video_arrays(cache, scores, split):
    mask = cache["splits"] == split
    aggregated = aggregate_scores(cache["video_ids"][mask], scores[mask])
    ids = sorted(aggregated)
    lookup = {}
    for video_id, label, group in zip(cache["video_ids"][mask], cache["labels"][mask], cache["groups"][mask], strict=True):
        value = (int(label), str(group))
        if str(video_id) in lookup and lookup[str(video_id)] != value:
            raise ValueError("Conflicting frame labels or source groups for a video.")
        lookup[str(video_id)] = value
    return ids, np.array([lookup[name][0] for name in ids]), np.array([aggregated[name] for name in ids]), np.array([lookup[name][1] for name in ids])


def training_weights(video_ids, labels):
    """Each video contributes equal total weight, then balance the two classes."""
    frame_counts = Counter(video_ids.tolist())
    video_labels = {}
    for video_id, label in zip(video_ids, labels, strict=True):
        if video_id in video_labels and video_labels[video_id] != int(label):
            raise ValueError("A training video has inconsistent labels.")
        video_labels[video_id] = int(label)
    class_counts = Counter(video_labels.values())
    if set(class_counts) != {0, 1}:
        raise ValueError("Usable training videos must contain both classes.")
    return np.array([len(video_labels) / (2 * class_counts[int(label)] * frame_counts[video_id])
                     for video_id, label in zip(video_ids, labels, strict=True)], dtype=np.float64)


def fit_head(cache, c_values, seed=42):
    train_mask = cache["splits"] == "train"
    if not train_mask.any():
        raise ValueError("No usable training frames.")
    features = cache["features"]
    weights = training_weights(cache["video_ids"][train_mask], cache["labels"][train_mask])
    # Fit all statistics using training frames only.
    scaler = StandardScaler().fit(features[train_mask], sample_weight=weights)
    standardized = scaler.transform(features)
    candidates = []
    best = None
    for c_value in c_values:
        started = time.perf_counter()
        classifier = LogisticRegression(C=float(c_value), max_iter=2000, solver="lbfgs", random_state=seed)
        classifier.fit(standardized[train_mask], cache["labels"][train_mask], sample_weight=weights)
        if int(classifier.n_iter_[0]) >= classifier.max_iter:
            raise ValueError("Classifier optimization did not converge; inspect the feature scale and regularization.")
        scores = classifier.predict_proba(standardized)[:, 1]
        _, labels, video_scores, _ = video_arrays(cache, scores, "val")
        threshold = select_threshold(labels, video_scores)
        metrics = classification_metrics(labels, video_scores, threshold)
        summary = {"C": float(c_value), "threshold": threshold, "validation": metrics,
                   "fit_seconds": time.perf_counter() - started, "iterations": int(classifier.n_iter_[0])}
        candidates.append(summary)
        ranking = (metrics["balanced_accuracy"], metrics["roc_auc"], -float(c_value))
        if best is None or ranking > best["ranking"]:
            best = {"classifier": classifier, "scaler": scaler, "ranking": ranking,
                    "summary": summary, "scores": scores}
    if best is None:
        raise ValueError("Provide at least one positive regularization value.")
    return best, candidates


def train_baseline(manifest, settings, crops, feature_root, output, backbones=None):
    audit_splits(manifest["rows"])
    torch = configure_torch(settings["cpu_threads"])
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    if (output / "model.pt").exists():
        raise FileExistsError("This run already has a model. Choose a new run directory to preserve the experiment.")
    backbones = backbones or settings["backbones"]
    comparison = []
    chosen = None
    for backbone in backbones:
        feature_path = extract_features(manifest, settings, crops, feature_root, backbone)
        feature_metadata = read_json(feature_path.with_suffix(".json"))
        with np.load(feature_path, allow_pickle=False) as archive:
            cache = {key: archive[key] for key in archive.files}
        # No test labels or test metrics are used for model selection.
        best, candidates = fit_head(cache, settings["regularization_c"], settings["seed"])
        summary = {"backbone": backbone, "training_type": "frozen_encoder_with_logistic_head",
                   "feature_metadata": feature_metadata, "candidates": candidates,
                   "selected": best["summary"]}
        write_json(output / f"{backbone}_validation.json", summary)
        comparison.append({"backbone": backbone, **best["summary"]})
        if chosen is None or best["ranking"] > chosen["ranking"]:
            chosen = {**best, "backbone": backbone, "feature_metadata": feature_metadata}
        print(f"{backbone}: validation balanced accuracy={best['summary']['validation']['balanced_accuracy']:.3f}, "
              f"AUC={best['summary']['validation']['roc_auc']:.3f}", flush=True)
    if chosen is None:
        raise ValueError("At least one backbone is required.")
    backbone = chosen["backbone"]
    encoder, _, _ = make_encoder(backbone, threads=settings["cpu_threads"])
    version = "visual-baseline-" + fingerprint({"manifest": manifest["fingerprint"], "settings": settings,
                                                 "feature_signature": chosen["feature_metadata"]["signature"],
                                                 "backbone": backbone, "C": chosen["summary"]["C"]})[:10]
    checkpoint = {
        "format_version": 1, "model_version": version, "backbone": backbone,
        "training_type": "frozen_ImageNet_encoder_plus_regularized_logistic_regression",
        "encoder_state_dict": encoder.state_dict(),
        "scaler_mean": torch.tensor(chosen["scaler"].mean_, dtype=torch.float32),
        "scaler_scale": torch.tensor(chosen["scaler"].scale_, dtype=torch.float32),
        "head_coefficient": torch.tensor(chosen["classifier"].coef_[0], dtype=torch.float32),
        "head_intercept": float(chosen["classifier"].intercept_[0]),
        "threshold": chosen["summary"]["threshold"],
        "class_mapping": {"REAL": 0, "FAKE": 1},
        "manifest_fingerprint": manifest["fingerprint"],
        "feature_signature": chosen["feature_metadata"]["signature"],
        "face_settings": chosen["feature_metadata"]["face_settings"],
        "detector_sha256": chosen["feature_metadata"]["detector_sha256"],
        "pretrained_weights": "IMAGENET1K_V1",
        "runtime_versions": runtime_versions(),
    }
    pending_checkpoint = output / "model.pt.tmp"
    torch.save(checkpoint, pending_checkpoint)
    summary = {
        "model_version": version, "created_at": datetime.now(timezone.utc).isoformat(),
        "training_type": checkpoint["training_type"], "selected_backbone": backbone,
        "selection_rule": "highest validation video balanced accuracy, then validation AUC, then smaller C",
        "manifest_fingerprint": manifest["fingerprint"], "dataset_counts": manifest["counts"],
        "settings": settings, "comparison": comparison, "selected": chosen["summary"],
        "checkpoint_bytes": pending_checkpoint.stat().st_size,
        "checkpoint_sha256": file_sha256(pending_checkpoint),
        "runtime_versions": runtime_versions(),
        "test_evaluated": False,
        "limitations": [manifest["label_limitation"], manifest["identity_limitation"],
                        "Small-sample results do not establish real-world or banking readiness.",
                        "The encoder is frozen, not fine-tuned on deepfake data.",
                        "Class weighting and threshold selection can affect score calibration; scores are not fraud probabilities."],
    }
    write_json(output / "training_summary.json", summary)
    pending_checkpoint.replace(output / "model.pt")
    return summary
