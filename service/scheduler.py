"""Persistent passive-mapping scheduler. Run as a service or invoke --once from cron."""

from __future__ import annotations

import argparse
import asyncio
import json
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from config import load_config, settings
from core.agent import AgentQuery, AgentRun, AgentState, AgentStep, FofaAgent, _asset_identity, _local_search_summary
from core.client import FofaClient
from core.liveness import probe_scheduled_assets, resolve_liveness
from core.models import SearchRequest
from core.report import write_agent_report
from core.schedules import (
    ScheduleInactiveError,
    ScheduleRequest,
    ScheduleStore,
    append_change_report,
    compare_snapshots,
    write_schedule_index,
)
from providers.registry import ProviderRegistry, ProviderRouter
from service.paths import database_url, output_root
from utils.datetime_compat import parse_iso_datetime


def schedule_store() -> ScheduleStore:
    return ScheduleStore(database_url())


async def execute_schedule(item: dict, store: ScheduleStore) -> dict:
    request = ScheduleRequest.model_validate(item["spec"])
    run_id = store.begin_run(item["id"])
    started_at = datetime.now(timezone.utc).astimezone(ZoneInfo(request.timing.timezone))
    registry = ProviderRegistry(settings, execution_mode="service")
    router = ProviderRouter(registry)
    folder = output_root() / "schedules" / item["id"] / run_id
    try:
        async with FofaClient(max_retries=1) as client:
            await client.account()
            if not request.queries:
                run = await FofaAgent(client, router).run(
                    request.task,
                    max_records=request.max_records,
                    max_pages=request.max_pages,
                    fields=request.fields,
                    smart_fields=False,
                    report_language=request.language,
                    sample=False,
                )
                if run.action.value != "fofa_search":
                    raise ValueError(
                        "Scheduled trend tracking needs an asset inventory, not host/stats aggregate mode; supply explicit queries"
                    )
            else:
                run = AgentRun(intent=request.task, fields=request.fields)
                seen = set()
                complete = True
                for query in request.queries:
                    remaining = request.max_records - len(run.assets)
                    if remaining <= 0:
                        complete = False
                        break
                    query_run = AgentQuery(query=query, source="schedule", strategy="precision")
                    run.queries.append(query_run)
                    run.query = run.query or query
                    if request.analyze:
                        run.steps.append(AgentStep(state=AgentState.EXECUTE, detail=f"Scheduled fixed query: {query}"))
                    async for page in client.iter_search(
                        SearchRequest(
                            query=query,
                            fields=request.fields,
                            size=min(100, remaining),
                            max_records=remaining,
                            max_pages=request.max_pages,
                        )
                    ):
                        query_run.pages += 1
                        query_run.available_count = page.total
                        query_run.result_count += len(page.records)
                        for record in page.records:
                            identity = _asset_identity(record.values)
                            if identity not in seen:
                                seen.add(identity)
                                run.assets.append(record.values)
                                run.asset_confidence.append("precision")
                                query_run.new_assets += 1
                    if query_run.available_count is None or query_run.result_count < query_run.available_count:
                        complete = False
                run.result_count = len(run.assets)
                run.state = AgentState.COMPLETED
                run.sample_stop_reason = "complete" if complete else "page_window"
            if run.error:
                raise ValueError(str(run.error))
            # Liveness has its own opt-in/default; Nuclei scanning still needs separate approval.
            run.scan_requested_by_user = False
            run.scan_recommended = False
            run.scan_targets = []
            run.scan_template_ids = []
            current_settings = load_config()
            alive_enabled, alive_source = resolve_liveness(request.task, request.check_alive, current_settings.fast_check.check_alive)
            run.liveness = await probe_scheduled_assets(
                run,
                enabled=alive_enabled,
                source=alive_source,
                timeout=current_settings.fast_check.timeout,
            )
            if run.liveness.get("checked_at"):
                run.liveness["checked_at"] = (
                    parse_iso_datetime(run.liveness["checked_at"])
                    .astimezone(ZoneInfo(request.timing.timezone))
                    .isoformat(timespec="seconds")
                )
            if alive_enabled and not request.analyze:
                run.summary, run.summary_source = _local_search_summary(run, language=request.language), "local"
            history = [row for row in store.runs(item["id"], 365) if row["status"] == "completed"]
            previous = history[0]["result"]["snapshot"] if history else None
            delta = compare_snapshots(previous, run)
            if request.analyze:
                try:
                    result = await router.generate(
                        "summarizer",
                        system=(
                            f"Write a professional defensive asset-change briefing in {request.language}. "
                            "Start with ## Conclusion (or ## 结论). Describe additions, missing records, service changes and priorities. "
                            "Use only supplied evidence. A missing indexed record is not an offline service; "
                            "a fingerprint is not a vulnerability. "
                            "Use supplied liveness observations when enabled; do not claim this run was passive-only then. "
                            "HTTP 4xx/5xx is still a response; TLS indicates certificate trust failure; Open means TCP connectivity. "
                            "A timeout is not proof of asset removal. No Nuclei scan was executed. "
                            "If comparisons are incomplete or scope changed, explicitly limit the conclusion. "
                            "is_initial_baseline=false means a previous reference exists, not that the baseline is missing. "
                            "Do not invent urgency/priority labels or absence of risk from unchanged counts. Keep it under 350 words."
                        ),
                        prompt=json.dumps(
                            {
                                "task": request.task,
                                "comparison": {
                                    **{key: value for key, value in delta.items() if key != "baseline"},
                                    "is_initial_baseline": delta["baseline"],
                                    "added": delta["added"][:20],
                                    "removed": delta["removed"][:20],
                                    "changed": delta["changed"][:20],
                                },
                                "snapshot_count": run.result_count,
                                "assets": run.assets[:20],
                                "liveness": run.liveness,
                            },
                            ensure_ascii=False,
                        ),
                    )
                    run.summary, run.summary_source = result.text, "model"
                except Exception:
                    run.summary, run.summary_source = _local_search_summary(run, language=request.language), "local"
            run.route_events = [event.model_dump(mode="json") for event in router.events]
            run.started_at = started_at
            run.finished_at = datetime.now(timezone.utc).astimezone(ZoneInfo(request.timing.timezone))
            for step in run.steps:
                step.started_at = step.started_at.astimezone(ZoneInfo(request.timing.timezone))
            report = write_agent_report(run, folder / "report.md", language=request.language)
            at = run.finished_at.astimezone().isoformat(timespec="seconds")
            trend = [
                {
                    "at": parse_iso_datetime(row["finished_at"])
                    .astimezone(ZoneInfo(request.timing.timezone))
                    .isoformat(timespec="seconds"),
                    "count": row["result"]["count"],
                }
                for row in reversed(history[:29])
            ]
            trend.append({"at": at, "count": run.result_count})
            append_change_report(report, delta, trend, request.language)
            snapshot = {
                "assets": run.assets,
                "count": run.result_count,
                "complete": delta["complete"],
                "query_fingerprint": delta["query_fingerprint"],
            }
            payload = {"run": run.model_dump(mode="json"), "changes": delta, "trend": trend, "liveness": run.liveness}
            folder.mkdir(parents=True, exist_ok=True)
            data_path = folder / "report.json"
            data_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
            result = {
                "count": run.result_count,
                "queries": [q.query for q in run.queries],
                "snapshot": snapshot,
                "reports": {"markdown": str(report), "html": str(report.with_suffix(".html")), "json": str(data_path)},
                "changes": {key: len(delta[key]) for key in ["added", "removed", "changed"]},
                "comparable": delta["comparable"],
                "baseline": delta["baseline"],
                "liveness": run.liveness,
            }
            store.finish_run(item, run_id, result)
            return result
    except asyncio.CancelledError:
        store.finish_run(item, run_id, None, "Execution cancelled; no empty snapshot was recorded", cancelled=True)
        raise
    except Exception as exc:
        store.finish_run(item, run_id, None, str(exc))
        return {"error": str(exc)}
    finally:
        await registry.aclose()
        write_schedule_index(store, output_root() / "schedules")


