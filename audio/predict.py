"""Score a video's decoded speech with a locally trained audio artifact."""

from __future__ import annotations

import subprocess
from pathlib import Path

import joblib
import numpy as np

from ml.common import read_json
from .dataset import sha256_file
from .features import FEATURE_VERSION, SAMPLE_RATE, waveform_features


def load_model(run):
    run = Path(run)
    summary = read_json(run / "training_summary.json")
    model_path = run / "model.joblib"
    if sha256_file(model_path) != summary["checkpoint_sha256"]:
        raise ValueError("Audio checkpoint checksum mismatch.")
    model = joblib.load(model_path)  # Only load artifacts created by our local training command.
    if model["format_version"] != 1 or model["feature_version"] != FEATURE_VERSION:
        raise ValueError("Audio checkpoint feature format is incompatible.")
    if float(model["threshold"]) != float(summary["threshold"]):
        raise ValueError("Audio checkpoint threshold differs from its training summary.")
    return summary, model


def decode_video_audio(video):
    from imageio_ffmpeg import get_ffmpeg_exe

    command = [get_ffmpeg_exe(), "-nostdin", "-v", "error", "-i", str(video), "-t", "60",
               "-map", "0:a:0", "-vn", "-ac", "1", "-ar", str(SAMPLE_RATE),
               "-f", "s16le", "-acodec", "pcm_s16le", "pipe:1"]
    result = subprocess.run(command, capture_output=True, timeout=45, check=False,
                            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    if result.returncode != 0 or not result.stdout:
        return None
    if len(result.stdout) > 60 * SAMPLE_RATE * 2 + 4096:
        raise ValueError("Decoded audio exceeds the 60-second video limit.")
    return np.frombuffer(result.stdout[:len(result.stdout) & ~1], dtype="<i2").astype(np.float32) / 32768.0


def predict_video_audio(run, video):
    summary, model = load_model(run)
    samples = decode_video_audio(video)
    if samples is None or len(samples) < SAMPLE_RATE // 2:
        return {"status": "insufficient_evidence", "score": None,
                "reason": "No readable audio track of at least half a second."}
    vectors = []
    window = 10 * SAMPLE_RATE
    for start in range(0, len(samples), window):
        segment = samples[start:start + window]
        if len(segment) < SAMPLE_RATE // 2:
            continue
        if float(np.sqrt(np.mean(np.square(segment)))) < 0.0005:
            continue
        vectors.append(waveform_features(segment, SAMPLE_RATE))
    if not vectors:
        return {"status": "insufficient_evidence", "score": None,
                "reason": "The audio track has too little usable signal."}
    scores = model["estimator"].predict_proba(np.stack(vectors))[:, 1]
    score = float(np.mean(scores))
    if not np.isfinite(score):
        raise ValueError("Audio model produced an invalid score.")
    threshold = float(model["threshold"])
    return {"status": "complete", "score": score,
            "verdict": "FAKE" if score >= threshold else "REAL",
            "threshold": threshold, "model_version": summary["model_version"],
            "segments": len(vectors),
            "warning": "ASVspoof LA speech is not banking KYC audio; this signal is not a fraud probability."}
