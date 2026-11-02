"""External update transaction. This file intentionally uses only the standard library."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import time
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

TOP_FILES = {
    "fofamap.py",
    "mcp_server.py",
    "pyproject.toml",
    "requirements.txt",
    "requirements.lock",
    "README.md",
    "README_EN.md",
    "LICENSE",
    "SECURITY.md",
    "MIGRATION.md",
    ".gitignore",
    ".env.example",
    "install.sh",
    "install.command",
    "install.bat",
    "install.ps1",
    "start.sh",
    "start.command",
    "start.bat",
}
DIRECTORIES = {"core", "providers", "service", "utils", "config", "scripts", "agent-kit", "examples", "docs", "tests", ".github"}


def owned(path: Path) -> bool:
    parts = path.parts
    if not parts or any(part in {"__pycache__", ".pytest_cache"} for part in parts):
        return False
    if parts[0] == "config":
        return path.as_posix() in {"config/__init__.py", "config/settings.example.yaml"}
    return (len(parts) == 1 and path.name in TOP_FILES) or (
        len(parts) > 1 and parts[0] in DIRECTORIES and path.suffix not in {".pyc", ".log"}
    )


def source_files(root: Path) -> dict[str, Path]:
    candidates = [root / name for name in TOP_FILES if (root / name).is_file()]
    for name in DIRECTORIES:
        directory = root / name
        if directory.is_symlink():
            raise RuntimeError("A source directory is a symlink; update stopped")
        if directory.is_dir():
            candidates.extend(path for path in directory.rglob("*") if path.is_file())
    if any(path.is_symlink() for path in candidates):
        raise RuntimeError("A source file is a symlink; update stopped")
    return {path.relative_to(root).as_posix(): path for path in candidates if owned(path.relative_to(root))}


@contextmanager
def update_lock(root: Path):
    path = root / ".fofamap-update.lock"
    with path.open("a+b") as handle:
        try:
            if os.name == "nt":
                import msvcrt

                handle.seek(0)
                handle.write(b"0")
                handle.flush()
                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl

                fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            raise RuntimeError("Another FofaMap update is already running") from exc
        try:
            yield
        finally:
            if os.name == "nt":
                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(handle, fcntl.LOCK_UN)


def run_install(root: Path, log: Path) -> None:
    python = root / (".venv/Scripts/python.exe" if os.name == "nt" else ".venv/bin/python")
    commands = [
        [
            str(python),
            "-m",
            "pip",
            "install",
            "--upgrade",
            "pip",
            "hatchling>=1.27",
            "editables>=0.5",
            "--only-binary=:all:",
            "--disable-pip-version-check",
            "--no-input",
        ],
        [
            str(python),
            "-m",
            "pip",
            "install",
            "--no-build-isolation",
            "-e",
            str(root),
            "--only-binary=:all:",
            "--disable-pip-version-check",
            "--no-input",
        ],
        [str(python), str(root / "scripts/check_installation.py")],
        [str(python), str(root / "scripts/register_command.py")],
    ]
    env = dict(os.environ, PYTHONUTF8="1", PYTHONIOENCODING="utf-8")
    for command in commands:
        with log.open("a", encoding="utf-8") as output:
            result = subprocess.run(  # noqa: S603 - fixed installer/check commands
                command, cwd=root, env=env, stdout=output, stderr=subprocess.STDOUT, check=False, timeout=900
            )
        if result.returncode:
            raise RuntimeError(f"Installation check failed (exit {result.returncode}); log: {log}")


def clear_bytecode(root: Path) -> None:
    """Prevent equal-size, same-second source changes from reusing stale code."""
    directories = [root] + [root / name for name in ("config", "core", "providers", "service", "utils", "scripts")]
    for directory in directories:
        caches = [directory / "__pycache__"] if directory == root else directory.rglob("__pycache__")
        for cache in caches:
            if cache.is_dir() and not cache.is_symlink():
                shutil.rmtree(cache)


def remove_empty_program_dirs(root: Path) -> None:
    for name in DIRECTORIES:
        directory = root / name
        if directory.is_symlink() or not directory.is_dir():
            continue
        directories = [path for path in directory.rglob("*") if path.is_dir() and not path.is_symlink()]
        for path in sorted(directories, key=lambda item: len(item.parts), reverse=True) + [directory]:
            try:
                path.rmdir()
            except OSError:
                pass  # A user file or an application resource still occupies it.


def apply_update(root: Path, source: Path, version: str, *, install=run_install) -> Path:
    root, source = root.resolve(), source.resolve()
    with update_lock(root):
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
        backup = root / ".fofamap-updates" / stamp
        backup.mkdir(parents=True)
        log = backup / "install.log"
        previous = source_files(root)
        incoming = source_files(source)
        for relative in incoming:
            destination = root / relative
            if destination.is_symlink() or any(parent.is_symlink() for parent in destination.parents):
                raise RuntimeError("An installation path is a symlink; update stopped")
        for relative, path in previous.items():
            destination = backup / "files" / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, destination)
        manifest = {"version": version, "status": "installing", "previous_files": list(previous), "incoming_files": list(incoming)}
        manifest_path = backup / "transaction.json"
        manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        try:
            # Remove obsolete code while keeping local data and configuration.
            for relative in previous.keys() - incoming.keys():
                previous[relative].unlink()
            for relative, path in incoming.items():
                destination = root / relative
                if destination.is_symlink() or any(parent.is_symlink() for parent in destination.parents if parent != root.parent):
                    raise RuntimeError("An installation path is a symlink; update stopped")
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(path, destination)
            clear_bytecode(root)
            remove_empty_program_dirs(root)
            install(root, log)
            manifest["status"] = "completed"
        except BaseException:
            for relative in incoming.keys() - previous.keys():
                destination = root / relative
                if destination.is_file() and not destination.is_symlink():
                    destination.unlink()
            for relative in previous:
                destination = root / relative
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(backup / "files" / relative, destination)
            manifest["status"] = "rolled_back"
            # Reinstall the old package metadata/entry points as well as source.
            try:
                clear_bytecode(root)
                install(root, log)
            except Exception:
                manifest["status"] = "source_restored_environment_needs_repair"
            raise
        finally:
            manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        return backup


def wait_for_exit(pid: int) -> None:
    if os.name == "nt":
        import ctypes

        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.OpenProcess.restype = ctypes.c_void_p
        handle = kernel.OpenProcess(0x00100000, False, pid)
        if handle:
            kernel.WaitForSingleObject.argtypes = [ctypes.c_void_p, ctypes.c_ulong]
            kernel.WaitForSingleObject(handle, 60000)
            kernel.CloseHandle.argtypes = [ctypes.c_void_p]
            kernel.CloseHandle(handle)
        # The native pip launcher can exit just after its Python child.
        time.sleep(1)
    else:
        for _ in range(600):
            try:
                os.kill(pid, 0)
            except ProcessLookupError:
                return
            time.sleep(0.1)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--version", required=True)
    parser.add_argument("--wait-pid", type=int)
    parser.add_argument("--pause", action="store_true")
    args = parser.parse_args()
    try:
        if args.wait_pid:
            wait_for_exit(args.wait_pid)
        print(f"Updating FofaMap to {args.version}. Keep this window open.", flush=True)
        backup = apply_update(args.root.resolve(), args.source.resolve(), args.version)
        print(f"Update complete. Run: fofamap\nBackup and log: {backup}", flush=True)
        return 0
    except Exception as exc:
        print(f"Update stopped: {exc}\nCheck .fofamap-updates in the installation folder.", flush=True)
        return 2
    finally:
        if args.pause:
            input("Press Enter to close...")


if __name__ == "__main__":
    raise SystemExit(main())
