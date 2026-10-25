"""Environment-backed settings for Campus Compass."""

from __future__ import annotations

import os
from pathlib import Path

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:  # pragma: no cover - dotenv is optional for direct runs
    pass


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _path_setting(name: str, default: str) -> Path:
    path = Path(os.getenv(name, default)).expanduser()
    return path if path.is_absolute() else PROJECT_ROOT / path


DATABASE_PATH = _path_setting("DATABASE_PATH", "data/campus_compass.sqlite3")
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "").strip().rstrip("/")
LLM_API_KEY = os.getenv("LLM_API_KEY", "").strip()
LLM_MODEL = os.getenv("LLM_MODEL", "").strip()
MIN_RETRIEVAL_SCORE = float(os.getenv("MIN_RETRIEVAL_SCORE", "0.12"))
MIN_QUERY_COVERAGE = float(os.getenv("MIN_QUERY_COVERAGE", "0.35"))
TOP_K = max(1, min(int(os.getenv("TOP_K", "4")), 8))
MAX_UPLOAD_MB = max(1, min(int(os.getenv("MAX_UPLOAD_MB", "10")), 25))
MAX_UPLOAD_BYTES = MAX_UPLOAD_MB * 1024 * 1024
CHUNK_SIZE = 900
CHUNK_OVERLAP = 120

