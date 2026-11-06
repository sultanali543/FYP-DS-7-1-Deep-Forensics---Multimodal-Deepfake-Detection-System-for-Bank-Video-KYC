"""Sample a few frames and cache unambiguous face crops for CPU training."""

from __future__ import annotations

from pathlib import Path
import re
import urllib.request
import zipfile

import cv2
import numpy as np

from .common import DEFAULT_ASSETS, fingerprint, file_sha256, read_json, write_json
from .data import open_video

YUNET_FILE = "face_detection_yunet_2023mar.onnx"
YUNET_POINTER = f"https://raw.githubusercontent.com/opencv/opencv_zoo/main/models/face_detection_yunet/{YUNET_FILE}"
YUNET_DOWNLOAD = f"https://media.githubusercontent.com/media/opencv/opencv_zoo/main/models/face_detection_yunet/{YUNET_FILE}"
FACE_KEYS = (
    "frames_per_video", "min_usable_frames", "image_size", "detector_max_side",
    "detector_score_threshold", "min_face_size", "crop_margin", "max_secondary_face_area_ratio",
)


def ensure_detector(assets=DEFAULT_ASSETS):
    """Verify the ONNX download against the publisher's Git LFS SHA-256."""
    assets = Path(assets)
    assets.mkdir(parents=True, exist_ok=True)
    path = assets / YUNET_FILE
    provenance = assets / "yunet_source.json"
    if path.exists() and provenance.exists():
        expected = read_json(provenance)["sha256"]
        if file_sha256(path) == expected:
            return path
        raise ValueError("The face detector checksum changed; remove the damaged asset and download it again.")
    with urllib.request.urlopen(YUNET_POINTER, timeout=45) as response:
        pointer = response.read(2048)
    match = re.search(rb"oid sha256:([a-f0-9]{64})", pointer)
    if not match:
        raise ValueError("The publisher's face-detector checksum was not available.")
    expected = match.group(1).decode()
    temporary = path.with_suffix(".download")
    try:
        with urllib.request.urlopen(YUNET_DOWNLOAD, timeout=60) as response, temporary.open("wb") as target:
            target.write(response.read(2 * 1024 * 1024))
        if file_sha256(temporary) != expected:
            raise ValueError("Face-detector checksum verification failed.")
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)
    write_json(provenance, {"url": YUNET_DOWNLOAD, "checksum_source": YUNET_POINTER, "sha256": expected})
    return path


def frame_positions(total_frames, samples):
    if total_frames < 1 or samples < 1:
        return []
    return np.unique(np.linspace(0, total_frames - 1, min(samples, total_frames)).astype(int)).tolist()


def square_box(box, width, height, margin):
    x, y, face_width, face_height = [float(value) for value in box[:4]]
    side = min(max(face_width, face_height) * (1 + 2 * margin), width, height)
    if side <= 1:
        return None
    left = min(max(0, x + face_width / 2 - side / 2), width - side)
    top = min(max(0, y + face_height / 2 - side / 2), height - side)
    return int(left), int(top), int(left + side), int(top + side)


class FaceCropper:
    def __init__(self, settings, detector_path):
        self.settings = settings
        cv2.setNumThreads(1)
        self.detector = cv2.FaceDetectorYN.create(
            str(detector_path), "", (320, 320),
            score_threshold=settings["detector_score_threshold"], nms_threshold=0.3, top_k=1000,
        )

    def crop(self, frame):
        height, width = frame.shape[:2]
        scale = min(1.0, self.settings["detector_max_side"] / max(height, width))
        resized = cv2.resize(frame, (max(1, round(width * scale)), max(1, round(height * scale))))
        self.detector.setInputSize((resized.shape[1], resized.shape[0]))
        _, found = self.detector.detect(resized)
        if found is None:
            return None, "no_face", None
        faces = [face for face in found if min(face[2], face[3]) / scale >= self.settings["min_face_size"]]
        if not faces:
            return None, "face_too_small", None
        faces.sort(key=lambda face: float(face[2] * face[3]), reverse=True)
        if len(faces) > 1 and faces[1][2] * faces[1][3] >= faces[0][2] * faces[0][3] * self.settings["max_secondary_face_area_ratio"]:
            return None, "multiple_dominant_faces", None
        original_box = faces[0][:4] / scale
        box = square_box(original_box, width, height, self.settings["crop_margin"])
        if box is None:
            return None, "invalid_crop", None
        left, top, right, bottom = box
        crop = frame[top:bottom, left:right]
        if crop.size == 0:
            return None, "empty_crop", None
        crop = cv2.resize(crop, (self.settings["image_size"], self.settings["image_size"]), interpolation=cv2.INTER_AREA)
        return crop, "usable", {"box": list(box), "face_score": float(faces[0][-1])}

    def sample_video(self, path):
        capture = cv2.VideoCapture(str(path))
        if not capture.isOpened():
            capture.release()
            raise ValueError("The video could not be opened.")
        try:
            total = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
            fps = float(capture.get(cv2.CAP_PROP_FPS))
            if total < 1 or not np.isfinite(fps) or fps <= 0:
                raise ValueError("Video frame count or frame rate is unavailable.")
            frames, attempts = [], []
            for position in frame_positions(total, self.settings["frames_per_video"]):
                capture.set(cv2.CAP_PROP_POS_FRAMES, position)
                success, frame = capture.read()
                if not success:
                    attempts.append({"frame_index": position, "reason": "unreadable_frame"})
                    continue
                crop, reason, details = self.crop(frame)
                attempts.append({"frame_index": position, "reason": reason})
                if crop is not None:
                    frames.append({"image": crop, "frame_index": position, "timestamp": position / fps, **details})
            return frames, attempts
        finally:
            capture.release()


