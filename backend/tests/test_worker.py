import cv2
import pytest
import json
import sys

from backend import worker
from backend.worker import inspect_video


@pytest.mark.parametrize("change,first_frame,expected", [
    ({cv2.CAP_PROP_FPS: 0}, True, "no readable"),
    ({cv2.CAP_PROP_FRAME_COUNT: 1801}, True, "60 seconds"),
    ({cv2.CAP_PROP_FPS: 120}, True, "60 frames"),
    ({cv2.CAP_PROP_FRAME_WIDTH: 7680}, True, "4K"),
    ({}, False, "first video frame"),
])
def test_decoded_video_checks_reject_excessive_or_unreadable_inputs(monkeypatch, change, first_frame, expected):
    props = {cv2.CAP_PROP_FRAME_COUNT: 300, cv2.CAP_PROP_FPS: 30,
             cv2.CAP_PROP_FRAME_WIDTH: 1920, cv2.CAP_PROP_FRAME_HEIGHT: 1080, **change}
    class Capture:
        released = False
        def isOpened(self): return True
        def get(self, key): return props[key]
        def read(self): return first_frame, object() if first_frame else None
        def release(self): self.released = True
    capture = Capture()
    monkeypatch.setattr(cv2, "VideoCapture", lambda _: capture)
    with pytest.raises(ValueError, match=expected):
        inspect_video("fixture.mp4")
    assert capture.released


def test_worker_adds_only_real_audio_scores(tmp_path, monkeypatch):
    audio_run = tmp_path / "audio"
    audio_run.mkdir()
    (audio_run / "model.joblib").write_bytes(b"checkpoint-present")
    monkeypatch.setattr(worker, "inspect_video", lambda _: {"duration": 2, "width": 320, "height": 240})
    from ml import predict as visual_predict
    from audio import predict as audio_predict
    monkeypatch.setattr(visual_predict, "predict_video", lambda *_args, **_kwargs: {
        "status": "complete", "scope": "visual_only", "visual": {"status": "complete", "score": 0.7, "verdict": "FAKE"},
        "audio": {"status": "not_implemented", "score": None}})
    monkeypatch.setattr(audio_predict, "predict_video_audio", lambda *_: {
        "status": "complete", "score": 0.6, "verdict": "FAKE", "model_version": "audio-test"})
    output = tmp_path / "result.json"
    args = ["worker", "--video", str(tmp_path / "clip.mp4"), "--output", str(output),
            "--run", str(tmp_path), "--assets", str(tmp_path), "--audio-run", str(audio_run)]
    monkeypatch.setattr(sys, "argv", args)
    worker.main()
    result = json.loads(output.read_text())
    assert result["scope"] == "multimodal"
    assert result["audio"]["score"] == 0.6
    monkeypatch.setattr(audio_predict, "predict_video_audio", lambda *_: {
        "status": "insufficient_evidence", "score": None})
    worker.main()
    result = json.loads(output.read_text())
    assert result["scope"] == "visual_only"
    assert result["audio"]["score"] is None
    monkeypatch.setattr(visual_predict, "predict_video", lambda *_args, **_kwargs: {
        "status": "insufficient_evidence", "scope": "visual_only", "reason": "No usable face frames.",
        "audio": {"status": "not_implemented", "score": None}})
    monkeypatch.setattr(audio_predict, "predict_video_audio", lambda *_: {
        "status": "complete", "score": 0.6, "verdict": "FAKE", "model_version": "audio-test"})
    worker.main()
    result = json.loads(output.read_text())
    assert result["status"] == "insufficient_evidence"
    assert result["scope"] == "multimodal"
    assert result["audio"]["score"] == 0.6
