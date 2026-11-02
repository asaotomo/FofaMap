"""Draft a typed schedule using the user's configured model; never execute the draft."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone

from core.liveness import liveness_intent
from core.schedules import ScheduleRequest, interval_from_text
from providers.http import HttpModelProvider
from providers.registry import ProviderRouter


async def draft_schedule(router: ProviderRouter, instruction: str, current: ScheduleRequest | None = None) -> ScheduleRequest:
    result = await router.generate(
        "planner",
        system=(
            "Convert the user's instruction into a FOFA asset-mapping schedule JSON with optional liveness checks. "
            "Return a complete ScheduleRequest matching the schema. "
            "Put the asset scope in task and the frequency only in timing, not in task. Never execute commands or queries. "
            "FOFA collection and optional liveness can be scheduled; Nuclei vulnerability scans need a separate approval. "
            "Liveness checks are separate: explicit 存活检测/check reachability means check_alive=true. "
            "Explicitly declining liveness means false; otherwise preserve a current override or use null to follow the global setting. "
            "Interpret relative dates from the supplied current time in the requested timezone, default Asia/Shanghai. "
            "Use timing for once/interval/hourly/daily/weekly/monthly and preserve the precise requested clock/frequency. "
            "For 每10分钟 / every 10 minutes use timing={recurrence:interval, interval_minutes:10, timezone:Asia/Shanghai}. "
            "Intervals can be any integer number of minutes >=1; do not round them to an hour or day. "
            "Never guess a missing date or ambiguous clock: return an object with error explaining what is missing. "
            "For natural-language mapping keep queries empty so the asset agent resolves them at execution time. "
            "If editing only timing, retain the task/queries/limits; if changing the asset scope, clear old queries unless "
            "the user explicitly provided replacement FOFA queries. Never invent company domains or ownership."
        ),
        prompt=json.dumps(
            {
                "now": datetime.now(timezone.utc).isoformat(),
                "instruction": instruction,
                "current": current.model_dump(mode="json") if current else None,
            },
            ensure_ascii=False,
        ),
        schema=ScheduleRequest.model_json_schema(),
    )
    data = result.structured or HttpModelProvider._decode_json(result.text)
    if not isinstance(data, dict):
        raise ValueError("AI did not return a schedule JSON; use manual settings or clarify the instruction")
    if data.get("error"):
        raise ValueError(str(data["error"]))
    alive = liveness_intent(instruction)
    if alive is not None:
        data["check_alive"] = alive
        if liveness_intent(data.get("task", "")) != alive:
            data["task"] = str(data.get("task") or instruction) + ("；进行存活检测。" if alive else "；不进行存活检测。")
    else:
        data["check_alive"] = current.check_alive if current else None
    # Explicit duration wins over a model's accidental rounding or legacy unsupported `when`.
    interval = interval_from_text(instruction, zone=data.get("timezone") or (current.timing.timezone if current else "Asia/Shanghai"))
    if interval:
        model_timing = data.get("timing") or {}
        explicit_start = re.search(r"明天|后天|\d{4}-\d{2}-\d{2}|\d{1,2}[:：]\d{2}|\d{1,2}点", instruction)
        if explicit_start and model_timing.get("recurrence") == "interval" and model_timing.get("anchor_at"):
            interval.anchor_at = type(interval).model_validate(model_timing).anchor_at
        data["timing"] = interval.model_dump(mode="json")
    if not data.get("fields"):
        data.pop("fields", None)
        if current:
            data["fields"] = current.fields
    return ScheduleRequest.model_validate(data)
