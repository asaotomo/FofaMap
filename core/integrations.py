"""Safe, reversible MCP and Agent Skill installers for supported hosts."""

from __future__ import annotations

import base64
import hashlib
import importlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import zipfile
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import quote

import yaml

try:
    import tomllib
except ImportError:  # Python 3.10
    import tomli as tomllib

from core.version import VERSION


class IntegrationError(ValueError):
    """Raised when an integration cannot be changed without risking user data."""


def _toml_value(value: Any) -> str:
    if isinstance(value, dict):
        return "{ " + ", ".join(f"{json.dumps(key, ensure_ascii=False)} = {_toml_value(item)}" for key, item in value.items()) + " }"
    if isinstance(value, list):
        return "[" + ", ".join(_toml_value(item) for item in value) + "]"
    if isinstance(value, (str, int, float, bool)):
        return json.dumps(value, ensure_ascii=False, allow_nan=False)
    raise IntegrationError(f"Unsupported TOML value: {type(value).__name__}; configuration was not overwritten")


@dataclass(frozen=True)
class HostSupport:
    id: str
    name: str
    mcp: str
    skills: str
    notes: str = ""
    aliases: tuple[str, ...] = ()


@dataclass
class IntegrationResult:
    target: str
    scope: str
    action: str
    dry_run: bool
    mcp_support: str
    skill_support: str
    changes: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    deeplink: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


HOSTS: tuple[HostSupport, ...] = (
    HostSupport("cursor", "Cursor", "native", "native", aliases=("cursor-agent",)),
    HostSupport("codex", "OpenAI Codex", "native", "native", aliases=("openai-codex",)),
    HostSupport("claude", "Claude Code", "native", "native", aliases=("claude-code",)),
    HostSupport("opencode", "OpenCode", "native", "native", aliases=("open-code",)),
    HostSupport(
        "deepseek-harness",
        "DeepSeek Harness",
        "tools-only",
        "native",
        "DeepSeek Harness 的 MCP 桥接只暴露 Tools，不会消费 MCP Resources 和 Prompts。",
        ("deepseek", "dsh"),
    ),
    HostSupport(
        "lmstudio",
        "LM Studio",
        "native",
        "compatibility",
        "LM Studio 原生支持 MCP，但没有官方智能体 Skill 加载器；Skill 已放到兼容目录，供社区加载器使用。",
        ("lm-studio",),
    ),
    HostSupport(
        "openclaw",
        "OpenClaw",
        "compatible-bundle",
        "compatible-bundle",
        "OpenClaw 会原生加载捆绑的 Codex 清单、MCP 服务和 Skill。",
        ("open-claw",),
    ),
    HostSupport("hermes", "Hermes Agent", "native", "native", aliases=("hermes-agent",)),
    HostSupport(
        "grok",
        "Grok Build",
        "claude-compatible-plugin",
        "native-plugin",
        "Grok Build 会加载 Claude 兼容的 MCP/插件包以及原生 Grok Skill。",
        ("gork", "grok-build"),
    ),
)

_BY_NAME = {name: host for host in HOSTS for name in (host.id, *host.aliases)}
_BEGIN = "# >>> fofamap managed integration >>>"
_END = "# <<< fofamap managed integration <<<"
_MARKER = ".fofamap-managed.json"


def supported_hosts() -> list[dict[str, Any]]:
    """Return stable, machine-readable host capability metadata."""
    return [asdict(host) for host in HOSTS]


def normalize_host(value: str) -> HostSupport:
    key = value.strip().lower()
    try:
        return _BY_NAME[key]
    except KeyError as exc:
        raise IntegrationError(f"不支持的智能体：{value}。可用值：{', '.join(host.id for host in HOSTS)}") from exc


def _asset_root() -> Path:
    root = Path(__file__).resolve().parent.parent / "agent-kit"
    if not root.is_dir():
        raise IntegrationError(f"安装包缺少 agent-kit 分发资产：{root}")
    return root


