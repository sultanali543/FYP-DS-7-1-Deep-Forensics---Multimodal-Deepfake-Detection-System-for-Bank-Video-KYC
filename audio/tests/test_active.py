import hashlib
import json

import pytest

from audio.active import selected_audio_run


def test_default_reference_and_verified_active_model(tmp_path):
    runs = tmp_path / "data/runs"
    assert selected_audio_run(tmp_path) == runs / "audio_baseline"
    candidate = runs / "candidate"
    candidate.mkdir(parents=True)
    content = b"checkpoint fixture"
    (candidate / "model.joblib").write_bytes(content)
    checksum = hashlib.sha256(content).hexdigest()
    (candidate / "training_summary.json").write_text(json.dumps({"status": "trained", "model_version": "v2", "checkpoint_sha256": checksum}))
    (candidate / "release_decision.json").write_text(json.dumps({"release_approved": True, "no_test_retuning": True,
        "candidate_model": "v2", "candidate_test": {"model_version": "v2", "checkpoint_sha256": checksum}}))
    pointer = runs / "audio_active.json"
    pointer.write_text(json.dumps({"format_version": 1, "run": "candidate", "model_version": "v2", "checkpoint_sha256": checksum}))
    assert selected_audio_run(tmp_path) == candidate.resolve()
    (candidate / "model.joblib").write_bytes(b"changed")
    with pytest.raises(ValueError, match="pointer is invalid"):
        selected_audio_run(tmp_path)


def test_failed_or_absent_release_cannot_activate_candidate(tmp_path, monkeypatch):
    runs = tmp_path / "data/runs"
    candidate = runs / "candidate"
    candidate.mkdir(parents=True)
    from audio import active
    summary = {"status": "trained", "model_version": "v2", "checkpoint_sha256": "hash"}
    monkeypatch.setattr("audio.predict.load_model", lambda _: (summary, object()))
    with pytest.raises(ValueError, match="approved release decision"):
        active.activate_run(candidate, tmp_path)
    (candidate / "release_decision.json").write_text(json.dumps({"release_approved": False,
        "no_test_retuning": True, "candidate_model": "v2",
        "candidate_test": {"model_version": "v2", "checkpoint_sha256": "hash"}}))
    with pytest.raises(ValueError, match="did not pass"):
        active.activate_run(candidate, tmp_path)
    assert not (runs / "audio_active.json").exists()


@pytest.mark.parametrize("value", [{"format_version": 1, "run": "../outside"}, {}, [], None])
def test_bad_active_pointer_never_silently_falls_back(tmp_path, value):
    runs = tmp_path / "data/runs"
    runs.mkdir(parents=True)
    (runs / "audio_active.json").write_text(json.dumps(value))
    with pytest.raises(ValueError, match="pointer is invalid"):
        selected_audio_run(tmp_path)
