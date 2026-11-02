"""Decide when an enabled web search should look up a vulnerability name, CVE, or published FOFA syntax."""

from __future__ import annotations

import base64
import binascii
import re
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlparse

import httpx

from core.version import VERSION
from utils.i18n import language, t
from utils.logger import logger

_RESEARCH_HINT = re.compile(
    r"漏洞|0day|在野|热点|hotspot|专题|专属语法|cve[-\s]?\d{4}|php\s*2\s*shell|log4shell|spring4shell",
    re.IGNORECASE,
)
_CVE = re.compile(r"CVE-\d{4}-\d{4,7}", re.IGNORECASE)
_FOFA_URL = re.compile(r"https?://(?:www\.)?fofa\.info/[^\s)\]>\"']+", re.IGNORECASE)
_FOFA_FIELD = (
    r"product\.version|body|header|title|banner|app|server|protocol|icon_hash|fid|js_name|js_md5|"
    r"product|cert|domain|host|country|region|city|port|os|status_code|after|before"
)
_FOFA_ATOM = rf'(?:{_FOFA_FIELD})\s*=\s*"(?:[^"\\]|\\.){{1,180}}"'
_FOFA_QUERY = re.compile(rf"(?i)(?:\(\s*)?{_FOFA_ATOM}(?:\s*(?:&&|\|\|)\s*\(?\s*{_FOFA_ATOM}\)?)*")
_PROCEDURE = re.compile(r"利用步骤|payload|反弹|poc\b|exp\b|exploit\s+step|webshell", re.IGNORECASE)
_SKIP_RESULT = re.compile(r"exploit|poc\b|payload|利用代码|武器化|mass-exploit", re.IGNORECASE)
_NAMED_ISSUE = re.compile(r"php\s*2\s*shell|log4shell|spring4shell|cve-\d{4}-\d{4,7}", re.IGNORECASE)

RESEARCH_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "search": {"type": "boolean"},
        "reason": {"type": "string"},
        "queries": {"type": "array", "maxItems": 3, "items": {"type": "string"}},
    },
    "required": ["search", "reason", "queries"],
}

RESEARCH_SYSTEM = (
    "You decide whether a public web lookup is needed before a FOFA asset query is written. "
    "Set search to true only when the request names a vulnerability, campaign, CVE, hotspot, or a new issue "
    "whose public name, CVE id, or official FOFA topic and query syntax are not already stated. "
    "Set search to false for an ordinary product, city, organization, or domain lookup. "
    "When search is true, return at most 3 queries, each under 120 characters: "
    "what the issue is and its CVE id; a fofa.info hotspot or topic page; the published FOFA query syntax. "
    "Do not request exploit steps, payloads, proof-of-concept code, or attack procedures. "
    "Write reason in the user's language, in one sentence, with no procedure."
)


@dataclass
class ResearchBrief:
    notes: str = ""
    searched: bool = False
    reason: str = ""
    queries: list[str] = field(default_factory=list)


def research_may_help(intent: str) -> bool:
    """Ordinary product or city lookups do not need a web lookup."""
    return bool(_RESEARCH_HINT.search(intent or ""))


def fallback_research_queries(intent: str) -> list[str]:
    topic = _topic_phrase(intent)
    if language() == "en":
        return [
            f"{topic} CVE"[:120],
            f"site:fofa.info {topic} hotspot"[:120],
            f"{topic} FOFA query syntax"[:120],
        ]
    return [
        f"{topic} CVE"[:120],
        f"site:fofa.info {topic} 专题"[:120],
        f"{topic} FOFA 查询语法"[:120],
    ]


def distill_search_results(results: list[dict[str, Any]]) -> str:
    """Keep the name, CVE, official page, and published query. Drop procedure text."""
    blocks: list[str] = []
    seen: set[str] = set()
    for item in results:
        if not isinstance(item, dict):
            continue
        title = str(item.get("title") or "").strip()
        url = str(item.get("url") or "").strip()
        summary = str(item.get("summary") or item.get("snippet") or "").strip()
        content = str(item.get("content") or "")[:8000]
        blob = "\n".join(part for part in (title, url, summary, content) if part)
        if not blob or blob in seen or _SKIP_RESULT.search(f"{title} {url}"):
            continue
        seen.add(blob)
        lines = [f"- {title} {url}".strip()]
        cves = sorted({match.group(0).upper() for match in _CVE.finditer(blob)})
        if cves:
            lines.append("  CVE: " + ", ".join(cves))
        pages = []
        for match in _FOFA_URL.finditer(blob):
            page = match.group(0).rstrip(".,;")
            if page not in pages:
                pages.append(page)
        if pages:
            lines.append("  FOFA topic: " + " ".join(pages[:3]))
        queries = []
        if urlparse(url).netloc.lower().endswith("fofa.info"):
            for match in _FOFA_QUERY.finditer(content or summary):
                query = " ".join(match.group(0).split())
                if query not in queries:
                    queries.append(query)
        if queries:
            for query in queries[:2]:
                lines.append("  Published FOFA query: " + query)
        elif summary and not _PROCEDURE.search(summary):
            lines.append("  " + summary[:300])
        if len(lines) > 1:
            blocks.append("\n".join(lines))
    return "\n".join(blocks)[:4000]