def resolve_mcp_stdio(server_command: str | None = None) -> dict[str, Any]:
    """Build a GUI-safe stdio launch spec without relying on the host's PATH."""
    if server_command is not None:
        command = server_command.strip()
        if not command or "\x00" in command:
            raise IntegrationError("MCP 服务命令不能为空或包含 NUL")
        return {"command": command, "args": []}

    # Do not resolve symlinks here: a virtualenv's python commonly points at the
    # base interpreter, and resolving it would silently discard the venv packages.
    python = str(Path(os.path.abspath(os.path.expanduser(sys.executable))))
    server = str((Path(__file__).resolve().parent.parent / "mcp_server.py").resolve())
    if not Path(python).is_file():
        raise IntegrationError(f"无法定位当前 Python 解释器：{python}")
    if not Path(server).is_file():
        raise IntegrationError(f"安装包缺少 MCP 服务入口：{server}")
    try:
        importlib.import_module("mcp.server.mcpserver")
    except ImportError as exc:
        raise IntegrationError(
            f"当前 Python 环境缺少 FofaMap {VERSION} 所需的 mcp>=2,<3。"
            "请先在虚拟环境中安装 Wheel 或执行 `python -m pip install .`，再重新运行 integrate。"
        ) from exc
    return {"command": python, "args": ["-u", server]}


def _backup(path: Path, dry_run: bool, changes: list[str]) -> None:
    if not path.exists():
        return
    backup = path.with_name(f"{path.name}.fofamap.bak")
    if backup.exists():
        if backup.read_bytes() == path.read_bytes():
            return
        backup = path.with_name(f"{path.name}.fofamap.{time.time_ns()}.bak")
    changes.append(f"backup {path} -> {backup}")
    if not dry_run:
        backup.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, backup)


def _write_text(path: Path, content: str, *, dry_run: bool, changes: list[str]) -> None:
    old = path.read_text(encoding="utf-8") if path.exists() else None
    if old == content:
        changes.append(f"unchanged {path}")
        return
    _backup(path, dry_run, changes)
    changes.append(f"write {path}")
    if not dry_run:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")


def _write_json(path: Path, data: dict[str, Any], *, dry_run: bool, changes: list[str]) -> None:
    _write_text(path, json.dumps(data, ensure_ascii=False, indent=2) + "\n", dry_run=dry_run, changes=changes)


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise IntegrationError(f"无法安全解析 JSON 配置 {path}：{exc}") from exc
    if not isinstance(value, dict):
        raise IntegrationError(f"配置根节点必须是 JSON 对象：{path}")
    return value


def _set_nested(data: dict[str, Any], keys: tuple[str, ...], value: Any) -> None:
    current = data
    for key in keys[:-1]:
        child = current.setdefault(key, {})
        if not isinstance(child, dict):
            raise IntegrationError(f"配置键 {'.'.join(keys[:-1])} 已存在且不是对象")
        current = child
    current[keys[-1]] = value


def _remove_nested(data: dict[str, Any], keys: tuple[str, ...]) -> bool:
    current: Any = data
    parents: list[tuple[dict[str, Any], str]] = []
    for key in keys[:-1]:
        if not isinstance(current, dict) or not isinstance(current.get(key), dict):
            return False
        parents.append((current, key))
        current = current[key]
    if not isinstance(current, dict) or keys[-1] not in current:
        return False
    del current[keys[-1]]
    for parent, key in reversed(parents):
        if parent[key] == {}:
            del parent[key]
    return True


def _json_config(
    path: Path,
    keys: tuple[str, ...],
    entry: dict[str, Any],
    *,
    uninstall: bool,
    dry_run: bool,
    changes: list[str],
) -> None:
    data = _read_json(path)
    if uninstall:
        changed = _remove_nested(data, keys)
    else:
        prior = data
        for key in keys:
            prior = prior.get(key, {}) if isinstance(prior, dict) else {}
        if isinstance(prior, dict):
            entry = {**prior, **entry, **({"cwd": prior["cwd"]} if prior.get("cwd") else {})}
        _set_nested(data, keys, entry)
        changed = True
    if not changed:
        changes.append(f"absent {path}:{'.'.join(keys)}")
        return
    _write_json(path, data, dry_run=dry_run, changes=changes)


