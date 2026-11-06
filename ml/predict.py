"""Load a trained artifact without downloading backbone weights again."""

from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np
from PIL import Image

from .common import configure_torch, file_sha256
from .faces import FaceCropper, ensure_detector
from .features import make_encoder


def predict_video(run, video, assets=None, cpu_threads=2):
    torch = configure_torch(cpu_threads)
    checkpoint = torch.load(Path(run) / "model.pt", map_location="cpu", weights_only=True)
    if checkpoint.get("format_version") != 1:
        raise ValueError("Unsupported checkpoint format.")
    detector_path = ensure_detector(assets) if assets else ensure_detector()
    if file_sha256(detector_path) != checkpoint["detector_sha256"]:
        raise ValueError("Inference face detector does not match the trained artifact.")
    cropper = FaceCropper(checkpoint["face_settings"], detector_path)
    frames, attempts = cropper.sample_video(video)
    result = {
        "mode": "live", "scope": "visual_only", "model_version": checkpoint["model_version"],
        "training_type": checkpoint["training_type"], "audio": {"status": "not_implemented", "score": None},
        "sampled_frames": len(attempts), "usable_frames": len(frames), "attempts": attempts,
        "warning": "Experimental visual baseline. The score does not establish identity or a probability of fraud.",
    }
    if len(frames) < checkpoint["face_settings"]["min_usable_frames"]:
        return {**result, "status": "insufficient_evidence", "reason": "Not enough unambiguous usable face frames."}
    encoder, transform, _ = make_encoder(checkpoint["backbone"], pretrained=False, threads=cpu_threads)
    encoder.load_state_dict(checkpoint["encoder_state_dict"], strict=True)
    tensors = []
    for item in frames:
        # Match the JPEG encoding used by the cached training face crops.
        success, encoded = cv2.imencode(".jpg", item["image"], [cv2.IMWRITE_JPEG_QUALITY, 95])
        if not success:
            raise ValueError("A face crop could not be encoded.")
        image = cv2.imdecode(encoded, cv2.IMREAD_COLOR)
        tensors.append(transform(Image.fromarray(cv2.cvtColor(image, cv2.COLOR_BGR2RGB))))
    with torch.inference_mode():
        vectors = torch.cat([encoder(torch.stack(tensors[offset:offset + 8])) for offset in range(0, len(tensors), 8)])
        standardized = (vectors - checkpoint["scaler_mean"]) / checkpoint["scaler_scale"]
        logits = standardized @ checkpoint["head_coefficient"] + checkpoint["head_intercept"]
        scores = torch.sigmoid(logits).numpy()
    score = float(np.mean(scores))
    if not np.isfinite(score):
        raise ValueError("The model produced an invalid score.")
    return {
        **result, "status": "complete",
        "visual": {"status": "complete", "score": score,
                   "verdict": "FAKE" if score >= checkpoint["threshold"] else "REAL",
                   "threshold": checkpoint["threshold"], "model_version": checkpoint["model_version"]},
        "frame_scores": [{"timestamp": item["timestamp"], "frame_index": item["frame_index"], "score": float(frame_score)}
                         for item, frame_score in zip(frames, scores, strict=True)],
    }
