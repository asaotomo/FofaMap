"""Stable service state paths independent of the GUI client's spawn directory."""

from __future__ import annotations

import os
from pathlib import Path

from config import settings, user_config_path


def workspace_root() -> Path:
    if os.getenv("FOFAMAP_STATE_DIR"):
        return Path(os.environ["FOFAMAP_STATE_DIR"]).expanduser().resolve()
    if os.getenv("FOFAMAP_CONFIG"):
        config = Path(os.environ["FOFAMAP_CONFIG"]).expanduser().resolve()
        return config.parent.parent if config.parent.name == "config" else config.parent
    source = Path(__file__).resolve().parent.parent
    if (source / "pyproject.toml").is_file() and (source / "config").is_dir():
        return source
    return user_config_path().parent.resolve()


def database_url() -> str:
    if os.getenv("FOFAMAP_DATABASE_URL"):
        return os.environ["FOFAMAP_DATABASE_URL"]
    root = workspace_root()
    root.mkdir(parents=True, exist_ok=True)
    return "sqlite:///" + str(root / "fofamap.sqlite3")


def output_root() -> Path:
    path = Path(settings.system.output_dir).expanduser()
    return path.resolve() if path.is_absolute() else workspace_root() / path