def _replace_managed_block(content: str, block: str | None) -> str:
    start = content.find(_BEGIN)
    end = content.find(_END)
    if (start < 0) != (end < 0) or (start >= 0 and end < start):
        raise IntegrationError("发现不完整的 FofaMap 托管集成标记，请先手动修复")
    if start >= 0:
        end += len(_END)
        content = (content[:start].rstrip() + "\n" + content[end:].lstrip("\n")).strip()
    if block is not None:
        managed = f"{_BEGIN}\n{block.rstrip()}\n{_END}"
        content = f"{content.rstrip()}\n\n{managed}" if content.strip() else managed
    return content.rstrip() + "\n" if content.strip() else ""


def _managed_config(path: Path, block: str, *, uninstall: bool, dry_run: bool, changes: list[str], remove_empty: bool = False) -> None:
    old = path.read_text(encoding="utf-8") if path.exists() else ""
    new = _replace_managed_block(old, None if uninstall else block)
    if path.suffix == ".toml":
        try:
            tomllib.loads(new)
        except ValueError as exc:
            raise IntegrationError("Generated TOML conflicts with existing user configuration; nothing was overwritten") from exc
    if uninstall and not new and remove_empty:
        if not path.exists():
            changes.append(f"absent {path}")
            return
        _backup(path, dry_run, changes)
        changes.append(f"remove {path}")
        if not dry_run:
            path.unlink()
        return
    _write_text(path, new, dry_run=dry_run, changes=changes)


def _copy_managed(source: Path, destination: Path, *, kind: str, force: bool, dry_run: bool, changes: list[str]) -> None:
    if destination.exists():
        marker = destination / _MARKER
        if not marker.exists() and not force:
            raise IntegrationError(f"拒绝覆盖非 FofaMap 管理的 {kind}：{destination}；确认后可使用 --force")
        if not marker.exists() and force:
            backup = destination.with_name(f"{destination.name}.fofamap.bak")
            if backup.exists():
                raise IntegrationError(f"备份目录已存在，无法安全覆盖：{backup}")
            changes.append(f"backup {destination} -> {backup}")
            if not dry_run:
                shutil.move(str(destination), str(backup))
        else:
            changes.append(f"replace {destination}")
            if not dry_run:
                shutil.rmtree(destination)
    else:
        changes.append(f"install {destination}")
    if not dry_run:
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(source, destination)
        (destination / _MARKER).write_text(
            json.dumps({"managed_by": "fofamap", "kind": kind, "version": VERSION}, indent=2) + "\n", encoding="utf-8"
        )


def _preflight_managed(destination: Path, *, kind: str, force: bool, uninstall: bool) -> None:
    """Reject ownership conflicts before any companion config is mutated."""
    if not destination.exists():
        return
    if (destination / _MARKER).exists():
        return
    verb = "删除" if uninstall else "覆盖"
    if uninstall or not force:
        raise IntegrationError(f"拒绝{verb}非 FofaMap 管理的 {kind}：{destination}" + ("；确认后可使用 --force" if not uninstall else ""))
    backup = destination.with_name(f"{destination.name}.fofamap.bak")
    if backup.exists():
        raise IntegrationError(f"备份目录已存在，无法安全覆盖：{backup}")


def _remove_managed(destination: Path, *, kind: str, dry_run: bool, changes: list[str]) -> None:
    if not destination.exists():
        changes.append(f"absent {destination}")
        return
    marker = destination / _MARKER
    if not marker.exists():
        raise IntegrationError(f"拒绝删除非 FofaMap 管理的 {kind}：{destination}")
    changes.append(f"remove {destination}")
    if not dry_run:
        shutil.rmtree(destination)


def _install_skill(destination: Path, *, uninstall: bool, force: bool, dry_run: bool, changes: list[str]) -> None:
    if uninstall:
        _remove_managed(destination, kind="skill", dry_run=dry_run, changes=changes)
    else:
        _copy_managed(_asset_root() / "skills" / "fofamap", destination, kind="skill", force=force, dry_run=dry_run, changes=changes)


