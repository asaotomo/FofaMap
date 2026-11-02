"""Recoverable deterministic workflow agent; the LLM plans and summarizes only."""

from __future__ import annotations

import inspect
import json
import re
import uuid
from collections import Counter
from collections.abc import Awaitable, Callable
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Literal

from opentelemetry import trace
from pydantic import BaseModel, Field

from core.client import FofaClient
from core.fields import (
    STATS_FIELDS,
    account_tier,
    available_fields,
    decide_fields,
    fofa_request_fields,
    merge_return_fields,
)
from core.membership import host_fallback_query, membership_from_account, membership_label, planner_capabilities_prompt
from core.models import FofaError, FofaErrorCode, SearchPage, SearchRequest
from core.rules import match_intent_rules, rules_hint_for_prompt
from core.scans import NETWORK_SERVICE_HINTS, align_scan_severities, default_nuclei_template_ids, nuclei_id_allowlist
from core.showcase import showcase_for
from providers.base import ProviderError
from providers.registry import ProviderRouter
from utils.i18n import language, t
from utils.logger import logger


class AgentState(str, Enum):
    INTENT = "intent_parsing"
    VALIDATE = "query_validation"
    EXECUTE = "execute"
    EVALUATE = "evaluate"
    REFLECT = "reflect"
    REPAIR = "query_repair"
    SUMMARIZE = "summarize"
    COMPLETED = "completed"
    FAILED = "failed"


class AgentAction(str, Enum):
    SEARCH = "fofa_search"
    HOST = "host_query"
    STATS = "stat_query"
    ICON = "icon_query"


class AgentStep(BaseModel):
    state: AgentState
    detail: str
    started_at: datetime = Field(default_factory=datetime.now)
    data: dict[str, Any] = Field(default_factory=dict)


class AgentQuery(BaseModel):
    query: str
    purpose: str = ""
    strategy: str = "balanced"
    source: str = "planner"
    available_count: int | None = None
    result_count: int = 0
    new_assets: int = 0
    pages: int = 0


class WebsiteCandidate(BaseModel):
    """A website surfaced by FOFA, with explicit attribution confidence."""

    domain: str
    url: str
    status: Literal["corroborated", "observed", "candidate"]
    confidence: Literal["high", "medium", "low"]
    evidence: list[str] = Field(default_factory=list)
    hosts: list[str] = Field(default_factory=list)


class AgentRun(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    intent: str
    action: AgentAction = AgentAction.SEARCH
    target: str | None = None
    stats_fields: list[str] = Field(default_factory=list)
    result_data: dict[str, Any] = Field(default_factory=dict)
    state: AgentState = AgentState.INTENT
    steps: list[AgentStep] = Field(default_factory=list)
    query: str | None = None
    queries: list[AgentQuery] = Field(default_factory=list)
    fields: list[str] = Field(default_factory=list)
    result_count: int = 0
    assets: list[dict[str, Any]] = Field(default_factory=list)
    assets_truncated: bool = False
    asset_confidence: list[str] = Field(default_factory=list)
    evidence_counts: dict[str, int] = Field(default_factory=dict)
    organization_names: list[str] = Field(default_factory=list)
    domain_hypotheses: list[str] = Field(default_factory=list)
    website_candidates: list[WebsiteCandidate] = Field(default_factory=list)
    reflection_rounds: int = 0
    reflection_notes: list[str] = Field(default_factory=list)
    summary: str | None = None
    summary_source: str = ""
    scan_advice: str | None = None
    scan_requested_by_user: bool = False
    scan_recommended: bool = False
    scan_reason: str = ""
    scan_scope_note: str = ""
    scan_template_ids: list[str] = Field(default_factory=list)
    scan_severities: list[str] = Field(default_factory=lambda: ["medium", "high", "critical"])
    scan_targets: list[str] = Field(default_factory=list)
    scan_protocols: list[str] = Field(default_factory=list)
    scan_limits: dict[str, int] = Field(default_factory=dict)
    scan_artifact: str | None = None
    scan_selection: dict[str, Any] = Field(default_factory=dict)
    liveness: dict[str, Any] = Field(default_factory=dict)
    report_artifact: str | None = None
    error: dict[str, Any] | None = None
    route_events: list[dict[str, Any]] = Field(default_factory=list)
    population_size: int = 0
    population_aggs: dict[str, Any] = Field(default_factory=dict)
    sample_limit: int = 0
    sample_stop_reason: str = ""
    sampled: bool = False
    field_tallies: dict[str, dict[str, int]] = Field(default_factory=dict)
    started_at: datetime = Field(default_factory=datetime.now)
    finished_at: datetime | None = None

    @property
    def scan_ready(self) -> bool:
        return bool(
            self.scan_requested_by_user and self.scan_targets and self.scan_template_ids and self.error is None
        )

    def shows_scan_decision(self, *, scan_error: str | None = None) -> bool:
        """Show scan scope only after the user asked for a scan, or a scan actually produced output."""
        return bool(self.scan_requested_by_user or self.scan_artifact or (self.scan_advice or "").strip() or scan_error)

    def uses_model_summary(self) -> bool:
        """True only when the briefing text came from a model, not a local fallback."""
        if self.summary_source == "local" or not (self.summary or "").strip():
            return False
        if self.summary_source == "model":
            return True
        return any(bool(event.get("model")) for event in self.route_events)


AgentProgressCallback = Callable[[AgentRun, AgentStep], None]
AgentPageCallback = Callable[[AgentRun, SearchPage, int], None | Awaitable[None]]
# Human-facing Agent runs keep every returned asset for small/medium result sets.
# Only larger runs are capped so terminal, JSON and report payloads stay bounded.
ASSET_PREVIEW_LIMIT = 500
MAX_QUERY_VARIANTS = 8
INITIAL_QUERY_VARIANTS = 5
MAX_REFLECTION_ROUNDS = 2
MAX_REFLECTION_ADDITIONS = 2
READABLE_SAMPLE = 8
PORTRAIT_FIELDS = ("server", "port", "os", "title")
DISTRIBUTION_FIELDS = (
    "domain",
    "port",
    "protocol",
    "base_protocol",
    "server",
    "product",
    "product_category",
    "os",
    "title",
    "city",
    "region",
    "country",
    "country_name",
    "org",
    "asn",
    "as",
    "icp",
    "status_code",
    "alive_status",
)
_TALLY_KEY_LIMIT = 300
EVIDENCE_RANK = {"recall": 1, "hypothesis": 2, "balanced": 3, "precision": 4}
STAT_FIELDS = STATS_FIELDS


def _reply_language(report_language: str = "zh") -> str:
    if report_language == "en" or language() == "en":
        return "en"
    return "zh"


def _english_reply_clause(report_language: str = "zh") -> str:
    if _reply_language(report_language) != "en":
        return ""
    return " The interface language is English. Write every natural-language field in English."


def _record_step(
    run: AgentRun,
    state: AgentState,
    detail: str,
    *,
    data: dict[str, Any] | None = None,
    on_progress: AgentProgressCallback | None = None,
) -> None:
    run.state = state
    step = AgentStep(state=state, detail=detail, data=data or {})
    run.steps.append(step)
    if on_progress:
        # Presentation observers must never be able to abort a FOFA run.
        try:
            on_progress(run, step)
        except Exception as exc:
            logger.warning(f"Agent progress observer failed: {exc}")


def _website_name(host: str) -> str:
    text = host.strip()
    if "://" in text:
        text = text.split("://", 1)[1]
    text = text.split("/", 1)[0].strip().lower()
    if text.startswith("[") and "]" in text:
        return text[1 : text.index("]")]
    if text.count(":") == 1 and text.rsplit(":", 1)[-1].isdigit():
        return text.rsplit(":", 1)[0]
    return text


def _tally_value(field: str, values: dict[str, Any]) -> str:
    if field == "domain":
        domain = str(values.get("domain") or "").strip()
        if domain:
            return domain.lower()
        return _website_name(str(values.get("host") or ""))
    raw = values.get(field)
    if isinstance(raw, list):
        raw = "、".join(str(item) for item in raw if item)
    return str(raw or "").strip()


def _remember_distribution(run: AgentRun, values: dict[str, Any]) -> None:
    """Count every returned row, including rows later omitted from the asset table."""
    selected = {str(field) for field in run.fields}
    for field in DISTRIBUTION_FIELDS:
        if field == "alive_status":
            if values.get("alive_status") in (None, ""):
                continue
        elif selected and field not in selected and not (field == "domain" and "host" in selected):
            continue
        elif not selected and field not in values and field != "domain":
            continue
        text = _tally_value(field, values)
        if not text:
            continue
        bucket = run.field_tallies.setdefault(field, {})
        if text not in bucket and len(bucket) >= _TALLY_KEY_LIMIT:
            bucket["__other__"] = bucket.get("__other__", 0) + 1
            continue
        bucket[text] = bucket.get(text, 0) + 1


def _record_page(
    run: AgentRun,
    page: SearchPage,
    page_number: int,
    *,
    strategy: str,
) -> None:
    run.result_count += len(page.records)
    for record in page.records:
        _remember_distribution(run, record.values)
        if len(run.assets) < ASSET_PREVIEW_LIMIT:
            run.assets.append(record.values)
            run.asset_confidence.append(strategy)
            continue
        weakest_rank = min(EVIDENCE_RANK.get(value, 1) for value in run.asset_confidence)
        if EVIDENCE_RANK.get(strategy, 1) <= weakest_rank:
            continue
        # Replace the latest weakest candidate so later high-quality strategies
        # cannot be hidden merely because a broad recall query arrived first.
        replace_at = max(index for index, value in enumerate(run.asset_confidence) if EVIDENCE_RANK.get(value, 1) == weakest_rank)
        run.assets[replace_at] = record.values
        run.asset_confidence[replace_at] = strategy
    if run.result_count > len(run.assets):
        run.assets_truncated = True


async def _notify_page(
    on_page: AgentPageCallback | None,
    run: AgentRun,
    page: SearchPage,
    page_number: int,
) -> None:
    if not on_page:
        return
    try:
        result = on_page(run, page, page_number)
        if inspect.isawaitable(result):
            await result
    except Exception as exc:
        logger.warning(f"Agent page observer failed: {exc}")


PLAN_SCHEMA = {
    "type": "object",
    "properties": {
        "action": {"type": "string", "enum": ["fofa_search", "host_query", "stat_query", "icon_query"]},
        "target": {"type": "string"},
        "queries": {
            "type": "array",
            "minItems": 0,
            "maxItems": INITIAL_QUERY_VARIANTS,
            "items": {
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "purpose": {"type": "string"},
                    "strategy": {"type": "string", "enum": ["precision", "balanced", "recall"]},
                },
                "required": ["query", "purpose", "strategy"],
                "additionalProperties": False,
            },
        },
        "stats_fields": {"type": "array", "items": {"type": "string"}},
        "fields": {"type": "array", "items": {"type": "string"}},
        "scan": {
            "type": "object",
            "properties": {
                "recommended": {"type": "boolean"},
                "reason": {"type": "string"},
                "template_ids": {"type": "array", "items": {"type": "string"}},
                "severities": {
                    "type": "array",
                    "items": {"type": "string", "enum": ["info", "low", "medium", "high", "critical"]},
                },
            },
            "required": ["recommended", "reason", "template_ids", "severities"],
            "additionalProperties": False,
        },
    },
    "required": ["action", "target", "queries", "stats_fields", "fields", "scan"],
    "additionalProperties": False,
}