async def run_due(store: ScheduleStore | None = None) -> list[dict]:
    store = store or schedule_store()
    store.heartbeat()
    outcomes = []

    async def pulse():
        while True:
            await asyncio.sleep(30)
            store.heartbeat()

    ticker = asyncio.create_task(pulse())
    try:
        for item in store.claim_due():
            if not store.get(item["id"], include_deleted=True)["enabled"]:
                # A task can be paused after the batch was claimed but before it starts.
                store.release_claim(item["id"])
                continue
            task = asyncio.create_task(execute_schedule(item, store))

            async def watch_stop(identifier=item["id"], running=task):
                while not running.done():
                    if store.get(identifier, include_deleted=True)["stop_requested"]:
                        running.cancel()
                        return
                    await asyncio.sleep(1)

            watcher = asyncio.create_task(watch_stop())
            try:
                outcomes.append(await asyncio.wait_for(task, timeout=3300))
            except ScheduleInactiveError:
                store.release_claim(item["id"])
                outcomes.append({"schedule_id": item["id"], "status": "cancelled"})
            except asyncio.CancelledError:
                if not store.get(item["id"], include_deleted=True)["stop_requested"]:
                    raise
                outcomes.append({"schedule_id": item["id"], "status": "cancelled"})
            except asyncio.TimeoutError:
                outcomes.append({"schedule_id": item["id"], "error": "Scheduler run deadline exceeded; lease will recover"})
            finally:
                watcher.cancel()
                await asyncio.gather(watcher, return_exceptions=True)
    finally:
        ticker.cancel()
        await asyncio.gather(ticker, return_exceptions=True)
    return outcomes


def main() -> None:
    parser = argparse.ArgumentParser(description="FofaMap passive asset-mapping scheduler")
    parser.add_argument("--once", action="store_true", help="Run due schedules once and exit (cron/systemd timer compatible)")
    parser.add_argument("--interval", type=int, default=30, help="Polling interval in seconds")
    args = parser.parse_args()
    if not 1 <= args.interval <= 60:
        parser.error("interval must be 1–60 seconds")

    async def loop():
        while True:
            result = await run_due()
            if result:
                print(
                    json.dumps(
                        [{key: value for key, value in row.items() if key not in {"snapshot", "queries"}} for row in result],
                        ensure_ascii=False,
                    ),
                    flush=True,
                )
            if args.once:
                return
            await asyncio.sleep(args.interval)

    asyncio.run(loop())


if __name__ == "__main__":
    main()
