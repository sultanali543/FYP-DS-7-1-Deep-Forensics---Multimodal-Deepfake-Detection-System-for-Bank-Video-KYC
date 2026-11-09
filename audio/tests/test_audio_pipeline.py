import io

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq
import pytest
import soundfile as sf

from audio import dataset
from audio.features import FEATURE_VERSION, audio_bytes_features, waveform_features


def test_waveform_features_are_reproducible_and_reject_bad_audio():
    time = np.arange(16000, dtype=np.float32) / 16000
    signal = 0.2 * np.sin(2 * np.pi * 440 * time)
    first = waveform_features(signal, 16000)
    assert first.shape == (241,)
    assert first.dtype == np.float32
    np.testing.assert_array_equal(first, waveform_features(signal, 16000))
    with pytest.raises(ValueError, match="16 kHz"):
        waveform_features(signal, 8000)
    with pytest.raises(ValueError, match="duration"):
        waveform_features(signal[:100], 16000)


def tiny_parquet(path, split, speaker):
    buffer = io.BytesIO()
    sf.write(buffer, np.zeros(16000, dtype=np.float32), 16000, format="FLAC")
    prefix = "LA_T_" if split == "train" else "LA_D_"
    names = [prefix + "0000001", prefix + "0000002"]
    rows = [{"speaker_id": speaker, "audio_file_name": name,
             "audio": {"bytes": buffer.getvalue(), "path": name + ".flac"},
             "system_id": "-" if key == 0 else "A01", "key": key}
            for name, key in zip(names, (0, 1), strict=True)]
    pq.write_table(pa.Table.from_pylist(rows), path, row_group_size=2)


def test_parquet_audit_separation_and_resumable_cache(tmp_path, monkeypatch):
    monkeypatch.setattr(dataset, "EXPECTED", {
        "train": {"rows": 2, "labels": {0: 1, 1: 1}, "prefix": "LA_T_"},
        "validation": {"rows": 2, "labels": {0: 1, 1: 1}, "prefix": "LA_D_"},
    })
    train, validation = tmp_path / "train.parquet", tmp_path / "validation.parquet"
    tiny_parquet(train, "train", "LA_0079")
    tiny_parquet(validation, "validation", "LA_0069")
    audit = dataset.audit_pair(train, validation)
    assert audit["train"]["labels"] == {"0": 1, "1": 1}
    assert audit["feature_version"] == FEATURE_VERSION
    assert set(audit["train"]["speakers"]).isdisjoint(audit["validation"]["speakers"])
    cache = tmp_path / "features"
    assert dataset.extract_split(train, "train", cache, audit["train"]["sha256"])
    assert dataset.extract_split(train, "train", cache, audit["train"]["sha256"])
    features = dataset.load_split(cache, 1)
    assert features["x"].shape == (2, 241)
    assert features["y"].tolist() == [0, 1]
    with pytest.raises(ValueError, match="another dataset"):
        dataset.extract_split(train, "train", cache, "different-hash")
    tiny_parquet(validation, "validation", "LA_0079")
    with pytest.raises(ValueError, match="speakers overlap"):
        dataset.audit_pair(train, validation, hash_files=False)
