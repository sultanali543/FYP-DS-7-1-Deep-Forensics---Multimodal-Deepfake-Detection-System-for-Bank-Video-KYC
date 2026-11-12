"""Manifest-based evaluation with fixed model thresholds and explicit coverage."""
from __future__ import annotations

import csv
import json
from pathlib import Path
import subprocess
import time

import numpy as np
import soundfile as sf
from threadpoolctl import threadpool_limits

from .dataset import sha256_file
from .features import SAMPLE_RATE
from .metrics import audio_metrics
from .predict import decode_video_audio, load_model, predict_samples

FIELDS = ("audio_id", "path", "label", "speaker_id", "system_id", "split", "source")
LABELS = {"real": 0, "bonafide": 0, "0": 0, "fake": 1, "spoof": 1, "1": 1}


def read_manifest(path, purpose, excluded_speakers=()):
    path = Path(path).resolve()
    if purpose not in {"development", "test"}:
        raise ValueError("Purpose must be development or test.")
    with path.open(encoding="utf-8-sig", newline="") as source:
        reader = csv.DictReader(source)
        if not set(FIELDS).issubset(reader.fieldnames or []):
            raise ValueError(f"Manifest requires columns: {', '.join(FIELDS)}")
        rows = list(reader)
    if not rows:
        raise ValueError("Evaluation manifest is empty.")
    ids, paths = set(), set()
    excluded_speakers = set(excluded_speakers)
    for row in rows:
        if any(not isinstance(row.get(key), str) or not row[key].strip() for key in FIELDS):
            raise ValueError("Every manifest field must be populated; use '-' for an unknown attack.")
        row.update({key: row[key].strip() for key in FIELDS})
        if row["label"].lower() not in LABELS:
            raise ValueError("Labels must be REAL/FAKE, bonafide/spoof, or 0/1.")
        row["y"] = LABELS[row["label"].lower()]
        split = row["split"].lower()
        if purpose == "test":
            if split not in {"test", "evaluation", "eval"} or row["audio_id"].startswith(("LA_T_", "LA_D_")):
                raise ValueError("Training/development clips cannot be labeled as independent test data.")
            if row["speaker_id"] in excluded_speakers:
                raise ValueError("Test speaker overlaps the run's training/development speakers.")
        elif split not in {"development", "validation", "dev"}:
            raise ValueError("Development evaluation requires a development/validation manifest.")
        file = Path(row["path"])
        if not file.is_absolute():
            file = path.parent / file
        file = file.resolve()
        if not file.is_file():
            raise ValueError(f"Audio file does not exist: {file}")
        if row["audio_id"] in ids or str(file).casefold() in paths:
            raise ValueError("Duplicate audio ID or file path in evaluation manifest.")
        ids.add(row["audio_id"])
        paths.add(str(file).casefold())
        row["path"] = str(file)
    if {row["y"] for row in rows} != {0, 1}:
        raise ValueError("Evaluation requires both genuine and spoof examples.")
    return rows


