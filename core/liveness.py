"""Explicit liveness intent, saved overrides and fresh scheduled HTTP/TCP observations."""

from __future__ import annotations

import re
from collections import Counter
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from utils.helpers import FastChecker, asset_probe_target, insert_alive_status_field

if TYPE_CHECKING:
    from core.agent import AgentRun


_LOCAL_FIELDS = {"alive_status", "alive_checked_at", "alive_error"}


def liveness_intent(text: str) -> bool | None:
    matches = list(
        re.finditer(
            r"存活(?:检测|探测|验证)?|探活|可达性(?:检测|验证)|连通性(?:检测|验证)|检测.{0,5}存活|"
            r"alive\s*(?:check|test)|check\s*(?:liveness|reachability)|reachability\s*(?:check|test)",
            text,
            re.I,
        )
    )
    if not matches:
        return None
    result = None
    for match in matches:
        before = text[max(0, match.start() - 15) : match.start()]
        after = text[match.end() : match.end() + 8]
        disabled = bool(
            re.search(r"(?:不|无需|不要|不用|不需要|关闭|禁用)(?:进行|做|开启|执行|再做|再|任何|的)*\s*$", before)
            or re.search(r"\b(?:no|without|disable|skip|do not)\s*$", before, re.I)
            or re.match(r"\s*(?:关闭|禁用|不要做)", after)
        )
        result = not disabled
    return result


def resolve_liveness(task: str, override: bool | None, default: bool) -> tuple[bool, str]:
    explicit = liveness_intent(task)
    if explicit is not None:
        return explicit, "task_request" if explicit else "task_opt_out"
    if override is not None:
        return override, "task_setting"
    return default, "global_default"


def indexed_values(values: dict) -> dict:
    """Probe observations are not FOFA inventory changes."""
    return {key: value for key, value in values.items() if key not in _LOCAL_FIELDS}


async def probe_scheduled_assets(run: AgentRun, *, enabled: bool, source: str, timeout: int) -> dict:
    metadata = {"enabled": enabled, "source": source}
    if not enabled:
        return metadata
    targets = []
    for row in run.assets:
        try:
            target = None if str(row.get("base_protocol", "")).lower() == "udp" else asset_probe_target(row)
        except (ValueError, TypeError):
            target = None
        targets.append(target)
    unique = list(dict.fromkeys(target for target in targets if target))
    # Always probe again for a new period; do not reuse a previous FOFA/local alive_status value.
    statuses = await FastChecker.check_alive(unique, timeout=timeout)
    for asset, target in zip(run.assets, targets, strict=True):
        asset["alive_status"] = statuses.get(target, "Error") if target else "N/A"
    run.fields = insert_alive_status_field(run.fields)
    counts = Counter(str(statuses.get(target, "Error")) for target in unique)
    http = sum(count for status, count in counts.items() if status.isdigit() and 100 <= int(status) <= 599)
    tcp = counts.get("Open", 0)
    tls = counts.get("TLS", 0)
    blocked = sum(count for status, count in counts.items() if status.startswith("Blocked"))
    metadata.update(
        {
            "checked_at": datetime.now(timezone.utc).isoformat(),
            "timeout_seconds": timeout,
            "checked": len(unique),
            "responsive": http + tcp + tls,
            "http_responses": http,
            "tcp_open": tcp,
            "tls_untrusted": tls,
            "unresponsive": len(unique) - http - tcp - tls - blocked,
            "blocked": blocked,
            "skipped_records": sum(target is None for target in targets),
            "status_counts": dict(counts),
            "note": "HTTP errors still prove a response. TLS means certificate verification failed; Open means TCP connected. "
            "No response is not proof that a service has been removed. No Nuclei template was run.",
        }
    )
    return metadata
