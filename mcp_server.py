"""FofaMap MCP 2.0 server (stdio by default, authenticated Streamable HTTP optionally)."""

from __future__ import annotations

import argparse
import asyncio
import hmac
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from pydantic import BaseModel, Field, ValidationError

from config import settings
from core.agent import FofaAgent, validate_query
from core.client import FofaClient
from core.exporter import export_pages
from core.fields import STATS_FIELDS, field_catalog
from core.models import ExportRequest, SearchRequest
from core.scanner import NucleiScanner
from core.scans import ScanApproval, ScanPlanRequest
from core.schedules import ScheduleRequest
from core.tool_errors import tool_guard
from core.usage_receipt import receipt
from core.version import BUILD_DATE, VERSION
from providers.registry import ProviderRegistry, ProviderRouter
from service.paths import database_url, output_root
from service.store import JobStore

try:
    from mcp.server.auth.provider import AccessToken
    from mcp.server.auth.settings import AuthSettings
    from mcp.server.mcpserver import Context, MCPServer
    from mcp.server.mcpserver.exceptions import ToolError
except ImportError as exc:  # clear migration failure instead of corrupting stdio
    raise RuntimeError(f"FofaMap {VERSION} requires mcp>=2,<3; install the {VERSION} dependencies") from exc


READ_ONLY = {"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": True}
LOCAL_READ = {"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False}
WRITE_SAFE = {"readOnlyHint": False, "destructiveHint": False, "idempotentHint": False, "openWorldHint": True}
SCAN_EXECUTE = {"readOnlyHint": False, "destructiveHint": True, "idempotentHint": False, "openWorldHint": True}

MCP_INSTRUCTIONS = (
    "FofaMap searches internet assets via FOFA. "
    "Follow the user's language for briefings and set report_language explicitly when requested; "
    "omitting report_language on fofa_render_report/fofa_agent_run follows the saved interface language. "
    "CLI smart-field preferences do not rewrite MCP fields; use fofa_fields suggestions and explicit fields. "
    "When the user names a product, OA, VPN, middleware, database, camera, CMS or ops panel, "
    "call fofa_rules first (no FOFA quota) and use the returned query values verbatim in fofa_search or fofa_stats. "
    "Never invent app= names. Empty keywords return a bounded catalog preview and category summary; "
    "inspect verified flags and focus with category/keyword. Legacy names have not been reverified. "
    "Host aggregation and stats APIs depend on FOFA vip_level; call fofa_account and fofa_fields first "
    "(the equivalent Resources are available on hosts that support them). "
    "Registered users have no host API; personal/education accounts have no stats API. "
    "Stats fields are only protocol, domain, port, title, os, server, country, asn, org, asset_type, fid and icp; "
    "product cannot be aggregated. "
    "fofa_search rejects invalid syntax locally. "
    "Map a requested count onto size (records per page), max_records (total cap) and max_pages. "
    "Examples: 只要前30个 means size=30, max_records=30, max_pages=1; "
    "前300条，每页100条 means size=100, max_records=300, max_pages=3. "
    "Do not raise a limit the user already stated. "
    "Omitting max_records and max_pages returns one page of size, not the full population; read total. "
    "Set both caps to fetch more, up to 1000 records and 20 pages. Use fofa_export for a larger file. "
    "Heavy return fields lower the effective page size: body to 500; cert/banner/header to 2000. "
    "fofa_render_report preserves up to 10000 supplied rows and rejects an inconsistent result_count. "
    "fofa_agent_run and fofa_exposure_review stay full unless sample is true. "
    "Call fofa_search_next immediately with the same size. "
    "An expired cursor (40870) means start a new fofa_search; page 1 is not the next page. "
    "A multi-page fofa_search already continues on numbered /search/all pages when its own cursor expires. "
    "city is English. region accepts English or Chinese. country accepts a code or the Chinese name. "
    "after and before are FOFA update time, not first-seen. "
    "Host aggregation is one request per second. Stats aggregation is one request per 5 seconds and returns the published top 5. "
    "product.version is a search field for business accounts and above, not a stats field. "
    "For a published FOFA hotspot, use the official topic query. A version hit is exposure, not a confirmed vulnerability. "
    "Use fofa_search for one exact query. "
    "MCP does not need FofaMap's configured model. The host agent parses the request, reflects on the rows, "
    "writes the briefing and advice, then calls fofa_render_report. "
    "Call fofa_agent_run only when the user explicitly wants FofaMap's own model, and set use_fofamap_model true. "
    "Its max_records is the deduplicated total across queries, not a promise to return the whole population. "
    "It never scans. "
    "fofa_agent_run returns a job immediately; poll fofa_job_status, cancel with fofa_job_cancel and keep this server running. "
    "Tool failures carry JSON in isError content text: error/code/api_code/retryable/action/message. "
    "Do not treat failures as zero matches. "
    "For a named product plus a place, a time window, port stats and a scan preview, call fofa_exposure_review. "
    "It returns the full update-time result, port distribution and every default-port target unless sample is true. "
    "It never runs Nuclei. A real scan still requires nuclei_plan and an explicit approval. "
    "Do not invent coverage ratios from the sample. "
    "Validate queries before spending quota. Never plan Nuclei scans without an explicit authorized scope. "
    "For scanning, inspect nuclei_capabilities, nuclei_guide and nuclei_templates, then present up to 3 nuclei_recommend "
    "commands with reasons. Let the user choose/customize through nuclei_customize before exact plan approval. "
    "When AI target selection is enabled, use nuclei_select_targets to review every candidate and record decisions before nuclei_plan. "
    "nuclei_execute returns a background job; poll fofa_job_status in the same server. Attach completed scan_job_id in fofa_render_report. "
    "For timed mapping use fofa_schedule_create/list/update/set_enabled/stop/delete/history. Show the timezone and resolved next_run. "
    "A saved schedule needs a running fofamap-scheduler worker; inspect its heartbeat before promising timed execution. "
    "Periodic jobs create snapshots, trend reports and a report index, and never auto-execute active scans."
)


class _TokenVerifier:
    async def verify_token(self, token: str) -> AccessToken | None:
        service_token = os.getenv("FOFAMAP_SERVICE_TOKEN", "")
        if service_token and hmac.compare_digest(token, service_token):
            return AccessToken(
                token=token,
                client_id="fofamap-static-token",
                scopes=["fofamap"],
                expires_at=None,
                resource=os.getenv("FOFAMAP_MCP_RESOURCE_URL"),
            )
        public_key = os.getenv("FOFAMAP_JWT_PUBLIC_KEY", "")
        issuer = os.getenv("FOFAMAP_JWT_ISSUER", "")
        if not public_key or not issuer:
            return None
        try:
            import jwt

            claims = jwt.decode(
                token,
                public_key,
                algorithms=["RS256", "ES256"],
                issuer=issuer,
                audience=os.getenv("FOFAMAP_JWT_AUDIENCE", "fofamap"),
            )
        except Exception:
            return None
        return AccessToken(
            token=token,
            client_id=str(claims.get("client_id") or claims.get("sub") or "jwt-client"),
            subject=claims.get("sub"),
            scopes=str(claims.get("scope", "fofamap")).split(),
            expires_at=int(claims["exp"]) if claims.get("exp") else None,
            resource=os.getenv("FOFAMAP_MCP_RESOURCE_URL"),
            claims=claims,
        )


class FofaMCPServer(MCPServer):
    """Normalize SDK argument validation failures without echoing secret input values."""

    async def call_tool(self, name, arguments, context=None):
        try:
            return await super().call_tool(name, arguments, context)
        except ToolError as exc:
            cause = exc.__cause__
            if isinstance(cause, ValidationError):
                details = [{"field": ".".join(map(str, row["loc"])), "type": row["type"], "message": row["msg"]}
                           for row in cause.errors(include_input=False, include_context=False)]
                raise ToolError(json.dumps({"error": True, "code": "invalid_argument", "retryable": False,
                                            "action": "correct_parameters", "tool": name,
                                            "message": "Tool arguments did not match its schema", "details": details},
                                           ensure_ascii=False)) from None
            raise


def _build_mcp() -> MCPServer:
    issuer = os.getenv("FOFAMAP_MCP_ISSUER_URL")
    resource = os.getenv("FOFAMAP_MCP_RESOURCE_URL")
    if issuer and resource:
        return FofaMCPServer(
            "fofamap_mcp",
            version=VERSION,
            instructions=MCP_INSTRUCTIONS,
            auth=AuthSettings(issuer_url=issuer, resource_server_url=resource, required_scopes=[]),
            token_verifier=_TokenVerifier(),
        )
    return FofaMCPServer("fofamap_mcp", version=VERSION, instructions=MCP_INSTRUCTIONS)


mcp = _build_mcp()
store = JobStore(database_url())


class SearchToolResult(BaseModel):
    summary: str
    query: str
    fields: list[str]
    records: list[dict[str, Any]]
    total: int | None = None
    next_cursor: str | None = None
    consumed: int | float | None = None
    pages: int = 1
    page_size: int = 100
    max_records: int = 100
    usage: dict[str, Any] = Field(default_factory=dict)
    duplicates_removed: int = 0


class GenericResult(BaseModel):
    summary: str
    data: dict[str, Any] = Field(default_factory=dict)


@mcp.tool(name="fofa_validate_query", annotations=LOCAL_READ)
@tool_guard
async def fofa_validate_query(query: str) -> GenericResult:
    """Perform local syntax checks without spending FOFA quota."""
    errors = validate_query(query)
    return GenericResult(
        summary="query is valid" if not errors else "query is invalid",
        data={"valid": not errors, "query": query, "errors": errors},
    )


@mcp.tool(name="fofa_fields", annotations=LOCAL_READ)
@tool_guard
async def fofa_fields(section: str = "summary", tier: str = "") -> GenericResult:
    """Return the versioned FOFA field and membership capability catalogue without using quota."""
    catalog = field_catalog()
    if section not in {"summary", "all", "stats", "memberships", "fields"}:
        raise ValueError("section: summary/all/stats/memberships/fields")
    if section != "all":
        catalog.pop("syntax", None)
    if section in {"stats", "memberships"}:
        catalog = {"source": catalog["source"], section: catalog[section]}
    elif section == "fields":
        catalog.pop("memberships", None)
    elif section == "summary":
        catalog["memberships"] = [
            {key: row[key] for key in ("vip_level", "name", "field_tier", "host_api", "stats_api")}
            for row in catalog["memberships"]
        ]
        catalog["full_catalog_hint"] = "Use section=memberships for limits, section=all for all details, or tier=personal."
    if tier:
        if tier not in {"registered", "personal", "professional", "business", "enterprise"}:
            raise ValueError("Unknown field tier")
        from core.fields import available_fields

        catalog = {"source": catalog["source"], "tier": tier, "fields": sorted(available_fields(tier))}
    return GenericResult(summary="FOFA field and membership catalogue; use section=all for full syntax", data=catalog)


@mcp.tool(name="fofa_account", annotations=READ_ONLY)
@tool_guard
async def fofa_account() -> GenericResult:
    """Return the current FOFA account tier, API capabilities and quota information."""
    async with FofaClient() as client:
        data = await client.account()
    return GenericResult(summary="FOFA account capabilities loaded",
                         data={**data, "fofamap": {"version": VERSION, "build_date": BUILD_DATE}})


def _require_valid_query(query: str) -> None:
    errors = validate_query(query)
    if errors:
        raise ToolError("invalid FOFA query, no quota spent: " + "; ".join(errors))


def _require_stats_fields(fields: list[str]) -> list[str]:
    accepted: list[str] = []
    rejected: list[str] = []
    for field in fields:
        name = field.strip()
        if not name:
            continue
        if name in STATS_FIELDS:
            accepted.append(name)
        else:
            rejected.append(name)
    if rejected or not accepted:
        allowed = ", ".join(sorted(STATS_FIELDS))
        bad = ", ".join(rejected) if rejected else "(empty)"
        raise ToolError(f"unsupported stats fields: {bad}. Allowed: {allowed}. product cannot be aggregated.")
    return accepted


def result_window(size: int, max_records: int | None, max_pages: int | None) -> tuple[int, int, int]:
    """Turn a requested page size and total cap into one FOFA window.

    With neither cap set, this is a single page of `size` records.
    """
    page_size = size
    if max_records is None and max_pages is None:
        return page_size, page_size, 1
    limit = page_size if max_records is None else max_records
    pages = max(1, (limit + page_size - 1) // page_size) if max_pages is None else max_pages
    return page_size, limit, pages


def _bounded(value: int, low: int, high: int, name: str) -> int:
    if not low <= value <= high:
        raise ToolError(f"{name} must be between {low} and {high}")
    return value


_CURSOR_SEEN: dict[str, tuple[float, str, set]] = {}


def _cursor_scope(request: SearchRequest) -> str:
    import hashlib

    return hashlib.sha256(json.dumps([request.query, request.fields, request.full], ensure_ascii=False).encode()).hexdigest()


def _record_key(row: dict) -> str:
    from core.agent import _asset_identity

    return json.dumps((*_asset_identity(row), str(row.get("ip") or "").strip().lower()), ensure_ascii=False)


def _continuation_seen(request: SearchRequest) -> set:
    import hashlib
    import time

    now = time.monotonic()
    for key in list(_CURSOR_SEEN):
        if _CURSOR_SEEN[key][0] < now:
            _CURSOR_SEEN.pop(key, None)
    if not request.cursor:
        return set()
    value = _CURSOR_SEEN.get(hashlib.sha256(request.cursor.encode()).hexdigest())
    return set(value[2]) if value and value[1] == _cursor_scope(request) else set()


def _remember_cursor(request: SearchRequest, cursor: str, seen: set) -> None:
    import hashlib
    import time

    if len(_CURSOR_SEEN) >= 64:
        _CURSOR_SEEN.pop(next(iter(_CURSOR_SEEN)))
    _CURSOR_SEEN[hashlib.sha256(cursor.encode()).hexdigest()] = (time.monotonic() + 600, _cursor_scope(request), set(list(seen)[-10000:]))


async def _search(request: SearchRequest, *, observe_cost: bool = False) -> SearchToolResult:
    _require_valid_query(request.query)
    records: list[dict[str, Any]] = []
    fields = list(request.fields)
    total = None
    cursor = None
    consumed = 0.0
    cost_reported = False
    pages = 0
    fallback = None
    seen = _continuation_seen(request)
    duplicates = 0
    before = after = None
    async with FofaClient() as client:
        if observe_cost:
            before = await client.account()
        async for page in client.iter_search(request):
            pages += 1
            fields = page.fields
            for record in page.records:
                key = _record_key(record.values)
                if key in seen:
                    duplicates += 1
                    continue
                seen.add(key)
                records.append(record.values)
            if page.total is not None:
                total = page.total
            cursor = page.next_cursor
            if page.consumed is not None:
                cost_reported = True
                consumed += float(page.consumed)
        if observe_cost:
            after = await client.account()
        usage = receipt(
            requests=getattr(client, "request_count", pages),
            fetched=getattr(client, "fetched_records", len(records)),
            returned=len(records),
            charged=consumed if cost_reported else None,
            before=before,
            after=after,
        )
        fallback = client.cursor_page_fallback
    more = bool(cursor) and (usage["records_fetched"] >= request.max_records or request.cursor is not None)
    if cursor:
        _remember_cursor(request, cursor, seen)
    summary = f"FOFA returned {len(records)} records in {pages} page(s); page size {request.size}; cap {request.max_records}."
    if total is not None:
        summary += f" Matched population is {total}."
    if fallback == "continued":
        summary += " The page cursor expired; later pages used numbered /search/all."
    elif fallback == "stopped":
        summary += " The page cursor expired again; kept the records already retrieved."
    if duplicates:
        summary += f" Removed {duplicates} duplicate endpoint records; continuation is not a stable FOFA snapshot."
    if request.max_records >= 1000:
        summary += " Use fofa_export for more than 1000 records."
    return SearchToolResult(
        summary=summary,
        query=request.query,
        fields=fields,
        records=records,
        total=total,
        next_cursor=cursor if more else None,
        consumed=consumed if cost_reported else None,
        usage=usage,
        duplicates_removed=duplicates,
        pages=pages,
        page_size=request.size,
        max_records=request.max_records,
    )


@mcp.tool(name="fofa_search", annotations=READ_ONLY)
@tool_guard
async def fofa_search(
    query: str,
    fields: list[str] | None = None,
    size: int = 100,
    max_records: int | None = None,
    max_pages: int | None = None,
    full: bool = False,
    observe_cost: bool = False,
) -> SearchToolResult:
    """Fetch one exact query. Omitting both caps returns one page of size; read total for the population."""
    page_size = _bounded(size, 1, 10_000, "size")
    if max_records is not None:
        max_records = _bounded(max_records, 1, 1000, "max_records")
    if max_pages is not None:
        max_pages = _bounded(max_pages, 1, 20, "max_pages")
    page_size, limit, pages = result_window(page_size, max_records, max_pages)
    return await _search(
        SearchRequest(
            query=query,
            fields=fields or settings.search.fields.split(","),
            size=page_size,
            max_records=limit,
            max_pages=pages,
            full=full,
        ),
        observe_cost=observe_cost,
    )


@mcp.tool(name="fofa_search_next", annotations=READ_ONLY)
@tool_guard
async def fofa_search_next(query: str, cursor: str, fields: list[str], size: int = 100, full: bool = False) -> SearchToolResult:
    """Continue with the opaque cursor immediately. An expired cursor (40870) is an error; start a new search."""
    page_size = _bounded(size, 1, 10_000, "size")
    return await _search(
        SearchRequest(
            query=query,
            cursor=cursor,
            continuous=True,
            fields=fields,
            size=page_size,
            max_records=page_size,
            max_pages=1,
            full=full,
        )
    )


@mcp.tool(name="fofa_icon_search", annotations=READ_ONLY)
@tool_guard
async def fofa_icon_search(
    url: str,
    fields: list[str] | None = None,
    size: int = 100,
    full: bool = False,
) -> SearchToolResult:
    """Fetch a public website favicon safely, calculate its FOFA MurmurHash3 value, and search matching assets."""
    from utils.helpers import IconHashCalculator

    query = await IconHashCalculator.get_hash(url)
    if not query:
        raise ValueError("unable to fetch a favicon or calculate its hash")
    page_size = _bounded(size, 1, 10_000, "size")
    return await _search(
        SearchRequest(
            query=query,
            fields=fields or settings.search.fields.split(","),
            size=page_size,
            max_records=page_size,
            max_pages=1,
            full=full,
        )
    )


@mcp.tool(name="fofa_host_profile", annotations=READ_ONLY)
@tool_guard
async def fofa_host_profile(host: str, detail: bool = True) -> GenericResult:
    """Get FOFA Host aggregation for one IP or DNS name. One request per second. Registered users have no Host API."""
    async with FofaClient() as client:
        data = await client.host_profile(host, detail=detail)
        data = {**data, "usage": receipt(requests=client.request_count, fetched=client.fetched_records, returned=1,
                                        charged=client.reported_charge)}
    return GenericResult(summary=f"Host profile loaded for {host}", data=data)


@mcp.tool(name="fofa_stats", annotations=READ_ONLY)
@tool_guard
async def fofa_stats(query: str, fields: list[str], size: int = 5) -> GenericResult:
    """Aggregate official dimensions. The published contract is the top 5. product cannot be aggregated. Wait 5 seconds between calls."""
    _require_valid_query(query)
    accepted = _require_stats_fields(fields)
    async with FofaClient() as client:
        data = await client.stats(query, accepted, size=size)
        data = {**data, "usage": receipt(requests=client.request_count, fetched=client.fetched_records, returned=0,
                                        charged=client.reported_charge)}
    return GenericResult(summary=f"Statistics loaded for {query}", data=data)


@mcp.tool(name="fofa_syntax", annotations=LOCAL_READ)
@tool_guard
async def fofa_syntax(section: str = "overview", keyword: str = "") -> GenericResult:
    """Return official FOFA query operators and syntax fields from the API appendix."""
    from core.syntax import syntax_catalog

    catalog = syntax_catalog()
    if section not in {"overview", "fields", "all"}:
        raise ValueError("section: overview/fields/all")
    if keyword:
        catalog["query_fields"] = [row for row in catalog["query_fields"] if keyword.lower() in row["field"].lower()]
    elif section == "overview":
        catalog["query_fields"] = catalog["query_fields"][:12]
    catalog["full_catalog_hint"] = "Use section=all or keyword=cert/product/port for focused fields"
    return GenericResult(summary="FOFA official query syntax", data=catalog)


@mcp.tool(name="fofa_rules", annotations=LOCAL_READ)
@tool_guard
async def fofa_rules(keyword: str = "", category: str = "", limit: int = 50) -> GenericResult:
    """Search a bounded rule preview; focus by category/keyword and inspect per-rule verification before product searches."""
    from core.rules import rules_catalog

    catalog = rules_catalog(keyword, category=category, limit=limit)
    return GenericResult(
        summary=f"{catalog['count']} shown of {catalog['matched_count']} matches; {catalog['total']} bundled rules", data=catalog
    )


async def _export(job_id: str, request: ExportRequest) -> None:
    store.update(job_id, status="running")
    try:
        path = output_root() / Path(request.filename or f"{job_id}.{request.format}").name
        async with FofaClient() as client:
            charged = 0.0
            reported = False

            async def pages():
                nonlocal charged, reported
                async for page in client.iter_search(request.search):
                    if page.consumed is not None:
                        reported = True
                        charged += float(page.consumed)
                    yield page

            artifact, count = await export_pages(pages(), path, request.format)
            usage = receipt(requests=client.request_count, fetched=client.fetched_records, returned=count,
                            charged=charged if reported else None)
        store.update(job_id, status="completed", result={"records": count, "usage": usage}, artifact_path=str(artifact.resolve()))
    except asyncio.CancelledError:
        store.update(job_id, status="cancelled", error={"code": "cancelled", "message": "Export cancelled; partial file may remain"})
        raise
    except Exception as exc:
        from core.tool_errors import error_payload

        store.update(job_id, status="failed", error=error_payload(exc, tool="fofa_export"))


@mcp.tool(name="fofa_export", annotations=WRITE_SAFE)
@tool_guard
async def fofa_export(request: ExportRequest) -> GenericResult:
    """Start a bounded export job; retrieve status and artifact through MCP resources."""
    _require_valid_query(request.search.query)
    job = store.create("export", request.model_dump(mode="json"))
    task = asyncio.create_task(_export(job["id"], request))
    _EXPORT_TASKS[job["id"]] = task
    task.add_done_callback(lambda done: _EXPORT_TASKS.pop(job["id"], None))
    return GenericResult(summary=f"Export job {job['id']} started", data=job)


_EXPORT_TASKS: dict[str, asyncio.Task] = {}


@mcp.tool(name="fofa_job_status", annotations=LOCAL_READ)
@tool_guard
async def fofa_job_status(job_id: str) -> GenericResult:
    """Read local export, agent or scan job state."""
    job = store.get(job_id)
    return GenericResult(summary=f"Job {job_id} is {job['status']}", data=job)


async def _planner_search_context(router: ProviderRouter, registry: ProviderRegistry, intent: str, enabled: bool | None) -> str:
    providers = getattr(registry, "providers", {})
    profile_for_task = getattr(router, "_profile_for_task", None)
    planner_name = profile_for_task("planner") if callable(profile_for_task) else ""
    planner = providers.get(planner_name) if planner_name else None
    if planner is None or not hasattr(planner, "web_search"):
        return ""
    profile = planner.profile
    previous = profile.search_enabled
    if enabled is not None:
        profile.search_enabled = enabled
    try:
        if not profile.search_enabled:
            return ""
        from core.research import build_search_context
        from core.showcase import showcase_for

        if showcase_for(intent) is not None:
            return ""
        brief = await build_search_context(router, planner, intent)
        return brief.notes
    except Exception:
        return ""
    finally:
        profile.search_enabled = previous


def _agent_progress(ctx: Context | None):
    def on_progress(run, step) -> None:
        if ctx is None:
            return

        async def notify() -> None:
            try:
                await ctx.report_progress(float(len(run.steps)), None, step.detail.replace("\n", " ")[:160])
            except Exception:
                return

        try:
            asyncio.get_running_loop().create_task(notify())
        except RuntimeError:
            return

    return on_progress


def _write_agent_artifacts(run, report_language: str) -> dict[str, str]:
    from core.report import write_agent_report

    destination = output_root() / f"mcp-{run.id[:8]}" / f"report_{datetime.now():%Y%m%d_%H%M%S}.md"
    scan_status = "not_requested"
    if run.scan_requested_by_user:
        scan_status = "awaiting_scan_plan_approval" if run.scan_ready else "no_scan_targets_or_incomplete_plan"
    elif run.scan_recommended:
        scan_status = "recommendation_only_no_user_authorization"
    path = write_agent_report(run, destination, scan_status=scan_status, language=report_language)
    html = path.with_suffix(".html")
    english = path.with_name(f"{path.stem}.en.html")
    return {
        "markdown": str(path),
        "html": str(html) if html.is_file() else "",
        "english_html": str(english) if english.is_file() else "",
    }


def _agent_brief(run, job_id: str, report: dict[str, str], *, size: int, max_pages: int) -> dict[str, Any]:
    preview = []
    confidences = list(run.asset_confidence)
    for index, asset in enumerate(run.assets[:20]):
        row = dict(asset)
        if index < len(confidences):
            row["evidence"] = confidences[index]
        preview.append(row)
    return {
        "job_id": job_id,
        "run_id": run.id,
        "state": run.state.value,
        "action": run.action.value,
        "query": run.query,
        "queries": [item.model_dump(mode="json") for item in run.queries],
        "result_count": run.result_count,
        "page_size": size,
        "max_pages": max_pages,
        "population_size": run.population_size,
        "population_aggs": run.population_aggs,
        "sample_limit": run.sample_limit,
        "sample_stop_reason": run.sample_stop_reason,
        "evidence_counts": run.evidence_counts,
        "website_candidates": [item.model_dump(mode="json") for item in run.website_candidates],
        "summary": run.summary,
        "asset_preview": preview,
        "assets_omitted": max(0, len(run.assets) - len(preview)),
        "report": report,
        "scan_executed": False,
        "error": run.error,
    }


class HostQuery(BaseModel):
    query: str
    purpose: str = ""
    strategy: str = "balanced"
    available_count: int = 0
    result_count: int = 0
    new_assets: int = 0


def _host_briefing(summary: str, advice: str, reflection: str, *, language: str) -> str:
    text = summary.strip()
    english = language == "en"
    advice_heading = "## Priority actions" if english else "## 处置优先级"
    reflection_heading = "## Coverage gaps" if english else "## 覆盖缺口"
    if advice.strip() and advice_heading not in text and "处置优先级" not in text and "Priority actions" not in text:
        text = f"{text}\n\n{advice_heading}\n{advice.strip()}"
    if reflection.strip() and reflection_heading not in text and "覆盖缺口" not in text and "Coverage gaps" not in text:
        text = f"{text}\n\n{reflection_heading}\n{reflection.strip()}"
    return text


@mcp.tool(name="fofa_render_report", annotations=WRITE_SAFE)
@tool_guard
async def fofa_render_report(
    intent: str,
    summary: str,
    query: str = "",
    advice: str = "",
    reflection: str = "",
    host_model: str = "",
    report_language: str | None = None,
    fields: list[str] | None = None,
    assets: list[dict[str, Any]] | None = None,
    queries: list[HostQuery] | None = None,
    result_count: int | None = None,
    population_size: int = 0,
    sampled: bool = False,
    sample_stop_reason: str = "",
    scan_advice: str = "",
    scan_job_id: str = "",
    scan_selection: dict[str, Any] | None = None,
) -> GenericResult:
    """Render host-agent text without calling FofaMap's model. Omitted report_language follows the saved interface language."""
    from core.agent import AgentAction, AgentQuery, AgentRun, AgentState
    from core.report import write_agent_report

    report_language = settings.system.language if report_language is None else report_language
    if report_language not in {"zh", "en", "both"}:
        raise ToolError("report_language must be zh, en, or both")
    briefing = _host_briefing(summary, advice, reflection, language="en" if report_language == "en" else "zh")
    if not briefing:
        raise ToolError("summary is required; the host agent writes the briefing, advice, and reflection")
    rows = list(assets or [])
    if len(rows) > 10_000:
        raise ToolError("assets is limited to 10000 report rows; use fofa_export for a larger inventory")
    if result_count is not None and result_count < len(rows):
        raise ToolError("result_count must be at least the number of supplied asset rows")
    if population_size < 0:
        raise ToolError("population_size must not be negative")
    if result_count is not None and result_count > len(rows) and not (sampled and sample_stop_reason.strip()):
        raise ValueError("result_count exceeds supplied rows; disclose the subset with sampled=true and sample_stop_reason")
    if population_size and result_count is not None and result_count > population_size:
        raise ValueError("result_count cannot exceed population_size")
    if population_size and len(rows) > population_size:
        raise ValueError("supplied rows cannot exceed population_size")
    planned = [
        AgentQuery(
            query=item.query,
            purpose=item.purpose,
            strategy=item.strategy if item.strategy in {"precision", "balanced", "hypothesis", "recall"} else "balanced",
            available_count=item.available_count,
            result_count=item.result_count,
            new_assets=item.new_assets,
            pages=1,
            source="host",
        )
        for item in (queries or [])
        if item.query.strip()
    ]
    model_name = host_model.strip() or "host"
    run = AgentRun(
        intent=intent,
        state=AgentState.COMPLETED,
        action=AgentAction.SEARCH,
        query=query or (planned[0].query if planned else None),
        fields=list(fields or []),
        result_count=len(rows) if result_count is None else result_count,
        population_size=population_size,
        sampled=sampled,
        sample_stop_reason=sample_stop_reason,
        assets=rows,
        assets_truncated=result_count is not None and result_count > len(rows),
        queries=planned,
        summary=briefing,
        summary_source="model",
        scan_advice=scan_advice.strip() or None,
        scan_selection=scan_selection or {},
        reflection_notes=[reflection.strip()] if reflection.strip() else [],
        route_events=[{"task": "summarizer", "provider": "host-agent", "model": model_name, "fallback": False}],
    )
    scan_status = "not_requested"
    if scan_job_id:
        scan_job = store.get(scan_job_id)
        if scan_job["kind"] != "scan_plan" or scan_job["status"] != "completed" or not scan_job.get("artifact_path"):
            raise ToolError("scan_job_id must refer to a completed Nuclei job with a result artifact")
        scope = ScanPlanRequest.model_validate(scan_job["payload"])
        run.scan_artifact = scan_job["artifact_path"]
        run.scan_requested_by_user = True
        run.scan_recommended = True
        run.scan_targets = scope.targets
        run.scan_template_ids = scope.template_ids
        run.scan_severities = scope.severities
        run.scan_protocols = scope.protocols
        run.scan_limits = {
            "rate_limit": scope.rate_limit,
            "concurrency": scope.concurrency,
            "max_duration": scope.max_duration,
        }
        scan_status = "completed"
    destination = output_root() / f"mcp-{run.id[:8]}" / f"report_{datetime.now():%Y%m%d_%H%M%S}.md"
    path = write_agent_report(run, destination, language=report_language, scan_status=scan_status)
    html = path.with_suffix(".html")
    english = path.with_name(f"{path.stem}.en.html")
    return GenericResult(
        summary="报告已用宿主智能体的文字生成，没有调用 FofaMap 配置的模型。",
        data={
            "run_id": run.id,
            "markdown": str(path),
            "html": str(html) if html.is_file() else "",
            "english_html": str(english) if english.is_file() else "",
            "model": "host-agent",
        },
    )


@mcp.tool(name="fofa_agent_run", annotations=READ_ONLY)
@tool_guard
async def fofa_agent_run(
    intent: str,
    max_records: int | None = None,
    max_pages: int | None = None,
    size: int = 100,
    sample: bool = False,
    report_language: str | None = None,
    web_search: bool | None = None,
    use_fofamap_model: bool = False,
    ctx: Context | None = None,
    max_duration: int = 600,
) -> GenericResult:
    """Start an Agent background job with use_fofamap_model=true; returns immediately.

    Poll fofa_job_status or cancel with fofa_job_cancel. Never scans. Omitted report_language follows interface language.
    """
    if not use_fofamap_model:
        raise ToolError(
            "MCP 默认由宿主智能体做语义解析、查询反思、报告和建议，不调用 FofaMap 配置的模型。"
            "请调用 fofa_rules、fofa_validate_query 和 fofa_search，再把写出的 summary、advice、reflection 交给 fofa_render_report。"
            "只有用户明确要求使用 FofaMap 自己的模型时，才设置 use_fofamap_model=true。"
        )
    from core.exposure import FULL_PAGE_CAP, FULL_RECORD_CAP, wants_sample

    report_language = settings.system.language if report_language is None else report_language
    if report_language not in {"zh", "en", "both"}:
        raise ToolError("report_language must be zh, en, or both")
    sampled = sample or wants_sample(intent)
    if max_records is None:
        max_records = 100 if sampled else FULL_RECORD_CAP
    if max_pages is None:
        max_pages = 3 if sampled else FULL_PAGE_CAP
    if not 1 <= max_records <= FULL_RECORD_CAP:
        raise ToolError("max_records must be between 1 and 1000000")
    if not 1 <= max_pages <= FULL_PAGE_CAP:
        raise ToolError("max_pages must be between 1 and 10000")
    if not 1 <= size <= 10_000:
        raise ToolError("size must be between 1 and 10000")
    if not 10 <= max_duration <= 3600:
        raise ValueError("max_duration must be 10–3600 seconds")
    job = store.create(
        "agent",
        {
            "intent": intent,
            "max_records": max_records,
            "max_pages": max_pages,
            "size": size,
            "sample": sampled,
            "report_language": report_language,
            "web_search": web_search,
            "max_duration": max_duration,
        },
    )
    task = asyncio.create_task(_run_agent_job(job["id"], dict(job["payload"])))
    _AGENT_TASKS[job["id"]] = task
    task.add_done_callback(lambda done: _AGENT_TASKS.pop(job["id"], None))
    return GenericResult(
        summary="Agent job accepted; poll fofa_job_status. Keep this MCP server running.",
        data={"job_id": job["id"], "status": "pending", "poll_tool": "fofa_job_status", "cancel_tool": "fofa_job_cancel"},
    )


_AGENT_TASKS: dict[str, asyncio.Task] = {}


async def _run_agent_job(job_id: str, payload: dict[str, Any]) -> None:
    store.update(job_id, status="running")
    registry = None
    try:
        registry = ProviderRegistry(settings, execution_mode="service")
        router = ProviderRouter(registry)

        async def collect():
            search_context = await _planner_search_context(router, registry, payload["intent"], payload.get("web_search"))
            async with FofaClient() as client:
                run = await FofaAgent(client, router).run(
                    payload["intent"],
                    max_records=payload["max_records"],
                    max_pages=payload["max_pages"],
                    size=payload["size"],
                    sample=payload["sample"],
                    search_context=search_context,
                    report_language="en" if payload["report_language"] == "en" else "zh",
                )
                usage = receipt(requests=client.request_count, fetched=client.fetched_records,
                                returned=len(run.assets), charged=client.reported_charge)
                return run, usage

        run, usage = await asyncio.wait_for(collect(), timeout=payload.get("max_duration", 600))
        report = _write_agent_artifacts(run, payload["report_language"]) if run.error is None else {}
        brief = _agent_brief(run, job_id, report, size=payload["size"], max_pages=payload["max_pages"])
        folder = output_root() / f"agent-{job_id}"
        folder.mkdir(parents=True, exist_ok=True)
        full = folder / "run.json"
        full.write_text(run.model_dump_json(indent=2), encoding="utf-8")
        # Keep a bounded preview in metadata; the full run remains an explicit local artifact.
        brief["summary"] = (run.summary or "")[:12000]
        brief["full_result_path"] = str(full)
        brief["usage"] = usage
        store.update(job_id, status="failed" if run.error else "completed", result=brief, error=run.error, artifact_path=str(full))
    except asyncio.CancelledError:
        store.update(
            job_id, status="cancelled", error={"code": "cancelled", "message": "Agent job cancelled; work already billed is not refunded"}
        )
        raise
    except Exception as exc:
        from core.tool_errors import error_payload

        store.update(job_id, status="failed", error=error_payload(exc, tool="fofa_agent_run"))
    finally:
        if registry is not None:
            await registry.aclose()


@mcp.tool(name="fofa_job_cancel", annotations=WRITE_SAFE)
@tool_guard
async def fofa_job_cancel(job_id: str) -> GenericResult:
    """Cancel an active Agent, Nuclei scan or export job in this server and reclaim its worker. Incurred charges are not refunded."""
    job = store.get(job_id)
    task = _AGENT_TASKS.get(job_id) or _SCAN_TASKS.get(job_id) or _EXPORT_TASKS.get(job_id)
    if job["status"] in {"completed", "failed", "cancelled"}:
        return GenericResult(summary="Job is already finished", data={"job_id": job_id, "status": job["status"]})
    if task is None:
        raise ValueError("Job is not an active task in this server; check its owner server")
    task.cancel()
    await asyncio.gather(task, return_exceptions=True)
    if store.get(job_id)["status"] != "cancelled":
        store.update(job_id, status="cancelled", error={"code": "cancelled", "message": "Cancelled before work started"})
    return GenericResult(summary="Job cancelled; active work stopped", data={"job_id": job_id, "status": "cancelled"})


@mcp.tool(name="fofa_exposure_review", annotations=READ_ONLY)
@tool_guard
async def fofa_exposure_review(
    product: str,
    city: str = "Shanghai",
    country: str = "CN",
    after: str | None = None,
    size: int = 100,
    max_records: int | None = None,
    sample: bool = False,
) -> GenericResult:
    """Return the full update-time result, port stats and a simulated scan. Set sample only when the user asked for 抽样."""
    from core.exposure import FULL_RECORD_CAP, exposure_review

    if not 1 <= size <= 10_000:
        raise ToolError("size must be between 1 and 10000")
    if max_records is not None and not 1 <= max_records <= FULL_RECORD_CAP:
        raise ToolError("max_records must be between 1 and 1000000")
    async with FofaClient() as client:
        data = await exposure_review(
            client,
            product=product,
            city=city,
            country=country,
            after=after,
            size=size,
            max_records=max_records,
            sample=sample,
        )
        data["usage"] = receipt(requests=client.request_count, fetched=client.fetched_records,
                                returned=data["result_count"], charged=client.reported_charge)
    scope = "抽样" if data["mode"] == "sample" else "全量"
    return GenericResult(summary=f"暴露面复核完成，范围是{scope}。扫描是模拟结果，没有运行 Nuclei。", data=data)


@mcp.tool(name="fofa_schedule_create", annotations=WRITE_SAFE)
@tool_guard
async def fofa_schedule_create(request: ScheduleRequest) -> GenericResult:
    """Save a passive one-time/interval/hourly/daily/weekly/monthly mapping schedule.

    Show timezone/next_run/queries/liveness. check_alive=null follows the current global default; task wording has priority.
    """
    from core.schedules import write_schedule_index
    from service.scheduler import schedule_store

    schedules = schedule_store()
    item = schedules.create(request)
    index = write_schedule_index(schedules, output_root() / "schedules")
    return GenericResult(
        summary="Schedule saved; verify worker status before promising timed execution",
        data={"schedule": item, "index": str(index), "worker": schedules.worker_status()},
    )


@mcp.tool(name="fofa_schedule_update", annotations=WRITE_SAFE)
@tool_guard
async def fofa_schedule_update(schedule_id: str, request: ScheduleRequest) -> GenericResult:
    """Replace a saved schedule's time, task and query specification while retaining history; running tasks cannot be edited."""
    from core.schedules import write_schedule_index
    from service.scheduler import schedule_store

    schedules = schedule_store()
    item = schedules.update(schedule_id, request)
    index = write_schedule_index(schedules, output_root() / "schedules")
    return GenericResult(summary="Schedule updated", data={"schedule": item, "index": str(index), "worker": schedules.worker_status()})


@mcp.tool(name="fofa_schedule_list", annotations=LOCAL_READ)
@tool_guard
async def fofa_schedule_list() -> GenericResult:
    """List durable schedules and the scheduler heartbeat. Does not run due tasks."""
    from service.scheduler import schedule_store

    schedules = schedule_store()
    return GenericResult(summary="FofaMap schedules", data={"schedules": schedules.list(), "worker": schedules.worker_status()})


@mcp.tool(name="fofa_schedule_history", annotations=LOCAL_READ)
@tool_guard
async def fofa_schedule_history(schedule_id: str, limit: int = 30, include_snapshots: bool = False) -> GenericResult:
    """Read execution history, counts, snapshot changes and MD/HTML/JSON paths."""
    from service.scheduler import schedule_store

    runs = schedule_store().runs(schedule_id, limit)
    if not include_snapshots:
        for run in runs:
            if run.get("result"):
                run["result"].pop("snapshot", None)
    return GenericResult(summary="Scheduled mapping history", data={"runs": runs})


@mcp.tool(name="fofa_schedule_set_enabled", annotations=WRITE_SAFE)
@tool_guard
async def fofa_schedule_set_enabled(schedule_id: str, enabled: bool) -> GenericResult:
    """Pause/resume a schedule; resuming recomputes a future due time."""
    from core.schedules import write_schedule_index
    from service.scheduler import schedule_store

    schedules = schedule_store()
    item = schedules.set_enabled(schedule_id, enabled)
    write_schedule_index(schedules, output_root() / "schedules")
    return GenericResult(summary="Schedule state updated", data={"schedule": item})


@mcp.tool(name="fofa_schedule_stop", annotations=WRITE_SAFE)
@tool_guard
async def fofa_schedule_stop(schedule_id: str) -> GenericResult:
    """Stop future runs and request cancellation of the active run (worker polls every second). Preserve history/reports."""
    from core.schedules import write_schedule_index
    from service.scheduler import schedule_store

    schedules = schedule_store()
    item = schedules.stop(schedule_id)
    write_schedule_index(schedules, output_root() / "schedules")
    return GenericResult(summary="Schedule stopped; active cancellation requested", data={"schedule": item})


@mcp.tool(
    name="fofa_schedule_delete",
    annotations={
        "readOnlyHint": False,
        "destructiveHint": True,
        "idempotentHint": True,
        "openWorldHint": False,
    },
)
@tool_guard
async def fofa_schedule_delete(schedule_id: str) -> GenericResult:
    """Delete a schedule from active management; cancel its run and retain history/reports in the index archive.

    Only call when the user explicitly requests deletion. Deleted tasks cannot be resumed or edited.
    """
    from core.schedules import write_schedule_index
    from service.scheduler import schedule_store

    schedules = schedule_store()
    item = schedules.delete(schedule_id)
    index = write_schedule_index(schedules, output_root() / "schedules")
    return GenericResult(summary="Schedule deleted; history and reports archived", data={"schedule": item, "index": str(index)})


@mcp.tool(name="nuclei_guide", annotations=LOCAL_READ)
@tool_guard
async def nuclei_guide(refresh: bool = False, section: str = "overview") -> GenericResult:
    """Read/cache the installed Nuclei command guide. Executable changes invalidate it; refresh after updates. Does not scan."""
    from core.nuclei_guide import command_guide

    data = await command_guide(refresh=refresh)
    data["output_note"] = ("-ot omits template-encoded, not template path metadata or HTTP responses. "
                           "Output may still exceed MiB; FofaMap drains pipes in bounded byte chunks and preserves full JSONL findings.")
    if section not in {"overview", "flags", "full"}:
        raise ValueError("section: overview/flags/full")
    if section != "full":
        help_text = data.pop("help", "")
        data["help_available"] = bool(help_text)
        data["examples"] = ["-rl 5 -c 2 -timeout 10", "-pt tcp -id redis-detect -severity info", "-pt http -id tech-detect -severity info"]
        data["customize_syntax"] = "nuclei_customize accepts CLI flags, not rate_limit=10; targets and output cannot be overridden"
        if section == "flags":
            data["flags"] = [
                line.strip()
                for line in help_text.splitlines()
                if any(
                    flag in line
                    for flag in ("-rate-limit ", "-concurrency ", "-timeout ", "-severity ", "-type ", "-headless ", "-code ", "-file ")
                )
            ]
    return GenericResult(summary="Version-matched Nuclei guide; section=full returns installed -h", data=data)


@mcp.tool(name="nuclei_recommend", annotations=LOCAL_READ)
@tool_guard
async def nuclei_recommend(intent: str, assets: list[dict[str, Any]] | None = None, targets: list[str] | None = None) -> GenericResult:
    """Prepare up to three reasoned, asset-aware commands and typed plans. No plan is approved or executed."""
    from core.nuclei_guide import recommend_scans

    return GenericResult(
        summary="Review/select/customize Nuclei proposals before approval",
        data=recommend_scans(intent, assets or [], targets),
    )


@mcp.tool(name="nuclei_select_targets", annotations=LOCAL_READ)
@tool_guard
async def nuclei_select_targets(
    intent: str, targets: list[str], assets: list[dict[str, Any]] | None = None, decisions: list[dict[str, Any]] | None = None
) -> GenericResult:
    """Prepare or validate host-AI target selection. No model/API calls, probing, approval or execution.

    First omit decisions to read numbered candidates. Host AI returns decisions {id,action,reason,duplicate_of}.
    Actions: keep/exclude/duplicate. Shared IP/title cannot merge virtual hosts or different protocols/ports.
    Missing decisions keep candidates. Present the audit to the user, then approve an exact plan of selected targets.
    """
    from core.scan_selection import apply_selection, candidates

    rows = candidates(targets, assets)
    if decisions is None:
        return GenericResult(summary="Host AI must review candidates against user intent; no scan executed", data={
            "intent": intent, "status": "awaiting_host_selection", "candidates": rows,
            "decision_example": {"id": 0, "action": "keep", "reason": "matches the requested scope", "duplicate_of": None},
            "note": "Do not infer duplicates or ownership from shared IP/title. Preserve uncertain distinct services.",
        })
    audit = apply_selection(targets, decisions, source="host_agent", assets=assets)
    return GenericResult(summary=f"Selected {audit['selected_count']} of {len(targets)} candidates; review before approval", data=audit)


@mcp.tool(name="nuclei_customize", annotations=LOCAL_READ)
@tool_guard
async def nuclei_customize(base_plan: ScanPlanRequest, parameters: str) -> GenericResult:
    """Accept CLI flags, e.g. '-rl 10 -c 3', '-pt tcp -id redis-detect -severity info', '-timeout 8 -retries 1'.

    Key=value is not supported. Does not execute shell text or approve the plan.
    """
    from core.nuclei_guide import customize_plan

    return GenericResult(
        summary="Customized draft; create and approve a new nuclei_plan",
        data={"plan": customize_plan(base_plan, parameters).model_dump()},
    )


@mcp.tool(name="nuclei_templates", annotations=LOCAL_READ)
@tool_guard
async def nuclei_templates(keyword: str = "", protocol: str = "", limit: int = 50) -> GenericResult:
    """List installed template IDs, protocol, severity and network ports without scanning. Exact IDs/paths still need an approved plan."""
    from core.scanner import inspect_nuclei_templates

    return GenericResult(summary="Installed Nuclei template catalog", data=await inspect_nuclei_templates(keyword, protocol, limit))


@mcp.tool(name="nuclei_capabilities", annotations=LOCAL_READ)
@tool_guard
async def nuclei_capabilities() -> GenericResult:
    """Inspect the local Nuclei executable, supported template types and non-Web target formats. Does not scan."""
    from core.nuclei_protocols import NUCLEI_PROTOCOLS
    from core.scanner import nuclei_subprocess_env, strip_nuclei_ansi
    from core.scans import NETWORK_SERVICE_HINTS, default_nuclei_template_ids

    executable = NucleiScanner().executable
    data: dict[str, Any] = {
        "installed": bool(executable),
        "executable": executable,
        "scanning_enabled": os.getenv("FOFAMAP_ENABLE_SCANNING", "false").lower() == "true",
        "approval_configured": bool(os.getenv("FOFAMAP_SCAN_APPROVAL_SECRET")),
        "protocols": sorted(NUCLEI_PROTOCOLS),
        "web_baseline": default_nuclei_template_ids(),
        "network_detection": NETWORK_SERVICE_HINTS,
        "target_examples": [
            "https://example.com",
            "tcp://example.com:6379",
            "tls://example.com:636",
            "dns://example.com",
        ],
        "udp": "Use udp://host:port with protocols=[javascript] and an explicit UDP JavaScript template; udp is not a -pt type.",
        "scope_note": "Template-defined ports/hosts also need authorization; inspect selected templates before approval.",
        "source": "https://docs.projectdiscovery.io/templates/protocols/network",
    }
    if executable:
        process = await asyncio.create_subprocess_exec(
            executable,
            "-version",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
            env=nuclei_subprocess_env(),
        )
        try:
            output, _ = await asyncio.wait_for(process.communicate(), timeout=10)
            data["version"] = strip_nuclei_ansi(output.decode(errors="replace"))[:2000]
        except asyncio.TimeoutError:
            process.kill()
            await process.wait()
            data["version_error"] = "Nuclei version probe timed out"
    return GenericResult(summary="Nuclei local capability inspection; no scan executed", data=data)


@mcp.tool(name="nuclei_plan", annotations=WRITE_SAFE)
@tool_guard
async def nuclei_plan(request: ScanPlanRequest) -> GenericResult:
    """Create an exact, expiring Nuclei plan and one-time approval token. Scanning must be enabled."""
    if os.getenv("FOFAMAP_ENABLE_SCANNING", "false").lower() != "true":
        raise ValueError("active scanning is disabled")
    job, token = ScanApproval(store, allow_private=settings.system.allow_private_network).create(request)
    return GenericResult(
        summary="Review target/template/severity scope before calling nuclei_execute",
        data={"plan": job, "approval_token": token},
    )


_SCAN_TASKS: dict[str, asyncio.Task] = {}


async def _run_scan_job(plan_id: str, payload: dict[str, Any]) -> None:
    started_at = datetime.now()
    plan = ScanPlanRequest.model_validate(payload)
    output = output_root() / f"scan-{plan_id}"

    def progress(event) -> None:
        store.update(
            plan_id,
            status="running",
            result={
                "progress": event.line,
                "finding_count": event.findings,
                "loaded_targets": event.loaded_targets,
                "loaded_templates": event.loaded_templates,
                "elapsed_seconds": round(event.elapsed_seconds, 1),
                "percent": event.percent,
                "requests": event.requests,
                "total_requests": event.total_requests,
                "rps": event.rps,
                "errors": event.errors,
            },
        )

    try:
        scan = await NucleiScanner().run_plan(plan, output, on_progress=progress)
        from core.agent import AgentRun, AgentState
        from core.report import write_agent_report

        run = AgentRun(
            intent="Nuclei authorized service review",
            state=AgentState.COMPLETED,
            started_at=started_at,
            finished_at=datetime.now(),
            scan_protocols=plan.protocols,
            scan_limits={
                "rate_limit": plan.rate_limit,
                "concurrency": plan.concurrency,
                "max_duration": plan.max_duration,
            },
            fields=["host"],
            assets=[{"host": target} for target in plan.targets],
            result_count=len(plan.targets),
            scan_requested_by_user=True,
            scan_recommended=True,
            scan_targets=plan.targets,
            scan_template_ids=plan.template_ids,
            scan_severities=plan.severities,
            scan_reason="Approved exact scope. Automated findings require manual verification.",
            scan_artifact=str(scan.artifact),
        )
        report = write_agent_report(run, output / "scan-report.md", scan_status="completed", language="en")
        result = scan.to_job_payload()
        result["report"] = {"markdown": str(report), "html": str(report.with_suffix(".html"))}
        result["log_path"] = str(output / "nuclei.log")
        store.update(plan_id, status="completed", artifact_path=str(scan.artifact.resolve()), result=result)
    except asyncio.CancelledError:
        partial = output / "nuclei.jsonl"
        store.update(plan_id, status="cancelled", artifact_path=str(partial) if partial.is_file() else None,
                     error={"code": "scan_cancelled", "message": "Scan cancelled; partial findings are not a completed scan"})
        raise
    except Exception as exc:
        from core.tool_errors import error_payload

        partial = output / "nuclei.jsonl"
        store.update(plan_id, status="failed", artifact_path=str(partial) if partial.is_file() else None,
                     error=error_payload(exc, tool="nuclei_execute"))


@mcp.tool(name="nuclei_execute", annotations=SCAN_EXECUTE)
@tool_guard
async def nuclei_execute(plan_id: str, approval_token: str, install_if_missing: bool = False) -> GenericResult:
    """Start an approved exact scan. install_if_missing=true requires separate user consent for official component downloads.

    Poll fofa_job_status until completed or failed. Keep the MCP server running.
    """
    if os.getenv("FOFAMAP_ENABLE_SCANNING", "false").lower() != "true":
        raise ValueError("active scanning is disabled")
    approval = ScanApproval(store, allow_private=settings.system.allow_private_network)
    approval.verify(plan_id, approval_token)
    from core.nuclei_install import ensure_installed, needs_setup

    if needs_setup(NucleiScanner().executable):
        if not install_if_missing:
            raise ValueError("Nuclei is not installed; ask the user Y=official download or N=manual install. "
                             "Only after explicit consent retry with install_if_missing=true; the plan has not been consumed.")
        await ensure_installed(consent=True)
    job = approval.consume(plan_id, approval_token)
    job = store.update(plan_id, status="running")
    task = asyncio.create_task(_run_scan_job(plan_id, job["payload"]))
    _SCAN_TASKS[plan_id] = task
    task.add_done_callback(lambda _: _SCAN_TASKS.pop(plan_id, None))
    return GenericResult(summary="Scan started. Poll fofa_job_status with job_id; retain this MCP server session.", data=job)


@mcp.resource("fofamap://fields")
def fields_resource() -> dict[str, Any]:
    """Current versioned FOFA field catalogue."""
    return field_catalog()


@mcp.resource("fofamap://runtime")
def runtime_resource() -> dict[str, Any]:
    """Quota-free version, build and code identity. No account or model calls."""
    from core.runtime import runtime_info

    return runtime_info()


@mcp.resource("fofamap://rules")
def rules_resource() -> dict[str, Any]:
    """Bundled FOFA app= fingerprint library (official names from fofa.info/library)."""
    from core.rules import rules_catalog

    return rules_catalog()


@mcp.resource("fofamap://account")
async def account_resource() -> dict[str, Any]:
    """Current FOFA account capability and usage data."""
    async with FofaClient() as client:
        return await client.account()


@mcp.resource("fofamap://jobs/{job_id}")
def job_resource(job_id: str) -> dict[str, Any]:
    """Job metadata; artifact_path points to large local results."""
    return store.get(job_id)


def _loopback(host: str) -> bool:
    return host in {"127.0.0.1", "::1", "localhost"}


async def check_server(
    url: str | None = None, *, expected_version: str | None = None,
    expected_build_date: str | None = None, expected_source: Path | None = None,
) -> dict[str, Any]:
    """Verify an actual MCP connection without using FOFA or model quota."""
    from mcp import Client, StdioServerParameters
    from mcp.client.stdio import stdio_client

    # mcp 2.0 accepts an explicit Transport; shorthand StdioServerParameters arrived later.
    server = url or stdio_client(StdioServerParameters(
        command=sys.executable, args=["-u", str(Path(__file__).resolve())], env=dict(os.environ)
    ))
    legacy_sse = bool(url and urlsplit(url).path.rstrip("/").endswith("/sse"))
    if legacy_sse:
        from mcp.client.sse import sse_client

        server = sse_client(url)
    async with Client(server, read_timeout_seconds=15, mode="legacy" if legacy_sse else "auto") as client:
        tools = await client.list_tools()
        names = sorted(tool.name for tool in tools.tools)
        required = {tool.name for tool in await mcp.list_tools()}
        if set(names) != required:
            raise RuntimeError(f"MCP tool catalogue mismatch: missing={sorted(required - set(names))}, "
                               f"extra={sorted(set(names) - required)}")
        metadata = await client.read_resource("fofamap://runtime")
        remote = json.loads(metadata.contents[0].text)
        want_version, want_date = expected_version or VERSION, expected_build_date or BUILD_DATE
        if remote.get("version") != want_version or remote.get("build_date") != want_date:
            raise RuntimeError(f"MCP build mismatch: expected {want_version}/{want_date}, "
                               f"received {remote.get('version')}/{remote.get('build_date')}")
        identity = client.server_info
        if identity is None or identity.version != remote["version"]:
            raise RuntimeError("MCP handshake version differs from runtime or server identity is missing")
        if remote.get("distribution_version") not in {None, want_version}:
            raise RuntimeError(f"Installed distribution version differs from server: {remote['distribution_version']} != {want_version}")
        if expected_source is not None:
            from core.runtime import source_fingerprint

            if source_fingerprint(expected_source.resolve()) != remote.get("source_fingerprint"):
                raise RuntimeError("Installed server code differs from --expect-source; rebuild/reinstall the current release")
        protocol_version = client.protocol_version
        result = await client.call_tool("fofa_validate_query", {"query": 'domain="example.com"'})
        if result.is_error or not result.structured_content["data"]["valid"]:
            raise RuntimeError("MCP local query validation failed")
    return {"ok": True, "version": remote["version"], "build_date": remote["build_date"],
            "server_info": {"name": identity.name, "version": identity.version},
            "protocol_version": protocol_version, "server": remote, "tool_count": len(names), "tools": names, "quota_spent": False,
            "runtime": {"python": sys.executable, "python_version": sys.version.split()[0],
                        "server_entry": str(Path(__file__).resolve()), "cwd": str(Path.cwd()),
                        "database_url": database_url() if database_url().startswith("sqlite:") else "external_database",
                        "output_root": str(output_root())}}


def run_server() -> None:
    from utils.stdio import configure_windows_stdio

    configure_windows_stdio()
    parser = argparse.ArgumentParser(description="FofaMap MCP 2.0 服务")
    parser.add_argument("--transport", choices=["stdio", "sse", "streamable-http", "http"], default="stdio", help="传输方式")
    parser.add_argument("--host", default=os.getenv("FOFAMAP_BIND_HOST", "127.0.0.1"), help="HTTP 绑定地址")
    parser.add_argument("--port", type=int, default=int(os.getenv("FOFAMAP_MCP_PORT", "8001")), help="HTTP 端口")
    parser.add_argument("--check", action="store_true", help="实际连接本机 stdio MCP 并验证工具加载，不消耗 FOFA 额度")
    parser.add_argument("--check-url", help="验证已有 HTTP/SSE MCP 地址，例如 http://127.0.0.1:8001/mcp")
    parser.add_argument("--expect-version", help="自检必须匹配此版本，否则非零退出")
    parser.add_argument("--expect-build-date", help="自检必须匹配此构建日期，否则非零退出")
    parser.add_argument("--expect-source", type=Path, help="自检服务代码必须匹配此源码目录的 SHA-256 指纹")
    args = parser.parse_args()
    if args.check or args.check_url:
        try:
            result = asyncio.run(asyncio.wait_for(check_server(
                args.check_url, expected_version=args.expect_version, expected_build_date=args.expect_build_date,
                expected_source=args.expect_source,
            ), timeout=30))
        except Exception as exc:
            from core.tool_errors import error_payload

            cause = exc
            while getattr(cause, "exceptions", None):
                cause = cause.exceptions[0]
            print(json.dumps({"ok": False, **error_payload(cause, tool="mcp_check")}, ensure_ascii=False), file=sys.stderr)
            raise SystemExit(1) from None
        print(json.dumps(result, ensure_ascii=False))
        return
    if args.transport == "http":
        args.transport = "streamable-http"
    if not 1 <= args.port <= 65535:
        parser.error("port must be between 1 and 65535")
    if args.transport != "stdio" and not _loopback(args.host):
        if not (
            (os.getenv("FOFAMAP_SERVICE_TOKEN") or os.getenv("FOFAMAP_JWT_PUBLIC_KEY"))
            and os.getenv("FOFAMAP_MCP_ISSUER_URL")
            and os.getenv("FOFAMAP_MCP_RESOURCE_URL")
        ):
            parser.error("非回环 HTTP/SSE 需要令牌校验器，以及 FOFAMAP_MCP_ISSUER_URL 和 FOFAMAP_MCP_RESOURCE_URL")
    if args.transport == "stdio":
        mcp.run(transport="stdio")
    elif args.transport == "sse":
        mcp.run(transport="sse", host=args.host, port=args.port)
    else:
        mcp.run(
            transport="streamable-http",
            host=args.host,
            port=args.port,
            stateless_http=True,
            json_response=True,
        )


if __name__ == "__main__":
    run_server()