def manifest_from_2019_protocol(protocol, audio_dir, output):
    """Import official 2019 LA evaluation protocol without random resplitting."""
    protocol, audio_dir, output = Path(protocol), Path(audio_dir).resolve(), Path(output)
    if output.exists():
        raise ValueError("Manifest output already exists.")
    rows = []
    for line in protocol.read_text(encoding="utf-8-sig").splitlines():
        if not line.strip():
            continue
        fields = line.split()
        if len(fields) != 5:
            raise ValueError("Expected five fields in an ASVspoof 2019 LA protocol line.")
        speaker, identifier, _, attack, label = fields
        if not identifier.startswith("LA_E_") or label not in {"bonafide", "spoof"}:
            raise ValueError("This is not an ASVspoof 2019 LA evaluation protocol.")
        if not identifier.replace("_", "").isalnum():
            raise ValueError("Invalid audio identifier.")
        file = audio_dir / f"{identifier}.flac"
        if not file.is_file():
            raise ValueError(f"Missing protocol audio: {file}")
        rows.append(dict(zip(FIELDS, (identifier, str(file), label, speaker, attack, "test", "ASVspoof2019-LA-evaluation"), strict=True)))
    if not rows or len({row["audio_id"] for row in rows}) != len(rows):
        raise ValueError("Protocol is empty or has duplicate identifiers.")
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x", encoding="utf-8", newline="") as target:
        writer = csv.DictWriter(target, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    return {"manifest": str(output.resolve()), "clips": len(rows), "protocol_sha256": sha256_file(protocol)}


def _decode(path):
    path = Path(path)
    if path.suffix.lower() in {".wav", ".flac"}:
        info = sf.info(path)
        # Same PCM16 input as the app, avoiding a new FFmpeg process per official utterance.
        if info.samplerate == SAMPLE_RATE and info.channels == 1 and info.subtype == "PCM_16":
            samples, _ = sf.read(path, frames=60 * SAMPLE_RATE, dtype="float32")
            return samples
    return decode_video_audio(path)


def evaluate_manifest(manifest, run, output, *, purpose="test", threads=2):
    if not 1 <= threads <= 4:
        raise ValueError("Use one to four CPU threads.")
    manifest, run, output = Path(manifest), Path(run), Path(output)
    summary, model = load_model(run)
    audit_file = run / "dataset_audit.json"
    if purpose == "test" and not audit_file.is_file():
        raise ValueError("The run's dataset audit is required to check test-speaker separation.")
    audit = json.loads(audit_file.read_text()) if audit_file.exists() else {}
    excluded = set(audit.get("train", {}).get("speakers", [])) | set(audit.get("validation", {}).get("speakers", []))
    rows = read_manifest(manifest, purpose, excluded)
    if (output / "predictions.csv").exists() or (output / "summary.json").exists():
        raise ValueError("Evaluation output already exists. Use a fresh directory.")
    output.mkdir(parents=True, exist_ok=True)
    records, started = [], time.monotonic()
    fields = ("audio_id", "speaker_id", "system_id", "label", "status", "score", "verdict", "seconds", "reason")
    with (output / "predictions.csv").open("x", encoding="utf-8", newline="") as target, threadpool_limits(limits=threads):
        writer = csv.DictWriter(target, fieldnames=fields)
        writer.writeheader()
        for index, row in enumerate(rows, 1):
            tick = time.monotonic()
            try:
                result = predict_samples(summary, model, _decode(row["path"]))
            except (OSError, ValueError, RuntimeError, subprocess.TimeoutExpired) as error:
                result = {"status": "failed", "reason": str(error)}
            record = {key: row[key] for key in ("audio_id", "speaker_id", "system_id", "label")}
            record.update({"status": result["status"], "score": result.get("score"),
                           "verdict": result.get("verdict"), "seconds": time.monotonic() - tick,
                           "reason": result.get("reason", "")})
            writer.writerow(record)
            target.flush()
            records.append({**record, "y": row["y"]})
            if index % 100 == 0 or index == len(rows):
                print(f"Evaluation: {index}/{len(rows)} clips", flush=True)
    usable = [row for row in records if row["status"] == "complete"]
    metrics = audio_metrics([row["y"] for row in usable], [row["score"] for row in usable], model["threshold"]) if {row["y"] for row in usable} == {0, 1} else None
    coverage = {}
    for label, name in ((0, "genuine"), (1, "spoof")):
        requested = sum(row["y"] == label for row in records)
        measured = sum(row["y"] == label for row in usable)
        coverage[name] = {"requested": requested, "scored": measured, "coverage": measured / requested}
    attacks = {}
    for system in sorted({row["system_id"] for row in records if row["y"] == 1}):
        subset = [row for row in usable if row["y"] == 1 and row["system_id"] == system]
        requested = sum(row["y"] == 1 and row["system_id"] == system for row in records)
        attacks[system] = {"requested": requested, "scored": len(subset),
                           "missed_spoof_rate": sum(row["verdict"] == "REAL" for row in subset) / len(subset) if subset else None}
    report = {"purpose": purpose, "model_version": summary["model_version"],
              "checkpoint_sha256": summary["checkpoint_sha256"], "threshold": model["threshold"],
              "manifest_sha256": sha256_file(manifest), "requested": len(records), "scored": len(usable),
              "coverage": len(usable) / len(records), "coverage_by_class": coverage, "metrics_on_scored_clips": metrics,
              "attacks": attacks, "elapsed_seconds": time.monotonic() - started,
              "median_inference_seconds": float(np.median([row["seconds"] for row in records])),
              "note": "Fixed saved threshold; no fitting or model selection. Labels/provenance are supplied by the manifest. Unscored clips are never counted as REAL. EER uses local tie-aware ROC interpolation, not the official discrete challenge convention."}
    (output / "summary.json").write_text(json.dumps(report, indent=2, allow_nan=False), encoding="utf-8")
    return report
