"""Local-only FastAPI application. Run with one Uvicorn worker."""
from contextlib import asynccontextmanager
import json

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.datastructures import UploadFile
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.formparsers import MultiPartException
from starlette.middleware.trustedhost import TrustedHostMiddleware

from ml.common import file_sha256
from .config import Settings
from .jobs import Jobs, run_prediction

LIMIT_MESSAGE = "This upload exceeds the 50 MB prototype limit."


def model_readiness(settings):
    """Verify local training artifacts without loading PyTorch in the web server."""
    try:
        model = settings.run / "model.pt"
        summary = json.loads((settings.run / "training_summary.json").read_text(encoding="utf-8"))
        detector = settings.assets / "face_detection_yunet_2023mar.onnx"
        provenance = json.loads((settings.assets / "yunet_source.json").read_text(encoding="utf-8"))
        if file_sha256(model) != summary["checkpoint_sha256"]:
            raise ValueError("Checkpoint checksum mismatch")
        if file_sha256(detector) != provenance["sha256"]:
            raise ValueError("Detector checksum mismatch")
        return {"ready": True, "model_version": summary["model_version"]}
    except (OSError, ValueError, KeyError):
        return {"ready": False, "reason": "The trained checkpoint or face detector is missing or damaged. Restore the local baseline files before analyzing videos."}


class UploadGuard:
    def __init__(self, app, settings):
        self.app, self.settings = app, settings

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or scope["method"] != "POST":
            return await self.app(scope, receive, send)
        headers = dict(scope["headers"])
        origin = headers.get(b"origin", b"").decode("latin-1")
        if origin and origin not in self.settings.origins:
            return await JSONResponse({"detail": "This browser origin is not allowed."}, status_code=403)(scope, receive, send)
        limit = self.settings.max_bytes + 1024 * 1024  # bounded multipart overhead
        try:
            length = int(headers.get(b"content-length", b"0"))
        except ValueError:
            return await JSONResponse({"detail": "Invalid upload length."}, status_code=400)(scope, receive, send)
        if length > limit:
            return await JSONResponse({"detail": LIMIT_MESSAGE}, status_code=413)(scope, receive, send)
        received = 0

        async def bounded_receive():
            nonlocal received
            message = await receive()
            received += len(message.get("body", b""))
            if received > limit:
                # Starlette closes multipart spool files when this exception occurs.
                raise MultiPartException(LIMIT_MESSAGE)
            return message

        await self.app(scope, bounded_receive, send)


def create_app(settings=None, *, runner=run_prediction, readiness=model_readiness):
    settings = settings or Settings()

    @asynccontextmanager
    async def lifespan(app):
        app.state.model = readiness(settings)
        app.state.jobs = Jobs(settings, runner)
        yield
        app.state.jobs.close()

    app = FastAPI(title="Deep Forensics local visual baseline", version="0.2.0", lifespan=lifespan)
    app.add_middleware(UploadGuard, settings=settings)
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=["127.0.0.1", "localhost", "testserver"])
    app.add_middleware(CORSMiddleware, allow_origins=list(settings.origins),
                       allow_methods=["GET", "POST"], allow_headers=["Content-Type"])

    @app.get("/api/health")
    def health(request: Request):
        state = request.app.state.model
        return {"service": "deep-forensics", "mode": "live", "scope": "visual_only",
                "status": "ready" if state["ready"] else "unavailable", **state,
                "max_upload_bytes": settings.max_bytes, "max_video_seconds": 60,
                "retention": "Uploaded copies are deleted after analysis. Results are kept in memory."}

    @app.post("/api/analyses", status_code=202)
    async def upload(request: Request):
        if not request.app.state.model["ready"]:
            raise HTTPException(503, request.app.state.model["reason"])
        jobs = request.app.state.jobs
        if not jobs.reserve():
            raise HTTPException(429, "The CPU queue is full. Wait for an analysis to finish, then try again.")
        directory = None
        submitted = False
        try:
            async with request.form(max_files=1, max_fields=0, max_part_size=1024) as form:
                file = form.get("file")
                if len(form) != 1 or not isinstance(file, UploadFile):
                    raise HTTPException(422, "Upload one MP4 using the file field.")
                name = (file.filename or "").replace("\\", "/").rsplit("/", 1)[-1]
                name = "".join(c for c in name if c.isprintable())[-180:]
                if not name.lower().endswith(".mp4") or file.content_type not in {None, "", "video/mp4", "application/mp4", "application/octet-stream"}:
                    raise HTTPException(415, "Choose an MP4 video.")
                if file.size is not None and file.size > settings.max_bytes:
                    raise HTTPException(413, LIMIT_MESSAGE)
                identifier, directory = jobs.new_upload()
                size, header = 0, b""
                with (directory / "video.mp4").open("wb") as target:
                    while chunk := await file.read(1024 * 1024):
                        size += len(chunk)
                        if size > settings.max_bytes:
                            raise HTTPException(413, LIMIT_MESSAGE)
                        if not header:
                            header = chunk[:12]
                        target.write(chunk)
                if not size:
                    raise HTTPException(400, "This video is empty. Choose another MP4.")
                if len(header) < 12 or header[4:8] != b"ftyp":
                    raise HTTPException(415, "The file contents are not a supported MP4. Renaming a file is not enough.")
            jobs.submit(identifier, directory, {"kind": "upload", "name": name, "size": size, "duration": None})
            submitted = True
            return {"id": identifier, "status": "queued"}
        except StarletteHTTPException as error:
            if error.detail == LIMIT_MESSAGE:
                raise HTTPException(413, LIMIT_MESSAGE) from error
            raise
        finally:
            if not submitted:
                try:
                    if directory is not None:
                        jobs.discard(directory)
                finally:
                    jobs.slots.release()

    @app.get("/api/analyses/{identifier}")
    def analysis(identifier: str, request: Request):
        result = request.app.state.jobs.get(identifier)
        if result is None:
            raise HTTPException(404, "This analysis is unavailable. The server may have restarted; upload the video again.")
        return result

    if (settings.frontend / "index.html").is_file():
        app.mount("/", StaticFiles(directory=settings.frontend, html=True), name="frontend")
    return app


app = create_app()
