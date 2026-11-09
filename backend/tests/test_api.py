import hashlib
import json
import subprocess
import threading
import time

from fastapi.testclient import TestClient
import pytest

from backend.app import create_app, model_readiness
from backend.config import Settings
from backend.jobs import Jobs, run_prediction

MP4_HEADER = b"\x00\x00\x00\x18ftypisom" + b"fixture"


def ready(_):
    return {"ready": True, "model_version": "test-model"}


def prediction(*_):
    return {"status": "complete", "model_version": "test-model", "usable_frames": 8,
            "sampled_frames": 12, "source_metadata": {"duration": 5, "width": 640, "height": 480},
            "visual": {"status": "complete", "score": 0.7, "verdict": "FAKE", "threshold": 0.66,
                       "model_version": "test-model"}}


@pytest.fixture
def settings(tmp_path):
    return Settings(temporary=tmp_path / "uploads", frontend=tmp_path / "frontend")


def terminal(client, identifier):
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        response = client.get(f"/api/analyses/{identifier}")
        assert response.status_code == 200
        result = response.json()
        if result["status"] not in {"queued", "running"}:
            return result
        time.sleep(0.01)
    pytest.fail("Analysis did not terminate")


def upload(client, name="clip.mp4", content=MP4_HEADER, content_type="video/mp4"):
    return client.post("/api/analyses", files={"file": (name, content, content_type)})


def test_success_preserves_prediction_and_deletes_only_server_copy(settings, tmp_path):
    original = tmp_path / "original.mp4"
    original.write_bytes(MP4_HEADER)
    with TestClient(create_app(settings, runner=prediction, readiness=ready)) as client:
        response = upload(client, name="../../original.mp4")
        assert response.status_code == 202
        result = terminal(client, response.json()["id"])
        assert result["source"]["name"] == "original.mp4"
        assert result["source"]["duration"] == 5
        assert result["visual"] == prediction()["visual"]
        assert result["usable_frames"] == 8
        assert result["mode"] == "live"
        assert result["upload_deleted"] is True
        assert result["audio"] == {"status": "not_implemented", "score": None}
        assert result["evidence"] == [] and result["sha256"] is None
        assert result["report_available"] is False
        assert list(client.app.state.jobs.directory.iterdir()) == []
        assert original.read_bytes() == MP4_HEADER
    assert list(settings.temporary.iterdir()) == []


@pytest.mark.parametrize("outcome", ["no_face", "crash", "timeout"])
def test_non_success_outcomes_never_invent_score_and_always_clean(settings, outcome):
    def runner(*_):
        if outcome == "crash":
            raise RuntimeError("internal path should not appear in the API")
        if outcome == "timeout":
            raise subprocess.TimeoutExpired("worker", 180)
        return {"status": "insufficient_evidence", "reason": "No usable face frames.", "usable_frames": 0}
    with TestClient(create_app(settings, runner=runner, readiness=ready)) as client:
        result = terminal(client, upload(client).json()["id"])
        assert result["status"] == ("insufficient_evidence" if outcome == "no_face" else "failed")
        assert "visual" not in result
        assert result["upload_deleted"] is True
        assert "internal path" not in json.dumps(result)
        assert list(client.app.state.jobs.directory.iterdir()) == []


@pytest.mark.parametrize("name,content,mime,code", [
    ("empty.mp4", b"", "video/mp4", 400),
    ("renamed.mp4", b"this is not an mp4", "video/mp4", 415),
    ("clip.avi", MP4_HEADER, "video/mp4", 415),
    ("clip.mp4", MP4_HEADER, "application/pdf", 415),
])
def test_rejected_uploads_release_capacity(settings, name, content, mime, code):
    with TestClient(create_app(settings, runner=prediction, readiness=ready)) as client:
        for _ in range(4):
            assert upload(client, name, content, mime).status_code == code
        assert upload(client).status_code == 202


def test_missing_duplicate_and_extra_multipart_fields_rejected(settings):
    with TestClient(create_app(settings, runner=prediction, readiness=ready)) as client:
        assert client.post("/api/analyses").status_code == 422
        files = [("file", ("one.mp4", MP4_HEADER)), ("file", ("two.mp4", MP4_HEADER))]
        assert client.post("/api/analyses", files=files).status_code == 400
        assert client.post("/api/analyses", files={"file": ("x.mp4", MP4_HEADER)}, data={"extra": "value"}).status_code == 400


def test_byte_limits_include_streamed_requests_without_content_length(tmp_path):
    settings = Settings(temporary=tmp_path / "uploads", frontend=tmp_path / "no-ui", max_bytes=32)
    with TestClient(create_app(settings, runner=prediction, readiness=ready)) as client:
        assert upload(client, content=MP4_HEADER * 10).status_code == 413
        assert client.post("/api/analyses", content=b"", headers={"Content-Length": "99999999"}).status_code == 413
        def chunks():
            yield b'--test\r\nContent-Disposition: form-data; name="file"; filename="x.mp4"\r\nContent-Type: video/mp4\r\n\r\n'
            yield MP4_HEADER
            for _ in range(18):
                yield b"x" * 65536
            yield b"\r\n--test--\r\n"
        result = client.post("/api/analyses", content=chunks(), headers={"Content-Type": "multipart/form-data; boundary=test"})
        assert result.status_code == 413
        assert list(client.app.state.jobs.directory.iterdir()) == []
        assert upload(client).status_code == 202


