import csv
import json

import numpy as np
import pytest
import soundfile as sf
from sklearn.dummy import DummyClassifier

from audio import evaluate
from audio.features import FEATURE_VERSION


def write_manifest(path, rows):
    with path.open("w", encoding="utf-8", newline="") as target:
        writer = csv.DictWriter(target, fieldnames=evaluate.FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def row(identifier, file, label, speaker="external", split="test"):
    return dict(zip(evaluate.FIELDS, (identifier, str(file), label, speaker, "-" if label == "REAL" else "A07", split, "test fixture"), strict=True))


def test_manifest_rejects_dev_disguised_as_test_and_speaker_leakage(tmp_path):
    first, second = tmp_path / "first.wav", tmp_path / "second.wav"
    first.touch()
    second.touch()
    manifest = tmp_path / "manifest.csv"
    rows = [row("LA_D_0001", first, "REAL"), row("LA_E_0002", second, "FAKE")]
    write_manifest(manifest, rows)
    with pytest.raises(ValueError, match="independent test"):
        evaluate.read_manifest(manifest, "test")
    rows[0]["audio_id"] = "LA_E_0001"
    write_manifest(manifest, rows)
    with pytest.raises(ValueError, match="speaker overlaps"):
        evaluate.read_manifest(manifest, "test", ["external"])
    assert len(evaluate.read_manifest(manifest, "test", ["training_speaker"])) == 2
    rows[1]["path"] = str(first)
    write_manifest(manifest, rows)
    with pytest.raises(ValueError, match="Duplicate"):
        evaluate.read_manifest(manifest, "test")


def test_official_protocol_import_requires_eval_ids_and_existing_files(tmp_path):
    protocol = tmp_path / "protocol.txt"
    protocol.write_text("LA_0001 LA_T_0000001 - - bonafide\n")
    with pytest.raises(ValueError, match="evaluation protocol"):
        evaluate.manifest_from_2019_protocol(protocol, tmp_path, tmp_path / "bad.csv")
    protocol.write_text("LA_0001 LA_E_0000001 - - bonafide\nLA_0002 LA_E_0000002 - A07 spoof\n")
    with pytest.raises(ValueError, match="Missing protocol audio"):
        evaluate.manifest_from_2019_protocol(protocol, tmp_path, tmp_path / "missing.csv")
    (tmp_path / "LA_E_0000001.flac").touch()
    (tmp_path / "LA_E_0000002.flac").touch()
    manifest = tmp_path / "eval.csv"
    result = evaluate.manifest_from_2019_protocol(protocol, tmp_path, manifest)
    assert result["clips"] == 2
    rows = evaluate.read_manifest(manifest, "test")
    assert [item["y"] for item in rows] == [0, 1]


def test_evaluation_preserves_threshold_and_reports_abstentions(tmp_path, monkeypatch):
    classifier = DummyClassifier(strategy="prior").fit(np.zeros((2, 241)), [0, 1])
    summary = {"model_version": "fixture", "checkpoint_sha256": "fixture"}
    model = {"estimator": classifier, "threshold": 0.7, "feature_version": FEATURE_VERSION}
    monkeypatch.setattr(evaluate, "load_model", lambda _: (summary, model))
    run = tmp_path / "run"
    run.mkdir()
    (run / "dataset_audit.json").write_text(json.dumps({"train": {"speakers": ["train"]}, "validation": {"speakers": ["dev"]}}))
    rows = []
    t = np.arange(16000, dtype=np.float32) / 16000
    for index, label in enumerate(("REAL", "FAKE", "REAL", "FAKE")):
        file = tmp_path / f"audio{index}.wav"
        signal = 0.1 * np.sin(2 * np.pi * 300 * t) if index < 2 else np.zeros_like(t)
        sf.write(file, signal, 16000, subtype="PCM_16")
        rows.append(row(f"external{index}", file, label))
    manifest, output = tmp_path / "manifest.csv", tmp_path / "report"
    write_manifest(manifest, rows)
    result = evaluate.evaluate_manifest(manifest, run, output)
    assert result["threshold"] == model["threshold"] == 0.7
    assert result["requested"] == 4 and result["scored"] == 2
    assert result["coverage"] == 0.5
    assert result["coverage_by_class"]["genuine"]["scored"] == 1
    assert result["metrics_on_scored_clips"]["confusion_matrix"] == [[1, 0], [1, 0]]
    with (output / "predictions.csv").open() as source:
        predictions = list(csv.DictReader(source))
    assert predictions[2]["status"] == "insufficient_evidence"
    assert predictions[2]["score"] == predictions[2]["verdict"] == ""
    with pytest.raises(ValueError, match="already exists"):
        evaluate.evaluate_manifest(manifest, run, output)
