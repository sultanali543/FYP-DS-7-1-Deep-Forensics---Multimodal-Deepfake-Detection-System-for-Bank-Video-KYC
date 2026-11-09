"""One isolated CPU prediction. The server can stop a stuck decoder on timeout."""
import argparse
import json
import math
import subprocess
from pathlib import Path

from .config import MAX_VIDEO_FRAMES, MAX_VIDEO_PIXELS, MAX_VIDEO_SECONDS


def inspect_video(path):
    import cv2

    capture = cv2.VideoCapture(str(path))
    try:
        if not capture.isOpened():
            raise ValueError("This MP4 could not be decoded. Try an MP4 encoded with H.264.")
        fps = capture.get(cv2.CAP_PROP_FPS)
        frames = capture.get(cv2.CAP_PROP_FRAME_COUNT)
        width = capture.get(cv2.CAP_PROP_FRAME_WIDTH)
        height = capture.get(cv2.CAP_PROP_FRAME_HEIGHT)
        if any(not math.isfinite(v) or v <= 0 for v in (fps, frames, width, height)):
            raise ValueError("This video has no readable frame rate, duration, or dimensions.")
        if frames / fps > MAX_VIDEO_SECONDS or frames > MAX_VIDEO_FRAMES or fps > 60.1:
            raise ValueError("Use a clip up to 60 seconds and 60 frames per second for this CPU prototype.")
        if width * height > MAX_VIDEO_PIXELS or max(width, height) > 4096:
            raise ValueError("Use a video at 4K resolution or smaller (1080p is recommended).")
        readable, frame = capture.read()
        if not readable or frame is None:
            raise ValueError("The first video frame could not be decoded. Try another MP4.")
        return {"duration": frames / fps, "width": int(width), "height": int(height)}
    finally:
        capture.release()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--video", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--audio-run", type=Path, required=True)
    parser.add_argument("--assets", type=Path, required=True)
    args = parser.parse_args()
    try:
        source = inspect_video(args.video)
    except ValueError as error:
        result = {"status": "failed", "error": str(error)}
    else:
        # Reuse the exact CLI prediction path, checkpoint, crops, and threshold.
        from ml.predict import predict_video
        result = {**predict_video(args.run, args.video, assets=args.assets), "source_metadata": source}
        if (args.audio_run / "model.joblib").is_file():
            try:
                from audio.predict import predict_video_audio
                result["audio"] = predict_video_audio(args.audio_run, args.video)
            except (OSError, ValueError, RuntimeError, KeyError, ImportError, subprocess.TimeoutExpired):
                result["audio"] = {"status": "unavailable", "score": None,
                                   "reason": "The audio model could not analyze this track."}
            if result["audio"]["status"] == "complete":
                result["scope"] = "multimodal"
    args.output.write_text(json.dumps(result, allow_nan=False), encoding="utf-8")


if __name__ == "__main__":
    main()
