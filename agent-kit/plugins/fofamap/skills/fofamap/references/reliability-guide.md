# Reliable MCP execution

## Errors

Failures use MCP `isError=true`. The first text content contains JSON, possibly after an SDK `Error executing tool …:` prefix; parse the JSON object. Do not assume `structured_content` exists for failures.

Fields: `error`, `code`, `api_code` when provided, `message`, `retryable`, `action`, `tool`. SDK argument validation returns field/type/message details without echoing submitted values. Typical actions:

| Code | Action |
|---|---|
| invalid_query | repair_query; no network for locally rejected syntax |
| cursor_expired / api_code=40070 (legacy alias 40870) | restart_search; do not present page 1 as a continuation |
| auth_failed / api_code=-700 | configure_credentials |
| quota_exhausted | stop_and_check_quota |
| permission_denied | check_membership |
| rate_limited | retry_with_backoff |
| not_found | check_id |
| scanning_disabled | configure_scanning |
| approval_required | obtain_new_approval |
| invalid_argument | correct_parameters |

Local validation covers known fields, quotes/escapes, grouping and operator operands. It does not certify FOFA semantic validity, membership or the existence of an app. Consult focused `fofa_syntax(keyword=...)` and `fofa_rules`; repair a server-rejected expression once, preserving collected evidence.

## Jobs and deadlines

`fofa_agent_run(use_fofamap_model=true)` responds with `job_id`, `pending`, `poll_tool`, `cancel_tool`. Poll `fofa_job_status` until completed/failed/cancelled. `max_duration` bounds model/FOFA collection (default 600 s, 10–3600). `fofa_job_cancel` stops a running Agent, scan or export in the same server and waits for cleanup. Cancellation cannot refund calls already incurred. A client call timing out does not itself confirm cancellation; inspect status and explicitly cancel if needed. Keep that MCP server alive; stored metadata persists, but a hard process restart does not resume work. Cross-server cancellation is rejected rather than pretending to stop someone else's worker.

Completed Agent metadata contains a bounded briefing; full rows/events are in `artifact_path`/`full_result_path`. The top-level status sentence does not duplicate the briefing. Larger results should remain artifacts.

## Deduplication and quotas

Searches deduplicate canonical endpoint + IP + port + protocol. Different virtual hosts/protocols/ports remain distinct. Known continuation cursors retain seen keys for 10 minutes in the current process (up to 64 chains and 10000 seen keys); unknown/expired/restarted chains cannot guarantee cross-call deduplication. FOFA cursors are not stable snapshots. Deduplicate again in durable downstream storage. Removed duplicates still count toward fetched/billed records and may make the returned unique count smaller than the cap.

`fofa_search(observe_cost=true)` reads account balances before and after the bounded request; this adds two account calls. `usage` reports actual request attempts, raw records fetched, unique records returned, API-reported consumed fpoint and its source. A reported zero stays zero; absent cost stays null/not_reported. Balance deltas are observations, can be cached/delayed or include other activity, and are not a charge calculation. `-1` is the upstream sentinel, not negative spending. Exports and Agent jobs include usage receipts too. Model tokens/cost are separate from FOFA points. Page size/count limits constrain reads; no hard monetary estimate is invented without a tariff from the API. `cost_budget` stops subsequent pages after reported consumption reaches it; it cannot guarantee a pre-billing hard cap when charges are absent or a page itself costs more.

Host profiles, stats and exposure reviews also include `usage`. Host record counts represent one aggregate profile, not its ports; stats return buckets and report zero inventory rows. Exposure receipts include both stats and search requests/charges. Reported fpoint sums only charges present in API responses; it is not a complete bill when some responses omit cost. `fofa_account.data.fofamap` identifies the running version and build date; `--check` exposes the same build metadata.

MCP search caps are 1000 records / 20 pages; use `fofa_export` (up to 1000000 explicitly bounded records) for larger inventories. `total` is the upstream matched population, never the number actually collected.

## Installation and runtime

Generated launches use an absolute Python/server path and cwd where supported. Reinstall preserves env/custom cwd/timeouts; paths remain readable Unicode. If a GUI host has no cwd support, service DB/output defaults are rooted in the source checkout or user state directory, not its profile directory. Override explicitly with `FOFAMAP_CONFIG`, `FOFAMAP_STATE_DIR`, `FOFAMAP_DATABASE_URL` as needed. New FOFA operations reload credentials from config/environment/Keyring. Environment changes outside a running process still require respawning that process.

Run `python /absolute/source/mcp_server.py --check` to inspect loaded entry, Python, cwd, state paths and all 31 tools without FOFA quota. If a bare `fofamap-mcp` loads old site-packages, reinstall the current wheel in that same interpreter or use the generated absolute launch; do not delete arbitrary installed files by guesswork.

Before an upgrade is accepted, run `fofamap-mcp --check --expect-version <release> --expect-build-date <date> --expect-source <source-root>` and `fofamap integrate --agent <host> --check-stale`. These are quota-free. A mismatch exits nonzero; re-install the current release or re-import the current Skill for that host and check again. The MCP check reports the remote build and negotiated protocol, not a guessed protocol.

Nuclei output is drained in byte chunks with bounded log prefixes, so the pipe limit is not a JSONL line-size ceiling. `-ot` targets `template-encoded`; a `template` path field or a large HTTP response does not prove embedded-template output. It is an output optimization, never the long-line safety boundary.