def test_queue_is_bounded_serial_and_health_stays_responsive(settings):
    entered, release = threading.Event(), threading.Event()
    calls = []
    def blocked(video, *_):
        calls.append(video)
        entered.set()
        assert release.wait(5)
        return prediction()
    with TestClient(create_app(settings, runner=blocked, readiness=ready)) as client:
        try:
            first = upload(client).json()["id"]
            assert entered.wait(2)
            second = upload(client).json()["id"]
            third = upload(client).json()["id"]
            assert len(calls) == 1
            assert upload(client).status_code == 429
            assert client.get(f"/api/analyses/{first}").json()["status"] == "running"
            assert client.get(f"/api/analyses/{second}").json()["status"] == "queued"
            assert client.get("/api/health").json()["ready"] is True
        finally:
            release.set()
        for identifier in (first, second, third):
            assert terminal(client, identifier)["upload_deleted"]
        assert len(calls) == 3


def test_readiness_cors_host_unknown_jobs_and_restart(settings):
    with TestClient(create_app(settings, runner=prediction, readiness=ready)) as client:
        assert client.get("/api/health", headers={"Origin": "http://127.0.0.1:5173"}).headers["access-control-allow-origin"] == "http://127.0.0.1:5173"
        assert client.post("/api/analyses", headers={"Origin": "https://unrelated.example"}).status_code == 403
        assert client.post("/api/analyses", headers={"Origin": "null"}).status_code == 403
        assert client.get("/api/health", headers={"Host": "unrelated.example"}).status_code == 400
        assert client.get("/api/analyses/unknown").status_code == 404
        identifier = upload(client).json()["id"]
        terminal(client, identifier)
    with TestClient(create_app(settings, runner=prediction, readiness=ready)) as client:
        assert client.get(f"/api/analyses/{identifier}").status_code == 404
    with TestClient(create_app(settings, readiness=lambda _: {"ready": False, "reason": "Model unavailable"})) as client:
        assert client.get("/api/health").json()["ready"] is False
        assert upload(client).status_code == 503


def test_readiness_checks_checkpoint_and_detector_hashes(tmp_path):
    run, assets = tmp_path / "run", tmp_path / "assets"
    run.mkdir(); assets.mkdir()
    settings = Settings(run=run, assets=assets, audio_run=tmp_path / "audio")
    assert model_readiness(settings)["ready"] is False
    checkpoint, detector = b"checkpoint", b"detector"
    (run / "model.pt").write_bytes(checkpoint)
    (assets / "face_detection_yunet_2023mar.onnx").write_bytes(detector)
    (assets / "yunet_source.json").write_text(json.dumps({"sha256": hashlib.sha256(detector).hexdigest()}))
    (run / "training_summary.json").write_text(json.dumps({"checkpoint_sha256": hashlib.sha256(checkpoint).hexdigest(), "model_version": "test"}))
    assert model_readiness(settings)["ready"] is True
    audio_run = settings.audio_run
    audio_run.mkdir(parents=True, exist_ok=True)
    (audio_run / "model.joblib").write_bytes(b"audio-checkpoint")
    (audio_run / "training_summary.json").write_text(json.dumps({
        "checkpoint_sha256": hashlib.sha256(b"audio-checkpoint").hexdigest(),
        "model_version": "audio-test", "status": "trained",
        "feature_version": "logmel128-cepstra40-summary-v1"}))
    assert model_readiness(settings)["audio_ready"] is True
    (audio_run / "model.joblib").write_bytes(b"damaged")
    assert model_readiness(settings)["audio_ready"] is False
    (run / "model.pt").write_bytes(b"damaged")
    assert model_readiness(settings)["ready"] is False


def test_cleanup_cannot_target_original_directory(settings, tmp_path):
    jobs = Jobs(settings)
    try:
        with pytest.raises(ValueError, match="outside"):
            jobs.discard(tmp_path)
    finally:
        jobs.close()


def test_timeout_is_passed_to_actual_subprocess_runner(settings, tmp_path, monkeypatch):
    def timed_out(args, **options):
        assert args[1:3] == ["-m", "backend.worker"]
        assert options["timeout"] == settings.timeout_seconds
        assert options["check"] is True
        raise subprocess.TimeoutExpired(args, options["timeout"])
    monkeypatch.setattr(subprocess, "run", timed_out)
    with pytest.raises(subprocess.TimeoutExpired):
        run_prediction(tmp_path / "video.mp4", tmp_path, settings)


def test_result_history_is_bounded(tmp_path):
    settings = Settings(temporary=tmp_path / "uploads", frontend=tmp_path / "no-ui", max_history=2)
    with TestClient(create_app(settings, runner=prediction, readiness=ready)) as client:
        identifiers = []
        for _ in range(4):
            identifier = upload(client).json()["id"]
            identifiers.append(identifier)
            terminal(client, identifier)
        assert client.get(f"/api/analyses/{identifiers[0]}").status_code == 404
        assert client.get(f"/api/analyses/{identifiers[-1]}").status_code == 200