def _install_plugin(
    destination: Path,
    *,
    stdio: dict[str, Any],
    uninstall: bool,
    force: bool,
    dry_run: bool,
    changes: list[str],
) -> None:
    if uninstall:
        _remove_managed(destination, kind="plugin", dry_run=dry_run, changes=changes)
        return
    _copy_managed(_asset_root() / "plugins" / "fofamap", destination, kind="plugin", force=force, dry_run=dry_run, changes=changes)
    if dry_run:
        return
    _set_plugin_launch(destination, stdio)


def _set_plugin_launch(destination: Path, stdio: dict[str, Any]) -> None:
    """Keep every plugin manifest on the same executable and argument list."""
    for relative in (".mcp.json", "openclaw.plugin.json"):
        path = destination / relative
        if not path.exists():
            continue
        data = _read_json(path)
        try:
            entry = data["mcpServers"]["fofamap"]
        except (KeyError, TypeError) as exc:
            raise IntegrationError(f"插件清单缺少 mcpServers.fofamap：{path}") from exc
        if not isinstance(entry, dict):
            raise IntegrationError(f"插件清单 mcpServers.fofamap 必须是对象：{path}")
        entry["command"] = stdio["command"]
        entry["args"] = list(stdio["args"])
        if stdio.get("cwd"):
            entry.setdefault("cwd", stdio["cwd"])
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _install_openclaw_plugin(
    destination: Path,
    *,
    home: Path,
    stdio: dict[str, Any],
    uninstall: bool,
    force: bool,
    dry_run: bool,
    changes: list[str],
) -> bool:
    """Use OpenClaw's tracked lifecycle when its CLI is available."""
    executable = shutil.which("openclaw")
    if executable is None:
        return False
    _preflight_managed(destination, kind="plugin", force=force, uninstall=uninstall)
    state_dir = home / ".openclaw"
    env = os.environ.copy()
    env["OPENCLAW_STATE_DIR"] = str(state_dir)
    env["OPENCLAW_CONFIG_PATH"] = str(state_dir / "openclaw.json")
    if uninstall:
        if not destination.exists():
            changes.append(f"absent {destination}")
            return True
        command = [executable, "plugins", "uninstall", "fofamap", "--force"]
        changes.append("run openclaw plugins uninstall fofamap --force")
    elif destination.exists():
        return False
    else:
        command = [executable, "plugins", "install", str(_asset_root() / "plugins" / "fofamap")]
        changes.append("run openclaw plugins install <fofamap-bundle>")
    if dry_run:
        return True
    completed = subprocess.run(command, capture_output=True, text=True, check=False, env=env)  # noqa: S603
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout).strip()
        raise IntegrationError(f"OpenClaw 插件生命周期命令失败：{detail}")
    if not uninstall:
        marker = destination / _MARKER
        marker.write_text(
            json.dumps({"managed_by": "fofamap", "kind": "plugin", "version": VERSION}, indent=2) + "\n",
            encoding="utf-8",
        )
        _set_plugin_launch(destination, stdio)
    return True


