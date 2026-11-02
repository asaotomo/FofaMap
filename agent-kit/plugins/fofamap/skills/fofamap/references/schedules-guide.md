# Scheduled mapping and historical reports

Use this workflow only for the user's requested FofaMap mapping schedules. These are product-owned persistent jobs, not reminders in the host chat.

## Create accurately

1. Separate the mapping task from the timing phrase. Confirm the IANA timezone (default `Asia/Shanghai`) and show the resolved local time, recurrence and next execution. Never silently guess an ambiguous date or AM/PM.
2. `fofa_schedule_create` accepts a `ScheduleRequest`: `name`, `task`, `when` or structured `timing`, optional fixed `queries`, `fields`, `max_records`, `max_pages`, `language`, `analyze`, and optional `check_alive` (null follows the current global default).
3. Supported `when` examples: `每1分钟`, `每10分钟`, `every 7 minutes`, `每天早上8点`, `每小时`, `每周一上午9点`, `每月1日8点`, `明天下午15:00`, or a full ISO datetime. For more exact host-side parsing use `timing={recurrence:interval/daily/hourly/weekly/monthly/once, timezone:Asia/Shanghai, hour:8, minute:0, weekday:0, monthday:1, run_at:...}`. For minute intervals use `timing={recurrence:interval, interval_minutes:10, timezone:Asia/Shanghai}`. The store persists its anchor; later runs retain cadence rather than drifting by each run duration. Minimum interval is 1 minute. Missed slots are skipped after a long run; the same task is not overlapped. Weekdays use Monday=0. A missing monthly date is skipped (31st does not become the last day). A past one-time task is rejected.
4. Prefer fixed FOFA queries verified with the user's scope before saving. Example scope translations: `domain="baidu.com" && city="Shanghai"`; `domain="iflytek.com" && city="Beijing"`. These are domain-scoped observations and not a complete inventory of those organizations. Resolve actual requested company/domain scope before use; do not claim these examples establish ownership.
5. Without supplied queries, the first run uses FofaMap's configured service-compatible model to plan an inventory. The first successful portfolio is frozen for later runs. With fixed queries, the scheduler can collect without a model; AI change analysis is optional and uses the configured service-compatible model. A host's interactive subscription alone is not an unattended model credential.
6. Inspect `worker` in the create/list result. **Saving a task does not start a scheduler.** A recent heartbeat comes from `fofamap-scheduler --interval 30`, or `fofamap-scheduler --once` invoked by cron/systemd. Do not promise timed execution until the worker is installed/running. Default precision is a polling interval plus task queue/runtime, not a hard real-time guarantee. Keep the machine and network available.

## Manage and read

- `fofa_schedule_list`: saved tasks, timezone/next due time, worker heartbeat.
- `fofa_schedule_update`: replace a spec while retaining history; a running task must finish before editing.
- `fofa_schedule_set_enabled`: pause/resume future executions. Pause does not interrupt an already-running measurement.
- `fofa_schedule_stop`: stop future runs and request current-run cancellation (worker checks every second). History and reports remain. Editing paused/stopped tasks preserves their state; explicitly resume when needed.
- `fofa_schedule_delete`: only on an explicit user deletion request; remove from task management, cancel the active run, prohibit edits/resume, and retain history/report files. The global index has an archive section. Deletion is idempotent and does not erase report files. Do not substitute delete for pause/stop.
- `fofa_schedule_history`: counts, deltas, status and report paths; large snapshots are excluded by default (`include_snapshots=true` is opt-in).

Reports live under `results/schedules/<schedule-id>/<run-id>/report.md`, `.html`, `.json`. Start at `results/schedules/index.html`; it links task history pages, and each history links all report formats. Indexes update on creation/edit and after success/failure. Links are relative so the whole folder can be copied/downloaded for offline reading. Dates are displayed in each task's timezone.

## Compare conservatively

Snapshots compare normalized host/port/protocol identities, with additions, missing entries and field changes. HTTP 80 and HTTPS 443 remain distinct. The first measurement is a baseline, not a historical increase. Subsequent reports include counts and trends over recent runs.

Only matching query/field scopes with complete snapshots support comparable indexed deltas. A changed query, truncated preview, page/budget limit or failed collection cannot prove disappearance; reports must label comparison limits. Failures create failed history records, not empty snapshots. FOFA index changes do not prove live service changes or confirmed vulnerabilities. Treat new management/database exposures as review leads, not automatic vulnerability findings.

Scheduled jobs collect FOFA records and generate reports. Optional HTTP/TCP liveness is separate from Nuclei scanning: explicit user wording requiring liveness overrides the switch, explicit opt-out disables it, otherwise check_alive true/false overrides and null follows the global setting reloaded each run. Do not let a model invent false to override a user's default setting. Every run probes freshly and retains unresponsive assets; response changes are not inventory additions/removals. The index and report show checked/responding counts. They do not reuse Nuclei tokens or automatically activate vulnerability scans; Nuclei still needs an approved exact plan.

The standalone terminal menu is available from main-menu item 15, or `fofamap schedule --schedule-action menu`. It supports AI drafts, manual frequency/time/query editing, pause/resume/stop/delete, history, report index and starting a local detached worker.

All terminal selection/input prompts support Esc or Ctrl+C to go back, and selections include a Back choice. Cancellation must not change task state.
