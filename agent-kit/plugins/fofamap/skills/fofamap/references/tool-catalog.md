# FofaMap tool catalog

## MCP tools

| Tool | Purpose | Side effect |
|---|---|---|
| `fofa_validate_query` | Validate FOFA syntax locally | None; no quota use |
| `fofa_fields` | Read field tiers and membership capability matrix | None; no quota use |
| `fofa_account` | Read current account tier, permissions and quota | FOFA quota/read |
| `fofa_search` | Fetch one exact query. Omitting both caps returns one page of `size`; read `total`. Caps are 1000 records and 20 pages | FOFA quota/read |
| `fofa_search_next` | Continue immediately with the same `size` and opaque cursor. An expired cursor (`40070`; legacy alias `40870`) starts a new search | FOFA quota/read |
| `fofa_icon_search` | Fetch a public favicon, calculate its FOFA hash and search it | Public HTTP + FOFA quota/read |
| `fofa_host_profile` | Load one host aggregation. Official limit is one request per second | FOFA quota/read; requires Host API membership |
| `fofa_stats` | Aggregate the 12 official dimensions. Published result is the top 5. `product` is rejected locally. Wait 5 seconds between calls | FOFA quota/read; requires stats API membership |
| `fofa_syntax` | Official query operators and fields | None |
| `fofa_rules` | Search bundled FOFA library `app=` names with keyword/category and limit (default 50, max 200); category_summary lists all groups. Check verified/verified_at; legacy mappings are unverified. Call **before** `fofa_search` when the user names a product/OA/VPN. Use returned queries verbatim. | None |
| `fofa_export` | Start a bounded background export | Writes a local artifact |
| `fofa_job_cancel` | Cancel an active Agent, Nuclei or export job owned by the current server; already incurred charges are not refunded | Local cancellation |
| `fofa_job_status` | Read export, agent, or scan job state | None |
| `fofa_render_report` | Accept up to 10000 supplied rows without silent truncation; totals normally equal the rows; a disclosed subset needs `sampled=true` + `sample_stop_reason` and a consistent population. Write the HTML report from the host agent's briefing, advice, and reflection. Does not call FofaMap's model | Local file |
| `fofa_agent_run` | Optional. Plans with FofaMap's configured model only when `use_fofamap_model` is true. Returns a background job immediately; poll status or cancel. Never scans | FOFA/model quota/read |
| `fofa_exposure_review` | Product plus place and update-time window. Full result, port distribution and every default-port target unless `sample` is true. Simulated scan log. Never runs Nuclei | FOFA quota/read |
| `fofa_schedule_create` | Save one-time/recurring mapping with optional liveness, show next time and worker status | Writes schedule metadata |
| `fofa_schedule_list` | Read schedules and scheduler heartbeat | Local read |
| `fofa_schedule_update` | Edit a future task's spec while retaining history | Local write |
| `fofa_schedule_set_enabled` | Pause/resume future executions | Local write |
| `fofa_schedule_stop` | Stop future runs and request active-run cancellation; retain history | Local write |
| `fofa_schedule_delete` | Remove from task management, cancel execution; retain report archive | Destructive task metadata change |
| `fofa_schedule_history` | Read counts, snapshot deltas and MD/HTML/JSON paths | Local read |
| `nuclei_capabilities` | Inspect executable/version, supported target formats and scan enablement | Local read |
| `nuclei_templates` | List installed IDs, protocols, severity and declared network ports | Local read; no target |
| `nuclei_guide` | Read/refresh installed-version help snapshot after updates | Local help/cache |
| `nuclei_select_targets` | Prepare numbered candidates or validate host-AI decisions; no model calls/probing/execution. Show the audit before approval | Local read |
| `nuclei_recommend` | Up to 3 reasoned service-specific commands and typed draft plans | No scan/approval |
| `nuclei_customize` | Convert supported custom parameters to a typed draft | No shell execution |
| `nuclei_plan` | Create an expiring, exact active-scan plan | Requires scanning enabled and authorization |
| `nuclei_execute` | Consume one approval token and start an exact background scan; optional install_if_missing defaults false and requires separate download consent; poll fofa_job_status | Destructive/open-world |

## MCP resources

- `fofamap://fields`: versioned FOFA field catalogue and vip_level API matrix (`https://fofa.info/api`).
- `fofamap://rules`: bundled FOFA `app=` fingerprint library.
- `fofamap://account`: account capabilities and usage.
- `fofamap://jobs/{job_id}`: job metadata and artifact path.

DeepSeek Harness currently bridges MCP Tools only; MCP Resources and Prompts are unavailable there. Other hosts may expose resources through host-specific wrapper tools.

## Common query patterns

```text
domain="example.com"
cert="example.com"
app="nginx" && country="CN" && city="Hangzhou"
region="浙江"
product.version="1.6.10"
ip="203.0.113.10"
icon_hash="123456789"
after="2023-01-01"
```

`city` is English. `region` accepts English or Chinese inside China. `country` accepts a code or the Chinese name; prefer the code. `after` and `before` are FOFA update time. For named products, do not guess `app=` strings. Call `fofa_rules` (for example keyword `ThinkPHP` or `Nginx`) and paste the returned query. `fofa_agent_run` does this lookup automatically. A version fingerprint is exposure, not a confirmed vulnerability.

## Official capability checks

Verified 2026-11-01 against [query field appendix](https://fofa.info/api), [API limits](https://fofa.info/api/limit), [stats API](https://fofa.info/api/stats/statistical), and [membership plans](https://fofa.info/vip). Use `fofa_fields` for the versioned catalog, source URLs and effective page limits. The client enforces host (1/s) and stats (1/5s) limits across short-lived clients in the same process and event loop; separate processes still need coordination.

The VIP sales page now lists 44/60/62 query syntaxes for registered/personal/professional plans; old snapshots list 45/57/59. Export counts remain 34/37/41/48/51. `asset_type` is a stats dimension and a legacy compatibility return field, not one of the 51 official search-return appendix fields.

## Offline report conveniences

Report tables support click sorting, Shift multi-column sorting, and restoring original order. The asset table can export a selected displayed field as a deduplicated TXT of currently visible rows. These controls never query FOFA or start scanners; they export only the data already in the report. The icon tool keeps the root-favicon fast path and, on a missing root icon, checks at most three static HTML `rel=icon` candidates. It does not execute JavaScript; a dynamically inserted favicon needs its explicit image URL.

For full scanning workflow and limits, read [nuclei-guide.md](nuclei-guide.md). A completed scan job can be attached to `fofa_render_report(scan_job_id=...)` for an integrated host-AI report.

For recurring mapping, timezone parsing, worker installation and report indexes, read [schedules-guide.md](schedules-guide.md).

Read [reliability-guide.md](reliability-guide.md) for portable error envelopes, measured costs, async jobs and paging limits. The current server exposes 31 tools.
# Language and fields

`fofa_render_report` and `fofa_agent_run` accept `report_language=zh|en|both`; an omitted/null value follows the configured interface language. A report-language override does not change the UI preference. Ordinary CLI smart-field defaults are separate from the MCP search contract; use the field catalogue and pass explicit `fields` for repeatable host-agent queries.

