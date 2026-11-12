"""Deterministic training/development channel simulations; never label-dependent."""
from __future__ import annotations

import hashlib
from pathlib import Path
import subprocess
import tempfile

import numpy as np
from imageio_ffmpeg import get_ffmpeg_exe

from .features import SAMPLE_RATE

VERSION = "aac-channel-batch-v2"
PROFILES = ("aac32", "aac64_noise")


def _run_codec(command, **options):
    # A sleeping/busy laptop can interrupt one batch. Retrying cannot change its
    # source samples or seed, and the cache is only committed after success.
    for attempt in range(2):
        try:
            return subprocess.run(command, **options)
        except subprocess.TimeoutExpired:
            if attempt == 1:
                raise


def _perturb(samples, audio_id, profile, seed):
    samples = np.asarray(samples, dtype=np.float32)
    if samples.ndim != 1 or not np.isfinite(samples).all() or not len(samples):
        raise ValueError("Channel simulation requires finite mono samples.")
    digest = hashlib.sha256(f"{seed}:{audio_id}:{profile}".encode()).digest()
    rng = np.random.default_rng(int.from_bytes(digest[:8], "little"))
    signal = samples.copy()
    if profile == "aac64_noise":
        rms = float(np.sqrt(np.mean(signal ** 2)))
        snr_db = float(rng.uniform(20, 30))
        signal += rng.normal(0, rms / 10 ** (snr_db / 20), len(signal)).astype(np.float32)
    signal *= np.float32(10 ** (float(rng.uniform(-12, 6)) / 20))
    # Avoid manufacturing clipping as an accidental class cue.
    peak = float(np.max(np.abs(signal)))
    if peak > 0.95:
        signal *= np.float32(0.95 / peak)
    return signal


def channel_view(samples, audio_id, profile, *, seed=20261111, scratch=None):
    return channel_batch([(audio_id, samples)], profile, seed=seed, scratch=scratch)[0]


def channel_batch(items, profile, *, seed=20261111, scratch=None):
    """One codec invocation per bounded batch, with silence isolating utterances."""
    if profile not in PROFILES:
        raise ValueError(f"Unknown channel profile: {profile}")
    if not items or len(items) > 100:
        raise ValueError("Use one to 100 utterances per channel batch.")
    guard = np.zeros(SAMPLE_RATE // 4, dtype=np.float32)
    parts, spans, offset = [], [], 0
    for audio_id, samples in items:
        signal = _perturb(samples, audio_id, profile, seed)
        parts.extend((guard, signal, guard))
        spans.append((offset + len(guard), offset + len(guard) + len(signal)))
        offset += len(signal) + 2 * len(guard)
    signal = np.concatenate(parts)
    executable = get_ffmpeg_exe()
    options = {"capture_output": True, "timeout": 120,
               "creationflags": getattr(subprocess, "CREATE_NO_WINDOW", 0)}
    with tempfile.TemporaryDirectory(prefix="audio-channel-", dir=scratch) as temporary:
        encoded = Path(temporary) / "encoded.m4a"
        # M4A edit-list metadata preserves AAC encoder delay; raw ADTS would not.
        command = [executable, "-nostdin", "-y", "-v", "error", "-f", "f32le", "-ar", str(SAMPLE_RATE),
                   "-ac", "1", "-i", "pipe:0", "-c:a", "aac", "-b:a",
                   "32k" if profile == "aac32" else "64k", "-threads", "1", str(encoded)]
        result = _run_codec(command, input=signal.astype("<f4").tobytes(), **options)
        if result.returncode:
            raise RuntimeError(f"AAC encoding failed: {result.stderr.decode(errors='replace')[-500:]}")
        result = _run_codec([executable, "-nostdin", "-v", "error", "-i", str(encoded),
                                 "-ac", "1", "-ar", str(SAMPLE_RATE), "-threads", "1",
                                 "-f", "f32le", "pipe:1"], **options)
        if result.returncode or len(result.stdout) % 4:
            raise RuntimeError("AAC decoding failed.")
        decoded = np.frombuffer(result.stdout, dtype="<f4")
        if not (len(signal) <= len(decoded) <= len(signal) + 2048) or not np.isfinite(decoded).all():
            raise ValueError("Unexpected decoded AAC duration or sample values.")
        return [decoded[start:end].copy() for start, end in spans]
