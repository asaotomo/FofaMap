"""UTF-8 output for Windows pipes, including JSON and MCP diagnostics."""
from __future__ import annotations

import sys
from typing import Any


def configure_utf8_stream(stream: Any) -> None:
    if hasattr(stream, "reconfigure"):
        stream.reconfigure(encoding="utf-8", errors="backslashreplace")


def configure_windows_stdio() -> None:
    if sys.platform == "win32":
        configure_utf8_stream(sys.stdout)
        configure_utf8_stream(sys.stderr)
