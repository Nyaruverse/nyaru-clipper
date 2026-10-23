from __future__ import annotations

import os
from pathlib import Path


_default_data_dir = Path("/data")


def get_data_dir() -> Path:
    """Locate storage without writes; before initialization the default is /data."""
    configured = os.getenv("APP_DATA_DIR")
    return Path(configured) if configured else _default_data_dir


def ensure_data_dir() -> Path:
    """Initialize storage and remember a successful default-path fallback."""
    global _default_data_dir

    data_dir = get_data_dir()
    try:
        data_dir.mkdir(parents=True, exist_ok=True)
    except PermissionError:
        if os.getenv("APP_DATA_DIR"):
            raise
        data_dir = Path(__file__).resolve().parents[2] / "data"
        data_dir.mkdir(parents=True, exist_ok=True)
        _default_data_dir = data_dir
    return data_dir