def queries_from_topic_html(html: str) -> list[str]:
    """Read the query strings FOFA publishes as links on a topic page."""
    found: list[str] = []
    for match in re.finditer(r"qbase64=([A-Za-z0-9_+/=-]{8,})", html or ""):
        raw = match.group(1)
        padded = raw + "=" * ((4 - len(raw) % 4) % 4)
        try:
            text = base64.b64decode(padded).decode("utf-8", "replace")
        except (binascii.Error, ValueError):
            text = ""
        text = " ".join(text.split())
        if text and text not in found:
            found.append(text)
    return found


def choose_official_query(queries: list[str]) -> str:
    """Prefer the affected-version list over a single version or a bare app name."""
    versioned = [query for query in queries if query.count('product.version="') >= 2 and len(query) <= 4096]
    if not versioned:
        return ""
    return max(versioned, key=lambda query: query.count('product.version="'))


def topic_page_candidates(intent: str) -> list[str]:
    found: list[str] = []
    if re.search(r"php", intent or "", re.IGNORECASE):
        found.append("https://fofa.info/php-hotspot")
    for match in re.finditer(r"[a-z][a-z0-9-]{2,24}", (intent or "").lower()):
        token = match.group(0)
        if token in {"php", "the", "and", "for", "cve"}:
            continue
        url = f"https://fofa.info/{token}-hotspot"
        if url not in found:
            found.append(url)
    return found[:3]


async def _official_topic_query(intent: str) -> tuple[str, str, list[str]]:
    candidates = topic_page_candidates(intent)
    if not candidates:
        return "", "", []
    async with httpx.AsyncClient(
        timeout=20,
        follow_redirects=False,
        headers={"User-Agent": f"FofaMap/{VERSION}"},
    ) as client:
        for url in candidates:
            try:
                response = await client.get(url)
            except Exception as exc:
                logger.warning(f"FOFA 专题页读取失败 {type(exc).__name__}")
                continue
            if response.status_code != 200 or "qbase64=" not in response.text:
                continue
            chosen = choose_official_query(queries_from_topic_html(response.text[:500_000]))
            if not chosen:
                continue
            cves = sorted({match.group(0).upper() for match in _CVE.finditer(response.text)})[:4]
            return chosen, url, cves
    return "", "", []


async def build_search_context(router: Any, provider: Any, intent: str) -> ResearchBrief:
    """Ask the model whether this intent needs a lookup, then search only when it says yes."""
    if provider is None or not research_may_help(intent):
        return ResearchBrief()
    queries: list[str] = []
    reason = ""
    try:
        system = RESEARCH_SYSTEM
        if language() == "en":
            system += " The interface language is English. Write reason in English."
        result = await router.generate(
            "planner",
            system=system,
            prompt=f"User intent: {intent}",
            schema=RESEARCH_SCHEMA,
        )
        data = result.structured if isinstance(getattr(result, "structured", None), dict) else {}
        reason = str(data.get("reason") or "").strip()
        if not data.get("search"):
            return ResearchBrief(reason=reason)
        queries = [str(item).strip()[:120] for item in data.get("queries") or [] if str(item).strip()][:3]
    except Exception:
        queries = fallback_research_queries(intent)
        reason = t(
            "公开检索的判断没有返回，改为按漏洞名称、CVE 和 FOFA 专题语法检索。",
            "The search decision did not return. Looking up the issue name, CVE, and FOFA topic syntax.",
        )
    if not queries:
        queries = fallback_research_queries(intent)
    collected: list[dict[str, Any]] = []
    for query in queries:
        rows: list[Any] = []
        try:
            rows = await provider.web_search(query, count=5, original_question=intent, need_content=True)
        except Exception as exc:
            logger.warning(f"公开检索失败 {type(exc).__name__}")
            rows = []
        collected.extend(item for item in rows if isinstance(item, dict))
    notes = distill_search_results(collected)
    official, topic_url, topic_cves = await _official_topic_query(intent)
    if official:
        cve_line = f"  CVE: {', '.join(topic_cves)}\n" if topic_cves else ""
        notes = f"- FOFA topic: {topic_url}\n{cve_line}  Published FOFA query: {official}\n{notes}".strip()
    if not reason:
        reason = t(
            "已检索公开资料，补充漏洞名称、CVE 和 FOFA 专题语法。",
            "Looked up the public issue name, CVE, and FOFA topic syntax.",
        )
    if not notes:
        reason = t(
            "公开检索没有给出可用的 CVE 或 FOFA 语法，继续用已有规则。",
            "Public search did not return a usable CVE or FOFA query. Continuing with the existing rules.",
        )
    return ResearchBrief(notes=notes, searched=True, reason=reason, queries=queries)


def _topic_phrase(intent: str) -> str:
    named = _NAMED_ISSUE.search(intent or "")
    if named:
        return re.sub(r"\s+", "", named.group(0))
    compact = " ".join((intent or "").split())
    return compact[:40] or "vulnerability"
