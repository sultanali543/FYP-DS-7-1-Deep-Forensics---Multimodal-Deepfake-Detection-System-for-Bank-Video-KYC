"""Shared file handling and settings. No training happens when this is imported."""

from __future__ import annotations

import hashlib
from importlib.metadata import version
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
DEFAULT_MANIFEST = DATA / "manifests" / "dfdc_sample.json"
DEFAULT_CROPS = DATA / "crops" / "dfdc_sample"
DEFAULT_ASSETS = DATA / "assets"
DEFAULT_RUNS = DATA / "runs"


def read_json(path):
    with Path(path).open(encoding="utf-8") as handle:
        return json.load(handle)


def write_json(path, value):
    """Replace a JSON output only after the complete new file has been written."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    with temporary.open("w", encoding="utf-8") as handle:
        json.dump(value, handle, indent=2, allow_nan=False)
        handle.write("\n")
    temporary.replace(path)


def file_sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(4 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def fingerprint(value):
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def runtime_versions():
    return {name: version(name) for name in (
        "torch", "torchvision", "opencv-python-headless", "numpy", "pillow", "scikit-learn",
    )}


def load_settings(path=None):
    path = Path(path) if path else ROOT / "ml" / "configs" / "baseline.json"
    settings = read_json(path)
    if settings["frames_per_video"] < settings["min_usable_frames"]:
        raise ValueError("frames_per_video must cover min_usable_frames.")
    if settings["image_size"] != 224:
        raise ValueError("This baseline uses the pretrained models' 224-pixel input.")
    if settings["batch_size"] < 1 or settings["cpu_threads"] < 1:
        raise ValueError("Batch size and CPU threads must be positive.")
    if not 1 <= settings["min_usable_frames"] <= settings["frames_per_video"] <= 120:
        raise ValueError("Use between 1 and 120 sampled frames and at least one usable frame.")
    if not settings["regularization_c"] or any(value <= 0 for value in settings["regularization_c"]):
        raise ValueError("Regularization values must be positive.")
    if settings["bootstrap_repeats"] < 1:
        raise ValueError("At least one bootstrap repeat is required.")
    return settings


def configure_torch(threads=2):
    # Keep downloaded weights inside the ignored project data directory.
    os.environ.setdefault("TORCH_HOME", str(DEFAULT_ASSETS / "torch"))
    import torch

    torch.set_num_threads(threads)
    return torch
