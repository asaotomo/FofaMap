"""Version-matched Nuclei guidance and typed, reviewable command recommendations."""

from __future__ import annotations

import asyncio
import json
import shlex
from pathlib import Path
from typing import Any

from core.nuclei_protocols import asset_scan_target, parse_scan_target
from core.scanner import build_nuclei_command, nuclei_subprocess_env, resolve_nuclei_executable, strip_nuclei_ansi
from core.scans import NETWORK_SERVICE_HINTS, ScanPlanRequest, default_nuclei_template_ids


async def command_guide(*, refresh: bool = False) -> dict[str, Any]:
    executable = resolve_nuclei_executable()
    if not executable:
        return {"installed": False, "install": "https://docs.projectdiscovery.io/opensource/nuclei/install"}
    path = Path(executable).resolve()
    stat = path.stat()
    fingerprint = f"{path}:{stat.st_size}:{stat.st_mtime_ns}"
    cache = Path.home() / ".cache/fofamap/nuclei-command-guide.json"
    if not refresh and cache.is_file():
        try:
            data = json.loads(cache.read_text(encoding="utf-8"))
            if data.get("fingerprint") == fingerprint:
                return data
        except (OSError, ValueError):
            pass
    process = await asyncio.create_subprocess_exec(
        executable, "-h", stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT, env=nuclei_subprocess_env()
    )
    try:
        output, _ = await asyncio.wait_for(process.communicate(), timeout=15)
    except asyncio.TimeoutError:
        process.kill()
        await process.wait()
        raise RuntimeError("Nuclei help probe timed out") from None
    if process.returncode:
        raise RuntimeError("Nuclei help probe failed")
    data = {
        "installed": True,
        "fingerprint": fingerprint,
        "executable": executable,
        "help": strip_nuclei_ansi(output.decode(errors="replace"))[:60000],
        "source": "https://docs.projectdiscovery.io/opensource/nuclei/running",
        "usage": "Use nuclei_recommend, inspect reasons/targets/limits, customize if needed, then nuclei_plan. "
        "Execute only after exact-scope approval; poll fofa_job_status in the same MCP server. "
        "Templates may declare additional ports; inspect nuclei_templates before approval.",
    }
    try:
        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    except OSError:
        data["cache_note"] = "Guide was read live but could not be cached"
    return data


def customize_plan(base: ScanPlanRequest, parameters: str) -> ScanPlanRequest:
    """Parse documented supported options, not shell commands; approval is still required."""
    tokens = shlex.split(parameters)
    if tokens and Path(tokens[0]).name in {"nuclei", "nuclei.exe"}:
        tokens.pop(0)
    data = base.model_dump()
    value_flags = {
        "-rl": ("rate_limit", int),
        "-rate-limit": ("rate_limit", int),
        "-c": ("concurrency", int),
        "-concurrency": ("concurrency", int),
        "-retries": ("retries", int),
        "-timeout": ("request_timeout", int),
        "-severity": ("severities", lambda x: x.split(",")),
        "-pt": ("protocols", lambda x: x.split(",")),
        "-id": ("template_ids", lambda x: x.split(",")),
        "-t": ("templates", lambda x: [x]),
    }
    switches = {
        "-headless": ("enable_headless", True),
        "-code": ("enable_code", True),
        "-file": ("enable_file", True),
        "-ni": ("allow_oast", False),
        "-no-interactsh": ("allow_oast", False),
    }
    position = 0
    while position < len(tokens):
        flag = tokens[position]
        if flag in {"-dr", "-duc", "-nc"}:
            position += 1
            continue
        if flag in switches:
            key, value = switches[flag]
            data[key] = value
            position += 1
            continue
        if flag not in value_flags or position + 1 >= len(tokens):
            raise ValueError(
                f"Unsupported custom parameter: {flag}. Use Nuclei CLI flags, e.g. -rl 10 -c 3; targets/output cannot be overridden here."
            )
        key, convert = value_flags[flag]
        data[key] = convert(tokens[position + 1])
        position += 2
    return ScanPlanRequest.model_validate(data)


def recommend_scans(intent: str, assets: list[dict[str, Any]], targets: list[str] | None = None) -> dict[str, Any]:
    groups: dict[str, list[str]] = {}
    unclassified = []
    explicit = set(targets or [])
    for row in assets[:1000]:
        target = asset_scan_target(row)
        if not target or (explicit and target not in explicit):
            continue
        endpoint = parse_scan_target(target)
        service = str(row.get("protocol") or "").lower()
        key = "web" if endpoint.kind == "web" else next((name for name in NETWORK_SERVICE_HINTS if name in service), "")
        if not key:
            unclassified.append(target)
        elif target not in groups.setdefault(key, []):
            groups[key].append(target)
    for target in targets or []:
        if any(target in group for group in groups.values()) or target in unclassified:
            continue
        endpoint = parse_scan_target(target)
        key = "web" if endpoint.kind == "web" else ""
        if key:
            groups.setdefault(key, []).append(target)
        else:
            unclassified.append(target)
    proposals = []
    for group, selected in list(groups.items())[:3]:
        ids = default_nuclei_template_ids() if group == "web" else [NETWORK_SERVICE_HINTS[group]]
        protocols = ["http", "ssl"] if group == "web" else ["javascript"] if group == "smb" else ["tcp"]
        plan = ScanPlanRequest(targets=selected, template_ids=ids, protocols=protocols, severities=["info", "low"])
        command = build_nuclei_command(
            resolve_nuclei_executable() or "nuclei", plan, Path("APPROVED_TARGETS.txt"), Path("nuclei.jsonl")
        )
        proposals.append(
            {
                "name": "Web/TLS baseline" if group == "web" else f"{group.upper()} service detection",
                "reason": "Web assets support bounded header/TLS baseline checks."
                if group == "web"
                else f"FOFA identified {group}; use its service detection template and preserve explicit ports.",
                "coverage": "Detection/baseline only; not all CVEs and not proof of absence of vulnerabilities.",
                "plan": plan.model_dump(),
                "target_lines": [parse_scan_target(t).nuclei_input for t in selected],
                "argv": command,
                "command_posix": shlex.join(command),
            }
        )
    return {
        "intent": intent,
        "proposals": proposals,
        "omitted_groups": max(0, len(groups) - 3),
        "needs_template_selection": list(dict.fromkeys(unclassified)),
        "next": "Present 1-3 proposals and reasons in the user language. The user selects/customizes; "
        "then create an exact nuclei_plan and obtain approval. Do not execute recommendations directly.",
    }
