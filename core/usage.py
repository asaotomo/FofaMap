"""Run clock and model-token totals shared by the CLI and the reports."""

from __future__ import annotations

from typing import Any


def run_usage_parts(run: Any, language: str = "zh") -> dict[str, str]:
    """Start clock, elapsed time, and combined model tokens for one run."""
    english = language == "en"
    finished = run.finished_at or run.started_at
    started = run.started_at.strftime("%Y-%m-%d %H:%M:%S")
    elapsed = _elapsed_text(max(0, int((finished - run.started_at).total_seconds())), english)
    totals = _combined_tokens(run)
    if totals is None:
        tokens = "Token usage was not returned" if english else "模型未返回 Token 用量"
    else:
        incoming, outgoing = totals
        total = incoming + outgoing
        tokens = (
            f"{total:,} (input {incoming:,} · output {outgoing:,})"
            if english
            else f"{total:,}（输入 {incoming:,} · 输出 {outgoing:,}）"
        )
    return {"started": started, "elapsed": elapsed, "tokens": tokens}


def _elapsed_text(seconds: int, english: bool) -> str:
    hours, rem = divmod(max(0, seconds), 3600)
    minutes, secs = divmod(rem, 60)
    if hours:
        return f"{hours}h {minutes:02d}m {secs:02d}s" if english else f"{hours} 小时 {minutes:02d} 分 {secs:02d} 秒"
    if minutes:
        return f"{minutes}m {secs:02d}s" if english else f"{minutes} 分 {secs:02d} 秒"
    return f"{secs}s" if english else f"{secs} 秒"


def _combined_tokens(run: Any) -> tuple[int, int] | None:
    seen = False
    incoming = 0
    outgoing = 0
    for event in run.route_events:
        prompt = event.get("input_tokens")
        completion = event.get("output_tokens")
        if prompt is None and completion is None:
            continue
        seen = True
        incoming += int(prompt or 0)
        outgoing += int(completion or 0)
    if not seen:
        return None
    return incoming, outgoing
