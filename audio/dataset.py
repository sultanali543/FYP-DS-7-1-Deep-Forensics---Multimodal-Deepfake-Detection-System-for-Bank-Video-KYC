"""Audit and stream the community Parquet reupload without unpacking audio."""

from __future__ import annotations

from collections import Counter
import hashlib
import json
from pathlib import Path

import numpy as np
import pyarrow.parquet as pq

from .features import FEATURE_VERSION, audio_bytes_features

EXPECTED = {
    "train": {"rows": 25380, "labels": {0: 2580, 1: 22800}, "prefix": "LA_T_"},
    "validation": {"rows": 24844, "labels": {0: 2548, 1: 22296}, "prefix": "LA_D_"},
}
COLUMNS = ["speaker_id", "audio_file_name", "system_id", "key"]


def sha256_file(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as source:
        for block in iter(lambda: source.read(4 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def audit(path, split, *, hash_file=True):
    """Check counts, labels, IDs and one embedded FLAC against public protocol totals."""
    path = Path(path).resolve()
    parquet = pq.ParquetFile(path)
    expected = EXPECTED[split]
    if parquet.metadata.num_rows != expected["rows"]:
        raise ValueError(f"{split} contains {parquet.metadata.num_rows} rows; expected {expected['rows']}.")
    if not set(COLUMNS + ["audio"]).issubset(parquet.schema_arrow.names):
        raise ValueError("The Parquet file lacks required ASVspoof fields.")
    table = parquet.read(columns=COLUMNS)
    names = table["audio_file_name"].to_pylist()
    speakers = set(table["speaker_id"].to_pylist())
    labels = Counter(table["key"].to_pylist())
    systems = Counter(table["system_id"].to_pylist())
    if dict(labels) != expected["labels"]:
        raise ValueError(f"{split} label counts do not match the ASVspoof protocol.")
    if len(set(names)) != len(names) or not all(name.startswith(expected["prefix"]) for name in names):
        raise ValueError(f"{split} audio IDs are duplicated or have the wrong prefix.")
    if any(not name or not name.startswith("LA_") for name in speakers):
        raise ValueError(f"{split} has invalid speaker IDs.")
    if any((label == 0) != (system == "-") for label, system in zip(table["key"].to_pylist(), table["system_id"].to_pylist(), strict=True)):
        raise ValueError(f"{split} labels conflict with attack system IDs.")
    first = next(parquet.iter_batches(batch_size=1, columns=["audio"]))["audio"][0].as_py()
    if first["path"] != names[0] + ".flac" or not first["bytes"].startswith(b"fLaC"):
        raise ValueError(f"{split} first audio payload is not the expected FLAC.")
    audio_bytes_features(first["bytes"])
    return {
        "path": str(path), "bytes": path.stat().st_size, "sha256": sha256_file(path) if hash_file else None,
        "rows": len(names), "labels": {str(k): v for k, v in sorted(labels.items())},
        "speakers": sorted(speakers), "systems": dict(sorted(systems.items())),
        "first_audio_id": names[0],
    }


def audit_pair(train_path, validation_path, *, hash_files=True):
    train = audit(train_path, "train", hash_file=hash_files)
    validation = audit(validation_path, "validation", hash_file=hash_files)
    if set(train["speakers"]) & set(validation["speakers"]):
        raise ValueError("Training and validation speakers overlap.")
    return {"source": "Bisher/ASVspoof_2019_LA community reupload", "track": "2019_LA",
            "feature_version": FEATURE_VERSION, "train": train, "validation": validation,
            "provenance_limit": "Counts and schema match the official plan; full audio-byte equivalence to Edinburgh is unverified."}


def extract_split(path, split, cache_dir, source_sha256, *, max_groups=None):
    """Store one atomic small feature cache per Parquet row group; resume safely."""
    path, cache_dir = Path(path), Path(cache_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)
    identity = {"source_sha256": source_sha256, "feature_version": FEATURE_VERSION}
    manifest = cache_dir / "identity.json"
    if manifest.exists() and json.loads(manifest.read_text(encoding="utf-8")) != identity:
        raise ValueError(f"Feature cache at {cache_dir} belongs to another dataset or extractor.")
    if not manifest.exists():
        manifest.write_text(json.dumps(identity, indent=2), encoding="utf-8")
    parquet = pq.ParquetFile(path)
    count = parquet.num_row_groups if max_groups is None else min(parquet.num_row_groups, max_groups)
    for group in range(count):
        output = cache_dir / f"group-{group:04d}.npz"
        if output.exists():
            continue
        rows = parquet.read_row_group(group).to_pylist()
        vectors, labels, ids, speakers, systems = [], [], [], [], []
        for row in rows:
            if row["audio"]["path"] != row["audio_file_name"] + ".flac":
                raise ValueError(f"Embedded audio path mismatch at {row['audio_file_name']}.")
            vectors.append(audio_bytes_features(row["audio"]["bytes"]))
            labels.append(int(row["key"]))
            ids.append(row["audio_file_name"])
            speakers.append(row["speaker_id"])
            systems.append(row["system_id"])
        temporary = output.with_suffix(".tmp.npz")
        np.savez_compressed(temporary, x=np.stack(vectors), y=np.asarray(labels),
                            ids=np.asarray(ids), speakers=np.asarray(speakers), systems=np.asarray(systems))
        temporary.replace(output)
        if (group + 1) % 10 == 0 or group + 1 == count:
            print(f"{split}: {group + 1}/{count} row groups cached", flush=True)
    return count == parquet.num_row_groups


def load_split(cache_dir, expected_groups):
    files = sorted(Path(cache_dir).glob("group-*.npz"))
    if len(files) != expected_groups:
        raise ValueError(f"Expected {expected_groups} complete feature groups in {cache_dir}; found {len(files)}.")
    arrays = {name: [] for name in ("x", "y", "ids", "speakers", "systems")}
    for file in files:
        with np.load(file, allow_pickle=False) as group:
            for name in arrays:
                arrays[name].append(group[name])
    return {name: np.concatenate(parts) for name, parts in arrays.items()}
