# Nuclei operation guide for FofaMap hosts

This guide describes the workflow. Use `nuclei_guide` for the actual installed engine's help snapshot and `nuclei_capabilities` for installation/enablement state. `fofamap --update` refreshes the help snapshot after a successful engine/template update. Updating the executable outside FofaMap invalidates the snapshot by executable identity, size and modification time. `refresh=true` forces a fresh read. A help snapshot does not automatically change approval policy or adapter semantics.

Primary references:
- https://docs.projectdiscovery.io/opensource/nuclei/running
- https://docs.projectdiscovery.io/templates/protocols/network
- https://docs.projectdiscovery.io/templates/protocols/dns
- https://docs.projectdiscovery.io/templates/protocols/javascript/introduction
- https://docs.projectdiscovery.io/templates/protocols/javascript/modules/net

## Recommend, customize, approve, execute

1. Confirm the user's authorized targets. FOFA results are observations, not proof that neighboring IPs, ICP matches or certificate neighbors are owned by the user.
2. Call `nuclei_capabilities` and `nuclei_guide`. If missing, install the official executable/templates for that worker. MCP scanning requires `FOFAMAP_ENABLE_SCANNING=true` and a private `FOFAMAP_SCAN_APPROVAL_SECRET` of at least 24 characters. Do not print that secret or persist it in a host MCP config.
3. Call `nuclei_templates(keyword, protocol)` for the exact available IDs, severity and template-defined ports. TCP templates and JavaScript templates can contain their own destination ports/hosts. Inspect these before approval; an input port alone is not a guarantee that a third-party template stays on that port.
4. Call `nuclei_recommend(intent, assets, targets)` to draft up to three service-specific proposals. Present the command, reason, target list, template scope, limits and coverage in the user's language. The rule-based suggestions are a starting point: explain why they fit the actual task and discard unsuitable proposals. Unclassified services are returned for explicit template selection rather than being silently treated as Web.
5. The user chooses a proposal or supplies custom options. `nuclei_customize(base_plan, parameters)` supports `-rl`, `-c`, `-timeout`, `-retries`, `-severity`, `-pt`, `-id`, `-t`, `-headless`, `-code`, `-file` and `-ni`. These update a typed draft only. Targets/output files cannot be retargeted through command text. Unsupported options fail explicitly; use the typed fields or extend the adapter deliberately. Never execute a pasted shell command as a substitute for approval.
6. Call `nuclei_plan` for the selected/customized draft, then show its exact targets/templates/protocols, flags and limits. Obtain explicit approval for that scope. Any later scope or parameter change requires a new plan.
7. Call `nuclei_execute` with that plan ID and one-time token. If the engine is missing, ask Y=download official binary/templates or N=manual installation. Only explicit Y permits retry with `install_if_missing=true`; N does not download or scan. Installation can take time. After readiness, execution returns `running`. Keep the same MCP server alive and poll `fofa_job_status(job_id)` until `completed` or `failed`; `running` is not success. Progress includes elapsed seconds, engine-reported percent/requests/total/rps/errors, loaded template/target counts and match count. Missing engine stats are unknown, never fabricated. Use `fofa_job_cancel` to stop an active scan in the same server; cancelled/partial output is not a completed scan.
8. Completed jobs contain grouped findings, template IDs, protocol, descriptions/remediation when provided by the template, JSONL/log/summary paths and HTML/Markdown report paths. Report automated findings as requiring verification, distinguish raw matches from grouped issues, and state the scope. A baseline run does not cover all CVEs.
9. To combine actual scan findings with host AI analysis, pass the completed ID as `scan_job_id` to `fofa_render_report`, together with the host's summary/advice and actual inventory. It attaches only the trusted job's stored scan artifact; no arbitrary file path is accepted.

## Targets and engines

