"""A small in-memory queue, with one CPU prediction running at a time."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from datetime import datetime, timezone
import json
import logging
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import uuid

from .config import ROOT

logger = logging.getLogger(__name__)


def run_prediction(video, directory, settings):
    output = directory / "prediction.json"
    subprocess.run(
        [sys.executable, "-m", "backend.worker", "--video", str(video),
         "--output", str(output), "--run", str(settings.run), "--assets", str(settings.assets),
         "--audio-run", str(settings.audio_run)],
        cwd=ROOT, check=True, timeout=settings.timeout_seconds,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    result = json.loads(output.read_text(encoding="utf-8"))
    if result.get("status") not in {"complete", "insufficient_evidence", "failed"}:
        raise ValueError("The prediction worker returned an invalid result.")
    return result


class Jobs:
    def __init__(self, settings, runner=run_prediction):
        self.settings, self.runner = settings, runner
        settings.temporary.mkdir(parents=True, exist_ok=True)
        # Each server owns only its directory. Never clear another process's files.
        self.directory = Path(tempfile.mkdtemp(prefix="server-", dir=settings.temporary)).resolve()
        self.pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="visual-analysis")
        self.slots = threading.BoundedSemaphore(settings.max_active)
        self.lock = threading.Lock()
        self.records = {}

    def reserve(self):
        return self.slots.acquire(blocking=False)

    def new_upload(self):
        identifier = "DF-" + uuid.uuid4().hex
        directory = self.directory / identifier
        directory.mkdir()
        return identifier, directory

    def discard(self, directory):
        # Verify the exact absolute target before recursive cleanup.
        directory = directory.resolve()
        if directory.parent != self.directory or not directory.name.startswith("DF-"):
            raise ValueError("Refusing cleanup outside this server's upload directory.")
        shutil.rmtree(directory)

    def submit(self, identifier, directory, source):
        with self.lock:
            self.records[identifier] = {
                "id": identifier, "mode": "live", "scope": "visual_only",
                "status": "queued", "stage": "queued", "source": source,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "audio": {"status": "not_implemented", "score": None},
                "evidence": [], "sha256": None, "report_available": False,
                "upload_deleted": False,
            }
        self.pool.submit(self._analyze, identifier, directory)

    def get(self, identifier):
        with self.lock:
            return deepcopy(self.records.get(identifier))

    def _analyze(self, identifier, directory):
        started = time.monotonic()
        with self.lock:
            self.records[identifier].update(status="running", stage="analyzing")
        try:
            prediction = self.runner(directory / "video.mp4", directory, self.settings)
        except subprocess.TimeoutExpired:
            prediction = {"status": "failed", "error": "Analysis exceeded the 3-minute CPU limit. Try a shorter clip at 1080p."}
        except Exception:
            logger.exception("Prediction failed for %s", identifier)
            prediction = {"status": "failed", "error": "The model could not analyze this video. Check the backend window and try another MP4."}
        finally:
            # Cleanup finishes before the terminal result becomes visible to the browser.
            deleted = False
            try:
                self.discard(directory)
                deleted = True
            except OSError:
                logger.exception("Upload cleanup failed for %s", identifier)
        with self.lock:
            record = self.records[identifier]
            record["source"].update(prediction.pop("source_metadata", {}))
            record.update(prediction, stage="complete", upload_deleted=deleted,
                          elapsed_seconds=round(time.monotonic() - started, 2))
            if not deleted:
                record["cleanup_warning"] = "The uploaded copy could not be deleted. Close the app and check data/backend/temporary."
            terminal = [key for key, value in self.records.items() if value["status"] not in {"queued", "running"}]
            for key in terminal[:-self.settings.max_history]:
                del self.records[key]
        self.slots.release()

    def close(self):
        self.pool.shutdown(wait=True)
        # There should be no uploads left. rmdir avoids recursive deletion here.
        try:
            self.directory.rmdir()
        except OSError:
            logger.warning("Temporary files remain under %s", self.directory)
