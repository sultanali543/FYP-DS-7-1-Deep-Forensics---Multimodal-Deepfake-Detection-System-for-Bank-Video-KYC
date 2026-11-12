import numpy as np
import pytest
import subprocess

from audio import augmentation
from audio.augmentation import channel_batch, channel_view
from audio.metrics import NoFeasibleThreshold, audio_metrics, select_robust_threshold, speaker_bootstrap_comparison
from audio.ensemble import AudioBlend
from audio.robustness import balanced_ids, condition_weights, load_channels, split_dev_speakers


def test_codec_timeout_retries_once_then_still_reports_persistent_failure(monkeypatch):
    calls = []

    def temporary_failure(command, **options):
        calls.append(command)
        if len(calls) == 1:
            raise subprocess.TimeoutExpired(command, options["timeout"])
        return "completed"

    monkeypatch.setattr(augmentation.subprocess, "run", temporary_failure)
    assert augmentation._run_codec(["ffmpeg"], timeout=1) == "completed"
    assert len(calls) == 2

    def failure(command, **options):
        raise subprocess.TimeoutExpired(command, options["timeout"])

    monkeypatch.setattr(augmentation.subprocess, "run", failure)
    with pytest.raises(subprocess.TimeoutExpired):
        augmentation._run_codec(["ffmpeg"], timeout=1)


def test_channel_roundtrip_preserves_length_alignment_and_determinism(tmp_path):
    t = np.arange(16000, dtype=np.float32) / 16000
    waveform = 0.1 * np.sin(2 * np.pi * (220 * t + 200 * t ** 2))
    changed = channel_view(waveform, "clip", "aac32", scratch=tmp_path)
    assert changed.shape == waveform.shape
    assert np.isfinite(changed).all()
    assert np.corrcoef(waveform, changed)[0, 1] > 0.9
    np.testing.assert_array_equal(changed, channel_view(waveform, "clip", "aac32", scratch=tmp_path))
    assert not list(tmp_path.iterdir())
    with pytest.raises(ValueError, match="Unknown"):
        channel_view(waveform, "clip", "missing")
    other = 0.1 * np.sin(2 * np.pi * 880 * t[:10000])
    batch = channel_batch([("clip", waveform), ("other", other)], "aac32", scratch=tmp_path)
    assert [len(item) for item in batch] == [16000, 10000]
    assert np.corrcoef(waveform, batch[0])[0, 1] > 0.9
    assert np.corrcoef(other, batch[1])[0, 1] > 0.9


def test_balanced_draw_covers_speakers_and_attacks_and_has_no_duplicate_ids():
    rows = [{"key": label, "speaker_id": speaker, "system_id": "-" if label == 0 else attack,
             "audio_file_name": f"{label}-{speaker}-{attack}-{i}"}
            for label in (0, 1) for speaker in ("a", "b") for attack in ("A01", "A02") for i in range(5)]
    ids = balanced_ids(rows, 8, 42)
    chosen = [row for row in rows if row["audio_file_name"] in ids]
    assert len(ids) == len(set(ids)) == 16
    assert sum(row["key"] == 0 for row in chosen) == 8
    assert {row["speaker_id"] for row in chosen} == {"a", "b"}
    assert ids == balanced_ids(rows, 8, 42)
    with pytest.raises(ValueError, match="more distinct"):
        balanced_ids(rows, 100, 42)
    calibration, selection = split_dev_speakers([f"speaker{i}" for i in range(20)])
    assert len(calibration) == len(selection) == 10
    assert set(calibration).isdisjoint(selection)


def test_weights_balance_class_and_channel_without_a_label_specific_codec():
    labels = np.array([0, 1, 1, 1, 0, 0, 1, 1])
    conditions = np.array(["clean"] * 4 + ["aac"] * 4)
    weights = condition_weights(labels, conditions)
    for condition in ("clean", "aac"):
        for label in (0, 1):
            assert weights[(conditions == condition) & (labels == label)].sum() == pytest.approx(2)
    with pytest.raises(ValueError, match="both classes"):
        condition_weights([0, 1], ["clean", "aac"])


def test_error_rates_score_polarity_eer_and_robust_threshold():
    labels = np.array([0, 0, 1, 1])
    perfect = audio_metrics(labels, [0.1, 0.2, 0.8, 0.9], 0.5)
    assert perfect["eer"] == 0
    assert perfect["real_flagged_as_fake_rate"] == 0
    assert perfect["fake_accepted_as_real_rate"] == 0
    assert audio_metrics(labels, [0.5] * 4, 0.5)["eer"] == pytest.approx(0.5)
    assert audio_metrics(labels, [0.9, 0.8, 0.2, 0.1], 0.5)["eer"] == 1
    conditions = {"clean": (labels, np.array([0.1, 0.2, 0.8, 0.9])),
                  "channel": (labels, np.array([0.4, 0.6, 0.7, 0.9]))}
    threshold = select_robust_threshold(conditions)
    assert 0.6 < threshold <= 0.7
    with pytest.raises(ValueError):
        select_robust_threshold({"bad": ([0, 0], [0.1, 0.2])})
    with pytest.raises(ValueError):
        audio_metrics(labels, [0.1, np.nan, 0.8, 0.9], 0.5)


def test_paired_bootstrap_retains_speaker_groups():
    y = [0, 1, 0, 1]
    scores = [0.1, 0.9, 0.3, 0.7]
    result = speaker_bootstrap_comparison(y, scores, scores, ["a", "a", "b", "b"], 0.5, 0.5, repeats=20)
    assert result["speakers"] == 2
    assert result["intervals_95"]["genuine_false_alarm_rate"] == [0.0, 0.0]
    assert result["intervals_95"]["missed_spoof_rate"] == [0.0, 0.0]


def test_constrained_threshold_protects_clean_classes_and_rejects_infeasible_case():
    y = np.array([0, 0, 1, 1])
    conditions = {"clean": (y, np.array([0.2, 0.7, 0.8, 0.9])),
                  "noisy": (y, np.array([0.1, 0.2, 0.3, 0.4]))}
    threshold = select_robust_threshold(conditions, (0.0, 0.0))
    assert 0.7 < threshold <= 0.8
    with pytest.raises(NoFeasibleThreshold):
        select_robust_threshold({"clean": (y, np.array([0.9, 0.8, 0.2, 0.1]))}, (0.0, 0.0))


def test_blend_retains_class_order_and_weighted_scores():
    class Fixed:
        classes_ = [0, 1]
        def __init__(self, score):
            self.score = score
        def predict_proba(self, x):
            return np.tile([1 - self.score, self.score], (len(x), 1))
    blend = AudioBlend(Fixed(0.2), Fixed(0.8), 0.25)
    np.testing.assert_allclose(blend.predict_proba(np.zeros((2, 241)))[:, 1], 0.35)
    assert blend.classes_.tolist() == [0, 1]


def test_incomplete_augmented_cache_cannot_be_trained(tmp_path):
    np.savez_compressed(tmp_path / "group-0000.npz", x=np.zeros((1, 241)), y=[0], ids=["one"],
                        speakers=["speaker"], systems=["-"], conditions=["aac32"])
    with pytest.raises(ValueError, match="incomplete"):
        load_channels(tmp_path, ["one"])