ENTITY_RESOLUTION_SCHEMA = {
    "type": "object",
    "properties": {
        "organization_names": {"type": "array", "maxItems": 6, "items": {"type": "string"}},
        "domains": {
            "type": "array",
            "maxItems": 6,
            "items": {
                "type": "object",
                "properties": {"domain": {"type": "string"}, "reason": {"type": "string"}},
                "required": ["domain", "reason"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["organization_names", "domains"],
    "additionalProperties": False,
}

QUERY_SCHEMA = {
    "type": "object",
    "properties": {
        "query": {"type": "string"},
        "fields": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["query", "fields"],
    "additionalProperties": False,
}

REFLECTION_SCHEMA = {
    "type": "object",
    "properties": {
        "observation": {"type": "string"},
        "coverage_sufficient": {"type": "boolean"},
        "queries": {
            "type": "array",
            "maxItems": MAX_REFLECTION_ADDITIONS,
            "items": {
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "purpose": {"type": "string"},
                    "strategy": {"type": "string", "enum": ["precision", "balanced", "recall"]},
                },
                "required": ["query", "purpose", "strategy"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["observation", "coverage_sufficient", "queries"],
    "additionalProperties": False,
}

SCAN_AUTHORIZATION_PATTERN = re.compile(r"(?:扫描|漏洞检测|漏洞扫描|nuclei|scan(?:ning)?)", re.IGNORECASE)
SCAN_DENIAL_PATTERN = re.compile(
    r"(?:不扫描|不扫|不做主动扫描)|(?:不要|不需要|无需|禁止|拒绝|不进行|请勿|勿|不做|不执行).{0,8}"
    r"(?:扫描|漏洞检测|漏洞扫描|nuclei)"
    r"|\b(?:no|do\s+not|don['’]t|without)\s+(?:active\s+|nuclei\s+)?scan(?:ning)?\b"
    r"|\b(?:do\s+not|don['’]t|never|must\s+not|without)\b[^.!?;\n]{0,120}\b(?:scan(?:ning)?|nuclei)\b",
    re.IGNORECASE,
)
SAFE_TEMPLATE_ID_PATTERN = re.compile(r"^[A-Za-z0-9._-]{1,128}$")
ORGANIZATION_SUFFIX_PATTERN = "公司|集团|大学|学院|学校|研究院|研究所|实验室|工作室|医院|协会|政府|委员会|中心|银行"
EN_ORGANIZATION_SUFFIX_PATTERN = (
    "university|college|company|corporation|institute|laboratory|studio|school|hospital|association|government|bank"
)
ORGANIZATION_INTENT_PATTERN = re.compile(
    rf"(?:{ORGANIZATION_SUFFIX_PATTERN})|(?:{EN_ORGANIZATION_SUFFIX_PATTERN})\b",
    re.IGNORECASE,
)
WEBSITE_INTENT_PATTERN = re.compile(r"(?:网站|官网|域名|站点|websites?|domains?|sites?)", re.IGNORECASE)
CN_ORGANIZATION_NAME_PATTERN = re.compile(rf"(?:[A-Za-z][A-Za-z0-9._&'-]*|[\u4e00-\u9fff]|\d+){{1,40}}(?:{ORGANIZATION_SUFFIX_PATTERN})")
EN_ORGANIZATION_NAME_PATTERN = re.compile(
    rf"\b((?:[A-Za-z][A-Za-z0-9.&']+\s+)+(?:{EN_ORGANIZATION_SUFFIX_PATTERN}))\b",
    re.IGNORECASE,
)
FALLBACK_NOISE_PATTERN = re.compile(
    r"(?:请|麻烦|帮我|帮忙|我要|需要|尽可能|尽量|查询|查找|搜索|收集|发现|分析|看看|一下|"
    r"的?子域名网站|的?子域名|子域名|的?官网(?:网站)?|官网|的?网站|网站|的?域名|域名|"
    r"的?站点|站点|的?主机名?|主机|的?网页|网页|"
    r"的?全网资产|的?公开资产|相关资产|资产清单|的?资产|相关|"
    r"并且|并|然后|进行|执行|漏洞检测|漏洞扫描|扫描一下|扫描)"
    r"|\b(?:please|help\s+me|find|search|collect|discover|"
    r"subdomains?|websites?|website|domains?|hosts?|assets?|and|scan(?:ning)?|them)\b",
    re.IGNORECASE,
)


def user_authorized_scan(intent: str) -> bool:
    return not SCAN_DENIAL_PATTERN.search(intent) and bool(SCAN_AUTHORIZATION_PATTERN.search(intent))


def _scan_template_ids_for_intent(intent: str, suggested: list[str]) -> list[str]:
    """Apply the bounded default profile unless the user named exact template IDs."""
    allowlist = nuclei_id_allowlist()
    normalized = list(dict.fromkeys(item for item in suggested if item in allowlist))
    lowered = intent.lower()
    explicit = [item for item in allowlist if item.lower() in lowered]
    if explicit:
        return [item for item in default_nuclei_template_ids() if item in explicit] + sorted(
            item for item in explicit if item not in default_nuclei_template_ids()
        )
    service_ids = [template_id for name, template_id in NETWORK_SERVICE_HINTS.items() if re.search(rf"\b{name}\b", lowered)]
    if service_ids and not re.search(r"https?|web|网站|网页", lowered):
        return list(dict.fromkeys([*service_ids, *[item for item in normalized if item not in default_nuclei_template_ids()]]))
    return list(dict.fromkeys([*default_nuclei_template_ids(), *service_ids, *normalized]))[:100]


def _fofa_literal(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"').replace("\r", " ").replace("\n", " ").strip()


def _organization_core_name(text: str) -> str | None:
    english = EN_ORGANIZATION_NAME_PATTERN.search(text)
    if english:
        return english.group(1).strip()
    chinese = CN_ORGANIZATION_NAME_PATTERN.search(text)
    if chinese:
        return chinese.group(0).strip()
    return None


def _fallback_search_term(intent: str) -> str:
    quoted = re.search(r"[“‘'\"]([^”’'\"]{2,100})[”’'\"]", intent)
    if quoted:
        return quoted.group(1).strip()
    cleaned = FALLBACK_NOISE_PATTERN.sub(" ", intent)
    cleaned = re.sub(r"[，。！？、,:：;；()（）\[\]{}]+", " ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    organization = _organization_core_name(cleaned) or _organization_core_name(intent)
    if organization:
        return organization[:100]
    parts = [part.strip() for part in cleaned.split() if len(part.strip()) >= 2]
    return max(parts, key=len)[:100] if parts else intent.strip()[:100]


_CITY_NAMES = {
    "上海": "Shanghai",
    "北京": "Beijing",
    "广州": "Guangzhou",
    "深圳": "Shenzhen",
    "杭州": "Hangzhou",
    "南京": "Nanjing",
    "成都": "Chengdu",
    "武汉": "Wuhan",
    "西安": "Xi'an",
    "重庆": "Chongqing",
    "天津": "Tianjin",
    "苏州": "Suzhou",
}
_CITY_FIELD = re.compile(r'(?i)(\bcity\s*=\s*")([^"]*)(")')


def normalize_fofa_city(query: str) -> str:
    """Rewrite Chinese city values. FOFA indexes city in English and returns nothing for 广州."""

    def replace(match: re.Match[str]) -> str:
        raw = match.group(2).strip()
        english = _CITY_NAMES.get(raw) or _CITY_NAMES.get(raw.removesuffix("市"))
        if not english:
            return match.group(0)
        return f"{match.group(1)}{_fofa_literal(english)}{match.group(3)}"

    return _CITY_FIELD.sub(replace, query)


_SUFFIX_DOMAIN = re.compile(r'(?i)\bdomain\s*=\s*"(\.[^"]*)"')


def normalize_fofa_query(query: str) -> str:
    """Correct the field mistakes that make an otherwise valid request return nothing."""
    query = normalize_fofa_city(query)
    query = _SUFFIX_DOMAIN.sub(r'host="\1"', query)
    query = re.sub(r'(?i)\s*&&\s*title\s*=\s*""', "", query)
    query = re.sub(r'(?i)title\s*=\s*""\s*&&\s*', "", query)
    return query.strip()


def _rejected_fingerprint(exc: FofaError) -> bool:
    text = str(exc)
    return "820300" in text or "不存在" in text


def _query_error_can_be_rewritten(exc: FofaError) -> bool:
    """Syntax and unknown-product errors belong to the model, not the user."""
    return exc.code is FofaErrorCode.INVALID_QUERY or _rejected_fingerprint(exc)


_REPAIR_SYSTEM = (
    "FOFA rejected this asset-discovery query. Rewrite exactly one valid FOFA query. "
    "Keep the user's organization, geography and time scope. Use the FOFA error to fix quotes, "
    "parentheses, operators, or an unknown app= name. Do not invent an app= name. If the product "
    "name is unknown, remove that app= clause and keep the rest of the scope. "
    "Do not add exploit steps or vulnerability claims. Return structured data only."
)


async def _rewrite_rejected_query(router: ProviderRouter, *, intent: str, query: str, error: str) -> str:
    try:
        repair = await router.generate(
            "query_repair",
            system=_REPAIR_SYSTEM,
            prompt=(
                f"Intent: {intent}\nRejected query: {query}\nFOFA error: {error}"
                + ("\nThe interface language is English. Return the repaired query only." if language() == "en" else "")
            ),
            schema=QUERY_SCHEMA,
        )
    except ProviderError:
        return ""
    repaired = repair.structured if isinstance(repair.structured, dict) else {}
    rewritten = normalize_fofa_query(str(repaired.get("query") or ""))
    if not rewritten or rewritten == query.strip() or validate_query(rewritten):
        return ""
    return rewritten


def _intent_city(intent: str) -> str:
    city = next((english for chinese, english in _CITY_NAMES.items() if chinese in intent), "")
    if city:
        return city
    match = re.search(r'\bcity\s*=\s*"?([A-Za-z][A-Za-z .\'-]{1,40})', intent, re.IGNORECASE)
    return match.group(1).strip() if match else ""


def _php_exposure_queries(intent: str) -> list[AgentQuery]:
    """Inventory exposed PHP assets. A fingerprint is not proof that PHP2Shell is exploitable."""
    if not re.search(r"php\s*2\s*shell|php2shell|cve-2026-10961[89]", intent, re.IGNORECASE):
        return []
    city = _intent_city(intent)
    geo = f' && city="{_fofa_literal(city)}" && country="CN"' if city else ' && country="CN"'
    statements = [
        (
            f'(header="PHP/" || header="X-Powered-By: PHP"){geo}',
            t("PHP 响应头暴露面", "PHP response-header exposure"),
            "precision",
        ),
        (
            f'(app="WordPress" || app="ThinkPHP" || app="Laravel" || app="Discuz"){geo}',
            t("常见 PHP 应用暴露面", "Common PHP application exposure"),
            "balanced",
        ),
    ]
    return [AgentQuery(query=query, purpose=purpose, strategy=strategy, source="php2shell") for query, purpose, strategy in statements]


def _deterministic_fallback_plan(intent: str) -> dict[str, Any]:
    """Produce a conservative executable search when planner JSON is unusable."""
    domain_match = re.search(r"(?:https?://)?((?:[a-z0-9-]+\.)+[a-z]{2,63})(?:/|\b)", intent, re.IGNORECASE)
    ip_match = re.search(r"(?<![\d.])(?:\d{1,3}\.){3}\d{1,3}(?![\d.])", intent)
    if domain_match:
        domain = _fofa_literal(domain_match.group(1).lower().removeprefix("www."))
        query = f'(domain="{domain}" || host="{domain}")'
        purpose = t(
            f"结构化规划降级：按用户提供的域名 {domain} 检索",
            f"Fallback plan: search the domain {domain} supplied by the user",
        )
        strategy = "precision"
    elif ip_match:
        ip = _fofa_literal(ip_match.group(0))
        query = f'ip="{ip}"'
        purpose = t(
            f"结构化规划降级：按用户提供的 IP {ip} 检索",
            f"Fallback plan: search the IP {ip} supplied by the user",
        )
        strategy = "precision"
    else:
        library = match_intent_rules(intent, limit=3)
        if library:
            return {
                "action": AgentAction.SEARCH.value,
                "target": "",
                "queries": [
                    {
                        "query": rule.query,
                        "purpose": t(f"规则库精确指纹：{rule.name}", f"Rule-library fingerprint: {rule.name}"),
                        "strategy": "precision",
                    }
                    for rule in library
                ],
                "stats_fields": [],
                "fields": ["host", "ip", "port", "protocol", "title", "domain"],
                "scan": {
                    "recommended": user_authorized_scan(intent),
                    "reason": t(
                        "用户明确提出扫描需求；先完成只读资产发现，再展示边界并请求确认。",
                        "The user asked for a scan. Finish the read-only discovery, then show the scope and ask for confirmation.",
                    )
                    if user_authorized_scan(intent)
                    else t("未明确要求主动扫描。", "The user did not ask for an active scan."),
                    "template_ids": default_nuclei_template_ids() if user_authorized_scan(intent) else [],
                    "severities": ["medium", "high", "critical"],
                },
            }
        term = _fofa_literal(_fallback_search_term(intent))
        clauses = [f'title="{term}"', f'body="{term}"']
        if ORGANIZATION_INTENT_PATTERN.search(term):
            clauses.insert(0, f'org="{term}"')
        query = "(" + " || ".join(clauses) + ")"
        purpose = t(
            f"结构化规划降级：围绕用户核心名称“{term}”进行保守召回",
            f"Fallback plan: conservative recall around the name “{term}”",
        )
        strategy = "recall"
    return {
        "action": AgentAction.SEARCH.value,
        "target": "",
        "queries": [{"query": query, "purpose": purpose, "strategy": strategy}],
        "stats_fields": [],
        "fields": ["host", "ip", "port", "protocol", "title", "domain"],
        "scan": {
            "recommended": user_authorized_scan(intent),
            "reason": t(
                "用户明确提出扫描需求；先完成只读资产发现，再展示边界并请求确认。",
                "The user asked for a scan. Finish the read-only discovery, then show the scope and ask for confirmation.",
            )
            if user_authorized_scan(intent)
            else t("未明确要求主动扫描。", "The user did not ask for an active scan."),
            "template_ids": default_nuclei_template_ids() if user_authorized_scan(intent) else [],
            "severities": ["medium", "high", "critical"],
        },
    }


def _scan_target(values: dict[str, Any]) -> str | None:
    from core.nuclei_protocols import asset_scan_target

    return asset_scan_target(values)


_PUBLISHED_QUERY = re.compile(r"Published FOFA query:\s*(.+)")


def _apply_stated_geo(query: str, intent: str) -> str:
    """Keep a published query, and add only a city or country the user actually named."""
    city = _intent_city(intent)
    if city and not re.search(r"\bcity\s*=", query, re.IGNORECASE):
        wrapped = query if query.startswith("(") else f"({query})"
        country = "" if re.search(r"\bcountry\s*=", query, re.IGNORECASE) else ' && country="CN"'
        return f'{wrapped} && city="{_fofa_literal(city)}"{country}'
    if city or re.search(r"\bcountry\s*=", query, re.IGNORECASE):
        return query
    if re.search(r"中国|国内|大陆", intent):
        return f'({query}) && country="CN"'
    return query


def _research_queries(notes: str, intent: str) -> list[AgentQuery]:
    """Use a FOFA query published in the research notes instead of a generic technology inventory."""
    found: list[AgentQuery] = []
    seen: set[str] = set()
    for match in _PUBLISHED_QUERY.finditer(notes or ""):
        raw = " ".join(match.group(1).split())
        if not raw or validate_query(raw):
            continue
        query = _apply_stated_geo(raw, intent)
        if query in seen or validate_query(query):
            continue
        seen.add(query)
        found.append(
            AgentQuery(
                query=query,
                purpose=t("公开专题给出的 FOFA 语法", "FOFA syntax published on the official topic"),
                strategy="precision",
                source="research",
            )
        )
    return found[:2]


def validate_query(query: str) -> list[str]:
    from core.query_validation import validate_query as validate

    return validate(query)


def _query_candidates(plan: dict[str, Any], *, source: str, limit: int) -> list[AgentQuery]:
    raw_candidates = plan.get("queries") if isinstance(plan.get("queries"), list) else []
    if not raw_candidates and plan.get("query"):
        raw_candidates = [{"query": plan["query"], "purpose": t("主查询", "Primary query")}]
    candidates: list[AgentQuery] = []
    seen: set[str] = set()
    for item in raw_candidates:
        if not isinstance(item, dict):
            continue
        query = str(item.get("query") or "").strip()
        if not query or query in seen:
            continue
        seen.add(query)
        candidates.append(
            AgentQuery(
                query=query,
                purpose=str(item.get("purpose") or t("补充资产维度", "Additional dimension")),
                strategy=str(item.get("strategy") or "balanced"),
                source=source,
            )
        )
        if len(candidates) >= limit:
            break
    return candidates


def _merge_library_queries(intent: str, queries: list[AgentQuery], *, limit: int) -> list[AgentQuery]:
    """Prepend bundled app= fingerprints when the user named a known product."""
    matched = match_intent_rules(intent, limit=min(3, limit))
    if not matched:
        return queries
    existing = " ".join(item.query for item in queries).lower()
    extras = [
        AgentQuery(
            query=rule.query,
            purpose=t(f"规则库精确指纹：{rule.name}", f"Rule-library fingerprint: {rule.name}"),
            strategy="precision",
            source="library",
        )
        for rule in matched
        if rule.query.lower() not in existing
    ]
    if not extras:
        return queries
    merged: list[AgentQuery] = []
    seen: set[str] = set()
    for item in extras + queries:
        key = item.query.strip().lower()
        if key in seen:
            continue
        seen.add(key)
        merged.append(item)
        if len(merged) >= limit:
            break
    return merged


def _domain_hypothesis_insert_at(queries: list[AgentQuery]) -> int:
    """Official-domain hypotheses should run before broad name or body recall."""
    for index, item in enumerate(queries):
        if item.strategy == "recall" or "结构化规划降级" in item.purpose or item.purpose.startswith("Fallback plan:"):
            return index
    return len(queries)


def _domain_hypothesis_candidate(plan: dict[str, Any]) -> AgentQuery | None:
    raw_items = plan.get("domains") if isinstance(plan.get("domains"), list) else []
    domains: list[str] = []
    for item in raw_items:
        if not isinstance(item, dict):
            continue
        domain = str(item.get("domain") or "").strip().lower()
        domain = re.sub(r"^https?://", "", domain).split("/", 1)[0].split(":", 1)[0].removeprefix("www.")
        if re.fullmatch(r"(?=.{1,253}$)(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}", domain):
            domains.append(domain)
    domains = list(dict.fromkeys(domains))[:6]
    if not domains:
        return None
    query = "(" + " || ".join(f'domain="{domain}" || host="{domain}"' for domain in domains) + ")"
    return AgentQuery(
        query=query,
        purpose=t("验证可能的官网域名：", "Check possible official domains: ") + ", ".join(domains),
        strategy="hypothesis",
        source="entity_resolution",
    )


def _normalized_domain(value: Any) -> str | None:
    text = str(value or "").strip().lower()
    if not text:
        return None
    text = re.sub(r"^https?://", "", text).split("/", 1)[0].split(":", 1)[0]
    text = text.removeprefix("*.").removeprefix("www.").rstrip(".")
    if not re.fullmatch(r"(?=.{1,253}$)(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}", text):
        return None
    return text


def _website_identity_terms(run: AgentRun) -> list[str]:
    source = " ".join([run.intent, *run.organization_names]).lower()
    named_domains = re.findall(r"\b(?:[a-z0-9-]+\.)+[a-z]{2,63}\b", run.intent.lower())
    if named_domains:
        # Task verbs such as inventory/public/including are not organization identity evidence.
        stems = [domain.removeprefix("www.").split(".")[0] for domain in named_domains]
        return list(dict.fromkeys(stem for stem in stems if len(stem) >= 3))
    generic = {
        "studio",
        "workroom",
        "website",
        "websites",
        "domain",
        "domains",
        "site",
        "工作室",
        "网站",
        "官网",
        "域名",
    }
    terms = [item for item in re.findall(r"[a-z][a-z0-9_-]{2,}|[\u4e00-\u9fff]{2,}", source) if item not in generic]
    return list(dict.fromkeys(terms))[:12]


def _derive_website_candidates(run: AgentRun) -> list[WebsiteCandidate]:
    """Turn noisy asset rows into a stable, evidence-labelled website inventory."""
    if not WEBSITE_INTENT_PATTERN.search(run.intent):
        return []
    terms = _website_identity_terms(run)
    hypotheses = set(run.domain_hypotheses)
    grouped: dict[str, dict[str, Any]] = {}
    for asset, strategy in zip(run.assets, run.asset_confidence, strict=False):
        host = str(asset.get("host") or "").strip()
        domain = _normalized_domain(asset.get("domain"))
        cert_domain = _normalized_domain(asset.get("cert.subject.cn"))
        host_domain = _normalized_domain(host)
        domain = domain or cert_domain or host_domain
        if not domain:
            continue
        searchable = " ".join(
            str(asset.get(field) or "").lower()
            for field in ("host", "domain", "title", "org", "icp", "cert.subject.org", "cert.subject.cn")
        )
        name_match = any(term in searchable for term in terms)
        if domain not in hypotheses and not name_match:
            continue
        entry = grouped.setdefault(
            domain,
            {
                "hosts": [],
                "strategies": set(),
                "brand_domain": any(term in domain for term in terms),
                "title_match": False,
                "icp": False,
                "certificate": False,
            },
        )
        if host and host not in entry["hosts"]:
            entry["hosts"].append(host)
        entry["strategies"].add(strategy)
        title = str(asset.get("title") or "").lower()
        entry["title_match"] = entry["title_match"] or any(term in title for term in terms)
        entry["icp"] = entry["icp"] or bool(str(asset.get("icp") or "").strip())
        entry["certificate"] = entry["certificate"] or cert_domain == domain

    candidates: list[WebsiteCandidate] = []
    for domain, entry in grouped.items():
        evidence: list[str] = []
        if domain in hypotheses:
            evidence.append("entity_resolution")
        if entry["title_match"]:
            evidence.append("name_in_title")
        if entry["icp"]:
            evidence.append("icp_observed")
        if entry["certificate"]:
            evidence.append("certificate_observed")
        evidence.extend(f"fofa_{item}" for item in sorted(entry["strategies"], key=lambda item: -EVIDENCE_RANK.get(item, 1)))
        if entry["icp"] and (entry["brand_domain"] or entry["title_match"]):
            status, confidence = "corroborated", "high"
        elif domain in hypotheses and entry["title_match"] and entry["certificate"]:
            status, confidence = "corroborated", "high"
        elif domain in hypotheses:
            status, confidence = "observed", "medium"
        else:
            status, confidence = "candidate", "low"
        hosts = entry["hosts"][:8]
        preferred = next(
            (
                item
                for item in hosts
                if item.startswith("https://")
                and (_normalized_domain(item) == domain or str(_normalized_domain(item) or "").endswith(f".{domain}"))
            ),
            None,
        )
        if not preferred:
            preferred = next(
                (
                    item
                    for item in hosts
                    if item.startswith("http://")
                    and (_normalized_domain(item) == domain or str(_normalized_domain(item) or "").endswith(f".{domain}"))
                ),
                None,
            )
        if not preferred:
            preferred = next((item for item in hosts if item.startswith("https://")), None)
        url = preferred or f"https://{domain}"
        candidates.append(
            WebsiteCandidate(
                domain=domain,
                url=url,
                status=status,
                confidence=confidence,
                evidence=list(dict.fromkeys(evidence)),
                hosts=hosts,
            )
        )
    rank = {"corroborated": 0, "observed": 1, "candidate": 2}
    return sorted(candidates, key=lambda item: (rank[item.status], item.domain))[:100]


def _asset_identity(values: dict[str, Any]) -> tuple[str, ...]:
    """One web endpoint, whether FOFA put the port in the host or in its own field."""
    host = str(values.get("host") or "").strip().lower().rstrip("/")
    port = str(values.get("port") or "").strip()
    protocol = str(values.get("protocol") or "").strip().lower()
    scheme = ""
    if host.startswith("https://"):
        scheme = "https"
        host = host[len("https://") :]
    elif host.startswith("http://"):
        scheme = "http"
        host = host[len("http://") :]
    host = host.split("/", 1)[0]
    embedded = ""
    if host.startswith("[") and "]" in host:
        name, _, rest = host.partition("]")
        host = f"{name}]"
        if rest.startswith(":") and rest[1:].isdigit():
            embedded = rest[1:]
    elif host.count(":") == 1:
        name, maybe_port = host.rsplit(":", 1)
        if maybe_port.isdigit():
            host, embedded = name, maybe_port
    if not port:
        port = embedded
    if not protocol:
        protocol = scheme
    if not port and protocol == "https":
        port = "443"
    elif not port and protocol == "http":
        port = "80"
    if host:
        return ("endpoint", host, port, protocol)
    ip = str(values.get("ip") or "").strip().lower()
    if ip:
        return ("endpoint", ip, port, protocol)
    return ("record", repr(sorted((str(key), str(value)) for key, value in values.items())))


def _compact_asset_sample(assets: list[dict[str, Any]], limit: int = 30) -> list[dict[str, str]]:
    useful_fields = (
        "host",
        "domain",
        "ip",
        "port",
        "protocol",
        "title",
        "org",
        "icp",
        "product",
        "server",
        "country",
        "cert.subject.org",
        "cert.subject.cn",
        "cert.issuer.org",
    )
    sample: list[dict[str, str]] = []
    for asset in assets[:limit]:
        compact = {
            field: str(asset[field]).replace("\r", " ").replace("\n", " ")[:240]
            for field in useful_fields
            if asset.get(field) not in (None, "", [], {})
        }
        if compact:
            sample.append(compact)
    return sample


def _top_counts(values: list[str], *, limit: int = 8) -> list[dict[str, Any]]:
    counter = Counter(value for value in values if value)
    return [{"name": name, "count": count} for name, count in counter.most_common(limit)]


def _asset_briefing_stats(run: AgentRun) -> dict[str, Any]:
    assets = run.assets
    truncated = [
        {
            "purpose": item.purpose,
            "available": item.available_count,
            "pulled": item.result_count,
        }
        for item in run.queries
        if item.available_count is not None and item.result_count < item.available_count
    ]
    return {
        "unique_assets": run.result_count,
        "previewed": len(assets),
        "evidence": dict(run.evidence_counts),
        "unique_domains": len({str(asset.get("domain") or "").strip() for asset in assets if asset.get("domain")}),
        "unique_ips": len({str(asset.get("ip") or "").strip() for asset in assets if asset.get("ip")}),
        "top_domains": _top_counts([str(asset.get("domain") or "").strip() for asset in assets]),
        "top_titles": _top_counts([re.sub(r"\s+", " ", str(asset.get("title") or "")).strip()[:80] for asset in assets]),
        "top_orgs": _top_counts([str(asset.get("org") or "").strip() for asset in assets]),
        "top_products": _top_counts([str(asset.get("product") or "").strip()[:100] for asset in assets]),
        "top_servers": _top_counts([str(asset.get("server") or "").strip()[:100] for asset in assets]),
        "top_countries": _top_counts([str(asset.get("country") or "").strip() for asset in assets]),
        "top_ports": _top_counts([str(asset.get("port") or "").strip() for asset in assets]),
        "top_protocols": _top_counts([str(asset.get("protocol") or "").strip().lower() for asset in assets]),
        "alive": _top_counts([str(asset.get("alive_status")) for asset in assets if asset.get("alive_status") not in (None, "")]),
        "truncated_queries": truncated,
    }


def _assets_with_evidence(run: AgentRun, *strategies: str, limit: int = 12) -> list[dict[str, str]]:
    picked: list[dict[str, Any]] = []
    for asset, evidence in zip(run.assets, run.asset_confidence, strict=False):
        if evidence in strategies:
            picked.append(asset)
        if len(picked) >= limit:
            break
    return _compact_asset_sample(picked, limit=limit)


def _query_evidence(run: AgentRun) -> list[dict[str, Any]]:
    return [
        {
            "purpose": item.purpose,
            "query": item.query,
            "available": item.available_count,
            "sampled": item.result_count,
        }
        for item in run.queries[:8]
    ]


def _search_summary_prompt(run: AgentRun, intent: str) -> str:
    return (
        f"User intent: {intent}\n"
        "The rows are passive indexed observations. Without probes do not call them currently reachable. "
        "A bare-IP entry does not prove access-control bypass; matching certificates do not prove legal ownership. "
        "A zero compound query does not negate positive domain records; describe its actual filters.\n"
        f"Executed query evidence: {json.dumps(_query_evidence(run), ensure_ascii=False)}\n"
        f"Structured website candidates: {[item.model_dump() for item in run.website_candidates]}\n"
        f"Inventory stats: {json.dumps(_asset_briefing_stats(run), ensure_ascii=False)}\n"
        f"Higher-confidence sample: {_assets_with_evidence(run, 'precision', 'balanced', 'hypothesis', limit=15)}\n"
        f"Recall/candidate sample: {_assets_with_evidence(run, 'recall', limit=15)}\n"
        f"Planned scan follow-up: requested={run.scan_requested_by_user}, recommended={run.scan_recommended}, "
        f"targets={len(run.scan_targets)}, template_ids={run.scan_template_ids}, severities={run.scan_severities}"
    )


SEARCH_SUMMARY_SYSTEM = (
    "You write a high-value defensive asset briefing in Simplified Chinese. The reader already saw the query-strategy table "
    "and the asset list; do not recount how many FOFA queries ran, do not explain balanced/recall/precision as a method, "
    "and do not narrate available_count, pagination, reflection rounds or intermediate totals. "
    "Start immediately with ## 结论. Do not write chain-of-thought, hidden reasoning, or a preamble. "
    "Synthesize concrete evidence, concentrations, anomalies, attribution limits, coverage gaps and prioritized actions; every claim "
    "must be traceable to the supplied data. Avoid generic security advice and do not pad the answer. Keep the briefing between 350 "
    "and 900 Chinese characters when data is non-empty. "
    "Output GitHub-flavored Markdown in this exact skeleton, with a blank line between sections:\n"
    "## 结论\n"
    "2-3 sentences stating the asset picture, confidence split and most important exposure signal.\n\n"
    "## 高置信资产\n"
    "- **资产簇**：`host`（`ip`），说明归属证据和用途\n\n"
    "## 风险与暴露面\n"
    "- **端口/技术/可达性信号**：具体数据，以及为什么值得关注；不要把暴露直接写成漏洞\n\n"
    "## 证据边界与噪声\n"
    "- **候选簇**：具体误报或归属不确定性及依据\n\n"
    "## 覆盖缺口\n"
    "- **数据缺口**：只写字段缺失、归属不确定或仍待交叉验证的范围。"
    "不要写可见量、取样条数、覆盖率或万分之一，也不要写斜杠计数；抽样边界由程序单独说明。\n\n"
    "## 处置优先级\n"
    "1. 基于具体资产和证据的验证动作、目的与预期结果\n"
    "Rules: use `##` headings only, never numbered section titles; each bullet is one short line; "
    "write 2-5 substantive bullets in each applicable evidence section and 3-5 ordered actions; "
    "wrap hosts, IPs and domains in backticks; bold the cluster label; at most 5 bullets per section; "
    "at most 3 hosts per bullet, then write 等 N 个; do not dump comma-separated subdomain lists. "
    "Do not restate population size, sample counts, coverage ratios, or slash-separated pull counts. "
    "Do not invent domains or products absent from the data. Assets returned by PHP header, server or PHP application "
    "queries are PHP exposure candidates; never call that set “无 PHP 指纹” merely because titles omit php2shell. "
    "A fingerprint is not a confirmed vulnerability. Treat Structured website candidates as the authoritative attribution "
    "boundary: list every corroborated website in the high-confidence section, never promote observed/candidate entries to confirmed "
    "or high-confidence, and do not omit a corroborated website merely because it appears late in the asset sample."
)

SEARCH_SUMMARY_SYSTEM_EN = (
    "You write a high-value defensive asset briefing in English. The reader already saw the query-strategy table "
    "and the asset list; do not recount how many FOFA queries ran, do not explain balanced/recall/precision as a method, "
    "and do not narrate available_count, pagination, reflection rounds or intermediate totals. "
    "Start immediately with ## Conclusion. Do not write chain-of-thought, hidden reasoning, or a preamble. "
    "Synthesize concrete evidence, concentrations, anomalies, attribution limits, coverage gaps and prioritized actions; every claim "
    "must be traceable to the supplied data. Avoid generic security advice and do not pad the answer. Keep the briefing between 180 "
    "and 450 words when data is non-empty. "
    "Output GitHub-flavored Markdown in this exact skeleton, with a blank line between sections:\n"
    "## Conclusion\n"
    "2-3 sentences stating the asset picture, confidence split and most important exposure signal.\n\n"
    "## High-confidence assets\n"
    "- **Cluster**: `host` (`ip`), with the attribution evidence and likely use\n\n"
    "## Exposure\n"
    "- **Port/technology/reachability**: concrete data, and why it matters; do not write exposure as a vulnerability\n\n"
    "## Evidence limits\n"
    "- **Candidate cluster**: a specific false-positive or attribution limit, with the reason\n\n"
    "## Coverage gaps\n"
    "- **Data gap**: missing fields, uncertain attribution, or a range still needing corroboration. "
    "Do not restate visible counts, sample sizes, coverage ratios, or slash-separated pull counts. "
    "The program states the sampling boundary separately.\n\n"
    "## Priority actions\n"
    "1. A verification action tied to a specific asset, its purpose, and the expected result\n"
    "Rules: use `##` headings only, never numbered section titles; each bullet is one short line; "
    "write 2-5 substantive bullets in each applicable evidence section and 3-5 ordered actions; "
    "wrap hosts, IPs and domains in backticks; bold the cluster label; at most 5 bullets per section; "
    "at most 3 hosts per bullet, then write and N more; do not dump comma-separated subdomain lists. "
    "Do not restate population size, sample counts, coverage ratios, or slash-separated pull counts. "
    "Do not invent domains or products absent from the data. Assets returned by PHP header, server or PHP application "
    "queries are PHP exposure candidates; never say the set has no PHP fingerprint merely because titles omit php2shell. "
    "A fingerprint is not a confirmed vulnerability. Treat Structured website candidates as the authoritative attribution "
    "boundary: list every corroborated website in the high-confidence section, never promote observed/candidate entries to confirmed "
    "or high-confidence, and do not omit a corroborated website merely because it appears late in the asset sample."
)


def _briefing_join(items: list[dict[str, Any]], *, limit: int = 5, wrap: bool = False) -> str:
    parts: list[str] = []
    for item in items[:limit]:
        name = str(item.get("name") or "").strip()
        if not name:
            continue
        label = f"`{name}`" if wrap else name
        count = item.get("count")
        parts.append(f"{label} ×{count}" if count not in (None, "") else label)
    return "、".join(parts)


def _local_search_summary(run: AgentRun, *, language: str = "zh") -> str:
    stats = _asset_briefing_stats(run)
    evidence = stats["evidence"]
    high = sum(int(evidence.get(key, 0) or 0) for key in ("precision", "balanced", "hypothesis"))
    recall = int(evidence.get("recall", 0) or 0)
    blank = "none" if language == "en" else "无"
    unknown = "unidentified" if language == "en" else "未识别"
    missing = "not returned" if language == "en" else "未返回"
    unchecked = "not probed" if language == "en" else "未探测"
    domains = _briefing_join(stats["top_domains"], wrap=True) or blank
    titles = _briefing_join(stats["top_titles"]) or blank
    ports = _briefing_join(stats["top_ports"]) or blank
    protocols = _briefing_join(stats["top_protocols"]) or blank
    products = _briefing_join(stats["top_products"]) or unknown
    servers = _briefing_join(stats["top_servers"]) or unknown
    countries = _briefing_join(stats["top_countries"]) or missing
    alive = _briefing_join(stats["alive"]) or unchecked
    corroborated = "、".join(f"`{item.domain}`" for item in run.website_candidates if item.status == "corroborated") or blank
    candidates = "、".join(f"`{item.domain}`（{item.status}）" for item in run.website_candidates if item.status != "corroborated") or blank
    if language == "en":
        return (
            "## Conclusion\n"
            f"The sample has {stats['unique_assets']} distinct assets across {stats['unique_domains']} domains and "
            f"{stats['unique_ips']} IPs; about {high} are higher confidence and {recall} are name or body candidates. "
            "Treat this as an exposure inventory. Ownership and vulnerability claims still need separate verification.\n\n"
            "## High-confidence assets\n"
            f"- **Corroborated sites**: {corroborated}\n"
            f"- **Main domains**: {domains}\n\n"
            "## Exposure\n"
            f"- **Ports and protocols**: ports {ports}; protocols {protocols}\n"
            f"- **Products and servers**: products {products}; servers {servers}\n"
            f"- **Reachability and geography**: liveness {alive}; geography {countries}\n\n"
            "## Evidence limits\n"
            f"- **Unconfirmed sites**: {candidates}\n"
            f"- **Frequent titles**: {titles}; a title or body hit is not ownership\n"
            f"- **Recall candidates**: {recall} still need site content, filing, certificate, or another authoritative source\n\n"
            "## Coverage gaps\n"
            "- **Fields and attribution**: product mix comes only from this sample; titles and body hits still need "
            "a certificate, filing, or official site\n"
            f"- **Open leads**: {candidates}\n\n"
            "## Priority actions\n"
            "1. Verify corroborated sites, their certificates, filings, and official redirects before treating them as in scope.\n"
            "2. Review unusual ports, reachability, and product fingerprints, and confirm whether the service should be public.\n"
            "3. Exclude third-party mentions, parked pages, and shared infrastructure from name or body candidates.\n"
            "4. Re-check targets, templates, and severity before any authorized scan, then validate hits manually.\n"
        )
    return (
        "## 结论\n"
        f"共识别去重资产 {stats['unique_assets']} 条，覆盖 {stats['unique_domains']} 个域名和 "
        f"{stats['unique_ips']} 个 IP；高置信约 {high} 条，名称/正文召回候选 {recall} 条。"
        "当前结果适合作为暴露面清单，但组织归属和漏洞结论仍需独立验证。\n\n"
        "## 高置信资产\n"
        f"- **交叉印证网站**：{corroborated}\n"
        f"- **主要域名**：{domains}\n\n"
        "## 风险与暴露面\n"
        f"- **端口与协议**：端口 {ports}；协议 {protocols}\n"
        f"- **产品与服务器**：产品 {products}；服务器 {servers}\n"
        f"- **可达性与地域**：存活状态 {alive}；地域 {countries}\n\n"
        "## 证据边界与噪声\n"
        f"- **待确认网站**：{candidates}\n"
        f"- **高频标题**：{titles}；标题或正文命中不等同于组织归属\n"
        f"- **召回候选**：{recall} 条仍需官网内容、备案、证书或权威来源交叉验证\n\n"
        "## 覆盖缺口\n"
        "- **字段与归属**：产品分布只来自本次抽样；标题或正文命中仍需证书、备案或官网交叉验证\n"
        f"- **未闭合线索**：{candidates}\n\n"
        "## 处置优先级\n"
        "1. 先核验交叉印证网站及其证书、备案和官网跳转关系，固化真实资产边界。\n"
        "2. 按非标准端口、可达性和产品指纹排序复核，确认服务用途与是否应对公网开放。\n"
        "3. 对名称/正文候选逐项排除第三方引用、停放页和共享基础设施，避免扩大扫描范围。\n"
        "4. 扫描前再次核对目标、模板及严重级别审批范围，并对命中结果进行人工验证。\n"
    )


def _local_generic_summary(run: AgentRun, *, language: str = "zh") -> str:
    if run.action is AgentAction.HOST:
        return _local_host_summary(run, language=language)
    if run.action is AgentAction.STATS:
        return _local_stats_summary(run, language=language)
    return _local_search_summary(run, language=language)


def _pct(count: int, total: int) -> str:
    if total <= 0:
        return "0%"
    return f"{count * 100 / total:.1f}%"


def _concentration(share: float, language: str) -> str:
    if language == "en":
        if share >= 0.7:
            return "highly concentrated"
        if share >= 0.4:
            return "relatively concentrated"
        return "spread out"
    if share >= 0.7:
        return "高度集中"
    if share >= 0.4:
        return "相对集中"
    return "比较分散"


def _agg_dimensions(run: AgentRun) -> list[tuple[str, list[tuple[str, int]]]]:
    aggs = run.result_data.get("aggs") if isinstance(run.result_data, dict) else None
    if not isinstance(aggs, dict):
        return []
    dimensions: list[tuple[str, list[tuple[str, int]]]] = []
    for field, rows in aggs.items():
        parsed = [
            (str(item.get("name")), int(item.get("count") or 0))
            for item in (rows or [])
            if isinstance(item, dict) and str(item.get("name") or "").strip()
        ]
        if parsed:
            dimensions.append((str(field), parsed))
    return dimensions


def _local_stats_summary(run: AgentRun, *, language: str = "zh") -> str:
    from core.html_report import _chart_title

    total = int(run.result_count or 0)
    dimensions = _agg_dimensions(run)
    lang = "en" if language == "en" else "zh"
    if language == "en":
        if total <= 0 or not dimensions:
            return (
                "## Conclusion\nThis query returned no aggregate distribution, so there is nothing to judge.\n\n"
                "## Data analysis\n- **Limit**: a zero result only means this query returned no buckets.\n"
            )
        lead_field, lead_rows = dimensions[0]
        lead_name, lead_count = lead_rows[0]
        share = lead_count / total if total else 0
        lines = [
            "## Conclusion",
            (
                f"{_chart_title(lead_field, lang)} is {_concentration(share, language)} on {lead_name}, "
                f"{_pct(lead_count, total)} of {total:,}. "
                "That describes where the exposure sits. It does not show missing authentication or a vulnerability."
            ),
            "",
            "## Data analysis",
        ]
        for field, rows in dimensions:
            top_name, top_count = rows[0]
            detail = f"- **{_chart_title(field, lang)}**: {top_name} has {top_count:,} ({_pct(top_count, total)})"
            if len(rows) > 1:
                second_name, second_count = rows[1]
                detail += f"; next is {second_name} with {second_count:,} ({_pct(second_count, total)})"
            lines.append(detail + ".")
        lines.append("- **Limit**: buckets do not include version, authentication, or whether the service is meant to be public.")
        return "\n".join(lines) + "\n"
    if total <= 0 or not dimensions:
        return (
            "## 结论\n这条语句没有返回可分析的分布，无法判断暴露面集中在哪里。\n\n"
            "## 数据分析\n- **边界**：总量为 0 只说明当前查询没有聚合结果，不能据此判断该范围内不存在资产。\n"
        )
    lead_field, lead_rows = dimensions[0]
    lead_name, lead_count = lead_rows[0]
    share = lead_count / total if total else 0
    lead_title = _chart_title(lead_field, lang)
    judgment = (
        f"{lead_title}{_concentration(share, language)}在 {lead_name}，占比 {_pct(lead_count, total)}（{lead_count:,} / {total:,}）。"
    )
    if len(dimensions) > 1:
        other_field, other_rows = dimensions[1]
        other_name, other_count = other_rows[0]
        other_share = other_count / total if total else 0
        judgment += (
            f"{_chart_title(other_field, lang)}{_concentration(other_share, language)}在 {other_name}，占比 {_pct(other_count, total)}。"
        )
        if share >= 0.7 and other_share >= 0.7:
            judgment += "两个维度都指向同一类结果，说明公开索引里主要是同一类服务，而不是均匀铺开的杂项。"
    judgment += "这是暴露面集中程度的判断，不能据此判断未授权或漏洞。"
    lines = ["## 结论", judgment, "", "## 数据分析"]
    for field, rows in dimensions:
        top_name, top_count = rows[0]
        detail = f"- **{_chart_title(field, lang)}**：{top_name} 有 {top_count:,}，占比 {_pct(top_count, total)}"
        if len(rows) > 1:
            second_name, second_count = rows[1]
            detail += f"；其次是 {second_name}，有 {second_count:,}，占比 {_pct(second_count, total)}"
        lines.append(detail + "。")
    distinct = run.result_data.get("distinct") if isinstance(run.result_data, dict) else None
    if isinstance(distinct, dict) and distinct.get("ip") is not None and int(distinct["ip"]) < total:
        lines.append(f"- **地址**：独立 IP {int(distinct['ip']):,} 少于总量 {total:,}，同一地址上往往有多条记录。")
    lines.append("- **边界**：聚合没有版本、认证状态，也不能说明这些服务是否应当对公网开放。")
    return "\n".join(lines) + "\n"


def _local_host_summary(run: AgentRun, *, language: str = "zh") -> str:
    data = run.result_data if isinstance(run.result_data, dict) else {}
    target = run.target or str(data.get("host") or data.get("ip") or "")
    ports = [item for item in (data.get("ports") or []) if isinstance(item, dict)]
    names: list[str] = []
    for port in ports:
        for product in port.get("products") or []:
            if isinstance(product, dict):
                name = str(product.get("product") or product.get("name") or "").strip()
                if name and name not in names:
                    names.append(name)
    shown = "、".join(names[:4]) if names else ""
    port_bits = [f"{port.get('port')}/{port.get('protocol') or '-'}" for port in ports[:6]]
    if language == "en":
        target_text = f"`{target}`" if target else "this host"
        product_text = shown or "no named product"
        return (
            "## Conclusion\n"
            f"The profile for {target_text} shows {len(ports)} port entries, led by {product_text}. "
            "This is the observed exposure. It does not show a vulnerability.\n\n"
            "## Data analysis\n"
            f"- **Ports**: {', '.join(port_bits) or 'none returned'}.\n"
            f"- **Products**: {product_text}.\n"
            "- **Limit**: the profile has no authentication state and is not a vulnerability finding.\n"
        )
    target_text = f"`{target}`" if target else "该主机"
    if not ports:
        body = f"{target_text} 的画像没有返回端口明细，无法判断暴露了哪些服务。"
    elif shown:
        body = f"{target_text} 公开了 {len(ports)} 个端口条目，组件主要是 {shown}。端口和组件互相印证的是 FOFA 观察到的服务，不是漏洞结论。"
    else:
        body = f"{target_text} 公开了 {len(ports)} 个端口条目，但没有返回组件名称。这只能说明端口在索引中可见。"
    listed = "、".join(port_bits) or "无"
    product_line = shown or "未返回"
    return (
        "## 结论\n"
        f"{body}不能据此判断未授权或漏洞。\n\n"
        "## 数据分析\n"
        f"- **端口与协议**：{listed}。\n"
        f"- **组件**：{product_line}。\n"
        "- **边界**：画像没有认证状态和版本验证，不能说明这些端口是否应当对公网开放。\n"
    )


def _summary_matches_language(text: str, language: str) -> bool:
    """Check prose language while allowing source names and queries in inline code."""
    if language == "en":
        prose = re.sub(r"```.*?```|`[^`]*`", "", text, flags=re.DOTALL)
        chinese = len(re.findall(r"[\u4e00-\u9fff]", prose))
        latin = len(re.findall(r"[A-Za-z]", prose))
        return latin >= 10 and latin >= chinese * 4
    if language == "zh":
        return len(re.findall(r"[\u4e00-\u9fff]", text)) >= 20
    return True


def _summary_has_judgment(text: str, language: str) -> bool:
    """A conclusion that only repeats the query, total, and top bucket is not an analysis."""
    if language == "en":
        lowered = text.lower()
        return any(token in lowered for token in ("concentrat", "spread", "share", "exposure", "does not"))
    return any(token in text for token in ("占比", "集中", "分散", "暴露面", "不能据此", "说明"))


_PROFILE_SUMMARY_SYSTEM = {
    "zh": (
        "用简体中文写主机暴露面解读。读者已经看到端口表，不要只罗列端口和产品。"
        "以 ## 结论 开头，用两三句判断这台主机暴露了什么、组件是否集中、有没有值得注意的端口。"
        "接着写 ## 数据分析，说明端口、协议和组件之间的对应关系，以及画像不能证明什么。"
        "把观察到的事实和推断分开。没有验证证据时不要写成漏洞或未授权。不要写利用步骤，不要改用英文。"
    ),
    "en": (
        "Write a host-profile conclusion in English. The reader already has the port table, so do not only list ports. "
        "Start with ## Conclusion and judge what is exposed. Then write ## Data analysis relating ports, protocols, "
        "and products. Do not claim a vulnerability without validation."
    ),
}
_STATS_SUMMARY_SYSTEM = {
    "zh": (
        "用简体中文写统计结论。读者已经看到查询语句和图表，不要复述查询语句、字段名，也不要只写“数量最高的取值”。"
        "以 ## 结论 开头，用两三句给出判断：分布是集中还是分散，头部取值占总量的比例，这种集中说明什么暴露面。"
        "接着写 ## 数据分析，用短列表比较每个维度的前两名和占比，并说明维度之间是否互相印证。"
        "数字和占比只能来自给定结果。总量为 0 时说明没有命中，不要编造分布。"
        "总量为零时，控制在200字内，写明没有返回分布、证据边界和一个复核步骤，"
        "不要逐个罗列空字段、费用字段或空对比表。"
        "不要把聚合写成漏洞或未授权，不要写利用步骤，不要改用英文。"
    ),
    "en": (
        "Write an aggregate-statistics conclusion in English. The reader already has the query and charts. "
        "Do not only restate the query, the field names, and the largest bucket. "
        "Start with ## Conclusion and judge whether the distribution is concentrated or spread, including the top share. "
        "Then write ## Data analysis comparing the top two buckets in each dimension. "
        "Use only numbers from the payload. Do not infer a vulnerability from the aggregate. "
        "For zero matches, use at most 100 words: state no distribution was returned, give the scope/coverage limit, "
        "and one verification step. Do not list null fields, cost fields, or empty comparison tables."
    ),
}


def _asset_briefing_has_sufficient_quality(text: str) -> bool:
    skeletons = (
        ("## 结论", "## 高置信资产", "## 风险与暴露面", "## 证据边界与噪声", "## 覆盖缺口", "## 处置优先级"),
        ("## Conclusion", "## High-confidence assets", "## Exposure", "## Evidence limits", "## Coverage gaps", "## Priority actions"),
    )
    substantive_lines = [line for line in text.splitlines() if line.lstrip().startswith(("- ", "1. ", "2. ", "3. "))]
    return len(text) >= 320 and any(all(heading in text for heading in required) for required in skeletons) and len(substantive_lines) >= 8


def _apply_generated_summary(
    run: AgentRun,
    text: str | None,
    *,
    fallback: str,
    require_asset_briefing: bool = False,
    language: str = "zh",
) -> None:
    cleaned = (text or "").strip()
    acceptable = bool(cleaned) and _summary_matches_language(cleaned, language)
    if acceptable and run.action is AgentAction.STATS and run.result_count == 0:
        acceptable = len(cleaned.split()) <= 120 if language == "en" else len(cleaned) <= 300
    if acceptable and run.action in {AgentAction.STATS, AgentAction.HOST} and not _summary_has_judgment(cleaned, language):
        acceptable = False
    if acceptable and (not require_asset_briefing or _asset_briefing_has_sufficient_quality(cleaned)):
        run.summary = cleaned
        run.summary_source = "model"
        return
    logger.warning("模型未返回达到质量门槛的总结，已改用本地结构化资产简报。")
    run.summary = fallback
    run.summary_source = "local"


_SCAN_ADVICE_SYSTEM = {
    "zh": (
        "你只根据给定的授权 Nuclei 命中写防御性修复建议，使用简体中文。"
        "不要写标题。先用一两句说明这些命中仍需人工复核，不能单独当成已确认漏洞。"
        "然后写编号清单，每一条对应一个检测项：点名站点、检测项，以及具体要改的配置或响应头。"
        "模板自带 remediation 时沿用，不要另写一套相反的修法。"
        "不要写利用步骤、payload 或攻击过程。不要编造数据里没有的 CVE、产品或主机。"
    ),
    "en": (
        "Write defensive remediation for the supplied authorized Nuclei findings, in English. "
        "Do not add a title. Start with one or two sentences stating that the hits still need human review "
        "and are not confirmed vulnerabilities by themselves. "
        "Then write a numbered list. Each item names the site, the check, and the concrete configuration or header change. "
        "When a template already includes remediation text, follow it. "
        "Do not write exploit steps, payloads, or attack procedures. Do not invent CVEs, products, or hosts."
    ),
}


def _scan_advice_prompt(run: AgentRun) -> str:
    from core.scanner import load_nuclei_result

    path = Path(str(run.scan_artifact or ""))
    if path.suffix != ".jsonl" or not path.is_file():
        return ""
    result = load_nuclei_result(path, target_count=len(run.scan_targets))
    if not result.findings:
        return ""
    hits = []
    for hit in result.grouped()[:20]:
        hits.append(
            {
                "target": hit.target,
                "template_id": hit.template_id,
                "name": hit.name,
                "severity": hit.severity,
                "details": list(hit.details),
                "count": hit.count,
                "description": hit.description[:500],
                "remediation": hit.remediation[:800],
            }
        )
    return f"User intent: {run.intent}\nScan reason: {run.scan_reason}\nFindings: {json.dumps(hits, ensure_ascii=False)}"


async def generate_scan_advice(run: AgentRun, router: Any, *, language: str = "zh") -> None:
    """Ask the configured model for remediation. Leave the report field empty when there is nothing to write."""
    prompt = _scan_advice_prompt(run)
    if not prompt:
        run.scan_advice = None
        return
    lang = "en" if language == "en" else "zh"
    events = getattr(router, "events", None)
    before = len(events) if isinstance(events, list) else 0
    result = await router.generate("summarizer", system=_SCAN_ADVICE_SYSTEM[lang], prompt=prompt)
    advice = (getattr(result, "text", None) or "").strip()
    run.scan_advice = advice or None
    if not isinstance(events, list):
        return
    for event in events[before:]:
        payload = event.model_dump(mode="json") if hasattr(event, "model_dump") else dict(event)
        run.route_events.append(payload)


def _align_action_to_membership(
    run: AgentRun,
    user_info: dict[str, Any],
    *,
    on_progress: AgentProgressCallback | None = None,
) -> None:
    membership = membership_from_account(user_info)
    if membership is None:
        return
    if run.action is AgentAction.STATS and not membership.stats_api:
        run.action = AgentAction.SEARCH
        _record_step(
            run,
            AgentState.INTENT,
            t(
                f"{membership.name} 无统计聚合 API，已改为普通检索",
                f"{membership_label(membership)} has no stats API, so this switched to a normal search",
            ),
            data={"vip_level": membership.vip_level, "fallback": AgentAction.SEARCH.value},
            on_progress=on_progress,
        )
        return
    if run.action is AgentAction.HOST and not membership.host_api:
        if run.target and not run.queries:
            fallback = host_fallback_query(run.target)
            run.queries = [
                AgentQuery(
                    query=fallback,
                    purpose=t(
                        f"{membership.name} 无主机聚合，改用检索",
                        f"{membership_label(membership)} has no host API, so this uses search",
                    ),
                    strategy="balanced",
                    source="membership",
                )
            ]
        run.action = AgentAction.SEARCH
        _record_step(
            run,
            AgentState.INTENT,
            t(
                f"{membership.name} 无主机聚合 API，已改为普通检索",
                f"{membership_label(membership)} has no host API, so this switched to a normal search",
            ),
            data={"vip_level": membership.vip_level, "target": run.target, "fallback": AgentAction.SEARCH.value},
            on_progress=on_progress,
        )


def _primary_visible(run: AgentRun) -> int:
    chosen = next((item for item in run.queries if run.query and item.query == run.query), None)
    if chosen is None and run.queries:
        chosen = run.queries[0]
    return int(chosen.available_count or 0) if chosen else 0


def _mark_sampling(run: AgentRun, max_records: int, *, truncated: bool = False, sampled: bool = False) -> None:
    if run.population_size <= 0:
        run.population_size = _primary_visible(run)
    run.sampled = sampled
    run.sample_limit = max_records
    sampled = run.result_count
    population = run.population_size
    partial = truncated or any((item.available_count or 0) > item.result_count for item in run.queries if item.pages > 0)
    if sampled >= max_records and (partial or population > sampled):
        run.sample_stop_reason = "user_limit"
    elif partial:
        run.sample_stop_reason = "page_window"
    elif population <= sampled or population == 0:
        run.sample_stop_reason = "complete"
    elif sampled >= max_records:
        run.sample_stop_reason = "user_limit"
    else:
        run.sample_stop_reason = "page_window"


async def _population_portrait(
    agent: FofaAgent,
    run: AgentRun,
    *,
    max_records: int,
    on_progress: AgentProgressCallback | None,
) -> None:
    primary = next((item for item in run.queries if item.query == run.query), None)
    visible = int(primary.available_count or 0) if primary else 0
    if primary is None or visible <= max(max_records * 10, 1000):
        return
    info = getattr(agent.client, "user_info", None)
    membership = membership_from_account(info) if info else None
    if membership is not None and not membership.stats_api:
        _record_step(
            run,
            AgentState.EVALUATE,
            t(
                "账号无统计接口，总体分布留空，仅保留抽样",
                "This account has no stats API. The sample is kept and the overall distribution is left empty.",
            ),
            on_progress=on_progress,
        )
        return
    stats = getattr(agent.client, "stats", None)
    if not callable(stats):
        return
    _record_step(
        run,
        AgentState.EXECUTE,
        t(
            "可见规模远大于抽样上限，正在读取主查询的统计分布",
            "The visible set is much larger than the sample cap. Reading the primary query distribution.",
        ),
        data={"query": primary.query, "fields": list(PORTRAIT_FIELDS)},
        on_progress=on_progress,
    )
    try:
        data = await stats(primary.query, list(PORTRAIT_FIELDS))
    except (FofaError, TypeError, AttributeError) as exc:
        code = exc.code.value if isinstance(exc, FofaError) else "stats_unavailable"
        _record_step(
            run,
            AgentState.EVALUATE,
            t("统计分布未获取，已保留抽样结果", "The distribution was not available. The sample is kept."),
            data={"code": code, "message": str(exc)},
            on_progress=on_progress,
        )
        return
    aggs = data.get("aggs") if isinstance(data, dict) else None
    if not isinstance(aggs, dict) or not aggs:
        return
    run.population_aggs = {str(key): value for key, value in aggs.items() if str(key) in PORTRAIT_FIELDS}
    size = int(data.get("size") or 0)
    if size:
        run.population_size = max(run.population_size, size)


class FofaAgent:
    def __init__(self, client: FofaClient, router: ProviderRouter) -> None:
        self.client = client
        self.router = router

    async def _execute_routed_action(
        self,
        run: AgentRun,
        intent: str,
        *,
        on_progress: AgentProgressCallback | None,
        report_language: str = "zh",
    ) -> bool:
        """Execute non-list actions selected by the planner; return whether the run is complete."""
        report_language = _reply_language(report_language)
        if run.action is AgentAction.ICON:
            if not run.target:
                raise ValueError(t("icon_query 需要明确的 URL 目标", "icon_query needs an explicit URL"))
            from utils.helpers import IconHashCalculator

            _record_step(
                run,
                AgentState.EXECUTE,
                t(f"正在安全获取 {run.target} 的网站图标", f"Fetching the favicon for {run.target}"),
                on_progress=on_progress,
            )
            icon_query = await IconHashCalculator.get_hash(run.target)
            if not icon_query:
                raise ValueError(t("无法获取网站图标或计算哈希", "Could not fetch the favicon or calculate its hash"))
            run.queries = [
                AgentQuery(
                    query=icon_query,
                    purpose=t("使用目标网站图标的 MurmurHash3 反查同类资产", "Find similar assets from the site favicon hash"),
                    strategy="balanced",
                )
            ]
            run.query = icon_query
            _record_step(
                run,
                AgentState.INTENT,
                t("已将图标反查动作转换为可审计的 FOFA 查询策略", "Turned the favicon lookup into an auditable FOFA query"),
                data={"target": run.target, "query": icon_query},
                on_progress=on_progress,
            )
            return False

        if run.action is AgentAction.HOST:
            if not run.target:
                raise ValueError(t("host_query 需要明确的 IP 地址或主机目标", "host_query needs an explicit IP or hostname"))
            _record_step(
                run,
                AgentState.EXECUTE,
                t(f"正在查询主机聚合画像：{run.target}", f"Reading the host profile for {run.target}"),
                on_progress=on_progress,
            )
            data = await self.client.host_profile(run.target)
            run.result_data = data
            run.result_count = 1
            _record_step(
                run,
                AgentState.EVALUATE,
                t(
                    f"主机画像已返回，共 {len(data.get('ports') or [])} 个端口条目",
                    f"Host profile returned {len(data.get('ports') or [])} port entries",
                ),
                data={"target": run.target, "ports": len(data.get("ports") or [])},
                on_progress=on_progress,
            )
            _record_step(
                run,
                AgentState.SUMMARIZE,
                t("正在生成单体资产暴露面解读", "Writing the host exposure briefing"),
                on_progress=on_progress,
            )
            summary = await self.router.generate(
                "summarizer",
                system=_PROFILE_SUMMARY_SYSTEM[_reply_language(report_language)] + _english_reply_clause(report_language),
                prompt=(
                    f"User intent: {intent}\nTarget: {run.target}\n"
                    f"Reply language: {'English' if report_language == 'en' else '简体中文'}\n"
                    f"FOFA Host data: {json.dumps(data, ensure_ascii=False, default=str)[:12000]}"
                ),
            )
            _apply_generated_summary(
                run,
                summary.text,
                fallback=_local_generic_summary(run, language=report_language),
                language=report_language,
            )
            _record_step(run, AgentState.COMPLETED, t("主机画像任务已完成", "Host profile finished"), on_progress=on_progress)
            return True

        if run.action is AgentAction.STATS:
            if not run.queries:
                raise ValueError(t("stat_query 需要一条 FOFA 查询语句", "stat_query needs one FOFA query"))
            run.stats_fields = list(dict.fromkeys(field for field in run.stats_fields if field in STAT_FIELDS)) or [
                "country",
                "port",
            ]
            data: dict[str, Any] = {}
            for index, item in enumerate(run.queries):
                errors = validate_query(item.query)
                if errors:
                    if index == 0:
                        raise ValueError(t("统计查询语法无效：", "The statistics query is invalid: ") + "; ".join(errors))
                    continue
                _record_step(
                    run,
                    AgentState.EXECUTE,
                    t(
                        f"正在执行统计聚合：{', '.join(run.stats_fields)}",
                        f"Running the aggregate: {', '.join(run.stats_fields)}",
                    ),
                    data={"query": item.query, "fields": run.stats_fields},
                    on_progress=on_progress,
                )
                skipped = False
                try:
                    data = await self.client.stats(item.query, run.stats_fields)
                except FofaError as exc:
                    if not _query_error_can_be_rewritten(exc):
                        raise
                    rewritten = await _rewrite_rejected_query(
                        self.router,
                        intent=intent,
                        query=item.query,
                        error=str(exc),
                    )
                    if rewritten:
                        _record_step(
                            run,
                            AgentState.REPAIR,
                            t(
                                "统计语句被 FOFA 拒绝，已交给 AI 重写后重试",
                                "FOFA rejected the stats query. Asking the model to rewrite it.",
                            ),
                            data={"from": item.query, "to": rewritten, "message": str(exc)},
                            on_progress=on_progress,
                        )
                        item.query = rewritten
                        try:
                            data = await self.client.stats(item.query, run.stats_fields)
                        except FofaError as again:
                            if not _query_error_can_be_rewritten(again):
                                raise
                            _record_step(
                                run,
                                AgentState.EVALUATE,
                                t("统计语句重写后仍被 FOFA 拒绝，已跳过", "FOFA rejected the rewritten stats query. Skipped."),
                                data={"query": item.query, "message": str(again)},
                                on_progress=on_progress,
                            )
                            skipped = True
                    else:
                        _record_step(
                            run,
                            AgentState.EVALUATE,
                            t(
                                "统计语句被 FOFA 拒绝，重写后仍不可用，已跳过",
                                "FOFA rejected the stats query and the rewrite was not usable. Skipped.",
                            ),
                            data={"query": item.query, "message": str(exc)},
                            on_progress=on_progress,
                        )
                        skipped = True
                if skipped:
                    continue
                size = int(data.get("size") or 0)
                item.available_count = size
                run.query = item.query
                run.result_data = data
                run.result_count = size
                _record_step(
                    run,
                    AgentState.EVALUATE,
                    t(f"统计聚合完成，FOFA 总量 {size:,} 条", f"Aggregate finished. FOFA total {size:,}."),
                    data={"query": item.query, "fields": run.stats_fields, "size": size},
                    on_progress=on_progress,
                )
                if size or index == len(run.queries) - 1:
                    break
                _record_step(
                    run,
                    AgentState.EVALUATE,
                    t("该语句总量为 0，继续尝试下一条查询", "This query returned 0. Trying the next one."),
                    data={"next": run.queries[index + 1].query},
                    on_progress=on_progress,
                )
            _record_step(
                run,
                AgentState.SUMMARIZE,
                t("正在生成统计分布解读", "Writing the distribution briefing"),
                on_progress=on_progress,
            )
            summary = await self.router.generate(
                "summarizer",
                system=_STATS_SUMMARY_SYSTEM[_reply_language(report_language)] + _english_reply_clause(report_language),
                prompt=(
                    f"User intent: {intent}\nQuery: {run.query}\nDimensions: {run.stats_fields}\n"
                    f"Reply language: {'English' if report_language == 'en' else '简体中文'}\n"
                    f"FOFA statistics: {json.dumps(data, ensure_ascii=False, default=str)[:12000]}"
                ),
            )
            _apply_generated_summary(
                run,
                summary.text,
                fallback=_local_generic_summary(run, language=report_language),
                language=report_language,
            )
            _record_step(run, AgentState.COMPLETED, t("统计聚合任务已完成", "Statistics finished"), on_progress=on_progress)
            return True

        return False

    async def _collect_routed_scan_candidates(
        self, run: AgentRun, *, max_records: int, max_pages: int, size: int, on_progress: AgentProgressCallback | None,
    ) -> None:
        """A statistics/profile action must not silently discard the user's scan request."""
        query = host_fallback_query(run.target) if run.action is AgentAction.HOST else run.query
        if not query:
            run.scan_scope_note = t(
                "用户要求扫描，但没有有效的资产查询范围。", "A scan was requested but no valid asset query is available."
            )
            return
        _record_step(
            run, AgentState.EXECUTE,
            t("用户要求扫描，正在按当前查询范围准备候选目标（AI 建议仅供参考）",
              "Preparing scan targets in the current query scope as requested by the user; AI advice is advisory"),
            on_progress=on_progress,
        )
        request = SearchRequest(
            query=query, fields=["host", "protocol", "ip", "port", "title"], size=min(size, max_records),
            max_records=max_records, max_pages=max_pages,
        )
        seen = set()
        for row in run.assets:
            target = _scan_target(row)
            if target:
                seen.add(target)
                run.scan_targets.append(target)
        fetched = 0
        async for page in self.client.iter_search(request):
            for record in page.records:
                if fetched >= max_records:
                    break
                fetched += 1
                target = _scan_target(record.values)
                if target and target not in seen:
                    seen.add(target)
                    run.assets.append(record.values)
                    run.scan_targets.append(target)
            if fetched >= max_records:
                break
        run.scan_scope_note = t(
            f"保留原统计/画像结果；按本次查询范围、最多 {max_pages} 页 / {max_records} 条准备了 {len(run.scan_targets)} 个扫描目标，"
            "不表示覆盖全部统计资产。等待确认精确方案。",
            f"Statistics/profile results are retained. Prepared {len(run.scan_targets)} scan targets within the query scope, "
            f"up to {max_pages} pages / {max_records} records; this is not coverage of every aggregate result. Awaiting plan approval.",
        )
        _record_step(run, AgentState.COMPLETED, run.scan_scope_note, on_progress=on_progress)

    async def run(
        self,
        intent: str,
        *,
        max_records: int = 1000,
        max_pages: int = 10,
        size: int = 100,
        fields: list[str] | None = None,
        smart_fields: bool = True,
        on_progress: AgentProgressCallback | None = None,
        on_page: AgentPageCallback | None = None,
        search_context: str = "",
        report_language: str = "zh",
        sample: bool = True,
        scan_requested: bool = False,
    ) -> AgentRun:
        report_language = _reply_language(report_language)
        run = AgentRun(intent=intent)
        span = trace.get_tracer("fofamap.agent").start_span("fofamap.agent.run")
        span.set_attribute("fofamap.agent.run_id", run.id)

        def finish() -> AgentRun:
            run.finished_at = datetime.now()
            run.route_events = [event.model_dump(mode="json") for event in self.router.events]
            span.set_attribute("fofamap.agent.action", run.action.value)
            span.set_attribute("fofamap.agent.state", run.state.value)
            span.set_attribute("fofamap.agent.result_count", run.result_count)
            if run.error:
                span.set_attribute("error.type", str(run.error.get("code", "agent_error")))
            span.end()
            return run

        try:
            _record_step(
                run,
                AgentState.INTENT,
                t("正在识别任务类型并制定 FOFA 执行策略", "Identifying the task and choosing a FOFA plan"),
                on_progress=on_progress,
            )
            run.scan_requested_by_user = user_authorized_scan(intent) or scan_requested
            user_info = getattr(self.client, "user_info", None) or {}
            vip_level = user_info.get("vip_level", user_info.get("level", "unknown"))
            tier = account_tier(vip_level)
            planner_system = (
                "You are a FOFA action router and query strategist. Select exactly one action: fofa_search for an asset list; "
                "host_query only for a single explicit IP/host profile; stat_query for counts, distributions, rankings or trends; "
                "or icon_query for reverse-searching an explicit website favicon. Put the explicit host/URL in target for host/icon "
                "actions, use an empty target for other actions, and select only supported aggregate dimensions for stat_query. "
                "For fofa_search, translate defensive asset-discovery intent into one to five high-quality, "
                "complementary read-only query strategies. A strategy may be a focused single clause or an advanced composite "
                "expression using parentheses, || and &&. Optimize the portfolio for coverage, precision and API efficiency: combine "
                "aliases or equivalent ownership signals in one query when that saves requests without adding noise; keep queries "
                "separate when they represent different precision/recall tradeoffs or need independent result evaluation. Include at "
                "least one balanced or recall-oriented strategy for organization discovery. Use domain, host, org, certificate "
                "subject, "
                "ICP, title, header or body only when semantically appropriate. Search syntax fields such as body= are independent of "
                "returned result fields. Do not invent a domain, ICP number, company alias or geography; organization-to-domain "
                "resolution is performed separately. Avoid an unbounded body/header organization-name query when it is likely to "
                "swamp the "
                "portfolio with third-party mentions; constrain it when a safe country, asset type or ownership signal is available. "
                "Keep every query "
                "within "
                "the exact organization, geography and authorization scope requested by the user. Avoid redundant queries whose result "
                "sets are predictably subsumed by another strategy. "
                "Also assess whether a bounded Nuclei follow-up would be useful. A scan recommendation is only a plan: "
                "never execute it. Use only template IDs made of letters, digits, dot, underscore or hyphen; "
                "For a general scan, the application will add its bounded multi-template web-baseline profile; "
                "use template_ids only for justified product-specific additions or exact IDs named by the user. "
                "Never emit shell arguments. Select returned fields from the allowed membership catalogue supplied in the user prompt; "
                "match the field count to the task and do not request body/header/banner unless the user asked for page content. "
                "When the user names a known product, OA, VPN, middleware, database, camera, CMS or ops panel, prefer the bundled "
                "FOFA library app= queries supplied in the user prompt. Use those query strings verbatim as precision strategies "
                "and do not invent app= names. "
                'FOFA stores city in English, such as city="Guangzhou" and city="Shanghai". '
                'A Chinese value such as city="广州" or city="广州市" matches nothing. '
                'region accepts Chinese names such as region="广东". country uses codes such as country="CN". '
                'A school or university is not host=".edu". Put the real registrable domain on domain=, '
                'for example domain="pku.edu.cn", domain="example.cn" or domain="example.com". '
                "Official school sites may use .edu.cn, .cn or .com. "
                'Use host=".edu" or host=".edu.cn" only when the user explicitly asks for that hostname suffix. '
                "A bare public suffix belongs on host=, never on domain=. "
                "For a named website domain, start with domain= alone. Do not append protocol=http/https merely because "
                "the user said website: online verification shows those protocol filters can erase valid indexed web records. "
                "Preserve protocol filters only when the user explicitly requested them. Inspect returned protocol values instead. "
                "Write purpose and scan.reason in the same language as the user intent. Keep FOFA field names inside the query."
            )
            planner_system += _english_reply_clause(report_language)
            showcase = showcase_for(intent)
            if showcase is not None:
                if showcase.max_records is not None:
                    max_records = showcase.max_records
                if showcase.page_size is not None:
                    size = showcase.page_size
                if showcase.max_pages is not None:
                    max_pages = showcase.max_pages
                sample = showcase.sample
                plan = showcase.as_plan()
                _record_step(
                    run,
                    AgentState.INTENT,
                    t(
                        "这条需求和实测通过的内置样例一致，已改用固定查询",
                        "This request matches a verified built-in example, so the fixed query is used",
                    ),
                    data={"query": showcase.resolved_query(), "action": showcase.action},
                    on_progress=on_progress,
                )
            else:
                try:
                    library_hint = rules_hint_for_prompt(intent)
                    planner_prompt = f"User intent: {intent}\n{planner_capabilities_prompt(vip_level)}"
                    if search_context:
                        planner_prompt += (
                            "\nPublic research notes. Use them only to name the issue, its CVE id, and a published FOFA query. "
                            "If a note contains a Published FOFA query, use that expression as the precision query and keep the "
                            "user's city, region and country. Do not replace it with a generic technology inventory. "
                            "A published fingerprint is exposure, not a confirmed vulnerability. "
                            "Do not copy exploit steps, payloads or attack procedures.\n" + search_context
                        )
                    if smart_fields and not fields:
                        planner_prompt += (
                            f"\nFOFA membership tier: {tier or 'registered'}"
                            f"\nAllowed return fields: {', '.join(sorted(available_fields(tier)))}"
                            f"\nSuggested return fields: {', '.join(merge_return_fields([], account_tier_name=tier, intent=intent))}"
                        )
                    if library_hint:
                        planner_prompt = f"{planner_prompt}\n{library_hint}"
                    plan_result = await self.router.generate(
                        "planner",
                        system=planner_system,
                        prompt=planner_prompt,
                        schema=PLAN_SCHEMA,
                    )
                    plan = plan_result.structured if isinstance(plan_result.structured, dict) else {}
                except ProviderError as exc:
                    if exc.code not in {"model_structured_output_error", "model_response_error", "model_request_error"}:
                        raise
                    plan = _deterministic_fallback_plan(intent)
                    _record_step(
                        run,
                        AgentState.INTENT,
                        t(
                            "规划模型返回格式异常，已自动切换为保守查询方案",
                            "The planner response was unusable, so a conservative query is used",
                        ),
                        data={"error": exc.code, "query": plan["queries"][0]["query"]},
                        on_progress=on_progress,
                    )
            try:
                run.action = AgentAction(str(plan.get("action") or AgentAction.SEARCH.value))
            except ValueError:
                run.action = AgentAction.SEARCH
            run.target = str(plan.get("target") or "").strip() or None
            run.stats_fields = [str(item) for item in plan.get("stats_fields", [])]
            run.queries = _query_candidates(plan, source="planner", limit=INITIAL_QUERY_VARIANTS)
            if showcase is None and run.action in {AgentAction.SEARCH, AgentAction.STATS}:
                merged = _merge_library_queries(intent, run.queries, limit=INITIAL_QUERY_VARIANTS)
                if [item.query for item in merged] != [item.query for item in run.queries]:
                    run.queries = merged
                    _record_step(
                        run,
                        AgentState.INTENT,
                        t("已按内置规则库补齐精确 app= 指纹", "Added the exact app= fingerprint from the built-in rule library"),
                        data={"queries": [item.query for item in merged if item.source == "library"]},
                        on_progress=on_progress,
                    )
            explicit_domain = bool(re.search(r"(?:https?://)?(?:[a-z0-9-]+\.)+[a-z]{2,63}(?:/|\b)", intent, re.IGNORECASE))
            generic_domain_scopes = {
                "ac.cn",
                "com.cn",
                "edu.cn",
                "gov.cn",
                "net.cn",
                "org.cn",
            }
            planned_domains = {
                value.lower().removeprefix("www.")
                for item in run.queries
                for value in re.findall(r'\b(?:domain|host)\s*=\s*"([^" ]+\.[a-z]{2,63})"', item.query, re.IGNORECASE)
            }
            run.domain_hypotheses = sorted(planned_domains - generic_domain_scopes)
            planned_domain = bool(planned_domains - generic_domain_scopes)
            should_resolve_domain = (
                run.action is AgentAction.SEARCH
                and not explicit_domain
                and not planned_domain
                and bool(ORGANIZATION_INTENT_PATTERN.search(intent))
            )
            if showcase is None and should_resolve_domain:
                _record_step(
                    run,
                    AgentState.INTENT,
                    t("正在将机构名称解析为待验证的官网域名线索", "Resolving the organization name into website-domain leads to verify"),
                    on_progress=on_progress,
                )
                try:
                    resolution_result = await self.router.generate(
                        "entity_resolver",
                        system=(
                            "Resolve a named organization for defensive FOFA asset discovery. Return its common and official name "
                            "variants, plus three to six plausible website domains. Prefer a domain known from reliable general "
                            "knowledge when available. Otherwise derive strong acronym/name stems and test realistic suffixes. "
                            "School and university sites commonly use .edu.cn, .cn or .com, and only sometimes .edu; "
                            'do not assume the official site is host=".edu". Company sites commonly use .com or .cn. '
                            "A province or administrative prefix may be absent from the common name. Every "
                            "domain is an untrusted hypothesis to be checked in FOFA, not proof of ownership. Do not fabricate ICP "
                            "numbers, IP addresses or ownership claims. Return structured data only."
                        ),
                        prompt=f"Organization request: {intent}{_english_reply_clause(report_language)}",
                        schema=ENTITY_RESOLUTION_SCHEMA,
                    )
                    resolution = resolution_result.structured if isinstance(resolution_result.structured, dict) else {}
                    run.organization_names = [str(item).strip() for item in resolution.get("organization_names", []) if str(item).strip()][
                        :6
                    ]
                    run.domain_hypotheses = list(
                        dict.fromkeys(
                            domain
                            for item in resolution.get("domains", [])
                            if isinstance(item, dict)
                            for domain in [_normalized_domain(item.get("domain"))]
                            if domain
                        )
                    )[:6]
                    hypothesis = _domain_hypothesis_candidate(resolution)
                    if hypothesis:
                        insert_at = _domain_hypothesis_insert_at(run.queries)
                        run.queries.insert(insert_at, hypothesis)
                        run.queries = run.queries[:INITIAL_QUERY_VARIANTS]
                        _record_step(
                            run,
                            AgentState.INTENT,
                            t(
                                "已生成官网域名候选，将先在 FOFA 中验证后再展示",
                                "Website-domain candidates are ready and will be checked in FOFA before display",
                            ),
                            data={
                                "organization_names": resolution.get("organization_names", []),
                                "query": hypothesis.query,
                            },
                            on_progress=on_progress,
                        )
                except ProviderError as exc:
                    # Entity resolution improves recall but must never make an otherwise
                    # valid FOFA workflow fail when a provider cannot satisfy its schema.
                    logger.warning(f"Organization domain resolution skipped: {exc}")
                    _record_step(
                        run,
                        AgentState.INTENT,
                        t(
                            "官网域名线索解析暂不可用，继续执行名称与证书等 FOFA 查询",
                            "Website-domain resolution is unavailable. Continuing with name and certificate queries.",
                        ),
                        on_progress=on_progress,
                    )
            researched = _research_queries(search_context, intent) if showcase is None else []
            exposure = [] if researched else _php_exposure_queries(intent)
            chosen = researched or exposure
            if showcase is None and chosen and run.action in {AgentAction.SEARCH, AgentAction.STATS}:
                seen = {item.query for item in chosen}
                run.queries = [*chosen, *[item for item in run.queries if item.query not in seen]][:INITIAL_QUERY_VARIANTS]
                if researched:
                    detail = t(
                        "已采用公开专题里的 FOFA 语法，并保留用户指定的地区；这只说明检索口径，不能判定漏洞存在",
                        "Using the published FOFA topic query and the requested geography. "
                        "This sets the search scope and does not confirm a vulnerability.",
                    )
                else:
                    detail = t(
                        "已补齐 PHP2Shell 对应的 PHP 暴露面查询；指纹只能说明资产类型，不能判定漏洞存在",
                        "Added the PHP exposure query for PHP2Shell. "
                        "A fingerprint shows the asset type and does not confirm a vulnerability.",
                    )
                _record_step(
                    run,
                    AgentState.INTENT,
                    detail,
                    data={"queries": [item.query for item in chosen]},
                    on_progress=on_progress,
                )
            if run.action in {AgentAction.SEARCH, AgentAction.STATS} and not run.queries:
                fallback = _deterministic_fallback_plan(intent)
                run.queries = _query_candidates(fallback, source="fallback", limit=INITIAL_QUERY_VARIANTS)
                if not run.queries:
                    raise ValueError(t("模型未生成任何 FOFA 查询候选", "The model did not produce a FOFA query"))
                _record_step(
                    run,
                    AgentState.INTENT,
                    t("规划结果没有可用查询，已切换为保守查询方案", "The plan had no usable query, so a conservative query is used"),
                    data={"query": run.queries[0].query},
                    on_progress=on_progress,
                )
            _align_action_to_membership(run, user_info, on_progress=on_progress)
            rewritten = []
            for item in run.queries:
                fixed = normalize_fofa_query(item.query)
                if fixed != item.query:
                    rewritten.append({"from": item.query, "to": fixed})
                    item.query = fixed
            if rewritten:
                _record_step(
                    run,
                    AgentState.INTENT,
                    t(
                        "已按 FOFA 实际索引改写城市名、域名后缀或空标题条件",
                        "Rewrote the city name, domain suffix, or empty title to match how FOFA indexes them",
                    ),
                    data={"queries": rewritten},
                    on_progress=on_progress,
                )
            run.query = run.queries[0].query if run.queries else None
            _record_step(
                run,
                AgentState.INTENT,
                t(f"已选择动作 {run.action.value}", f"Selected action {run.action.value}"),
                data={"action": run.action.value, "target": run.target, "stats_fields": run.stats_fields},
                on_progress=on_progress,
            )
            scan = plan.get("scan") if isinstance(plan.get("scan"), dict) else {}
            run.scan_recommended = bool(scan.get("recommended", False))
            run.scan_reason = str(scan.get("reason", ""))
            run.scan_template_ids = list(dict.fromkeys(
                str(item) for item in scan.get("template_ids", []) if str(item) in nuclei_id_allowlist()
            ))[:100]
            if run.scan_requested_by_user or run.scan_recommended:
                run.scan_template_ids = _scan_template_ids_for_intent(intent, run.scan_template_ids)
            severities = [str(item).lower() for item in scan.get("severities", [])
                          if str(item).lower() in {"info", "low", "medium", "high", "critical"}]
            if severities:
                run.scan_severities = list(dict.fromkeys(severities))
            if run.scan_template_ids:
                run.scan_severities = align_scan_severities(run.scan_template_ids, run.scan_severities)
            if await self._execute_routed_action(run, intent, on_progress=on_progress, report_language=report_language):
                if run.scan_requested_by_user and not run.error:
                    await self._collect_routed_scan_candidates(
                        run, max_records=max_records, max_pages=max_pages, size=size, on_progress=on_progress,
                    )
                return finish()
            if not run.queries:
                raise ValueError(t("所选动作未生成 FOFA 查询语句", "The selected action did not produce a FOFA query"))
            run.fields = [str(item) for item in plan.get("fields", [])]
            if fields:
                run.fields = list(dict.fromkeys(str(item).strip() for item in fields if str(item).strip()))
            elif smart_fields:
                run.fields = merge_return_fields(run.fields, account_tier_name=tier, intent=intent)
            else:
                run.fields = run.fields or ["host", "ip", "port", "protocol", "title"]
            scan = plan.get("scan") if isinstance(plan.get("scan"), dict) else {}
            run.scan_recommended = bool(scan.get("recommended", False))
            run.scan_reason = str(scan.get("reason", ""))
            run.scan_template_ids = list(
                dict.fromkeys(str(item) for item in scan.get("template_ids", []) if SAFE_TEMPLATE_ID_PATTERN.fullmatch(str(item)))
            )[:100]
            allowed_template_ids = nuclei_id_allowlist()
            run.scan_template_ids = [item for item in run.scan_template_ids if item in allowed_template_ids]
            if run.scan_requested_by_user or run.scan_recommended:
                run.scan_template_ids = _scan_template_ids_for_intent(intent, run.scan_template_ids)
            severities = [
                str(item).lower()
                for item in scan.get("severities", [])
                if str(item).lower() in {"info", "low", "medium", "high", "critical"}
            ]
            if severities:
                run.scan_severities = list(dict.fromkeys(severities))
            if run.scan_template_ids:
                run.scan_severities = align_scan_severities(run.scan_template_ids, run.scan_severities)
            if run.scan_requested_by_user or run.scan_recommended:
                run.fields = list(dict.fromkeys([*run.fields, "host", "protocol", "ip", "port", "title"]))
            field_decision = decide_fields(run.fields, tier)
            run.fields = field_decision.allowed or ["host", "ip", "port", "protocol", "title"]

            _record_step(
                run,
                AgentState.INTENT,
                t(f"已生成 {len(run.queries)} 个初始查询策略", f"Prepared {len(run.queries)} initial queries"),
                data={"queries": [item.model_dump() for item in run.queries], "fields": run.fields},
                on_progress=on_progress,
            )
            if field_decision.denied:
                _record_step(
                    run,
                    AgentState.VALIDATE,
                    t(
                        "已按 FOFA 会员权限调整返回字段；查询语法中的高级检索字段不受影响",
                        "Adjusted the return fields for this membership. Advanced search fields in the query are unchanged.",
                    ),
                    data={"denied": field_decision.denied, "fields": run.fields},
                    on_progress=on_progress,
                )
            elif smart_fields and not fields:
                _record_step(
                    run,
                    AgentState.INTENT,
                    t(
                        f"已按账号等级（{tier or '未知'}）和任务智能选择 {len(run.fields)} 个返回字段",
                        f"Selected {len(run.fields)} return fields for tier {tier or 'unknown'} and this task",
                    ),
                    data={"tier": tier, "fields": run.fields},
                    on_progress=on_progress,
                )

            for index, candidate in enumerate(run.queries, start=1):
                errors = validate_query(candidate.query)
                if errors:
                    _record_step(
                        run,
                        AgentState.VALIDATE,
                        t(f"查询策略 {index} 语法存在问题，正在修复", f"Query {index} has a syntax problem and is being repaired"),
                        data={"query": candidate.query, "errors": errors},
                        on_progress=on_progress,
                    )
                    repair = await self.router.generate(
                        "query_repair",
                        system="Repair only the syntax of a FOFA query. Preserve every organization and geography scope constraint.",
                        prompt=f"Intent: {intent}\nQuery: {candidate.query}\nErrors: {errors}",
                        schema=QUERY_SCHEMA,
                    )
                    repaired = repair.structured if isinstance(repair.structured, dict) else {}
                    candidate.query = str(repaired.get("query", ""))
                    run.fields = [str(item) for item in repaired.get("fields", run.fields)]
                    remaining = validate_query(candidate.query)
                    if remaining:
                        raise ValueError(
                            t("模型无法生成有效的 FOFA 查询：", "The model could not produce a valid FOFA query: ") + "; ".join(remaining)
                        )
                _record_step(
                    run,
                    AgentState.VALIDATE,
                    t(f"查询策略 {index}/{len(run.queries)} 语法校验通过", f"Query {index}/{len(run.queries)} passed syntax checks"),
                    data={"query": candidate.query, "purpose": candidate.purpose},
                    on_progress=on_progress,
                )
            run.query = run.queries[0].query

            page_number = 0
            seen_assets: set[tuple[str, ...]] = set()
            evidence_by_asset: dict[tuple[str, ...], str] = {}

            async def execute_queries(candidates: list[AgentQuery]) -> None:
                nonlocal page_number
                for batch_index, candidate in enumerate(candidates):
                    remaining_budget = max_records - run.result_count
                    if remaining_budget <= 0:
                        break
                    # Share the *remaining* global budget across only the strategies
                    # that are actually about to run. Empty/low-hit strategies thus
                    # return their unused capacity to later, broader strategies.
                    remaining_candidates = len(candidates) - batch_index
                    even_share = max(1, (remaining_budget + remaining_candidates - 1) // remaining_candidates)
                    if sample and batch_index > 0 and remaining_budget < READABLE_SAMPLE:
                        break
                    if sample and even_share < READABLE_SAMPLE and remaining_candidates > 1:
                        query_budget = min(remaining_budget, READABLE_SAMPLE)
                    else:
                        query_budget = even_share
                    if sample and candidate.strategy == "recall":
                        query_budget = min(query_budget, 200)
                    query_number = run.queries.index(candidate) + 1
                    _record_step(
                        run,
                        AgentState.EXECUTE,
                        t(
                            f"正在执行查询策略 {query_number}/{len(run.queries)}：{candidate.purpose}",
                            f"Running query {query_number}/{len(run.queries)}: {candidate.purpose}",
                        ),
                        data={"query": candidate.query, "budget": query_budget},
                        on_progress=on_progress,
                    )
                    for attempt in range(2):
                        rejected: FofaError | None = None
                        request = SearchRequest(
                            query=candidate.query,
                            fields=fofa_request_fields(run.fields) or run.fields,
                            size=min(size, query_budget),
                            max_records=query_budget,
                            max_pages=max_pages,
                        )

                        def _consume_cursor_notice(number: int = query_number) -> None:
                            status = getattr(self.client, "cursor_page_fallback", None)
                            if not status:
                                return
                            self.client.cursor_page_fallback = None
                            if status == "continued":
                                detail = t(
                                    f"查询策略 {number} 的翻页游标已过期，已改用页码继续",
                                    f"Query {number} page cursor expired. Continuing with page numbers.",
                                )
                            else:
                                detail = t(
                                    f"查询策略 {number} 的翻页游标已过期，已保留已取回的资产",
                                    f"Query {number} page cursor expired. Kept the assets already retrieved.",
                                )
                            _record_step(run, AgentState.EVALUATE, detail, on_progress=on_progress)

                        try:
                            async for page in self.client.iter_search(request):
                                _consume_cursor_notice()
                                page_number += 1
                                candidate.pages += 1
                                raw_records = list(page.records)
                                if page.total is not None:
                                    if page.total > 0 and _primary_visible(run) == 0:
                                        run.query = candidate.query
                                    candidate.available_count = max(candidate.available_count or 0, page.total)
                                candidate.result_count += len(raw_records)
                                unique_records = []
                                for record in raw_records:
                                    identity = _asset_identity(record.values)
                                    previous_evidence = evidence_by_asset.get(identity)
                                    if previous_evidence is None or EVIDENCE_RANK.get(candidate.strategy, 1) > EVIDENCE_RANK.get(
                                        previous_evidence, 1
                                    ):
                                        evidence_by_asset[identity] = candidate.strategy
                                    if identity in seen_assets:
                                        continue
                                    seen_assets.add(identity)
                                    unique_records.append(record)
                                page.records = unique_records
                                await _notify_page(on_page, run, page, page_number)
                                candidate.new_assets += len(page.records)
                                _record_page(run, page, page_number, strategy=candidate.strategy)
                                _record_step(
                                    run,
                                    AgentState.EXECUTE,
                                    t(
                                        f"策略 {query_number} 第 {candidate.pages} 页：返回 {len(raw_records)} 条，"
                                        f"新增 {len(page.records)} 条，累计去重资产 {run.result_count} 条",
                                        f"Query {query_number} page {candidate.pages}: {len(raw_records)} returned, "
                                        f"{len(page.records)} new, {run.result_count} unique so far",
                                    ),
                                    data={
                                        "query": candidate.query,
                                        "page": candidate.pages,
                                        "raw_records": len(raw_records),
                                        "new_assets": len(page.records),
                                        "records": run.result_count,
                                    },
                                    on_progress=on_progress,
                                )
                                if run.scan_requested_by_user or run.scan_recommended:
                                    for record in page.records:
                                        target = _scan_target(record.values)
                                        if target and target not in run.scan_targets and len(run.scan_targets) < 10_000:
                                            run.scan_targets.append(target)
                            _consume_cursor_notice()
                            break
                        except FofaError as exc:
                            if not _query_error_can_be_rewritten(exc):
                                raise
                            rejected = exc
                        if rejected is None:
                            break
                        rewritten = ""
                        if attempt == 0 and candidate.pages == 0:
                            rewritten = await _rewrite_rejected_query(
                                self.router,
                                intent=intent,
                                query=candidate.query,
                                error=str(rejected),
                            )
                        if rewritten:
                            _record_step(
                                run,
                                AgentState.REPAIR,
                                t(
                                    f"查询策略 {query_number} 被 FOFA 拒绝，已交给 AI 重写后重试",
                                    f"FOFA rejected query {query_number}. Asking the model to rewrite it.",
                                ),
                                data={"from": candidate.query, "to": rewritten, "message": str(rejected)},
                                on_progress=on_progress,
                            )
                            candidate.query = rewritten
                            continue
                        detail = (
                            t(
                                f"查询策略 {query_number} 重写后仍被 FOFA 拒绝，已跳过并继续其余语句",
                                f"FOFA still rejected rewritten query {query_number}. Skipped. Continuing with the others.",
                            )
                            if attempt
                            else t(
                                f"查询策略 {query_number} 被 FOFA 拒绝，AI 没能写出替代语句，已跳过并继续其余语句",
                                f"FOFA rejected query {query_number} and the model did not produce a replacement. Skipped.",
                            )
                        )
                        _record_step(
                            run,
                            AgentState.EVALUATE,
                            detail,
                            data={"query": candidate.query, "message": str(rejected)},
                            on_progress=on_progress,
                        )
                        break

            initial_queries = list(run.queries)
            await execute_queries(initial_queries)
            ran = sum(1 for item in initial_queries if item.pages)
            _record_step(
                run,
                AgentState.EVALUATE,
                t(
                    f"首轮 {ran} 个查询完成，共发现 {run.result_count} 条去重资产",
                    f"The first pass finished {ran} queries and found {run.result_count} unique assets",
                ),
                data={"records": run.result_count, "queries": [item.model_dump() for item in initial_queries if item.pages]},
                on_progress=on_progress,
            )
            await _population_portrait(self, run, max_records=max_records, on_progress=on_progress)

            for reflection_round in range(1, MAX_REFLECTION_ROUNDS + 1):
                if showcase is not None:
                    break
                if len(run.queries) >= MAX_QUERY_VARIANTS or run.result_count >= max_records:
                    break
                population = max((int(item.available_count or 0) for item in run.queries), default=0)
                if sample and population > max(max_records * 10, 1000) and max_records - run.result_count < READABLE_SAMPLE:
                    _record_step(
                        run,
                        AgentState.REFLECT,
                        t(
                            "可见规模远大于抽样上限，不再追加查询",
                            "The visible set is far above the sample cap, so no more queries were added",
                        ),
                        data={"population": population, "sampled": run.result_count, "limit": max_records},
                        on_progress=on_progress,
                    )
                    break
                _record_step(
                    run,
                    AgentState.REFLECT,
                    t(
                        f"正在进行第 {reflection_round}/{MAX_REFLECTION_ROUNDS} 轮结果驱动反思",
                        f"Reflection round {reflection_round}/{MAX_REFLECTION_ROUNDS}",
                    ),
                    on_progress=on_progress,
                )
                run.reflection_rounds = reflection_round
                try:
                    reflection = await self.router.generate(
                        "reflector",
                        system=(
                            "You are the result-reflection stage of a FOFA asset-discovery agent. Evaluate each executed strategy using "
                            "its raw hit count and deduplicated additions, then propose zero to two efficient complementary strategies. "
                            "A strategy may be a single clause or an advanced composite expression with parentheses, || and &&. Never "
                            "mechanically split every field into a separate query. Combine equivalent aliases/signals when that improves "
                            "API efficiency; separate precision and recall strategies when their noise profiles differ. When all results "
                            "are zero, use a correction ladder: first remove only unsupported or overly strict conditions, then try a "
                            "balanced composite across semantically valid ownership/content fields, and finally a bounded recall query "
                            "using the strongest user-provided identifier. Do not invent domains, ICP numbers, aliases, parent companies "
                            "or geographies without evidence. When results exist, derive follow-ups only from concrete sample signals "
                            "such as domains returned by FOFA, certificate subjects, organization names, ICP values, products or titles. "
                            "A strategy labeled hypothesis proves only that a candidate domain is indexed by FOFA; it does not confirm "
                            "ownership. You may pivot from its observed IP/certificate to find related candidates, but must not call the "
                            "domain confirmed or official without independent ownership evidence. Do not "
                            "repeat or submit a query predictably subsumed by one already executed. Never expand the user's organization, "
                            "geography or authorization scope. Mark coverage sufficient only when the user's goal has meaningful nonzero "
                            "coverage or no safe evidence-based strategy remains. "
                            "Write observation and purpose in the same language as the user intent."
                            + _english_reply_clause(report_language)
                        ),
                        prompt=(
                            f"User intent: {intent}\n"
                            f"Reflection round: {reflection_round}/{MAX_REFLECTION_ROUNDS}\n"
                            f"Executed strategy metrics: {[item.model_dump() for item in run.queries]}\n"
                            f"Unique asset count: {run.result_count}\n"
                            f"Compact asset sample: {_compact_asset_sample(run.assets)}"
                        ),
                        schema=REFLECTION_SCHEMA,
                    )
                except ProviderError as exc:
                    note = t(
                        f"第 {reflection_round} 轮反思不可用：{exc}；保留已完成查询结果并继续生成总结。",
                        f"Reflection round {reflection_round} is unavailable: {exc}. Keeping the finished results and writing the summary.",
                    )
                    run.reflection_notes.append(note)
                    _record_step(
                        run,
                        AgentState.REFLECT,
                        t(
                            f"第 {reflection_round} 轮反思降级，保留 {run.result_count} 条已发现资产",
                            f"Reflection round {reflection_round} fell back. Keeping {run.result_count} assets.",
                        ),
                        data={"error": exc.code, "message": str(exc)},
                        on_progress=on_progress,
                    )
                    break
                reflected = reflection.structured if isinstance(reflection.structured, dict) else {}
                observation = str(reflected.get("observation") or "").strip()
                if observation:
                    run.reflection_notes.append(observation)
                coverage_sufficient = bool(reflected.get("coverage_sufficient", False))
                existing_queries = {item.query for item in run.queries}
                remaining_slots = min(MAX_REFLECTION_ADDITIONS, MAX_QUERY_VARIANTS - len(run.queries))
                additions = [
                    item
                    for item in _query_candidates(
                        reflected,
                        source=f"reflection_{reflection_round}",
                        limit=remaining_slots,
                    )
                    if item.query not in existing_queries
                ]
                valid_additions: list[AgentQuery] = []
                for item in additions:
                    item.query = normalize_fofa_query(item.query)
                    errors = validate_query(item.query)
                    if errors:
                        repair = await self.router.generate(
                            "query_repair",
                            system=(
                                "Repair only the syntax of this reflected FOFA query. Preserve every organization and geography "
                                "scope constraint and do not broaden the query."
                            ),
                            prompt=f"Intent: {intent}\nQuery: {item.query}\nErrors: {errors}",
                            schema=QUERY_SCHEMA,
                        )
                        repaired = repair.structured if isinstance(repair.structured, dict) else {}
                        item.query = normalize_fofa_query(str(repaired.get("query") or ""))
                    if item.query not in existing_queries and not validate_query(item.query):
                        existing_queries.add(item.query)
                        valid_additions.append(item)
                additions = valid_additions
                run.queries.extend(additions)
                _record_step(
                    run,
                    AgentState.REFLECT,
                    t(
                        f"第 {reflection_round} 轮反思完成，新增 {len(additions)} 个混合查询策略",
                        f"Reflection round {reflection_round} added {len(additions)} queries",
                    ),
                    data={
                        "observation": observation,
                        "coverage_sufficient": coverage_sufficient,
                        "queries": [item.model_dump() for item in additions],
                    },
                    on_progress=on_progress,
                )
                if not additions:
                    break
                count_before = run.result_count
                await execute_queries(additions)
                round_new_assets = run.result_count - count_before
                _record_step(
                    run,
                    AgentState.EVALUATE,
                    t(
                        f"第 {reflection_round} 轮补充查询新增 {round_new_assets} 条去重资产",
                        f"Reflection round {reflection_round} added {round_new_assets} unique assets",
                    ),
                    data={"new_assets": round_new_assets, "records": run.result_count},
                    on_progress=on_progress,
                )
                if coverage_sufficient or count_before > 0 or round_new_assets > 0:
                    break

            run.asset_confidence = [evidence_by_asset.get(_asset_identity(asset), "recall") for asset in run.assets]
            ranked_assets = sorted(
                zip(run.assets, run.asset_confidence, strict=True),
                key=lambda item: EVIDENCE_RANK.get(item[1], 1),
                reverse=True,
            )
            run.assets = [asset for asset, _confidence in ranked_assets]
            run.asset_confidence = [confidence for _asset, confidence in ranked_assets]
            run.evidence_counts = {
                strategy: sum(1 for value in evidence_by_asset.values() if value == strategy)
                for strategy in ("precision", "balanced", "hypothesis", "recall")
                if any(value == strategy for value in evidence_by_asset.values())
            }
            run.website_candidates = _derive_website_candidates(run)
            if run.website_candidates:
                _record_step(
                    run,
                    AgentState.EVALUATE,
                    t(
                        f"已整理 {len(run.website_candidates)} 个带证据等级的网站候选",
                        f"Prepared {len(run.website_candidates)} website candidates with evidence levels",
                    ),
                    data={"websites": [item.model_dump() for item in run.website_candidates]},
                    on_progress=on_progress,
                )

            skipped = [item for item in run.queries if item.pages == 0]
            cap_name = t("抽样上限", "sample cap") if sample else t("取回上限", "retrieval cap")
            if skipped and len(skipped) < len(run.queries):
                run.queries = [item for item in run.queries if item.pages > 0]
                _record_step(
                    run,
                    AgentState.EVALUATE,
                    t(
                        f"{cap_name} {max_records} 条，其余 {len(skipped)} 条语句未执行",
                        f"{cap_name} {max_records}; {len(skipped)} queries were not run",
                    ),
                    on_progress=on_progress,
                )
            _mark_sampling(run, max_records, truncated=bool(skipped), sampled=sample)
            finished = (
                t(
                    f"已执行 {len(run.queries)} 个查询策略，另有 {len(skipped)} 条因{cap_name}未执行，共发现 {run.result_count} 条去重资产",
                    f"Ran {len(run.queries)} queries. {len(skipped)} were not run because of the {cap_name}. "
                    f"Found {run.result_count} unique assets.",
                )
                if skipped
                else t(
                    f"全部 {len(run.queries)} 个查询策略执行完成，共发现 {run.result_count} 条去重资产",
                    f"All {len(run.queries)} queries finished. Found {run.result_count} unique assets.",
                )
            )
            _record_step(
                run,
                AgentState.EVALUATE,
                finished,
                data={"records": run.result_count, "queries": [item.model_dump() for item in run.queries]},
                on_progress=on_progress,
            )
            if run.result_count == 0:
                run.scan_recommended = False
                run.scan_reason = t(
                    "未发现可供扫描的资产，已取消初始扫描建议。",
                    "No assets are available to scan, so the initial scan suggestion was dropped.",
                )
                run.scan_template_ids = []
                run.scan_targets = []

            _record_step(
                run,
                AgentState.SUMMARIZE,
                t("正在基于资产样本生成总结", "Writing the briefing from the asset sample"),
                on_progress=on_progress,
            )
            summary_system = (
                SEARCH_SUMMARY_SYSTEM_EN if _reply_language(report_language) == "en" else SEARCH_SUMMARY_SYSTEM
            ) + _english_reply_clause(report_language)
            summary = await self.router.generate(
                "summarizer",
                system=summary_system,
                prompt=_search_summary_prompt(run, intent),
            )
            _apply_generated_summary(
                run,
                summary.text,
                fallback=_local_search_summary(run, language=report_language),
                require_asset_briefing=True,
                language=report_language,
            )
            _record_step(run, AgentState.COMPLETED, t("侦察任务已完成", "Reconnaissance finished"), on_progress=on_progress)
        except FofaError as exc:
            # Account, quota, rate-limit and transport errors stop the run.
            # A rejected statement is rewritten once inside the query loop.
            run.error = exc.as_dict()
            _record_step(run, AgentState.FAILED, t("FOFA 查询失败", "FOFA query failed"), data=run.error, on_progress=on_progress)
        except ProviderError as exc:
            run.error = {
                "code": exc.code,
                "message": str(exc),
                "retryable": exc.retryable,
                "hint": exc.hint,
                "status_code": exc.status_code,
            }
            _record_step(run, AgentState.FAILED, t("AI 模型调用失败", "The model call failed"), data=run.error, on_progress=on_progress)
        except Exception as exc:
            run.error = {"code": "agent_error", "message": str(exc), "retryable": False}
            _record_step(run, AgentState.FAILED, t("智能体执行失败", "The agent run failed"), data=run.error, on_progress=on_progress)
        return finish()
