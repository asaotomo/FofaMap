"""Install a user-level fofamap command and persist its PATH, without admin rights."""

from __future__ import annotations

import argparse
import ctypes
import hashlib
import os
import shlex
import shutil
import subprocess
import tempfile
from pathlib import Path

BEGIN = "# >>> FofaMap command >>>"
END = "# <<< FofaMap command <<<"
INSTALL_MARKER = "FofaMap managed installation v1"


def record_installation(root: Path, target: Path) -> None:
    """Record launcher ownership, without credentials, for offline uninstallation."""
    content = f"{INSTALL_MARKER}\n{root.resolve()}\n{hashlib.sha256(target.read_bytes()).hexdigest()}\n"
    for path in (root / ".fofamap-install", target.parent / ".fofamap-install"):
        temporary = path.with_name(path.name + f".new-{os.getpid()}")
        temporary.write_text(content, encoding="utf-8")
        os.replace(temporary, path)


def update_profile(path: Path, bin_dir: Path, *, fish: bool = False) -> None:
    content = path.read_text(encoding="utf-8") if path.exists() else ""
    block = (
        f"fish_add_path --move --path {shlex.quote(str(bin_dir))}"
        if fish
        else (
            f"_fofamap_bin={shlex.quote(str(bin_dir))}\n"
            '_fofamap_new="$_fofamap_bin"\n_fofamap_rest="$PATH"\n'
            'while :; do\n  _fofamap_entry=${_fofamap_rest%%:*}\n'
            '  if [ "$_fofamap_entry" != "$_fofamap_bin" ]; then\n'
            '    _fofamap_new="$_fofamap_new:$_fofamap_entry"\n  fi\n'
            '  case "$_fofamap_rest" in\n'
            '    *:*) _fofamap_rest=${_fofamap_rest#*:} ;;\n    *) break ;;\n  esac\ndone\n'
            'export PATH="$_fofamap_new"\n'
            "unset _fofamap_bin _fofamap_new _fofamap_rest _fofamap_entry"
        )
    )
    managed = f"{BEGIN}\n{block}\n{END}"
    if BEGIN in content:
        start = content.index(BEGIN)
        end = content.find(END, start)
        if end < 0:
            raise RuntimeError(f"Incomplete FofaMap PATH block in {path}")
        updated = content[:start] + managed + content[end + len(END) :]
    else:
        updated = content.rstrip("\n") + ("\n\n" if content else "") + managed + "\n"
    if updated != content:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(updated, encoding="utf-8")


def prepend_path(existing: str, bin_dir: str, *, windows: bool = False) -> str:
    separator = ";" if windows else os.pathsep
    normalize = (
        (lambda value: os.path.expandvars(value.strip().strip('"')).replace("/", "\\").rstrip("\\").casefold())
        if windows
        else (lambda value: value.rstrip("/"))
    )
    key = normalize(bin_dir)
    return separator.join([bin_dir] + [entry for entry in existing.split(separator) if entry and normalize(entry) != key])


def register_windows_path(bin_dir: Path) -> None:
    import winreg

    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, "Environment") as key:
        try:
            existing, kind = winreg.QueryValueEx(key, "Path")
        except FileNotFoundError:
            existing, kind = "", winreg.REG_EXPAND_SZ
        winreg.SetValueEx(key, "Path", 0, kind, prepend_path(existing, str(bin_dir), windows=True))
    # Notify Explorer/Windows Terminal so newly opened terminals inherit PATH.
    result = ctypes.c_size_t()
    ctypes.windll.user32.SendMessageTimeoutW(0xFFFF, 0x001A, 0, "Environment", 0x0002, 3000, ctypes.byref(result))


def register(root: Path, *, home: Path | None = None, windows: bool | None = None) -> Path:
    windows = os.name == "nt" if windows is None else windows
    home = Path.home() if home is None else home
    bin_dir = (Path(os.environ.get("LOCALAPPDATA") or home / "AppData/Local") / "FofaMap/bin") if windows else home / ".local/bin"
    source = root / (".venv/Scripts/fofamap.exe" if windows else ".venv/bin/fofamap")
    if not source.is_file():
        raise RuntimeError(f"pip did not create the CLI entry point: {source}")
    bin_dir.mkdir(parents=True, exist_ok=True)
    target = bin_dir / source.name
    temporary = bin_dir / (source.name + f".new-{os.getpid()}")
    if windows:
        shutil.copy2(source, temporary)
    else:
        temporary.symlink_to(source.resolve())
    os.replace(temporary, target)
    # Use an unrelated directory: registration must work outside the source tree.
    with tempfile.TemporaryDirectory(prefix="fofamap-command-check-") as cwd:
        checked = subprocess.run(  # noqa: S603 - pip-generated application launcher
            [str(target), "--version"], cwd=cwd, capture_output=True, text=True, encoding="utf-8", timeout=30
        )
        if checked.returncode or "FofaMap, version" not in checked.stdout:
            raise RuntimeError("The registered CLI did not pass its version check")
    if windows:
        register_windows_path(bin_dir)
    else:
        profiles = [home / name for name in (".profile", ".bashrc", ".zshrc", ".zprofile")]
        # Do not create .bash_profile: that would suppress an existing .profile.
        profiles += [home / name for name in (".bash_profile", ".bash_login") if (home / name).exists()]
        for profile in profiles:
            update_profile(profile, bin_dir)
        if Path(os.environ.get("SHELL", "")).name == "fish":
            update_profile(home / ".config/fish/config.fish", bin_dir, fish=True)
    os.environ["PATH"] = prepend_path(os.environ.get("PATH", ""), str(bin_dir), windows=windows)
    record_installation(root, target)
    print(f"Command registered and checked: {target}")
    print("Open a new terminal, then run: fofamap")
    return target


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    register(parser.parse_args().root.resolve())