def _paths(host: str, scope: str, root: Path, home: Path) -> tuple[Path | None, Path | None]:
    project = scope == "project"
    mapping: dict[str, tuple[Path | None, Path | None]] = {
        "cursor": (
            root / ".cursor" / "mcp.json" if project else home / ".cursor" / "mcp.json",
            root / ".cursor" / "skills" / "fofamap" if project else home / ".cursor" / "skills" / "fofamap",
        ),
        "codex": (
            root / ".codex" / "config.toml" if project else home / ".codex" / "config.toml",
            root / ".agents" / "skills" / "fofamap" if project else home / ".agents" / "skills" / "fofamap",
        ),
        "claude": (
            root / ".mcp.json" if project else home / ".claude.json",
            root / ".claude" / "skills" / "fofamap" if project else home / ".claude" / "skills" / "fofamap",
        ),
        "opencode": (
            root / "opencode.json" if project else home / ".config" / "opencode" / "opencode.json",
            root / ".opencode" / "skills" / "fofamap" if project else home / ".config" / "opencode" / "skills" / "fofamap",
        ),
        "deepseek-harness": (
            root / ".dsh" / "fofamap.cordis.yml" if project else home / ".dsh" / "cordis.patch.yml",
            root / ".dsh" / "skills" / "fofamap" if project else home / ".dsh" / "skills" / "fofamap",
        ),
        "lmstudio": (home / ".lmstudio" / "mcp.json", home / ".lmstudio" / "skills" / "fofamap"),
        "openclaw": (
            root / ".openclaw" / "extensions" / "fofamap" if project else home / ".openclaw" / "extensions" / "fofamap",
            None,
        ),
        "hermes": (
            home / ".hermes" / "config.yaml",
            root / ".agents" / "skills" / "fofamap" if project else home / ".hermes" / "skills" / "fofamap",
        ),
        "grok": (
            root / ".grok" / "plugins" / "fofamap" if project else home / ".grok" / "plugins" / "fofamap",
            None,
        ),
    }
    return mapping[host]


def _skill_hashes(root: Path) -> dict[str, str]:
    return {
        path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(root.rglob("*"))
        if path.is_file() and not path.is_symlink() and not any(part.startswith(".") for part in path.relative_to(root).parts)
    }


def integration_status(target: str, *, scope: str = "user", root: Path | None = None, home: Path | None = None) -> dict[str, Any]:
    """Read-only byte-level check of installed Skill content and managed release marker."""
    host = normalize_host(target)
    if scope not in {"user", "project"}:
        raise IntegrationError("scope 必须是 user 或 project")
    config_path, destination = _paths(host.id, scope, (root or Path.cwd()).resolve(), (home or Path.home()).resolve())
    marker_root = destination
    if destination is None:
        assert config_path is not None
        marker_root = config_path
        destination = config_path / "skills/fofamap"
    expected = _skill_hashes(_asset_root() / "skills/fofamap")
    actual = _skill_hashes(destination) if destination.is_dir() else {}
    marker = marker_root / _MARKER
    installed_version = None
    try:
        managed = json.loads(marker.read_text(encoding="utf-8"))
        owned = managed.get("managed_by") == "fofamap"
        installed_version = managed.get("version")
    except (OSError, ValueError, AttributeError):
        owned = False
    missing = sorted(expected.keys() - actual.keys())
    extra = sorted(actual.keys() - expected.keys())
    changed = sorted(name for name in expected.keys() & actual.keys() if expected[name] != actual[name])
    status = ("missing" if not destination.exists() else "unmanaged" if not owned
              else "stale" if missing or extra or changed or installed_version != VERSION else "current")
    return {"target": host.id, "scope": scope, "status": status, "ok": status == "current", "skill_path": str(destination),
            "expected_version": VERSION, "installed_version": installed_version, "missing": missing, "extra": extra, "changed": changed}


