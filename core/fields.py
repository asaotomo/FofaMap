"""Versioned FOFA field capability catalogue, aligned with https://fofa.info/api/introd."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from core.membership import MEMBERSHIP_SOURCE, MEMBERSHIP_VERIFIED, MEMBERSHIP_VIP_SOURCE, membership_catalog, membership_for
from core.syntax import syntax_catalog

CATALOG_VERSION = "2026-11-official"

# Return fields documented for /api/v1/search/all and /api/v1/search/next (GoFOFA / 官方附录).
BASE_FIELDS = {
    "ip",
    "port",
    "protocol",
    "country",
    "country_name",
    "region",
    "city",
    "longitude",
    "latitude",
    "asn",
    "org",
    "host",
    "domain",
    "os",
    "server",
    "icp",
    "title",
    "jarm",
    "header",
    "banner",
    "cert",
    "base_protocol",
    "link",
    "cert.issuer.org",
    "cert.issuer.cn",
    "cert.subject.org",
    "cert.subject.cn",
    "tls.ja3s",
    "tls.version",
    "cert.sn",
    "cert.not_before",
    "cert.not_after",
    "cert.domain",
    "status_code",
}
TIER_FIELDS = {
    "personal": {"header_hash", "banner_hash", "banner_fid"},
    "professional": {"cname", "lastupdatetime", "product", "product_category"},
    "business": {"product.version", "icon_hash", "cert.is_valid", "cname_domain", "body", "cert.is_match", "cert.is_equal"},
    "enterprise": {"icon", "fid", "structinfo"},
}
# Query-side names that are not in the /search/all return appendix.
COMPAT_RETURN_FIELDS = {"asset_type"}

# Official /api/v1/search/stats dimensions. Other names return [820027] 不支持的聚合字段.
STATS_FIELDS = {
    "protocol",
    "domain",
    "port",
    "title",
    "os",
    "server",
    "country",
    "asn",
    "org",
    "asset_type",
    "fid",
    "icp",
}

DEFAULT_SEARCH_FIELDS = "host,protocol,ip,port,title,domain,country"
CORE_RETURN_FIELDS = ("host", "protocol", "ip", "port", "title")
# Local-only columns. Never send these to /search/all — FOFA may echo them back empty,
# which previously made later pages look "already probed".
LOCAL_RESULT_FIELDS = {"alive_status", "evidence"}
TIER_MAX_FIELDS = {
    None: 8,
    "personal": 8,
    "professional": 10,
    "business": 14,
    "enterprise": 16,
}
_HEAVY_FIELDS = {"body", "header", "banner", "structinfo", "icon"}
_INTENT_FIELD_HINTS = (
    (r"子域|subdomain|域名|官网|网站", ("domain", "cname", "icp", "cert.subject.cn")),
    (r"证书|https|tls|ssl", ("cert", "cert.subject.org", "cert.subject.cn", "cert.issuer.org", "tls.version")),
    (r"产品|指纹|组件|中间件|框架|oa|vpn|cms", ("product", "product_category", "product.version", "server", "os")),
    (r"图标|favicon|icon", ("icon_hash", "icon")),
    (r"组织|公司|集团|大学|学院|单位|通服|全网资产", ("domain", "org", "icp", "cert.subject.org", "asn")),
    (r"地理|城市|省份|国家|region", ("country", "country_name", "region", "city")),
    (r"存活|状态码|status", ("status_code",)),
    (r"正文|源码|body=|banner|header", ("server", "header", "banner", "body")),
)


@dataclass(frozen=True)
class FieldDecision:
    allowed: list[str]
    denied: list[str]
    alternatives: list[str]


def fofa_request_fields(fields: list[str] | None) -> list[str]:
    """Drop local display columns before calling FOFA /search/all."""
    return [field for field in (fields or []) if field and field not in LOCAL_RESULT_FIELDS]


def search_page_size(size: int, fields: list[str]) -> int:
    """Official search/all field-dependent page limits also apply to continuations."""
    names = set(fields)
    limit = 500 if "body" in names else 2000 if names & {"cert", "banner", "header"} else 10_000
    return min(size, limit)


def available_fields(account_tier: str | None = None) -> set[str]:
    allowed = set(BASE_FIELDS) | set(COMPAT_RETURN_FIELDS)
    order = ["personal", "professional", "business", "enterprise"]
    if account_tier in order:
        for tier in order[: order.index(account_tier) + 1]:
            allowed.update(TIER_FIELDS[tier])
    return allowed


def decide_fields(requested: list[str], account_tier: str | None = None) -> FieldDecision:
    allowed_catalog = available_fields(account_tier)
    allowed = [field for field in requested if field in allowed_catalog]
    denied = [field for field in requested if field not in allowed_catalog]
    alternatives = [field for field in ("host", "ip", "port", "protocol", "title") if field not in allowed]
    return FieldDecision(allowed=allowed, denied=denied, alternatives=alternatives)


def account_tier(vip_level: Any) -> str | None:
    membership = membership_for(vip_level)
    return membership.field_tier if membership else None


def suggest_fields(intent: str, *, account_tier_name: str | None = None, query: str = "") -> list[str]:
    haystack = f"{intent} {query}".lower()
    allowed = available_fields(account_tier_name)
    limit = TIER_MAX_FIELDS.get(account_tier_name, TIER_MAX_FIELDS[None])
    selected: list[str] = []

    def add(*names: str) -> None:
        for name in names:
            if name in allowed and name not in selected and len(selected) < limit:
                if name in _HEAVY_FIELDS and not re.search(r"正文|源码|body=|banner|header", haystack):
                    continue
                selected.append(name)

    add(*CORE_RETURN_FIELDS)
    # PHP / CVE exposure tasks need the fingerprint columns before website
    # attribution fields consume the membership field budget.
    if re.search(r"php|cve-\d|漏洞", haystack, re.IGNORECASE):
        add("server", "product")
    for pattern, names in _INTENT_FIELD_HINTS:
        if re.search(pattern, haystack, re.IGNORECASE):
            add(*names)
    add("domain", "country")
    if account_tier_name in {"professional", "business", "enterprise"}:
        add("product", "lastupdatetime", "server")
    if account_tier_name in {"business", "enterprise"}:
        add("icon_hash", "cname", "icp")
    add("status_code")
    return selected


def merge_return_fields(*groups: list[str], account_tier_name: str | None = None, intent: str = "") -> list[str]:
    suggested = suggest_fields(intent, account_tier_name=account_tier_name)
    merged: list[str] = []
    for group in (suggested, *groups):
        for field in group:
            name = str(field).strip()
            if name and name not in merged:
                merged.append(name)
    decision = decide_fields(merged, account_tier_name)
    haystack = intent.lower()
    filtered = [
        field
        for field in decision.allowed
        if field not in _HEAVY_FIELDS or any(token in haystack for token in ("正文", "源码", "body", "banner", "header"))
    ]
    limit = TIER_MAX_FIELDS.get(account_tier_name, TIER_MAX_FIELDS[None])
    return (filtered or list(CORE_RETURN_FIELDS))[:limit]


def field_catalog() -> dict:
    return {
        "version": CATALOG_VERSION,
        "source": "https://fofa.info/api/introd",
        "membership_source": MEMBERSHIP_SOURCE,
        "membership_vip_source": MEMBERSHIP_VIP_SOURCE,
        "verified_at": MEMBERSHIP_VERIFIED,
        "page_limits": {"default": 10000, "cert_banner_header": 2000, "body": 500},
        "base": sorted(BASE_FIELDS),
        "compat": sorted(COMPAT_RETURN_FIELDS),
        "tiers": {k: sorted(v) for k, v in TIER_FIELDS.items()},
        "stats": sorted(STATS_FIELDS),
        "memberships": membership_catalog(),
        "syntax": syntax_catalog(),
    }
