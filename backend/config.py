from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MAX_VIDEO_SECONDS = 60
MAX_VIDEO_PIXELS = 3840 * 2160
MAX_VIDEO_FRAMES = 3600


@dataclass(frozen=True)
class Settings:
    run: Path = ROOT / "data/runs/cpu_baseline"
    assets: Path = ROOT / "data/assets"
    temporary: Path = ROOT / "data/backend/temporary"
    frontend: Path = ROOT / "frontend/dist-live"
    max_bytes: int = 50 * 1024 * 1024
    max_active: int = 3
    max_history: int = 100
    timeout_seconds: float = 180
    origins: tuple[str, ...] = (
        "http://127.0.0.1:8000", "http://localhost:8000",
        "http://127.0.0.1:5173", "http://localhost:5173",
    )
