"""FOFA membership capabilities, aligned with https://fofa.info/api."""

from __future__ import annotations

import ipaddress
from dataclasses import asdict, dataclass
from typing import Any

from utils.i18n import t

MEMBERSHIP_SOURCE = "https://fofa.info/api"
MEMBERSHIP_VIP_SOURCE = "https://fofa.info/vip"
MEMBERSHIP_VERIFIED = "2026-11-01"
DAILY_FREE_REQUESTS = 3000


@dataclass(frozen=True)
class Membership:
    vip_level: int
    name: str
    field_tier: str | None
    host_api: bool
    stats_api: bool
    requests_per_second: float
    remain_from_interface: bool
    export_fields: int | None
    query_syntax: int | str
    notes: str = ""

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


# Exact vip_level mapping from the official API capability table. Do not use ranges:
# vip 22 (教育账户) is not business, and vip 1 is personal rather than unmapped.
MEMBERSHIPS: dict[int, Membership] = {
    0: Membership(0, "注册用户", None, False, False, 1.0, True, 34, 44),
    1: Membership(1, "普通会员", "personal", True, False, 1.0, False, 37, 60, "权限等同订阅个人版"),
    2: Membership(2, "高级会员", "professional", True, True, 1.0, False, 41, 62, "权限等同订阅专业版"),
    5: Membership(5, "标准企业版", "enterprise", True, True, 5.0, True, None, "全部"),
    11: Membership(11, "订阅个人版", "personal", True, False, 1.0, True, 37, 60),
    12: Membership(12, "订阅专业版", "professional", True, True, 1.0, True, 41, 62),
    13: Membership(13, "订阅商业版", "business", True, True, 2.0, True, 48, "全部"),
    22: Membership(22, "教育账户", "personal", True, False, 1.0, False, 37, "教育账户"),
}

MEMBERSHIP_EN = {
    0: "Registered",
    1: "Personal",
    2: "Professional",
    5: "Enterprise",
    11: "Personal plan",
    12: "Professional plan",
    13: "Business plan",
    22: "Education",
}


def membership_label(membership: Membership) -> str:
    return t(membership.name, MEMBERSHIP_EN.get(membership.vip_level, membership.name))


def parse_vip_level(value: Any) -> int | None:
    if value in (None, "", "-", "unknown"):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def membership_for(vip_level: Any) -> Membership | None:
    level = parse_vip_level(vip_level)
    if level is None:
        return None
    return MEMBERSHIPS.get(level)


def membership_from_account(user_info: dict[str, Any] | None) -> Membership | None:
    data = user_info or {}
    return membership_for(data.get("vip_level", data.get("level")))


def membership_catalog() -> list[dict[str, Any]]:
    return [MEMBERSHIPS[level].as_dict() for level in sorted(MEMBERSHIPS)]


def capability_error(user_info: dict[str, Any] | None, api: str) -> str | None:
    membership = membership_from_account(user_info)
    if membership is None:
        return None
    label = membership_label(membership)
    if api == "host" and not membership.host_api:
        return t(
            f"{membership.name}（vip_level={membership.vip_level}）无主机聚合 API，"
            f"请改用普通检索（ip= / host=）。详见 {MEMBERSHIP_SOURCE}",
            f"{label} (vip_level={membership.vip_level}) has no host API. "
            f"Use a normal search with ip= or host=. See {MEMBERSHIP_SOURCE}",
        )
    if api == "stats" and not membership.stats_api:
        return t(
            f"{membership.name}（vip_level={membership.vip_level}）无统计聚合 API，"
            f"请改用普通检索。详见 {MEMBERSHIP_SOURCE}",
            f"{label} (vip_level={membership.vip_level}) has no stats API. "
            f"Use a normal search. See {MEMBERSHIP_SOURCE}",
        )
    return None


def host_fallback_query(target: str) -> str:
    text = target.strip().strip("'\"")
    try:
        ipaddress.ip_address(text)
        return f'ip="{text}"'
    except ValueError:
        return f'host="{text}"'


def capped_requests_per_second(configured: float, vip_level: Any) -> float:
    membership = membership_for(vip_level)
    if membership is None:
        return configured
    return min(configured, membership.requests_per_second)


def format_quota(data: dict[str, Any], membership: Membership | None = None) -> str:
    membership = membership or membership_from_account(data)
    query = data.get("remain_api_query")
    data_remain = data.get("remain_api_data")
    points = next((data[name] for name in ("fofa_point", "remain_free_point", "remain") if data.get(name) is not None), None)
    parts: list[str] = []
    daily_pack = membership is not None and not membership.remain_from_interface
    if daily_pack and query in (-1, "-1", None, ""):
        parts.append(t(f"查询：每日 {DAILY_FREE_REQUESTS} 次", f"Queries: {DAILY_FREE_REQUESTS}/day"))
    elif query not in (None, ""):
        parts.append(t(f"查询：{query}", f"Queries: {query}"))
    if daily_pack and data_remain in (-1, "-1", None, ""):
        parts.append(t("数据：套餐额度", "Data: plan quota"))
    elif data_remain not in (None, ""):
        parts.append(t(f"数据：{data_remain}", f"Data: {data_remain}"))
    if points not in (None, "", "-") and str(points) not in {str(query), str(data_remain)}:
        parts.append(t(f"F点：{points}", f"F-points: {points}"))
    return " · ".join(parts) if parts else "-"


def planner_capabilities_prompt(vip_level: Any) -> str:
    membership = membership_for(vip_level)
    if membership is None:
        return f"FOFA membership level: {vip_level} (unknown; do not assume host/stats APIs)"
    lines = [
        f"FOFA membership: {membership_label(membership)} (vip_level={membership.vip_level})",
        f"Host aggregation API: {'yes' if membership.host_api else 'no'}",
        f"Stats aggregation API: {'yes' if membership.stats_api else 'no'}",
        f"Official rate limit: {membership.requests_per_second:g} req/s",
    ]
    if not membership.host_api:
        lines.append("Do not select host_query; use fofa_search with ip= or host= instead.")
    if not membership.stats_api:
        lines.append("Do not select stat_query; use fofa_search instead.")
    return "\n".join(lines)
