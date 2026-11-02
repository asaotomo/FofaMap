"""Shared user-distribution policy for release packaging and source updates.

Keep this module standard-library-only: it is also used before dependency upgrades.
"""

from __future__ import annotations

import posixpath
import re
from pathlib import Path

ROOT_FILES = (
    "fofamap.py",
    "mcp_server.py",
    "README.md",
    "README_EN.md",
    "LICENSE",
    "pyproject.toml",
    ".gitignore",
    ".env.example",
    "install.bat",
    "install.ps1",
    "install.sh",
    "install.command",
    "start.bat",
    "start.sh",
    "start.command",
)
INSTALL_FILES = (
    "install_language.py",
    "install_lifecycle.sh",
    "install_lifecycle.ps1",
    "check_installation.py",
    "register_command.py",
    "update_worker.py",
    "uv-checksums.txt",
    "uv-version.txt",
    "readme_demo.py",
)
USER_DOCS = (
    "AI_INSTALL.md",
    "AGENT_INTEGRATIONS.md",
    "FOFA_RULES.md",
    "INSTALL_WINDOWS.md",
    "INSTALL_WINDOWS_EN.md",
    "INSTALL_MANUAL.md",
    "INSTALL_MANUAL_EN.md",
    "MODEL_PRESETS_20261102.md",
    "RELEASE_CONTENTS.md",
)
RUNTIME_DIRS = ("config", "core", "providers", "service", "utils", "agent-kit", "examples")


def included_file(path: Path) -> bool:
    return not any(part in {"__pycache__", ".pytest_cache", ".DS_Store"} for part in path.parts) and path.suffix not in {
        ".pyc",
        ".pyo",
        ".log",
    }


def release_entries(root: Path) -> dict[str, Path]:
    """Map final relative paths to originals without shipping developer tooling."""
    entries = {name: root / name for name in ROOT_FILES}
    deployment = root / "deployment/fofamap-scheduler.service"
    if deployment.is_file():
        entries["examples/deployment/fofamap-scheduler.service"] = deployment
    entries.update({f"scripts/{name}": root / "scripts" / name for name in INSTALL_FILES})
    entries.update({f"docs/{name}": root / "docs" / name for name in USER_DOCS if (root / "docs" / name).is_file()})
    for name in ("SECURITY.md", "MIGRATION.md"):
        original = root / name if (root / name).is_file() else root / "docs" / name
        entries[f"docs/{name}"] = original
    version = re.search(r'VERSION\s*=\s*["\']([^"\']+)', (root / "core/version.py").read_text(encoding="utf-8"))
    if not version:
        raise ValueError("Cannot determine the source release version")
    for directory in (*RUNTIME_DIRS, f"docs/assets/readme/{version[1]}", "docs/data"):
        for path in (root / directory).rglob("*"):
            if not path.is_file() or not included_file(path):
                continue
            relative = path.relative_to(root)
            if relative.parts[0] == "docs" and path.name == "tests.png":
                continue
            if relative.parts[0] == "config" and not (path.suffix == ".py" or relative.as_posix() == "config/settings.example.yaml"):
                continue
            entries[relative.as_posix()] = path
    missing = [name for name, path in entries.items() if not path.is_file()]
    if missing:
        raise ValueError(f"Incomplete user distribution: {missing}")
    if any(path.is_symlink() for path in entries.values()):
        raise ValueError("A release input is a symbolic link")
    return dict(sorted(entries.items()))


def entry_bytes(root: Path, name: str, path: Path, entries: dict[str, Path]) -> bytes:
    """Relocate document links; executable code and assets are copied byte-for-byte."""
    if path.suffix != ".md":
        return path.read_bytes()
    source = path.relative_to(root).as_posix()
    destinations = {original.relative_to(root).as_posix(): destination for destination, original in entries.items()}

    def replace(match: re.Match[str]) -> str:
        target = match[1]
        if target.startswith(("https://", "http://", "mailto:", "#", "data:")):
            return match[0]
        url, sep, fragment = target.partition("#")
        resolved = posixpath.normpath(posixpath.join(posixpath.dirname(source), url))
        if resolved not in destinations:
            return match[0]
        relocated = posixpath.relpath(destinations[resolved], posixpath.dirname(name) or ".")
        return "](" + relocated + (sep + fragment if sep else "") + ")"

    text = path.read_text(encoding="utf-8")
    return re.sub(r"\]\(([^)]+)\)", replace, text).encode("utf-8")


def file_role(name: str) -> str:
    if name.startswith("scripts/"):
        return "installation/update/registration" if not name.endswith("readme_demo.py") else "documented tutorial workflows"
    if name.startswith("agent-kit/"):
        return "Skill/plugin installation and export assets"
    if name.startswith(("config/", "core/", "providers/", "service/", "utils/")) or name in {"fofamap.py", "mcp_server.py"}:
        return "application runtime or runtime asset"
    if name.startswith("examples/"):
        return "documented query/schedule inputs"
    if name.startswith(("docs/", "README")):
        return "user documentation, screenshots, or verification evidence"
    return "installation metadata, launch entry, license, or safe configuration template"


def stage_user_bundle(source: Path, destination: Path) -> dict[str, Path]:
    entries = release_entries(source)
    destination.mkdir(parents=True, exist_ok=False)
    for name, path in entries.items():
        target = destination / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(entry_bytes(source, name, path, entries))
        target.chmod(path.stat().st_mode & 0o777)
    return entries