| Asset | Typed target | Template protocol |
|---|---|---|
| HTTP/HTTPS | `https://example.com:8443/` | `http` |
| TCP service (SSH, Redis, MongoDB, SMB, RDP, FTP, databases) | `tcp://example.com:6379` | `tcp` or suitable service-specific `javascript` |
| TLS service | `tls://example.com:636` | `ssl` or a TCP/JavaScript template that explicitly establishes TLS |
| DNS records | `dns://example.com` | `dns`; a domain is not a custom resolver endpoint |
| UDP service | `udp://example.com:1161` | a reviewed `javascript`/Code UDP template; **`udp` is not a native `-pt` filter** |
| Browser workflow | explicit HTTP(S) URL | `headless`, with `enable_headless=true` |
| WebSocket / WHOIS / Code / File | engine/template-specific | explicitly selected protocols; Code/File require their enable flags and trusted templates |

Service schemes normalize to native Nuclei `host:port`, preserving explicit ports and bracketed IPv6. Plain legacy domains retain HTTPS behavior; use `dns://` for DNS. Do not invent a port for a non-Web service. Code/File are explicit engine options; the remote-asset target parser does not accept arbitrary local file paths. No local disk audit is implied.

Headless depends on an available browser. Code/File and external OAST are separate, approval-bound options; `allow_oast` defaults false. Web checks default to the existing 10-template Web/TLS baseline. Known SSH/MySQL/MongoDB/Redis/RDP/SMB detection IDs can be selected, but detection alone is not a full service security assessment. Other templates must be explicitly allowlisted or included in an approved all-template scope.

## Limits, errors and evidence

Typed limits: `rate_limit` default 5/s, `concurrency` 2, `request_timeout` 10 s, `retries` 0, `max_duration` 300 s. The overall deadline is enforced by the worker, not an invented Nuclei flag. Automatic redirects and OAST are disabled by default. Preserve exact scope when retrying an environmental failure.

No executable, zero loaded templates/targets, nonzero exit, cancellation and timeout are errors, not a clean scan. The worker stops its process on cancellation/deadline. Keep the server/session running for background jobs. Process restarts do not resume an interrupted scan automatically.

## AI target selection switch

CLI `--scan-ai-dedupe` enables a configured-model review before approval; `--no-scan-ai-dedupe` disables it. The default is `system.scan_ai_dedupe` (false), editable through menu 14. The approval menu can toggle it for the current run. The full audit is saved as `scan-selection.json` and included in MD/HTML/JSON reports. Selection failures block execution until retried or explicitly disabled.

For host-AI workflows, call `nuclei_select_targets(intent, targets, assets)` to get numbered candidates, then supply `decisions=[{id,action,reason,duplicate_of}]`. Actions are `keep`, `exclude` and `duplicate`. IDs cannot invent targets; duplicates must reference an identical canonical endpoint. Missing decisions keep candidates. Distinct virtual hosts, protocols, ports and paths remain separate even if they share IPs/titles. Present all exclusions; the selected scope still requires a new exact approved plan. The tool never invokes FofaMap's model; host AI does the reasoning.

## CLI progress and cancellation

Nuclei receives `-no-stdin -stats -sj -si 1` plus an automatically allocated local metrics port (not port 0, which breaks periodic statistics on older engines). FofaMap owns Esc/Ctrl+C, reads engine JSON statistics and updates one terminal panel. Redirected output uses throttled progress lines. On cancellation/deadline the process group is reclaimed and partial JSONL/logs are retained, marked incomplete. Esc at the approval menu returns without creating a scan.

A zero-match result with network/TLS errors or fake-IP (198.18.0.0/15) DNS answers is marked `inconclusive` with diagnostics in job metadata, Markdown and HTML. FofaMap does not change the user's proxy settings. No matches is never proof of no vulnerabilities.

Custom syntax examples: `-rl 10 -c 3`, `-timeout 8 -retries 1`, `-pt tcp -id redis-detect -severity info`. Key=value syntax is not supported. `nuclei_guide` returns a compact overview by default; request `section="flags"` or `section="full"` deliberately. Template keyword matching uses ID/name/tags word boundaries; `tag:rdp` matches tags, so `rdp` does not match `wordpress` by substring.
