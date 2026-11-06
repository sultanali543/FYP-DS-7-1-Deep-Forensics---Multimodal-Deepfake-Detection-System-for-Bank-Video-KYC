"""Use an ImageNet encoder once, then train a small classifier on cached features."""

from __future__ import annotations

from pathlib import Path
import time

import numpy as np
from PIL import Image

from .common import configure_torch, fingerprint, read_json, runtime_versions, write_json
from .faces import FACE_KEYS

BACKBONES = ("efficientnet_b0", "resnet18")


def make_encoder(name, pretrained=True, threads=2):
    torch = configure_torch(threads)
    from torchvision import models

    if name == "efficientnet_b0":
        weights = models.EfficientNet_B0_Weights.IMAGENET1K_V1
        encoder = models.efficientnet_b0(weights=weights if pretrained else None)
        dimension = encoder.classifier[1].in_features
        encoder.classifier = torch.nn.Identity()
    elif name == "resnet18":
        weights = models.ResNet18_Weights.IMAGENET1K_V1
        encoder = models.resnet18(weights=weights if pretrained else None)
        dimension = encoder.fc.in_features
        encoder.fc = torch.nn.Identity()
    else:
        raise ValueError(f"Supported backbones: {', '.join(BACKBONES)}")
    encoder.eval()
    encoder.requires_grad_(False)
    return encoder, weights.transforms(), dimension


def feature_signature(manifest, crop_summary, backbone):
    return fingerprint({"manifest": manifest["fingerprint"], "faces": crop_summary["signature"],
                        "backbone": backbone, "weights": "IMAGENET1K_V1", "aggregation": "mean_frame_scores",
                        "runtime_versions": runtime_versions()})


def extract_features(manifest, settings, crops, output, backbone):
    crops, output = Path(crops), Path(output)
    crop_summary = read_json(crops / "summary.json")
    if (crop_summary.get("manifest_fingerprint") != manifest["fingerprint"]
            or crop_summary["face_settings"] != {key: settings[key] for key in FACE_KEYS}):
        raise ValueError("Face crops belong to different data or settings. Re-run face preparation.")
    if crop_summary["processed_videos"] != len(manifest["rows"]):
        raise ValueError("Prepare all manifest videos before training; a limited smoke check is not a training dataset.")
    signature = feature_signature(manifest, crop_summary, backbone)
    output.mkdir(parents=True, exist_ok=True)
    feature_path = output / f"{backbone}.npz"
    metadata_path = output / f"{backbone}.json"
    if feature_path.exists() and metadata_path.exists() and read_json(metadata_path).get("signature") == signature:
        print(f"Using cached {backbone} features.", flush=True)
        return feature_path
    torch = configure_torch(settings["cpu_threads"])
    encoder, transform, dimension = make_encoder(backbone, threads=settings["cpu_threads"])
    values, video_ids, labels, splits, groups = [], [], [], [], []
    rejected = []
    started = time.perf_counter()
    for index, row in enumerate(manifest["rows"], 1):
        directory = crops / Path(row["video_id"]).stem
        audit = read_json(directory / "audit.json")
        if audit["signature"] != crop_summary["signature"]:
            raise ValueError("Mixed face-cache settings detected. Re-run face preparation.")
        if audit["status"] != "usable":
            rejected.append({"video_id": row["video_id"], "split": row["split"], "label": row["label"], "status": audit["status"]})
            continue
        tensors = []
        for item in audit["crops"]:
            with Image.open(directory / item["filename"]) as image:
                tensors.append(transform(image.convert("RGB")))
        with torch.inference_mode():
            for offset in range(0, len(tensors), settings["batch_size"]):
                batch = torch.stack(tensors[offset:offset + settings["batch_size"]])
                features = encoder(batch).cpu().numpy().astype(np.float32)
                if not np.all(np.isfinite(features)):
                    raise ValueError("The encoder produced invalid features.")
                values.append(features)
                count = len(features)
                video_ids.extend([row["video_id"]] * count)
                labels.extend([row["label"]] * count)
                splits.extend([row["split"]] * count)
                groups.extend([row["group_id"]] * count)
        print(f"[{index}/{len(manifest['rows'])}] {backbone}: {row['video_id']}", flush=True)
    if not values:
        raise ValueError("No usable face features were produced.")
    np.savez_compressed(feature_path, features=np.concatenate(values), video_ids=np.array(video_ids),
                        labels=np.array(labels, dtype=np.int64), splits=np.array(splits), groups=np.array(groups))
    write_json(metadata_path, {
        "signature": signature, "manifest_fingerprint": manifest["fingerprint"],
        "crop_signature": crop_summary["signature"], "backbone": backbone,
        "pretrained_weights": "IMAGENET1K_V1", "feature_dimension": dimension,
        "frames": len(video_ids), "usable_videos": len(set(video_ids)), "rejected": rejected,
        "elapsed_seconds": time.perf_counter() - started,
        "face_settings": {key: settings[key] for key in FACE_KEYS},
        "detector_sha256": crop_summary["detector_sha256"],
        "runtime_versions": runtime_versions(),
        "warning": "ImageNet weights are generic visual features, not a pretrained deepfake detector.",
    })
    return feature_path
