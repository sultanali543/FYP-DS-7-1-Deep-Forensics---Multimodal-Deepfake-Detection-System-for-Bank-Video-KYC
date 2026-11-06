"""Read official DFDC labels and keep related source videos in one split."""

from __future__ import annotations

from collections import Counter, defaultdict
from contextlib import contextmanager
from datetime import datetime, timezone
import json
from pathlib import Path, PurePosixPath
import shutil
import tempfile
import zipfile

from .common import DATA, file_sha256, fingerprint, read_json, write_json


def safe_name(name):
    """DFDC metadata keys must be ordinary video basenames, never paths."""
    if not isinstance(name, str) or not name:
        raise ValueError("A video name is missing from the metadata.")
    if Path(name).name != name or "/" in name or "\\" in name or ":" in name:
        raise ValueError("Metadata contains a path where a video name is expected.")
    if not name.lower().endswith(".mp4"):
        raise ValueError("The small DFDC baseline expects MP4 video filenames.")
    return name


def metadata_rows(metadata):
    if not isinstance(metadata, dict) or not metadata:
        raise ValueError("Expected a nonempty DFDC metadata.json object.")
    if len(metadata) > 1000:
        raise ValueError("Choose the small labeled training sample, not a full training shard.")
    rows = []
    for name, info in sorted(metadata.items()):
        safe_name(name)
        if not isinstance(info, dict) or info.get("label") not in ("REAL", "FAKE"):
            raise ValueError(f"Missing REAL/FAKE metadata label for {name}.")
        original = info.get("original")
        if original:
            safe_name(original)
        if info["label"] == "FAKE" and not original:
            raise ValueError(f"Missing original-video reference for {name}; grouping would be unsafe.")
        rows.append({
            "video_id": name,
            "label": int(info["label"] == "FAKE"),
            "original": original or name,
        })
    if {row["label"] for row in rows} != {0, 1}:
        raise ValueError("Both real and fake labeled training videos are required.")
    return rows


def add_source_groups(rows):
    # Union related filenames, including references whose original file is absent.
    parent = {}

    def find(name):
        parent.setdefault(name, name)
        if parent[name] != name:
            parent[name] = find(parent[name])
        return parent[name]

    for row in rows:
        first, second = find(row["video_id"]), find(row["original"])
        if first != second:
            parent[max(first, second)] = min(first, second)
    for row in rows:
        row["group_id"] = find(row["video_id"])
    return rows


def assign_splits(rows, seed=42):
    """Use five source-group folds: three train, one validation, one test."""
    import numpy as np
    from sklearn.model_selection import StratifiedGroupKFold

    groups = [row["group_id"] for row in rows]
    if len(set(groups)) < 10:
        raise ValueError("At least 10 independent source groups are needed for this baseline split.")
    labels = np.array([row["label"] for row in rows])
    splitter = StratifiedGroupKFold(n_splits=5, shuffle=True, random_state=seed)
    for fold, (_, indices) in enumerate(splitter.split(np.zeros(len(rows)), labels, groups)):
        split = "test" if fold == 0 else "val" if fold == 1 else "train"
        for index in indices:
            rows[int(index)]["split"] = split
    audit_splits(rows)
    return rows


def audit_splits(rows):
    group_splits = defaultdict(set)
    counts = {split: Counter() for split in ("train", "val", "test")}
    seen = set()
    for row in rows:
        if row["video_id"] in seen:
            raise ValueError("Duplicate video ID in the manifest.")
        seen.add(row["video_id"])
        if row.get("split") not in counts:
            raise ValueError("Every video must have a valid split.")
        group_splits[row["group_id"]].add(row["split"])
        counts[row["split"]][row["label"]] += 1
    if any(len(splits) != 1 for splits in group_splits.values()):
        raise ValueError("Source-video leakage detected between splits.")
    if any(set(count) != {0, 1} for count in counts.values()):
        raise ValueError("Each split must contain real and fake videos; use more source groups.")
    return {
        split: {"real": count[0], "fake": count[1], "total": sum(count.values())}
        for split, count in counts.items()
    }