def face_cache_signature(manifest, settings, detector_path):
    return fingerprint({
        "manifest": manifest["fingerprint"],
        "settings": {key: settings[key] for key in FACE_KEYS},
        "detector_sha256": file_sha256(detector_path),
        "jpeg_quality": 95,
        "opencv_version": cv2.__version__,
    })


def prepare_faces(manifest, settings, output, detector_path, limit=None):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    signature = face_cache_signature(manifest, settings, detector_path)
    cropper = FaceCropper(settings, detector_path)
    selected_rows = manifest["rows"][:limit] if limit else manifest["rows"]
    audits = []
    for index, row in enumerate(selected_rows, 1):
        directory = output / Path(row["video_id"]).stem
        audit_path = directory / "audit.json"
        if audit_path.exists():
            previous = read_json(audit_path)
            if previous.get("signature") == signature and all((directory / item["filename"]).exists() for item in previous.get("crops", [])):
                audits.append(previous)
                print(f"[{index}/{len(selected_rows)}] cached {row['video_id']}: {previous['status']}", flush=True)
                continue
        directory.mkdir(parents=True, exist_ok=True)
        audit = {"video_id": row["video_id"], "signature": signature, "crops": [], "attempts": []}
        try:
            with open_video(manifest, row) as path:
                frames, attempts = cropper.sample_video(path)
            for item in frames:
                filename = f"frame_{item['frame_index']:06d}.jpg"
                if not cv2.imwrite(str(directory / filename), item.pop("image"), [cv2.IMWRITE_JPEG_QUALITY, 95]):
                    raise OSError("The crop image could not be saved.")
                audit["crops"].append({"filename": filename, **item})
            audit["attempts"] = attempts
            audit["status"] = "usable" if len(frames) >= settings["min_usable_frames"] else "insufficient_evidence"
        except (ValueError, OSError, cv2.error, zipfile.BadZipFile) as error:
            audit["status"] = "failed"
            audit["reason"] = str(error)
        write_json(audit_path, audit)
        audits.append(audit)
        print(f"[{index}/{len(selected_rows)}] {row['video_id']}: {audit['status']} ({len(audit['crops'])} crops)", flush=True)
    summary = {
        "signature": signature, "processed_videos": len(audits),
        "manifest_fingerprint": manifest["fingerprint"],
        "usable_videos": sum(item["status"] == "usable" for item in audits),
        "insufficient_evidence": sum(item["status"] == "insufficient_evidence" for item in audits),
        "failed_videos": sum(item["status"] == "failed" for item in audits),
        "face_settings": {key: settings[key] for key in FACE_KEYS},
        "detector_sha256": file_sha256(detector_path),
    }
    write_json(output / "summary.json", summary)
    return summary


def create_crop_review(manifest, crops, output, max_videos=12):
    """Show only training crops, keeping held-out test images out of manual review."""
    from PIL import Image, ImageDraw

    crops, output = Path(crops), Path(output)
    rows = [row for row in manifest["rows"] if row["split"] == "train"]
    chosen = [rows[index] for index in frame_positions(len(rows), max_videos)]
    if not chosen:
        raise ValueError("No training videos are available for crop review.")
    sheet = Image.new("RGB", (720, 56 + 170 * len(chosen)), "#f5f5f2")
    draw = ImageDraw.Draw(sheet)
    draw.text((12, 12), "Training crop review | preprocessing check only", fill="#202b25")
    for index, row in enumerate(chosen):
        top = 56 + index * 170
        directory = crops / Path(row["video_id"]).stem
        audit = read_json(directory / "audit.json")
        label = "FAKE" if row["label"] else "REAL"
        draw.text((12, top), f"{row['video_id']} | {label} | {audit['status']}", fill="#202b25")
        frames = audit["crops"]
        for column, frame_index in enumerate(frame_positions(len(frames), 3)):
            with Image.open(directory / frames[frame_index]["filename"]) as image:
                sheet.paste(image.convert("RGB").resize((140, 140)), (12 + column * 230, top + 22))
    output.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(output)
    return {"review_image": str(output.resolve()), "training_videos_shown": len(chosen)}
