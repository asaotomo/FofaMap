"""Persist the installer's language without copying runtime credentials into YAML."""

from __future__ import annotations

import argparse
import os
import shutil
import sys
import tempfile
from datetime import datetime
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def save_language(language: str, *, root: Path = ROOT) -> Path:
    from config import _default_read_path, config_write_path

    if language not in {"zh", "en"}:
        raise ValueError("Language must be zh or en")
    existing = _default_read_path(dict(os.environ))
    target = existing if existing.is_file() else config_write_path(cwd=root)
    data = {}
    if target.is_file():
        try:
            data = yaml.safe_load(target.read_text(encoding="utf-8")) or {}
            if not isinstance(data, dict) or not isinstance(data.get("system", {}), dict):
                raise ValueError("Invalid settings document")
        except (ValueError, TypeError, yaml.YAMLError):
            backup = target.with_name(f"{target.name}.broken-{datetime.now():%Y%m%d%H%M%S}-{os.getpid()}")
            shutil.copy2(target, backup)
            if os.name != "nt":
                backup.chmod(0o600)
            print(("损坏的配置已备份：" if language == "zh" else "Damaged configuration backed up: ") + str(backup))
            data = {}
    data.setdefault("system", {})["language"] = language
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=".fofamap-language-", dir=target.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            yaml.safe_dump(data, stream, allow_unicode=True, sort_keys=False)
        os.replace(temporary, target)
    finally:
        Path(temporary).unlink(missing_ok=True)
    # A small non-secret record makes the selection available before Python exists.
    marker = root / ".fofamap-language"
    marker.write_text(language + "\n", encoding="ascii")
    print(("界面语言已保存：简体中文 · " if language == "zh" else "Interface language saved: English · ") + str(target))
    return target


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--language", required=True, choices=("zh", "en"))
    save_language(parser.parse_args().language)