def import_dfdc(source, output, seed=42):
    source = Path(source).resolve()
    if not source.exists():
        raise FileNotFoundError("The selected dataset archive or folder does not exist.")
    if source.is_file():
        if not zipfile.is_zipfile(source):
            raise ValueError("Choose a ZIP containing the labeled training videos and metadata.json.")
        with zipfile.ZipFile(source) as archive:
            matches = [name for name in archive.namelist() if PurePosixPath(name).name == "metadata.json"]
            if len(matches) != 1:
                raise ValueError("Choose the small sample archive containing exactly one metadata.json.")
            metadata_member = matches[0]
            if archive.getinfo(metadata_member).file_size > 10 * 1024 * 1024:
                raise ValueError("The metadata file is unexpectedly large.")
            metadata = json.loads(archive.read(metadata_member))
            rows = metadata_rows(metadata)
            prefix = PurePosixPath(metadata_member).parent
            members = set(archive.namelist())
            for row in rows:
                member = str(prefix / row["video_id"])
                if member not in members:
                    raise ValueError(f"The archive is missing labeled video {row['video_id']}.")
                info = archive.getinfo(member)
                if info.file_size > 512 * 1024 * 1024:
                    raise ValueError("A clip exceeds the 512 MB small-sample safety limit.")
                row["archive_member"] = member
        print("Hashing the selected archive for reproducibility…", flush=True)
        source_info = {"kind": "zip", "path": str(source), "sha256": file_sha256(source),
                       "size": source.stat().st_size, "mtime_ns": source.stat().st_mtime_ns}
    else:
        matches = list(source.rglob("metadata.json"))
        if len(matches) != 1:
            raise ValueError("Choose a folder containing exactly one training metadata.json.")
        directory = matches[0].parent
        metadata = read_json(matches[0])
        rows = metadata_rows(metadata)
        for row in rows:
            path = directory / row["video_id"]
            if not path.is_file():
                raise ValueError(f"The folder is missing labeled video {row['video_id']}.")
            row["size"] = path.stat().st_size
            row["sha256"] = file_sha256(path)
        source_info = {"kind": "directory", "path": str(directory)}
    rows = assign_splits(add_source_groups(rows), seed)
    payload = {
        "format_version": 1,
        "dataset": "dfdc_labeled_training_sample",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "seed": seed,
        "source": source_info,
        "metadata_sha256": fingerprint(metadata),
        "label_mapping": {"REAL": 0, "FAKE": 1},
        "split_method": "StratifiedGroupKFold: 3 train folds, 1 validation fold, 1 test fold",
        "label_limitation": "DFDC labels are clip-level and can include voice-only manipulation; this baseline examines faces only.",
        "identity_limitation": "Grouping uses original-video references, not verified actor identities.",
        "counts": audit_splits(rows),
        "rows": rows,
    }
    payload["fingerprint"] = fingerprint({
        "rows": rows, "metadata_sha256": payload["metadata_sha256"],
        "source_sha256": source_info.get("sha256"), "seed": seed,
    })
    write_json(output, payload)
    return payload


@contextmanager
def open_video(manifest, row):
    """Read one ZIP member at a time instead of unpacking a second full dataset."""
    source = manifest["source"]
    if source["kind"] == "directory":
        path = Path(source["path"]) / safe_name(row["video_id"])
        if file_sha256(path) != row["sha256"]:
            raise ValueError("A video changed after manifest creation; import the dataset again.")
        yield path
        return
    archive_path = Path(source["path"])
    stat = archive_path.stat()
    if stat.st_size != source["size"] or stat.st_mtime_ns != source["mtime_ns"]:
        raise ValueError("The dataset archive changed; import it again before processing.")
    temporary_root = DATA / "temporary"
    temporary_root.mkdir(parents=True, exist_ok=True)
    handle = tempfile.NamedTemporaryFile(suffix=".mp4", prefix="dfdc-", dir=temporary_root, delete=False)
    temporary_path = Path(handle.name)
    try:
        with handle, zipfile.ZipFile(archive_path) as archive, archive.open(row["archive_member"]) as member:
            shutil.copyfileobj(member, handle, length=1024 * 1024)
        yield temporary_path
    finally:
        temporary_path.unlink(missing_ok=True)