def integrate_host(
    target: str,
    *,
    scope: str = "user",
    root: Path | None = None,
    home: Path | None = None,
    server_command: str | None = None,
    uninstall: bool = False,
    dry_run: bool = False,
    force: bool = False,
) -> IntegrationResult:
    """Install or remove one host integration without copying credentials."""
    host = normalize_host(target)
    if scope not in {"user", "project"}:
        raise IntegrationError("scope 必须是 user 或 project")
    root = (root or Path.cwd()).resolve()
    home = (home or Path.home()).expanduser().resolve()
    action = "uninstall" if uninstall else "install"
    result = IntegrationResult(host.id, scope, action, dry_run, host.mcp, host.skills)
    if host.notes:
        result.notes.append(host.notes)
    config_path, skill_path = _paths(host.id, scope, root, home)
    stdio = resolve_mcp_stdio(server_command) if not uninstall else {"command": "", "args": [], "cwd": str(root)}
    if not uninstall:
        stdio["cwd"] = str(root)
        result.notes.append("MCP 启动配置已固定为当前 Python 与服务入口的绝对路径，不依赖 GUI 应用的 PATH。")

    if host.id in {"openclaw", "grok"}:
        assert config_path is not None
        handled = False
        if host.id == "openclaw" and scope == "user":
            handled = _install_openclaw_plugin(
                config_path,
                home=home,
                stdio=stdio,
                uninstall=uninstall,
                force=force,
                dry_run=dry_run,
                changes=result.changes,
            )
        if not handled:
            _install_plugin(
                config_path,
                stdio=stdio,
                uninstall=uninstall,
                force=force,
                dry_run=dry_run,
                changes=result.changes,
            )
        if host.id == "openclaw":
            result.notes.append("安装完成后请重启 OpenClaw，或刷新其插件列表。")
        else:
            result.notes.append("Grok Build 会自动发现已安装的 Claude 兼容插件包。")
        return result

    assert config_path is not None and skill_path is not None
    _preflight_managed(skill_path, kind="skill", force=force, uninstall=uninstall)
    if host.id in {"cursor", "claude", "lmstudio"}:
        _json_config(
            config_path,
            ("mcpServers", "fofamap"),
            stdio,
            uninstall=uninstall,
            dry_run=dry_run,
            changes=result.changes,
        )
    elif host.id == "opencode":
        _json_config(
            config_path,
            ("mcp", "fofamap"),
            {"type": "local", "command": [stdio["command"], *stdio["args"]], "enabled": True},
            uninstall=uninstall,
            dry_run=dry_run,
            changes=result.changes,
        )
    elif host.id == "codex":
        prior = {}
        if config_path.exists() and not uninstall:
            try:
                parsed = tomllib.loads(config_path.read_text(encoding="utf-8"))
                prior = parsed.get("mcp_servers", {}).get("fofamap", {})
            except (ValueError, TypeError) as exc:
                raise IntegrationError("Existing Codex TOML cannot be safely parsed; configuration was not overwritten") from exc
        entry = {**prior, **stdio, **({"cwd": prior["cwd"]} if prior.get("cwd") else {})}
        block = "[mcp_servers.fofamap]\n" + "\n".join(
            f"{key} = {_toml_value(value)}" for key, value in entry.items()
        )
        _managed_config(config_path, block, uninstall=uninstall, dry_run=dry_run, changes=result.changes)
    elif host.id == "deepseek-harness":
        prior = {}
        if config_path.exists():
            old = config_path.read_text(encoding="utf-8")
            if _BEGIN in old and _END in old:
                old = old.split(_BEGIN, 1)[1].split(_END, 1)[0]
                try:
                    parsed = yaml.safe_load(old)
                    prior = next(
                        (item["config"] for patch in parsed or [] for item in patch.get("insert", []) if item.get("id") == "mcp-fofamap"),
                        {},
                    )
                except (ValueError, TypeError, KeyError, yaml.YAMLError):
                    raise IntegrationError(
                        "Existing DSH managed block cannot be safely parsed; configuration was not overwritten"
                    ) from None
        config = {
            **prior,
            "serverName": "fofamap",
            "transport": "stdio",
            "command": stdio["command"],
            "args": stdio["args"],
            "cwd": prior.get("cwd") or stdio["cwd"],
            "failOnStartupError": True,
        }
        block = yaml.safe_dump(
            [{"insert": [{"id": "mcp-fofamap", "name": "@deepseek-ai/dsh-mcp-client", "config": config}]}],
            allow_unicode=True,
            sort_keys=False,
        )
        _managed_config(config_path, block, uninstall=uninstall, dry_run=dry_run, changes=result.changes, remove_empty=scope == "project")
        if scope == "project":
            result.notes.append(f"启动 DeepSeek Harness 时请加上 --patch {config_path}，以启用此项目级 MCP 桥接。")
    elif host.id == "hermes":
        try:
            data = yaml.safe_load(config_path.read_text(encoding="utf-8")) if config_path.exists() else {}
        except (OSError, yaml.YAMLError) as exc:
            raise IntegrationError(f"无法安全解析 Hermes YAML 配置 {config_path}：{exc}") from exc
        if data is None:
            data = {}
        if not isinstance(data, dict):
            raise IntegrationError(f"Hermes 配置根节点必须是对象：{config_path}")
        if uninstall:
            changed = _remove_nested(data, ("mcp_servers", "fofamap"))
        else:
            prior = data.get("mcp_servers", {}).get("fofamap", {})
            entry = {**prior, **stdio, "enabled": True, "trust": prior.get("trust", "untrusted")}
            if prior.get("cwd"):
                entry["cwd"] = prior["cwd"]
            _set_nested(data, ("mcp_servers", "fofamap"), entry)
            changed = True
        if changed:
            _write_text(
                config_path,
                yaml.safe_dump(data, allow_unicode=True, sort_keys=False),
                dry_run=dry_run,
                changes=result.changes,
            )
        else:
            result.changes.append(f"absent {config_path}:mcp_servers.fofamap")

    _install_skill(skill_path, uninstall=uninstall, force=force, dry_run=dry_run, changes=result.changes)
    if host.id == "lmstudio":
        encoded = base64.b64encode(json.dumps(stdio, separators=(",", ":")).encode()).decode()
        result.deeplink = f"lmstudio://add_mcp?name=fofamap&config={quote(encoded, safe='')}"
    return result


