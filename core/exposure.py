"""Exposure review: official app rule, update-time window, port stats, and a simulated scan.

The default retrieves the whole FOFA result for that query. A shorter pull happens only when the caller
asks for a sample. This module never starts Nuclei.
"""

from __future__ import annotations

import re
from datetime import date
from typing import Any

from core.agent import validate_query
from core.models import SearchRequest
from core.rules import resolve_rule_query

# Vendor defaults we are willing to name. Anything else stays unlabeled.
DEFAULT_PORTS: dict[str, tuple[int, ...]] = {"Grafana": (3000,)}
FULL_RECORD_CAP = 1_000_000
FULL_PAGE_CAP = 10_000
_SAMPLE_WORDS = re.compile(r"抽样|样本|sample", re.IGNORECASE)


def wants_sample(text: str) -> bool:
    return bool(_SAMPLE_WORDS.search(text or ""))


def month_start(today: date | None = None) -> str:
    current = today or date.today()
    return current.replace(day=1).isoformat()


def exposure_query(rule_query: str, *, city: str, country: str, after: str) -> str:
    body = rule_query if rule_query.startswith("(") else f"({rule_query})"
    return f'{body} && city="{city}" && country="{country}" && after="{after}"'


def port_rows(stats: dict[str, Any]) -> list[dict[str, Any]]:
    aggs = stats.get("aggs") if isinstance(stats, dict) else None
    raw = aggs.get("port") if isinstance(aggs, dict) else None
    rows = []
    for item in raw or []:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or "").strip()
        if not name:
            continue
        rows.append({"port": name, "count": int(item.get("count") or 0)})
    return rows


def _port_of(asset: dict[str, Any]) -> str:
    port = str(asset.get("port") or "").strip()
    if port:
        return port
    host = str(asset.get("host") or "")
    if host.count(":") == 1 and host.rsplit(":", 1)[-1].isdigit():
        return host.rsplit(":", 1)[-1]
    return ""


def default_port_targets(assets: list[dict[str, Any]], ports: tuple[int, ...]) -> list[dict[str, str]]:
    wanted = {str(port) for port in ports}
    targets = []
    seen: set[str] = set()
    for asset in assets:
        if _port_of(asset) not in wanted:
            continue
        ip = str(asset.get("ip") or "").strip()
        host = str(asset.get("host") or ip).strip()
        port = _port_of(asset)
        label = host if host else ip
        if not label or label in seen:
            continue
        seen.add(label)
        targets.append({"host": label, "ip": ip, "port": port, "url": f"http://{ip or label}:{port}"})
    return targets


def simulate_scan(targets: list[dict[str, str]]) -> dict[str, Any]:
    count = len(targets)
    progress = [
        {"stage": "queued", "done": 0, "total": count, "message": "模拟扫描已排队，尚未连接目标"},
        {"stage": "loaded", "done": 0, "total": count, "message": f"已装入 {count} 个默认端口目标，模板未加载"},
        {"stage": "running", "done": count, "total": count, "message": "模拟进度走完，没有发出扫描请求"},
        {"stage": "finished", "done": count, "total": count, "message": "模拟结束。没有漏洞结果。"},
    ]
    return {
        "mode": "simulated",
        "executed": False,
        "findings": [],
        "progress": progress,
        "note": "这是模拟反馈，没有运行 Nuclei，不能当作漏洞结论。真实扫描仍要单独授权。",
    }


def _pull_limits(*, sample: bool, page_size: int, max_records: int | None, population: int) -> tuple[int, int]:
    if sample:
        limit = max_records or min(page_size, 20)
        pages = max(1, min(FULL_PAGE_CAP, (limit + page_size - 1) // page_size))
        return limit, pages
    limit = max_records or population or FULL_RECORD_CAP
    if max_records is None and population:
        limit = population
    pages = max(1, min(FULL_PAGE_CAP, (limit + page_size - 1) // page_size))
    return limit, pages


async def exposure_review(
    client: Any,
    *,
    product: str,
    city: str = "Shanghai",
    country: str = "CN",
    after: str | None = None,
    size: int = 100,
    max_records: int | None = None,
    sample: bool = False,
) -> dict[str, Any]:
    rule = resolve_rule_query(product)
    window = after or month_start()
    query = exposure_query(rule.query, city=city, country=country, after=window)
    errors = validate_query(query)
    if errors:
        raise ValueError("暴露面语句无效：" + "; ".join(errors))
    stats = await client.stats(query, ["port"], size=100)
    population = int(stats.get("size") or 0) if isinstance(stats, dict) else 0
    limit, pages = _pull_limits(sample=sample, page_size=size, max_records=max_records, population=population)
    request = SearchRequest(
        query=query,
        fields=["host", "ip", "port", "protocol", "title"],
        size=min(size, limit),
        max_records=limit,
        max_pages=pages,
    )
    assets: list[dict[str, Any]] = []
    async for page in client.iter_search(request):
        if page.total:
            population = max(population, int(page.total))
        assets.extend(record.values for record in page.records)
    ports = DEFAULT_PORTS.get(rule.name, ())
    targets = default_port_targets(assets, ports) if ports else []
    scan = simulate_scan(targets)
    return {
        "product": rule.name,
        "rule_query": rule.query,
        "query": query,
        "time_basis": "FOFA after 是资产更新时间晚于该日期，包含本月有更新的资产，不是首次发现时间。",
        "after": window,
        "mode": "sample" if sample else "full",
        "population_size": population,
        "result_count": len(assets),
        "assets": assets,
        "port_distribution": port_rows(stats if isinstance(stats, dict) else {}),
        "default_ports": [str(port) for port in ports],
        "default_port_note": (
            "扫描目标是本次取回的全部默认端口资产。"
            if ports
            else "规则库没有收录该产品的默认端口，因此没有扫描目标。"
        ),
        "scan_targets": targets,
        "scan": scan,
    }
