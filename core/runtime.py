"""Quota-free build identity for release verification and installed-source diagnostics."""

from __future__ import annotations

import hashlib
import sys
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

from core.version import BUILD_DATE, VERSION


def code_files(root: Path) -> list[Path]:
    files = [root / name for name in ("fofamap.py", "mcp_server.py")]
    for folder in ("config", "core", "providers", "service", "utils"):
        files.extend(path for path in (root / folder).rglob("*.py") if "__pycache__" not in path.parts)
    if any(not path.is_file() for path in files) or not (root / "core/version.py").is_file():
        raise ValueError(f"Not a complete FofaMap source/install directory: {root}")
    return sorted(files)


def source_fingerprint(root: Path) -> str:
    digest = hashlib.sha256()
    for path in code_files(root):
        digest.update(path.relative_to(root).as_posix().encode() + b"\0")
        digest.update(hashlib.sha256(path.read_bytes()).digest())
    return digest.hexdigest()


ROOT = Path(__file__).resolve().parents[1]
SOURCE_FINGERPRINT = source_fingerprint(ROOT)


def runtime_info() -> dict:
    try:
        installed_version = version("fofamap")
    except PackageNotFoundError:
        installed_version = None
    return {
        "version": VERSION, "build_date": BUILD_DATE, "source_fingerprint": SOURCE_FINGERPRINT,
        "distribution_version": installed_version, "python": sys.executable,
        "source_root": str(ROOT), "server_entry": str(ROOT / "mcp_server.py"),
    }