def export_skill(destination: Path) -> Path:
    """Create an importable ZIP-based .skill containing only the bundled skill."""
    destination = destination.expanduser().resolve()
    if destination.suffix != ".skill":
        raise IntegrationError("Skill archive must use the .skill extension")
    if destination.exists():
        raise IntegrationError(f"Refusing to overwrite an existing archive: {destination}")
    source = _asset_root() / "skills" / "fofamap"
    destination.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(destination, "x", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(source.rglob("*")):
            if path.is_file() and not path.is_symlink() and not path.name.startswith("."):
                archive.write(path, Path("fofamap") / path.relative_to(source))
    return destination


def import_skill(
    source: Path,
    target: str,
    *,
    scope: str = "user",
    root: Path | None = None,
    home: Path | None = None,
    force: bool = False,
    dry_run: bool = False,
) -> list[str]:
    """Install a bounded .skill archive without executing it or changing MCP configuration."""
    host = normalize_host(target)
    if scope not in {"user", "project"}:
        raise IntegrationError("scope must be user or project")
    _, destination = _paths(host.id, scope, (root or Path.cwd()).resolve(), (home or Path.home()).expanduser().resolve())
    if destination is None:
        raise IntegrationError(f"{host.name} uses a plugin bundle; install with integrate --agent {host.id}")
    if source.suffix != ".skill":
        raise IntegrationError("Skill archive must use the .skill extension")
    changes: list[str] = []
    try:
        with zipfile.ZipFile(source) as archive, tempfile.TemporaryDirectory(prefix="fofamap-skill-") as temporary:
            members = archive.infolist()
            if len(members) > 100 or sum(item.file_size for item in members) > 16 * 1024 * 1024:
                raise IntegrationError("Skill archive exceeds the 100-file / 16 MiB limit")
            for item in members:
                name = item.filename
                parts = Path(name).parts
                mode = item.external_attr >> 16
                if (
                    not parts
                    or parts[0] != "fofamap"
                    or ".." in parts
                    or "\\" in name
                    or mode & 0o170000 == 0o120000
                    or item.file_size > 4 * 1024 * 1024
                ):
                    raise IntegrationError(f"Unsafe skill archive entry: {name}")
            if "fofamap/SKILL.md" not in archive.namelist():
                raise IntegrationError("Skill archive must contain fofamap/SKILL.md")
            for item in members:
                path = Path(temporary) / item.filename
                if item.is_dir():
                    path.mkdir(parents=True, exist_ok=True)
                else:
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_bytes(archive.read(item))
            _copy_managed(Path(temporary) / "fofamap", destination, kind="skill", force=force, dry_run=dry_run, changes=changes)
    except (zipfile.BadZipFile, OSError) as exc:
        raise IntegrationError(f"Could not import skill archive: {exc}") from exc
    return changes
