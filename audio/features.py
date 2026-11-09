"""Deterministic, bounded-memory acoustic features shared by training and inference."""

from __future__ import annotations

from functools import lru_cache
import io

import numpy as np
from scipy.fft import dct, rfft
import soundfile as sf

SAMPLE_RATE = 16000
FFT_SIZE = 512
FRAME_SIZE = 400
HOP_SIZE = 160
MEL_BANDS = 128
CEPSTRA = 40
FEATURE_VERSION = "logmel128-cepstra40-summary-v1"


@lru_cache(maxsize=1)
def mel_filters():
    def hertz_to_mel(hertz):
        return 2595.0 * np.log10(1.0 + hertz / 700.0)

    def mel_to_hertz(mel):
        return 700.0 * (10.0 ** (mel / 2595.0) - 1.0)

    positions = mel_to_hertz(np.linspace(hertz_to_mel(0), hertz_to_mel(SAMPLE_RATE / 2), MEL_BANDS + 2))
    bins = np.arange(FFT_SIZE // 2 + 1) * SAMPLE_RATE / FFT_SIZE
    lower, centers, upper = positions[:-2], positions[1:-1], positions[2:]
    rising = (bins[None, :] - lower[:, None]) / (centers - lower)[:, None]
    falling = (upper[:, None] - bins[None, :]) / (upper - centers)[:, None]
    weights = np.maximum(0, np.minimum(rising, falling)).astype(np.float32)
    weights /= np.maximum(weights.sum(axis=1, keepdims=True), 1e-8)
    return weights


def waveform_features(waveform, sample_rate):
    if sample_rate != SAMPLE_RATE or waveform.ndim != 1:
        raise ValueError("Audio must be mono at 16 kHz.")
    if not (int(0.5 * SAMPLE_RATE) <= len(waveform) <= 30 * SAMPLE_RATE):
        raise ValueError("Audio duration must be between 0.5 and 30 seconds.")
    if not np.isfinite(waveform).all():
        raise ValueError("Audio has invalid sample values.")
    signal = waveform.astype(np.float32, copy=False)
    signal = np.pad(signal, (FRAME_SIZE // 2, FRAME_SIZE // 2))
    frames = np.lib.stride_tricks.sliding_window_view(signal, FRAME_SIZE)[::HOP_SIZE]
    window = np.hanning(FRAME_SIZE).astype(np.float32)
    spectrum = rfft(frames * window, n=FFT_SIZE, axis=1)
    power = np.square(np.abs(spectrum)).astype(np.float32)
    logmel = np.log(np.maximum(power @ mel_filters().T, 1e-10))
    cepstra = dct(logmel, type=2, axis=1, norm="ortho")[:, :CEPSTRA]
    delta = np.diff(cepstra, axis=0)
    vector = np.concatenate((
        cepstra.mean(axis=0), cepstra.std(axis=0),
        np.percentile(cepstra, 10, axis=0), np.percentile(cepstra, 90, axis=0),
        delta.mean(axis=0), delta.std(axis=0),
        np.array([np.log(np.maximum(np.mean(np.square(waveform)), 1e-10))]),
    )).astype(np.float32)
    if not np.isfinite(vector).all():
        raise ValueError("Audio features are not finite.")
    return vector


def audio_bytes_features(audio_bytes):
    waveform, sample_rate = sf.read(io.BytesIO(audio_bytes), dtype="float32", always_2d=False)
    return waveform_features(waveform, sample_rate)
