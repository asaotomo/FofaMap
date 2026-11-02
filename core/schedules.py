"""Timezone-aware schedules, durable runs and conservative asset-snapshot comparisons."""

from __future__ import annotations

import hashlib
import html
import json
import re
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Literal
from zoneinfo import ZoneInfo

from pydantic import BaseModel, Field, model_validator
from sqlalchemy import inspect as inspect_database
from sqlalchemy import text
from sqlalchemy.exc import OperationalError

from core.agent import AgentRun, _asset_identity, validate_query
from core.liveness import indexed_values
from service.store import JobStore
from utils.datetime_compat import parse_iso_datetime

UTC = timezone.utc


class ScheduleInactiveError(ValueError):
    """The schedule was disabled/deleted after being claimed and must not start."""


class Timing(BaseModel):
    recurrence: Literal["once", "interval", "hourly", "daily", "weekly", "monthly"]
    timezone: str = "Asia/Shanghai"
    hour: int = Field(default=8, ge=0, le=23)
    minute: int = Field(default=0, ge=0, le=59)
    weekday: int = Field(default=0, ge=0, le=6)
    monthday: int = Field(default=1, ge=1, le=31)
    run_at: datetime | None = None
    interval_minutes: int | None = Field(default=None, ge=1, le=525600)
    anchor_at: datetime | None = None

    @model_validator(mode="after")
    def valid(self):
        ZoneInfo(self.timezone)
        if self.recurrence == "once" and self.run_at is None:
            raise ValueError("One-time schedules require an exact run_at")
        if self.recurrence == "interval" and self.interval_minutes is None:
            raise ValueError("间隔任务需要 interval_minutes（1–525600 分钟）")
        if self.anchor_at is not None and self.anchor_at.tzinfo is None:
            self.anchor_at = self.anchor_at.replace(tzinfo=ZoneInfo(self.timezone))
        return self

    def next_after(self, now: datetime) -> datetime | None:
        zone = ZoneInfo(self.timezone)
        local = now.astimezone(zone)
        if self.recurrence == "interval":
            step = timedelta(minutes=self.interval_minutes)
            anchor = self.anchor_at.astimezone(UTC) if self.anchor_at else now.astimezone(UTC)
            # Preserve the requested cadence; a long run skips missed slots without accumulating drift.
            elapsed = now.astimezone(UTC) - anchor
            return anchor + step * max(1, elapsed // step + 1)
        if self.recurrence == "once":
            at = self.run_at
            if at.tzinfo is None:
                at = at.replace(tzinfo=zone)
            return at.astimezone(UTC) if at > now else None
        # Calendar selection naturally skips absent dates such as February 31.
        if self.recurrence == "hourly":
            candidate = now.astimezone(UTC).replace(second=0, microsecond=0) + timedelta(minutes=1)
            for _ in range(180):
                if candidate.astimezone(zone).minute == self.minute:
                    return candidate
                candidate += timedelta(minutes=1)
            raise ValueError("Could not resolve hourly clock time")
        for offset in range(370):
            date = (local + timedelta(days=offset)).date()
            if self.recurrence == "weekly" and date.weekday() != self.weekday:
                continue
            if self.recurrence == "monthly" and date.day != self.monthday:
                continue
            candidate = datetime(date.year, date.month, date.day, self.hour, self.minute, tzinfo=zone)
            # Skip nonexistent local clock times rather than silently shifting a requested hour.
            if candidate.astimezone(UTC).astimezone(zone).replace(fold=0) != candidate.replace(fold=0):
                continue
            if candidate > now:
                return candidate.astimezone(UTC)
        raise ValueError("Could not determine a future schedule time")


def interval_from_text(value: str, *, zone: str = "Asia/Shanghai") -> Timing | None:
    """Recognize explicit recurring durations, including inside a full task sentence."""
    value = value.translate(str.maketrans("０１２３４５６７８９", "0123456789"))
    match = re.search(r"(?:每隔?|间隔)\s*(\d+|[一二两三四五六七八九十百千]+)\s*(分钟|小时|分(?!钟)|天)", value)
    english = re.search(r"\bevery\s+(\d+)\s*(minutes?|mins?|hours?|hrs?|days?)\b", value, re.I)
    if not match and not english:
        if re.search(r"每分钟|每隔一分钟", value):
            return Timing(recurrence="interval", timezone=zone, interval_minutes=1)
        return None
    token, unit = (match[1], match[2]) if match else (english[1], english[2].lower())
    if token.isdigit():
        number = int(token)
    else:
        digits = dict(zip("一二两三四五六七八九", [1, 2, 2, 3, 4, 5, 6, 7, 8, 9], strict=True))
        number, digit = 0, 0
        for char in token:
            if char in digits:
                digit = digits[char]
            else:
                number += (digit or 1) * {"十": 10, "百": 100, "千": 1000}[char]
                digit = 0
        number += digit
    multiplier = 60 if unit == "小时" or unit.startswith(("hour", "hr")) else 1440 if unit == "天" or unit.startswith("day") else 1
    return Timing(recurrence="interval", timezone=zone, interval_minutes=number * multiplier)


def timing_label(timing: Timing, *, english: bool = False) -> str:
    if timing.recurrence == "interval":
        return f"Every {timing.interval_minutes} minutes" if english else f"每 {timing.interval_minutes} 分钟"
    return (
        timing.recurrence
        if english
        else {"once": "单次", "hourly": "每小时", "daily": "每天", "weekly": "每周", "monthly": "每月"}[timing.recurrence]
    )


def parse_when(value: str, *, zone: str = "Asia/Shanghai", now: datetime | None = None) -> Timing:
    current = (now or datetime.now(UTC)).astimezone(ZoneInfo(zone))
    value = value.strip()
    interval = interval_from_text(value, zone=zone)
    if interval:
        return interval
    if re.match(r"^\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}", value):
        return Timing(recurrence="once", timezone=zone, run_at=parse_iso_datetime(value))
    clock = re.search(r"(\d{1,2})(?:[:：](\d{2})|点(?:(\d{1,2})分?)?)", value)
    if clock:
        hour = int(clock[1])
        minute = int(clock[2] or clock[3] or 0)
        if re.search(r"下午|晚上|晚间|傍晚|(?i:pm)", value) and hour < 12:
            hour += 12
        if re.search(r"凌晨|早上|上午|(?i:am)", value) and hour == 12:
            hour = 0
    elif re.search(r"每小时|hourly|every hour", value, re.I):
        offset = re.search(r"每小时\s*(\d{1,2})分", value)
        hour, minute = 0, int(offset[1]) if offset else 0
    else:
        try:
            at = parse_iso_datetime(value)
            return Timing(recurrence="once", timezone=zone, run_at=at)
        except ValueError as exc:
            raise ValueError("请填写明确时间，例如每10分钟、每天8点、每周一9点、每月1日8点、明天15:00 或 ISO 日期时间") from exc
    data: dict[str, Any] = {"timezone": zone, "hour": hour, "minute": minute}
    if re.search(r"每小时|hourly|every hour", value, re.I):
        return Timing(recurrence="hourly", **data)
    if re.search(r"每天|每日|daily|every day", value, re.I):
        return Timing(recurrence="daily", **data)
    week = re.search(r"每周([一二三四五六日天])", value)
    if week:
        return Timing(recurrence="weekly", weekday="一二三四五六日".index(week[1].replace("天", "日")), **data)
    month = re.search(r"每月(\d{1,2})[日号]", value)
    if month:
        return Timing(recurrence="monthly", monthday=int(month[1]), **data)
    offset = 2 if "后天" in value else 1 if re.search(r"明天|明早|tomorrow", value, re.I) else 0
    explicit_date = re.search(r"(\d{4})-(\d{2})-(\d{2})", value)
    if not explicit_date and not re.search(r"今天|今晚|明天|明早|后天|today|tomorrow", value, re.I):
        raise ValueError("A one-time time must include a date or 今天/明天; no date is guessed")
    date = (current + timedelta(days=offset)).date()
    if explicit_date:
        date = datetime(int(explicit_date[1]), int(explicit_date[2]), int(explicit_date[3])).date()
    at = datetime(date.year, date.month, date.day, hour, minute, tzinfo=ZoneInfo(zone))
    return Timing(recurrence="once", run_at=at, **data)


class ScheduleRequest(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    task: str = Field(min_length=1, max_length=5000)
    when: str = ""
    timezone: str = "Asia/Shanghai"
    timing: Timing | None = None
    queries: list[str] = Field(default_factory=list, max_length=10)
    fields: list[str] = Field(default_factory=lambda: ["host", "ip", "port", "protocol", "title", "domain"], min_length=1)
    max_records: int = Field(default=1000, ge=1, le=100000)
    max_pages: int = Field(default=10, ge=1, le=1000)
    language: Literal["zh", "en"] = "zh"
    analyze: bool = True
    check_alive: bool | None = None

    @model_validator(mode="after")
    def valid(self):
        if self.timing is None:
            self.timing = parse_when(self.when, zone=self.timezone)
        for query in self.queries:
            errors = validate_query(query)
            if errors:
                raise ValueError("; ".join(errors))
        return self


def compare_snapshots(previous: dict | None, run: AgentRun) -> dict:
    current = {json.dumps(_asset_identity(row)): indexed_values(row) for row in run.assets}
    fingerprint = hashlib.sha256(
        json.dumps(
            {"queries": sorted(q.query for q in run.queries), "fields": sorted(indexed_values(dict.fromkeys(run.fields)))},
            ensure_ascii=False,
        ).encode()
    ).hexdigest()
    complete = not run.error and not run.assets_truncated and run.sample_stop_reason == "complete"
    if previous is None:
        return {
            "baseline": True,
            "comparable": False,
            "current_count": run.result_count,
            "added": [],
            "removed": [],
            "changed": [],
            "complete": complete,
            "query_fingerprint": fingerprint,
            "note": "Initial baseline; no historical increase or decrease can be inferred.",
        }
    old = {json.dumps(_asset_identity(row)): indexed_values(row) for row in previous.get("assets", [])}
    comparable = complete and previous.get("complete", False) and previous.get("query_fingerprint") == fingerprint
    shared = current.keys() & old.keys()
    changes = [
        {
            "before": old[key],
            "after": current[key],
            "fields": [field for field in set(old[key]) | set(current[key]) if old[key].get(field) != current[key].get(field)],
        }
        for key in sorted(shared)
        if old[key] != current[key]
    ]
    return {
        "baseline": False,
        "comparable": comparable,
        "current_count": run.result_count,
        "previous_count": previous.get("count"),
        "net_change": run.result_count - int(previous.get("count") or 0),
        "added": [current[k] for k in sorted(current.keys() - old.keys())],
        "removed": [old[k] for k in sorted(old.keys() - current.keys())],
        "changed": changes,
        "complete": complete,
        "query_fingerprint": fingerprint,
        "note": "Indexed additions/removals, not proof of a live service change."
        if comparable
        else "Incomplete or changed query window: additions/removals are snapshot differences, not confirmed exposure changes.",
    }


class ScheduleStore:
    def __init__(self, database_url: str):
        self.engine = JobStore(database_url).engine
        with self.engine.begin() as connection:
            connection.execute(
                text("""CREATE TABLE IF NOT EXISTS fofamap_schedules (
                id VARCHAR(64) PRIMARY KEY, spec TEXT NOT NULL, enabled INTEGER NOT NULL DEFAULT 1,
                next_run VARCHAR(64), lease_until VARCHAR(64), created_at VARCHAR(64) NOT NULL)""")
            )
            connection.execute(
                text("""CREATE TABLE IF NOT EXISTS fofamap_schedule_runs (
                id VARCHAR(64) PRIMARY KEY, schedule_id VARCHAR(64) NOT NULL, status VARCHAR(32) NOT NULL,
                started_at VARCHAR(64) NOT NULL, finished_at VARCHAR(64), result TEXT, error TEXT)""")
            )
            columns = {column["name"] for column in inspect_database(connection).get_columns("fofamap_schedules")}
            for name, definition in (("stop_requested", "INTEGER NOT NULL DEFAULT 0"), ("deleted_at", "VARCHAR(64)")):
                if name not in columns:
                    try:
                        with connection.begin_nested():
                            connection.execute(text(f"ALTER TABLE fofamap_schedules ADD COLUMN {name} {definition}"))
                    except OperationalError:
                        # Another menu/MCP/worker can migrate the same existing database concurrently.
                        if name not in {col["name"] for col in inspect_database(connection).get_columns("fofamap_schedules")}:
                            raise

    def heartbeat(self) -> None:
        with self.engine.begin() as c:
            c.execute(text("CREATE TABLE IF NOT EXISTS fofamap_scheduler_state (id INTEGER PRIMARY KEY, heartbeat VARCHAR(64))"))
            c.execute(text("DELETE FROM fofamap_scheduler_state WHERE id=1"))
            c.execute(
                text("INSERT INTO fofamap_scheduler_state(id,heartbeat) VALUES(1,:at)"),
                {"at": datetime.now(UTC).isoformat()},
            )

    def worker_status(self) -> dict:
        with self.engine.begin() as c:
            c.execute(text("CREATE TABLE IF NOT EXISTS fofamap_scheduler_state (id INTEGER PRIMARY KEY, heartbeat VARCHAR(64))"))
            at = c.execute(text("SELECT heartbeat FROM fofamap_scheduler_state WHERE id=1")).scalar()
        age = (datetime.now(UTC) - parse_iso_datetime(at)).total_seconds() if at else None
        return {
            "recent_heartbeat": at,
            "heartbeat_local": parse_iso_datetime(at).astimezone().isoformat() if at else None,
            "heartbeat_timezone": str(datetime.now().astimezone().tzinfo),
            "worker_recently_seen": age is not None and age < 120,
            "required_command": "fofamap-scheduler --interval 30",
            "note": "Saving a schedule does not start the worker. Keep the scheduler service running.",
        }

    def create(self, request: ScheduleRequest, now: datetime | None = None) -> dict:
        now = (now or datetime.now(UTC)).astimezone(UTC)
        request = request.model_copy(deep=True)
        if request.timing.recurrence == "interval" and request.timing.anchor_at is None:
            request.timing.anchor_at = now
        due = request.timing.next_after(now)
        if due is None:
            raise ValueError("The requested time is in the past; please select a future time")
        identifier = str(uuid.uuid4())
        with self.engine.begin() as c:
            c.execute(
                text("INSERT INTO fofamap_schedules(id,spec,next_run,created_at) VALUES (:id,:spec,:due,:now)"),
                {"id": identifier, "spec": request.model_dump_json(), "due": due.isoformat(), "now": now.isoformat()},
            )
        return self.get(identifier)

    def get(self, identifier: str, *, include_deleted: bool = False) -> dict:
        with self.engine.connect() as c:
            row = c.execute(text("SELECT * FROM fofamap_schedules WHERE id=:id"), {"id": identifier}).mappings().first()
        if row is None or (row["deleted_at"] and not include_deleted):
            raise KeyError(identifier)
        result = dict(row)
        result["spec"] = json.loads(result["spec"])
        result["control_status"] = (
            "deleted" if result["deleted_at"] else "stopped" if result["stop_requested"] else "active" if result["enabled"] else "paused"
        )
        return result

    def list(self, *, include_deleted: bool = False) -> list[dict]:
        with self.engine.connect() as c:
            identifiers = c.execute(text("SELECT id FROM fofamap_schedules ORDER BY created_at")).scalars().all()
        # Recheck each row so a concurrent deletion cannot revive an active-list entry.
        items = [self.get(identifier, include_deleted=True) for identifier in identifiers]
        return items if include_deleted else [item for item in items if not item["deleted_at"]]

    def update(self, identifier: str, request: ScheduleRequest) -> dict:
        current = self.get(identifier)
        now = datetime.now(UTC)
        request = request.model_copy(deep=True)
        if request.timing.recurrence == "interval" and request.timing.anchor_at is None:
            request.timing.anchor_at = now
        if current.get("lease_until") and parse_iso_datetime(current["lease_until"]) > now:
            raise ValueError("A running schedule cannot be edited; pause and wait for completion first")
        due = request.timing.next_after(now)
        if due is None:
            raise ValueError("The requested time is in the past")
        with self.engine.begin() as c:
            c.execute(
                text("UPDATE fofamap_schedules SET spec=:spec,next_run=:due WHERE id=:id AND deleted_at IS NULL"),
                {"id": identifier, "spec": request.model_dump_json(), "due": due.isoformat()},
            )
        return self.get(identifier)

    def set_enabled(self, identifier: str, enabled: bool) -> dict:
        item = self.get(identifier)
        due = item["next_run"]
        if enabled:
            next_time = ScheduleRequest.model_validate(item["spec"]).timing.next_after(datetime.now(UTC))
            if next_time is None:
                raise ValueError("A past one-time task cannot be resumed")
            due = next_time.isoformat()
        with self.engine.begin() as c:
            c.execute(
                text("UPDATE fofamap_schedules SET enabled=:enabled,next_run=:due,stop_requested=0 WHERE id=:id AND deleted_at IS NULL"),
                {"id": identifier, "enabled": int(enabled), "due": due},
            )
        return self.get(identifier)

    def stop(self, identifier: str) -> dict:
        """Disable future runs and ask any live worker to cancel this run; retain history."""
        self.get(identifier)
        with self.engine.begin() as c:
            c.execute(
                text("UPDATE fofamap_schedules SET enabled=0,stop_requested=1 WHERE id=:id AND deleted_at IS NULL"), {"id": identifier}
            )
        return self.get(identifier)

    def delete(self, identifier: str) -> dict:
        """Remove a task from management/scheduling, retaining its report archive and history."""
        self.get(identifier, include_deleted=True)
        with self.engine.begin() as c:
            c.execute(
                text("""UPDATE fofamap_schedules SET enabled=0,stop_requested=1,next_run=NULL,
                deleted_at=COALESCE(deleted_at,:now) WHERE id=:id"""),
                {"id": identifier, "now": datetime.now(UTC).isoformat()},
            )
        return self.get(identifier, include_deleted=True)

    def release_claim(self, identifier: str) -> None:
        with self.engine.begin() as c:
            c.execute(text("UPDATE fofamap_schedules SET lease_until=NULL WHERE id=:id"), {"id": identifier})

    def claim_due(self, now: datetime | None = None) -> list[dict]:
        now = (now or datetime.now(UTC)).astimezone(UTC)
        claimed = []
        with self.engine.begin() as c:
            rows = (
                c.execute(
                    text("""SELECT * FROM fofamap_schedules WHERE enabled=1 AND deleted_at IS NULL AND next_run<=:now
                AND (lease_until IS NULL OR lease_until<:now) ORDER BY next_run"""),
                    {"now": now.isoformat()},
                )
                .mappings()
                .all()
            )
            for row in rows:
                updated = c.execute(
                    text("""UPDATE fofamap_schedules SET lease_until=:lease WHERE id=:id
                    AND enabled=1 AND deleted_at IS NULL
                    AND (lease_until IS NULL OR lease_until<:now)"""),
                    {"id": row["id"], "now": now.isoformat(), "lease": (now + timedelta(hours=1)).isoformat()},
                )
                if updated.rowcount:
                    claimed.append(dict(row))
        for item in claimed:
            item["spec"] = json.loads(item["spec"])
        return claimed

    def runs(self, identifier: str, limit: int = 30) -> list[dict]:
        with self.engine.connect() as c:
            rows = (
                c.execute(
                    text("SELECT * FROM fofamap_schedule_runs WHERE schedule_id=:id ORDER BY started_at DESC LIMIT :limit"),
                    {"id": identifier, "limit": max(1, min(limit, 365))},
                )
                .mappings()
                .all()
            )
        result = []
        for row in rows:
            item = dict(row)
            if item["result"]:
                item["result"] = json.loads(item["result"])
            result.append(item)
        return result

    def begin_run(self, identifier: str) -> str:
        run_id = str(uuid.uuid4())
        with self.engine.begin() as c:
            updated = c.execute(
                text("""INSERT INTO fofamap_schedule_runs(id,schedule_id,status,started_at)
                    SELECT :id,id,:status,:at FROM fofamap_schedules
                    WHERE id=:schedule AND enabled=1 AND deleted_at IS NULL"""),
                {"id": run_id, "schedule": identifier, "status": "running", "at": datetime.now(UTC).isoformat()},
            )
            if not updated.rowcount:
                raise ScheduleInactiveError("任务已暂停、停止或删除，本轮不再启动")
        return run_id

    def finish_run(self, item: dict, run_id: str, result: dict | None, error: str | None = None, *, cancelled: bool = False):
        request = ScheduleRequest.model_validate(item["spec"])
        # Freeze the first successful query portfolio for comparable recurring measurements.
        if result and not request.queries:
            request.queries = result.get("queries", [])
        due = request.timing.next_after(datetime.now(UTC))
        with self.engine.begin() as c:
            c.execute(
                text("UPDATE fofamap_schedule_runs SET status=:status,finished_at=:at,result=:result,error=:error WHERE id=:id"),
                {
                    "id": run_id,
                    "status": "cancelled" if cancelled else "failed" if error else "completed",
                    "at": datetime.now(UTC).isoformat(),
                    "result": json.dumps(result, ensure_ascii=False) if result else None,
                    "error": error,
                },
            )
            c.execute(
                text(
                    "UPDATE fofamap_schedules SET spec=:spec,lease_until=NULL,"
                    "next_run=CASE WHEN deleted_at IS NOT NULL THEN NULL ELSE :due END,"
                    "enabled=CASE WHEN deleted_at IS NOT NULL OR enabled=0 THEN 0 ELSE :enabled END WHERE id=:id"
                ),
                {
                    "id": item["id"],
                    "spec": request.model_dump_json(),
                    "due": due.isoformat() if due else None,
                    "enabled": int(due is not None),
                },
            )


def append_change_report(markdown: Path, delta: dict, trend: list[dict], language: str = "zh") -> None:
    english = language == "en"
    heading = "Snapshot changes and trend" if english else "快照变化与趋势"
    note = delta["note"]
    if not english:
        note = (
            "首次建立基线，不判断历史增减。"
            if delta["baseline"]
            else "同范围完整索引快照的增减，不代表服务实时上下线。"
            if delta["comparable"]
            else "范围变化或取回不完整：只能比较快照差异，不能认定资产真实新增或消失。"
        )
    lines = [f"\n## {heading}\n", note, "\n| Time | Count |\n|---|---:|"]
    for point in trend:
        lines.append(f"| {point['at']} | {point['count']} |")
    for key, label in [("added", "新增 / Added"), ("removed", "减少 / Removed"), ("changed", "变化 / Changed")]:
        lines.extend(
            [
                f"\n### {label} ({len(delta[key])})\n",
                "```json",
                json.dumps(delta[key], ensure_ascii=False, indent=2),
                "```",
            ]
        )
    with markdown.open("a", encoding="utf-8") as handle:
        handle.write("\n".join(lines) + "\n")
    maximum = max((point["count"] for point in trend), default=1) or 1
    bars = "".join(
        f'<div class="bar-row"><span>{html.escape(point["at"])}</span>'
        f'<div class="bar-track"><span class="bar-fill" '
        f'style="width:{point["count"] / maximum * 100:.2f}%;background:#0071e3"></span></div>'
        f"<strong>{point['count']}</strong></div>"
        for point in trend
    )
    from core.html_report import _table_block

    blocks = []
    for key, label in [("added", "新增 / Added"), ("removed", "减少 / Removed"), ("changed", "变化 / Changed")]:
        rows = []
        for change in delta[key][:200]:
            asset = change.get("after", change)
            cells = [
                asset.get("host") or asset.get("ip") or "—",
                asset.get("port") or "—",
                asset.get("protocol") or "—",
                ", ".join(change.get("fields", [])) if key == "changed" else asset.get("title") or "—",
            ]
            rows.append("<tr>" + "".join(f"<td>{html.escape(str(cell))}</td>" for cell in cells) + "</tr>")
        table = (
            "<table><thead><tr><th>Host / IP</th><th>Port</th><th>Protocol</th><th>Detail</th></tr></thead>"
            + "<tbody>"
            + "".join(rows)
            + "</tbody></table>"
        )
        blocks.append(
            f"<h3>{html.escape(label)} ({len(delta[key])})</h3>"
            + (
                _table_block(
                    table,
                    label="Export CSV" if english else "导出 CSV",
                    filename=f"{key}.csv",
                    table_id=f"changes-{key}",
                )
                if rows
                else "<p>—</p>"
            )
        )
    detail = "".join(blocks) + '<p><a href="report.json">完整变化数据 / Full change data (JSON)</a></p>'
    section = f'<section id="changes"><h2>{heading}</h2><p>{html.escape(note)}</p>{bars}{detail}</section>'
    html_path = markdown.with_suffix(".html")
    page = html_path.read_text(encoding="utf-8")
    html_path.write_text(page.replace("</main>", section + "</main>"), encoding="utf-8")


def write_schedule_index(store: ScheduleStore, root: Path) -> Path:
    """Rebuild offline dashboard and per-task history with relative report links."""
    from core.schedule_index import write_index

    return write_index(store, root)
