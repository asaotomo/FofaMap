"""Interactive schedule menu. All persistence uses the same store as MCP and the worker."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import click
from questionary import Choice
from rich.markup import escape
from rich.table import Table

from config import settings
from core.liveness import resolve_liveness
from core.schedules import ScheduleRequest, Timing, parse_when, timing_label, write_schedule_index
from service.scheduler import schedule_store
from utils import prompts as questionary
from utils.cli_ui import console, section
from utils.datetime_compat import parse_iso_datetime
from utils.i18n import t


class CancelForm(Exception):
    pass


def _state_label(value: str) -> str:
    return {"active": t("启用", "Active"), "paused": t("暂停", "Paused"), "stopped": t("停止", "Stopped")}.get(value, value)


def _ask(prompt):
    value = prompt.ask()
    if value is None:
        raise CancelForm
    return value


def _text(label: str, default: str = "") -> str:
    return _ask(questionary.text(label, default=default)).strip()


def _number(label: str, default: int, low: int, high: int) -> int:
    return int(_ask(questionary.text(label, default=str(default), validate=lambda s: s.isdigit() and low <= int(s) <= high)))


def _clock(default: str) -> tuple[int, int]:
    value = _text(t("执行时间（24小时 HH:MM）：", "Clock time (24-hour HH:MM):"), default)
    parsed = datetime.strptime(value, "%H:%M")
    return parsed.hour, parsed.minute


def _timing(current: ScheduleRequest | None = None) -> Timing:
    mode = _ask(
        questionary.select(
            t("执行频率 / 时间：", "Frequency / time:"),
            choices=[
                Choice(t("自然语言时间，例如每天8点、明天15:00", "Natural time, e.g. 每天8点 / 明天15:00"), "natural"),
                Choice(t("仅执行一次", "One time"), "once"),
                Choice(t("每隔 N 分钟（如 1 / 5 / 10 / 30 分钟）", "Every N minutes (e.g. 1 / 5 / 10 / 30)"), "interval"),
                Choice(t("每小时", "Hourly"), "hourly"),
                Choice(t("每天", "Daily"), "daily"),
                Choice(t("每周", "Weekly"), "weekly"),
                Choice(t("每月", "Monthly"), "monthly"),
            ],
            default=current.timing.recurrence if current else "natural",
        )
    )
    zone = _text(t("任务时区（IANA）：", "Task timezone (IANA):"), current.timing.timezone if current else "Asia/Shanghai")
    ZoneInfo(zone)
    if mode == "natural":
        return parse_when(_text(t("执行时间描述：", "Time description:")), zone=zone)
    if mode == "once":
        at = _text(t("执行日期时间（YYYY-MM-DD HH:MM）：", "Run at (YYYY-MM-DD HH:MM):"))
        return Timing(recurrence="once", timezone=zone, run_at=parse_iso_datetime(at))
    if mode == "interval":
        minutes = _number(
            t("每隔多少分钟执行（1–525600）：", "Run every N minutes (1–525600):"),
            (current.timing.interval_minutes or 10) if current else 10,
            1,
            525600,
        )
        return Timing(recurrence="interval", timezone=zone, interval_minutes=minutes)
    if mode == "hourly":
        return Timing(
            recurrence="hourly",
            timezone=zone,
            minute=_number(t("每小时第几分钟（0–59）：", "Minute of each hour (0–59):"), current.timing.minute if current else 0, 0, 59),
        )
    hour, minute = _clock(f"{current.timing.hour:02}:{current.timing.minute:02}" if current else "08:00")
    extra = {}
    if mode == "weekly":
        extra["weekday"] = int(
            _ask(
                questionary.select(
                    t("星期：", "Weekday:"),
                    choices=[
                        Choice(t(f"星期{day}", english), str(i))
                        for i, (day, english) in enumerate(
                            zip(
                                "一二三四五六日",
                                ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"],
                                strict=True,
                            )
                        )
                    ],
                    default=str(current.timing.weekday if current else 0),
                )
            )
        )
    if mode == "monthly":
        extra["monthday"] = _number(
            t("每月几日（不存在的日期会跳过）：", "Day of month (absent dates are skipped):"),
            current.timing.monthday if current else 1,
            1,
            31,
        )
    return Timing(recurrence=mode, timezone=zone, hour=hour, minute=minute, **extra)


def _content(data: dict) -> None:
    data["task"] = _text(t("任务需求 / 自然语言：", "Task / natural-language requirement:"), data.get("task", ""))
    mode = _ask(
        questionary.select(
            t("执行内容：", "Query mode:"),
            choices=[
                Choice(t("自然语言测绘（AI 在执行时生成查询）", "Natural language (AI plans queries at execution)"), "natural"),
                Choice(t("固定 FOFA 查询（多条用换行输入）", "Fixed FOFA queries (one per line)"), "query"),
            ],
            default="query" if data.get("queries") else "natural",
        )
    )
    if mode == "natural":
        data["queries"] = []
    else:
        value = _ask(
            questionary.text(
                t(
                    "FOFA 查询，每行一条（Alt+Enter 或 Esc, Enter 完成）：",
                    "FOFA queries, one per line (Alt+Enter or Esc, Enter to finish):",
                ),
                default="\n".join(data.get("queries", [])),
                multiline=True,
            )
        )
        data["queries"] = [line.strip() for line in value.splitlines() if line.strip()]
        if not data["queries"]:
            raise ValueError(t("固定查询不能为空。", "Fixed queries cannot be empty."))


def _limits(data: dict) -> None:
    data["max_records"] = _number(t("每轮最多资产数：", "Maximum assets per run:"), data.get("max_records", 1000), 1, 100000)
    data["max_pages"] = _number(t("每条查询最多页数：", "Maximum pages per query:"), data.get("max_pages", 10), 1, 1000)
    data["analyze"] = _ask(
        questionary.confirm(
            t("使用 AI 分析快照变化和风险线索？", "Use AI to analyze snapshot changes and risk signals?"), default=data.get("analyze", True)
        )
    )
    _alive_setting(data)


def _alive_setting(data: dict) -> None:
    value = data.get("check_alive")
    choice = _ask(
        questionary.select(
            t("存活检测设置（任务文字明确要求时优先）：", "Liveness (explicit task wording takes precedence):"),
            choices=[
                Choice(t("跟随全局默认", "Follow global default"), "inherit"),
                Choice(t("开启存活检测", "Enable liveness"), "on"),
                Choice(t("关闭存活检测", "Disable liveness"), "off"),
            ],
            default="inherit" if value is None else "on" if value else "off",
        )
    )
    data["check_alive"] = {"inherit": None, "on": True, "off": False}[choice]


def _alive_description(request: ScheduleRequest) -> str:
    enabled, source = resolve_liveness(request.task, request.check_alive, settings.fast_check.check_alive)
    reason = {
        "task_request": t("任务明确要求", "required by task"),
        "task_opt_out": t("任务明确关闭", "disabled by task"),
        "task_setting": t("任务开关", "task setting"),
        "global_default": t("全局默认", "global default"),
    }[source]
    return (t("开启", "Enabled") if enabled else t("关闭", "Disabled")) + f" · {reason}"


def _preview(request: ScheduleRequest) -> None:
    due = request.timing.next_after(datetime.now(timezone.utc))
    table = Table(title=t("计划任务预览", "Schedule preview"), show_header=False)
    for key, value in [
        (t("名称", "Name"), request.name),
        (t("任务", "Task"), request.task),
        (t("频率", "Frequency"), timing_label(request.timing, english=t("zh", "en") == "en")),
        (t("时区", "Timezone"), request.timing.timezone),
        (
            t("下次执行", "Next run"),
            due.astimezone(ZoneInfo(request.timing.timezone)).strftime("%Y-%m-%d %H:%M:%S")
            if due
            else t("已过期，请调整时间", "Expired; edit the run time"),
        ),
        (
            t("查询", "Queries"),
            "\n".join(request.queries)
            or t("执行时由 AI 规划；首次成功后固定查询口径", "AI plans at execution; successful query scope is then frozen"),
        ),
        (t("每轮上限", "Limits"), f"{request.max_records} assets · {request.max_pages} pages/query"),
        (t("AI 分析", "AI analysis"), str(request.analyze)),
        (t("存活检测", "Liveness"), _alive_description(request)),
    ]:
        table.add_row(key, escape(value))
    console.print(table)


def _manual(current: ScheduleRequest | None = None) -> ScheduleRequest | None:
    data = current.model_dump(mode="json") if current else {}
    if current is None:
        data["name"] = _text(t("任务名称：", "Task name:"))
        _content(data)
        data["timing"] = _timing().model_dump(mode="json")
        _limits(data)
    while True:
        request = ScheduleRequest.model_validate(data)
        _preview(request)
        action = _ask(
            questionary.select(
                t("调整设置：", "Edit settings:"),
                choices=[
                    Choice(t("保存任务", "Save schedule"), "save"),
                    Choice(t("修改名称", "Edit name"), "name"),
                    Choice(t("修改自然语言需求 / FOFA 查询", "Edit task / FOFA queries"), "content"),
                    Choice(t("调整时间、频率、时区", "Edit time, frequency, timezone"), "timing"),
                    Choice(t("调整查询上限与 AI 分析", "Edit limits / AI analysis"), "limits"),
                    Choice(t("设置存活检测", "Liveness settings"), "alive"),
                    Choice(t("取消，返回计划任务菜单", "Cancel and return"), "cancel"),
                ],
            )
        )
        if action == "save":
            return request
        if action == "cancel":
            return None
        previous = dict(data)
        try:
            if action == "name":
                data["name"] = _text(t("任务名称：", "Task name:"), request.name)
            elif action == "content":
                _content(data)
            elif action == "timing":
                data["timing"] = _timing(request).model_dump(mode="json")
                data["when"] = ""
            elif action == "limits":
                _limits(data)
            elif action == "alive":
                _alive_setting(data)
        except CancelForm:
            data = previous
            continue


def _ai(current: ScheduleRequest | None = None) -> ScheduleRequest | None:
    from core.schedule_planner import draft_schedule
    from providers.registry import ProviderRegistry, ProviderRouter

    instruction = _text(t("描述计划需求 / 调整要求：", "Describe the schedule / changes:"))
    if not instruction:
        raise CancelForm

    async def generate():
        registry = ProviderRegistry(settings, execution_mode="interactive")
        try:
            return await draft_schedule(ProviderRouter(registry), instruction, current)
        finally:
            await registry.aclose()

    with console.status(t("AI 正在解析计划…", "AI is drafting the schedule…")):
        request = asyncio.run(generate())
    return _manual(request)


def _pick(store) -> dict:
    items = store.list()
    if not items:
        raise ValueError(t("暂无计划任务。", "No schedules yet."))
    identifier = _ask(
        questionary.select(
            t("选择计划任务：", "Choose a schedule:"),
            choices=[
                Choice(f"{item['spec']['name']} · {_state_label(item['control_status'])} · {item['id'][:8]}", item["id"]) for item in items
            ],
        )
    )
    return store.get(identifier)


def _listing(store) -> None:
    table = Table(title=t("计划任务", "Scheduled tasks"))
    for label in [t("名称", "Name"), t("状态", "State"), t("频率", "Frequency"), t("下次执行（任务时区）", "Next run (task timezone)")]:
        table.add_column(label)
    for item in store.list():
        spec = item["spec"]
        due = (
            parse_iso_datetime(item["next_run"]).astimezone(ZoneInfo(spec["timing"]["timezone"])).strftime("%Y-%m-%d %H:%M:%S")
            if item["enabled"] and item["next_run"]
            else "—"
        )
        table.add_row(
            escape(spec["name"]),
            _state_label(item["control_status"]),
            timing_label(Timing.model_validate(spec["timing"]), english=t("zh", "en") == "en"),
            due,
        )
    console.print(table)
    worker = store.worker_status()["worker_recently_seen"]
    console.print(
        t("后台调度：", "Scheduler: ")
        + (
            t("最近有心跳", "recent heartbeat")
            if worker
            else t("未检测到心跳；请启动后台调度服务", "no heartbeat; start the scheduler service")
        )
    )


def schedule_menu() -> None:
    store = schedule_store()
    root = Path(settings.system.output_dir).resolve() / "schedules"
    section(t("计划任务管理", "Schedule manager"), t("AI 或手动设置 · 历史报告保留", "AI or manual settings · history retained"))
    choices = [
        Choice(t("1. AI 创建计划任务", "1. Create with AI"), "ai"),
        Choice(t("2. 手动创建计划任务", "2. Create manually"), "manual"),
        Choice(t("3. 修改任务内容 / 时间 / 频率", "3. Edit task / time / frequency"), "edit"),
        Choice(t("4. 暂停后续执行（当前轮继续）", "4. Pause future runs (current run continues)"), "pause"),
        Choice(t("5. 恢复任务", "5. Resume schedule"), "resume"),
        Choice(t("6. 停止任务（取消当前轮并禁用后续）", "6. Stop task (cancel current and future runs)"), "stop"),
        Choice(t("7. 查看执行历史", "7. Execution history"), "history"),
        Choice(t("8. 打开报告总目录", "8. Open report index"), "reports"),
        Choice(t("9. 启动本机后台调度", "9. Start local background scheduler"), "worker"),
        Choice(t("10. 删除计划任务（保留历史报告）", "10. Delete schedule (keep report archive)"), "delete"),
        Choice(t("0. 返回主菜单", "0. Back to main menu"), "back"),
    ]
    while True:
        _listing(store)
        action = None
        try:
            action = _ask(questionary.select(t("计划任务操作：", "Schedule action:"), choices=choices))
            if action == "back":
                return
            if action in {"ai", "manual", "edit"}:
                item = _pick(store) if action == "edit" else None
                current = ScheduleRequest.model_validate(item["spec"]) if item else None
                method = (
                    _ask(
                        questionary.select(
                            t("修改方式：", "Edit method:"),
                            choices=[Choice(t("手动设置", "Manual settings"), "manual"), Choice(t("AI 调整", "Adjust with AI"), "ai")],
                        )
                    )
                    if item
                    else action
                )
                request = _ai(current) if method == "ai" else _manual(current)
                if request:
                    saved = store.update(item["id"], request) if item else store.create(request)
                    console.print(t("已保存：", "Saved: ") + saved["id"] + f" · {_state_label(saved['control_status'])}")
            elif action == "delete":
                item = _pick(store)
                if _ask(
                    questionary.confirm(
                        t(
                            f"删除任务“{item['spec']['name']}”？将取消执行并从任务列表移除，历史报告保留。",
                            f"Delete '{item['spec']['name']}'? Cancel execution and remove from tasks; keep report history.",
                        ),
                        default=False,
                    )
                ):
                    store.delete(item["id"])
                    console.print(
                        t("任务已删除；历史报告可在报告总目录的归档区查看。", "Task deleted; reports remain in the index archive.")
                    )
            elif action in {"pause", "resume", "stop"}:
                item = _pick(store)
                if action == "stop":
                    store.stop(item["id"])
                    console.print(
                        t(
                            "已停止后续执行；后台将在约 1 秒内处理当前轮取消。历史报告保留。",
                            "Future runs stopped; an active worker handles cancellation within about 1 second. History retained.",
                        )
                    )
                else:
                    store.set_enabled(item["id"], action == "resume")
            elif action == "history":
                item = _pick(store)
                table = Table(
                    t("执行时间", "Started"), t("结果", "Status"), t("资产数", "Count"), t("HTML 报告 / 错误", "HTML report / error")
                )
                zone = ZoneInfo(item["spec"]["timing"]["timezone"])
                for row in store.runs(item["id"]):
                    result = row.get("result") or {}
                    table.add_row(
                        parse_iso_datetime(row["started_at"]).astimezone(zone).isoformat(),
                        row["status"],
                        str(result.get("count", "—")),
                        escape(result.get("reports", {}).get("html") or row.get("error") or "—"),
                    )
                console.print(table)
            elif action == "reports":
                index = write_schedule_index(store, root)
                console.print(str(index), markup=False)
                click.launch(str(index))
            elif action == "worker":
                if store.worker_status()["worker_recently_seen"]:
                    console.print(t("后台最近有心跳，无需重复启动。", "A scheduler heartbeat is present; no duplicate worker started."))
                else:
                    from service.scheduler_control import start_worker

                    result = start_worker(root)
                    console.print(t("已启动后台调度进程：", "Scheduler process started: ") + str(result["pid"]))
                    console.print(t("日志：", "Log: ") + result["log"], markup=False)
                    console.print(
                        t(
                            "请保持电脑开机且可联网；服务器开机自启见 README 的 systemd 配置。",
                            "Keep the machine awake and online; see README for systemd autostart.",
                        )
                    )
            write_schedule_index(store, root)
        except CancelForm:
            # A nested form cancels only that operation; top-level cancellation returns to main.
            if action is None:
                return
            continue
        except Exception as exc:
            from pydantic import ValidationError

            detail = (
                "; ".join(str(error["msg"]).removeprefix("Value error, ") for error in exc.errors())
                if isinstance(exc, ValidationError)
                else str(exc)
            )
            console.print(t("操作未完成：", "Operation failed: ") + escape(detail))
