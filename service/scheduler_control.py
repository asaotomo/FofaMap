"""Launch the local scheduler detached from the interactive terminal."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def start_worker(root: Path) -> dict:
    root = root.resolve()
    root.mkdir(parents=True, exist_ok=True)
    log = root / "scheduler.log"
    options = (
        {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS}
        if os.name == "nt"
        else {"start_new_session": True}
    )
    with log.open("ab") as stream:
        process = subprocess.Popen(  # noqa: S603 - fixed local Python module, no shell or user command
            [sys.executable, "-m", "service.scheduler", "--interval", "30"],
            stdin=subprocess.DEVNULL,
            stdout=stream,
            stderr=stream,
            cwd=Path.cwd(),
            **options,
        )
    return {"pid": process.pid, "log": str(log)}
