"""Quota-free post-install verification, shared by Windows/macOS/Linux installers."""

from __future__ import annotations

import importlib.metadata
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    sys.path.insert(0, str(ROOT))
    from core.version import BUILD_DATE, VERSION

    installed = importlib.metadata.version("fofamap")
    if installed != VERSION:
        raise RuntimeError(f"Installed version {installed} does not match source {VERSION}")
    with tempfile.TemporaryDirectory(prefix="fofamap-install-check-") as temporary:
        env = {
            **os.environ,
            "PYTHONUTF8": "1",
            "PYTHONIOENCODING": "utf-8",
            "FOFAMAP_STATE_DIR": temporary,
            "FOFAMAP_DATABASE_URL": f"sqlite:///{Path(temporary) / 'jobs.db'}",
        }
        env.pop("PYTHONPATH", None)
        commands = [
            [sys.executable, str(ROOT / "fofamap.py"), "--version"],
            [
                sys.executable,
                str(ROOT / "mcp_server.py"),
                "--check",
                "--expect-version",
                VERSION,
                "--expect-build-date",
                BUILD_DATE,
                "--expect-source",
                str(ROOT),
            ],
        ]
        for command in commands:
            result = subprocess.run(command, cwd=ROOT, env=env, capture_output=True, text=True, encoding="utf-8", timeout=90, check=False)  # noqa: S603 - repository-owned checks
            if result.returncode:
                raise RuntimeError(result.stderr or result.stdout)
            if command is commands[0]:
                if VERSION not in result.stdout:
                    raise RuntimeError("Unexpected CLI version")
                print(result.stdout.strip())
            else:
                checked = json.loads(result.stdout)
                if not checked.get("ok") or checked.get("quota_spent"):
                    raise RuntimeError("MCP installation check did not pass")
                print(f"MCP: {checked['tool_count']} tools; version/source verified; no FOFA/model requests")
    print("Installation check PASS")


if __name__ == "__main__":
    main()
