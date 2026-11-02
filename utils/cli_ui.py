"""Human-first Rich terminal presentation for FofaMap's classic and wizard modes."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any

from rich import box
from rich.align import Align
from rich.console import Console, Group
from rich.markdown import Heading, Markdown
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from config import config_write_path
from core.models import AssetRecord, SearchPage
from core.version import BUILD_DATE, STUDIO, STUDIO_URL, VERSION
from utils.helpers import insert_alive_status_field
from utils.i18n import language, t

if TYPE_CHECKING:
    from core.agent import AgentRun
    from core.scanner import NucleiProgressEvent, NucleiScanResult

SEVERITY_LABELS = {
    "critical": "严重",
    "high": "高危",
    "medium": "中危",
    "low": "低危",
    "info": "信息",
    "unknown": "未知",
}

console = Console(highlight=False)


class _LeftAlignedHeading(Heading):
    LEVEL_ALIGN = {f"h{level}": "left" for level in range(1, 7)}

    def __rich_console__(self, console, options):
        text = self.text.copy()
        text.justify = "left"
        if self.tag == "h2":
            text.stylize("bold cyan")
            yield Text()
        elif self.tag == "h1":
            text.stylize("bold cyan")
        elif self.tag == "h3":
            text.stylize("bold")
        yield text


class LeftAlignedMarkdown(Markdown):
    """Rich Markdown with left-aligned headings and extra space before h2."""

    elements = {**Markdown.elements, "heading_open": _LeftAlignedHeading}


_SECTION_TITLES = {
    "结论": "结论",
    "高置信": "高置信资产",
    "高置信资产": "高置信资产",
    "噪声": "噪声与误报",
    "噪声与误报": "噪声与误报",
    "暴露面": "暴露面",
    "风险与暴露面": "风险与暴露面",
    "证据边界与噪声": "证据边界与噪声",
    "覆盖缺口": "覆盖缺口",
    "处置优先级": "处置优先级",
    "缺口": "下一步",
    "下一步": "下一步",
    "缺口与下一步": "下一步",
}


def normalize_summary_markdown(text: str) -> str:
    """Turn numbered walls of text into scannable `##` sections for the terminal."""
    if not text or not str(text).strip():
        return text
    body = str(text).replace("\r\n", "\n").strip()
    body = re.sub(
        r"^(?:#{1,6}\s*)?(?:\*\*)?(?:[一二三四五1-5][\.、]|[1-5]\.\s*)\s*"
        r"(结论|高置信资产|高置信|噪声与误报|噪声|风险与暴露面|暴露面|证据边界与噪声|"
        r"覆盖缺口|处置优先级|缺口与下一步|下一步|缺口)\s*(?:\*\*)?\s*$",
        lambda match: f"## {_SECTION_TITLES.get(match.group(1), match.group(1))}",
        body,
        flags=re.MULTILINE,
    )
    body = re.sub(r"\n{3,}", "\n\n", body)
    body = re.sub(r"([^\n])\n(## )", r"\1\n\n\2", body)
    return body.strip() + "\n"


def _summary_panel(markdown: str) -> Panel:
    rendered = LeftAlignedMarkdown(
        normalize_summary_markdown(markdown),
        code_theme="monokai",
        inline_code_theme="monokai",
        hyperlinks=False,
    )
    return Panel(
        rendered,
        title=f"[bold]{t('AI 总结', 'AI summary')}[/]",
        border_style="magenta",
        padding=(1, 3),
        expand=True,
    )


def print_banner() -> None:
    lines = [
        "  ______      ____        __  ___",
        " / ____/___  / __/___ _  /  |/  /___ _____",
        '/ /_  / __ \\/ /_/ __ `/ / /|_/ / __ `/ __ \\',
        "/ __/ / /_/ / __/ /_/ / / /  / / /_/ / /_/ /",
        "/_/    \\____/_/  \\__,_/ /_/  /_/\\__,_/ .___/",
        "                                      /_/",
    ]
    logo = Text()
    colors = ("#83d9db", "#7bd1d5", "#72c8ce", "#69bec7", "#60b4bf", "#57aab7")
    for index, (line, color) in enumerate(zip(lines, colors, strict=True)):
        logo.append(line + ("\n" if index < len(lines) - 1 else ""), style=f"bold {color}")
    width = min(console.width, 64)
    compact = width < max(map(len, lines)) + 6
    if compact:
        logo = Text("FofaMap", style="bold #7bd1d5")
    meta = Text()
    meta.append(f"v{VERSION}", style="bold #e2e8f0")
    meta.append(f"   {BUILD_DATE}", style="#94a3b8")
    if not compact:
        meta.append(f"   {STUDIO_URL}", style=f"#72c8ce link {STUDIO_URL}")
    credit = Text()
    if not compact:
        credit.append("[ AI Powered & Interactive Wizard ]", style="#94a3b8")
        credit.append("  —  ", style="#4b6575")
    credit.append(f"By {STUDIO}", style="#cbd5e1")
    content = [Align.center(logo), Text(""), Align.center(meta)]
    if compact:
        content.append(Align.center(Text(STUDIO_URL, style=f"#72c8ce link {STUDIO_URL}")))
    content.append(Align.center(credit))
    console.print(Panel(Group(*content), border_style="#4b7b85", padding=(1, 2), width=width))


def section(title: str, subtitle: str | None = None) -> None:
    label = Text(f" {title} ", style="bold black on cyan")
    if subtitle:
        label.append(f"   {subtitle}", style="not bold #94a3b8 on default")
    console.print()
    console.print(label)


def render_account(data: dict[str, Any]) -> None:
    from core.membership import format_quota, membership_from_account, membership_label

    name = data.get("username") or data.get("name") or data.get("email") or t("FOFA 用户", "FOFA user")
    membership = membership_from_account(data)
    vip_raw = data.get("vip_level") if data.get("vip_level") is not None else data.get("level") or data.get("vip") or "-"
    if membership:
        tier_label = t(
            f"{membership.name}（vip_level={membership.vip_level}）",
            f"{membership_label(membership)} (vip_level={membership.vip_level})",
        )
        capability = (
            f"{t('主机聚合', 'Host API')} {_yes(membership.host_api)} · "
            f"{t('统计聚合', 'Stats API')} {_yes(membership.stats_api)} · "
            f"{membership.requests_per_second:g} req/s"
        )
    else:
        tier_label = str(vip_raw)
        capability = t("未知（未识别的 vip_level）", "Unknown (unrecognized vip_level)")
    remain = format_quota(data, membership)
    email = str(data.get("email") or "")
    if "@" in email:
        local, domain = email.split("@", 1)
        email = f"{local[:2]}***@{domain}"
    grid = Table.grid(padding=(0, 2))
    grid.add_column(style="bold cyan")
    grid.add_column(style="white")
    grid.add_row(t("账号", "Account"), str(name))
    if email:
        grid.add_row(t("邮箱", "Email"), email)
    grid.add_row(t("会员等级", "Membership"), tier_label)
    grid.add_row(t("接口权限", "API access"), capability)
    grid.add_row(t("可用额度", "Quota"), remain)
    console.print(Panel(grid, title=f"[bold green]✓ {t('FOFA 登录成功', 'FOFA login succeeded')}[/]", border_style="green", expand=False))


def _yes(flag: bool) -> str:
    style = "bold bright_green" if flag else "bold bright_red"
    word = t("是", "Yes") if flag else t("否", "No")
    return f"[{style}]{word}[/]"


def _switch_row(label: str, enabled: bool) -> tuple[str, str]:
    """On and off use different colors, and the row title follows the same color."""
    style = "bold bright_green" if enabled else "bold bright_red"
    word = t("是", "Yes") if enabled else t("否", "No")
    return f"[{style}]{label}[/]", f"[{style}]{word}[/]"


def _append_run_switches(
    grid: Table,
    *,
    ai: bool,
    check_alive: bool,
    deep_search: bool,
    smart_fields: bool,
    nuclei: bool,
    scan_ai_dedupe: bool = False,
) -> None:
    language_name = "English" if language() == "en" else "中文"
    grid.add_row(f"[bold cyan]{t('界面语言', 'Language')}[/]", f"[bold bright_white]{language_name}[/]")
    grid.add_row(*_switch_row(t("AI 分析", "AI analysis"), ai))
    grid.add_row(*_switch_row(t("存活检测", "Alive check"), check_alive))
    grid.add_row(*_switch_row(t("深度搜索", "Deep search"), deep_search))
    grid.add_row(*_switch_row(t("智能字段", "Smart fields"), smart_fields))
    if nuclei:
        grid.add_row(
            f"[bold yellow]{t('漏洞扫描', 'Vuln scan')}[/]",
            f"[bold yellow]{t('已请求 · 待方案审批', 'Requested · awaiting plan approval')}[/]",
        )
    else:
        grid.add_row(*_switch_row(t("漏洞扫描", "Vuln scan"), False))
    grid.add_row(*_switch_row(t("AI 扫描筛选", "AI scan selection"), scan_ai_dedupe))


def render_run_switches(
    *,
    ai: bool,
    check_alive: bool,
    deep_search: bool,
    smart_fields: bool,
    nuclei: bool,
    scan_ai_dedupe: bool = False,
) -> None:
    grid = Table.grid(padding=(0, 2))
    grid.add_column(no_wrap=True)
    grid.add_column()
    _append_run_switches(
        grid,
        ai=ai,
        check_alive=check_alive,
        deep_search=deep_search,
        smart_fields=smart_fields,
        nuclei=nuclei,
        scan_ai_dedupe=scan_ai_dedupe,
    )
    console.print(Panel(grid, title=f"[bold bright_cyan]{t('本次开关', 'Switches')}[/]", border_style="bright_cyan"))


def render_deep_search(reason: str, *, notes: bool = False, failed: str | None = None) -> None:
    """Box the deep-search decision the same way as the switch and progress panels."""
    if failed:
        body = failed
        border = "yellow"
    else:
        body = reason.strip()
        if notes:
            body += t(
                "\n这些线索只用来写查询，不能当成漏洞已经确认。",
                "\nThese notes only shape the query. They do not confirm a vulnerability.",
            )
        border = "cyan"
    console.print(Panel(body, title=f"[bold]{t('深度搜索', 'Deep search')}[/]", border_style=border))


def render_query_overview(
    query: str,
    fields: list[str],
    pages: int,
    size: int,
    full: bool,
    *,
    ai: bool = False,
    check_alive: bool = False,
    deep_search: bool = False,
    smart_fields: bool = False,
    nuclei: bool = False,
    scan_ai_dedupe: bool = False,
) -> None:
    grid = Table.grid(padding=(0, 2))
    grid.add_column(no_wrap=True)
    grid.add_column()
    grid.add_row(f"[bold cyan]{t('查询语句', 'Query')}[/]", f"[bright_white]{query}[/]")
    grid.add_row(f"[bold cyan]{t('返回字段', 'Fields')}[/]", f"[bright_white]{', '.join(fields)}[/]")
    budget = t(f"最多 {pages} 页 × {size} 条", f"up to {pages} pages × {size} rows")
    grid.add_row(f"[bold cyan]{t('查询预算', 'Budget')}[/]", f"[bright_white]{budget}[/]")
    grid.add_row(*_switch_row(t("历史数据", "Historical data"), bool(full)))
    _append_run_switches(
        grid,
        ai=ai,
        check_alive=check_alive,
        deep_search=deep_search,
        smart_fields=smart_fields,
        nuclei=nuclei,
        scan_ai_dedupe=scan_ai_dedupe,
    )
    console.print(Panel(grid, title=f"[bold bright_cyan]{t('检索任务', 'Search task')}[/]", border_style="bright_cyan"))


def _cell(value: Any, limit: int = 72) -> str:
    text = "" if value is None else str(value).replace("\n", " ").replace("\r", " ")
    return text if len(text) <= limit else text[: limit - 1] + "…"


def _visible_fields(fields: list[str], terminal_width: int) -> list[str]:
    priority = ["host", "ip", "port", "protocol", "alive_status", "evidence", "status_code", "title", "country", "domain"]
    preferred = [field for field in priority if field in fields]
    preferred.extend(field for field in fields if field not in preferred)
    limit = 5 if terminal_width < 100 else 7 if terminal_width < 140 else 9
    return preferred[:limit]


def build_asset_table(page: SearchPage, display_rows: int = 100, terminal_width: int | None = None) -> Table:
    visible_fields = _visible_fields(page.fields, terminal_width or console.width)
    table = Table(
        box=box.SIMPLE_HEAVY,
        header_style="bold cyan",
        row_styles=["", "dim"],
        show_lines=False,
        expand=True,
    )
    table.add_column("#", justify="right", style="dim", no_wrap=True)
    widths = {
        "host": 30,
        "ip": 18,
        "port": 7,
        "protocol": 10,
        "status_code": 8,
        "title": 36,
        "country": 9,
        "domain": 24,
        "alive_status": 12,
        "evidence": 8,
    }
    minimums = {
        "host": 22,
        "ip": 15,
        "port": 5,
        "protocol": 6,
        "status_code": 6,
        "title": 18,
        "country": 4,
        "domain": 14,
        "alive_status": 7,
        "evidence": 4,
    }
    labels = {
        "host": t("主机", "Host"),
        "ip": "IP",
        "port": t("端口", "Port"),
        "protocol": t("协议", "Protocol"),
        "status_code": t("状态码", "Status"),
        "title": t("标题", "Title"),
        "country": t("国家", "Country"),
        "domain": t("域名", "Domain"),
        "alive_status": t("存活", "Alive"),
        "lastupdatetime": t("更新时间", "Updated"),
        "product.version": t("版本", "Version"),
        "evidence": t("归属证据", "Evidence"),
    }
    for field in visible_fields:
        justify = "right" if field in {"port", "status_code"} else "left"
        table.add_column(
            labels.get(field, field),
            justify=justify,
            overflow="ellipsis",
            no_wrap=True,
            min_width=minimums.get(field, 8),
            max_width=widths.get(field, 18),
            ratio=2 if field in {"host", "title"} else 1,
        )
    for index, record in enumerate(page.records[:display_rows], start=1):
        table.add_row(str(index), *[_cell(record.values.get(field)) for field in visible_fields])
    return table


def render_search_page(page: SearchPage, page_number: int, display_rows: int = 100) -> None:
    count = len(page.records)
    title = t(f"第 {page_number} 页 · {count} 条", f"Page {page_number} · {count} rows")
    if page.total is not None:
        title += t(f" · FOFA 总量 {page.total:,}", f" · FOFA total {page.total:,}")
    console.print(Panel(build_asset_table(page, display_rows), title=f"[bold green]{title}[/]", border_style="green"))
    hidden = [field for field in page.fields if field not in _visible_fields(page.fields, console.width)]
    if hidden:
        console.print(
            f"[dim]{t('为适配当前终端宽度，表格隐藏字段：', 'Hidden to fit the terminal: ')}{', '.join(hidden)}"
            f"{t('；导出文件仍保留全部字段。', '. The export still keeps every field.')}[/]"
        )
    if count > display_rows:
        console.print(
            "[dim]"
            + t(
                f"本页仅展示前 {display_rows} 条，其余 {count - display_rows} 条仍会写入导出文件。",
                f"This page shows the first {display_rows} rows. The other {count - display_rows} are still exported.",
            )
            + "[/]"
        )


def render_search_summary(*, records: int, pages: int, artifact: str | None, elapsed: float) -> None:
    parts = [
        f"[bold green]✓ {t('检索完成', 'Search finished')}[/]",
        t(f"共 [bold]{records:,}[/] 条", f"[bold]{records:,}[/] rows"),
        t(f"{pages} 页", f"{pages} pages"),
        t(f"耗时 {elapsed:.2f}s", f"{elapsed:.2f}s"),
    ]
    if artifact:
        parts.append(t(f"已保存至 [cyan]{artifact}[/]", f"saved to [cyan]{artifact}[/]"))
    console.print(Panel("  ·  ".join(parts), border_style="green"))


def render_host(data: dict[str, Any]) -> None:
    grid = Table.grid(padding=(0, 2))
    grid.add_column(style="bold cyan")
    grid.add_column()
    for label, key in (
        (t("主机", "Host"), "host"),
        ("IP", "ip"),
        (t("国家/地区", "Country"), "country_name"),
        (t("组织", "Organization"), "org"),
        ("ASN", "asn"),
        (t("更新时间", "Updated"), "update_time"),
    ):
        grid.add_row(label, _cell(data.get(key, "-")))
    items: list[Any] = [Panel(grid, title=f"[bold]{t('主机资产画像', 'Host profile')}[/]", border_style="cyan")]
    ports = data.get("ports") or []
    if ports:
        table = Table(box=box.SIMPLE_HEAVY, header_style="bold cyan", expand=True)
        table.add_column(t("端口", "Port"), justify="right")
        table.add_column(t("协议", "Protocol"))
        table.add_column(t("产品", "Product"))
        table.add_column(t("更新时间", "Updated"))
        for port in sorted(ports, key=lambda item: item.get("port") or 0):
            products = ", ".join(str(product.get("product") or product.get("name") or "") for product in (port.get("products") or []))
            table.add_row(
                _cell(port.get("port")),
                _cell(port.get("protocol")),
                _cell(products),
                _cell(port.get("update_time")),
            )
        items.append(
            Panel(
                table,
                title=f"[bold green]{t(f'开放端口 · {len(ports)}', f'Open ports · {len(ports)}')}[/]",
                border_style="green",
            )
        )
    else:
        lines: list[str] = []
        for label, key in (
            (t("端口", "Port"), "port"),
            (t("协议", "Protocol"), "protocol"),
            (t("产品", "Product"), "product"),
            (t("分类", "Category"), "category"),
            (t("域名", "Domain"), "domain"),
        ):
            value = data.get(key)
            if isinstance(value, list) and value:
                shown = ", ".join(_cell(item, 40) for item in value[:12])
                extra = t(f" 等 {len(value)} 项", f" and {len(value) - 12} more") if len(value) > 12 else ""
                lines.append(f"[bold cyan]{label}[/]  {shown}{extra}")
        if lines:
            items.append(Panel("\n".join(lines), title=f"[bold green]{t('聚合概览', 'Aggregates')}[/]", border_style="green"))
    console.print(Group(*items))


def render_stats(data: dict[str, Any], query: str) -> None:
    console.print(
        Panel(
            f"[bold]{t('查询：', 'Query: ')}[/]{query}\n[bold]{t('统计总量：', 'Total: ')}[/]{data.get('size', 0):,}",
            border_style="cyan",
        )
    )
    for field, rows in (data.get("aggs") or {}).items():
        table = Table(box=box.SIMPLE_HEAVY, header_style="bold cyan", expand=False)
        table.add_column("#", justify="right", style="dim")
        table.add_column(field.upper(), min_width=24)
        table.add_column(t("数量", "Count"), justify="right")
        for index, item in enumerate((rows or [])[:20], start=1):
            table.add_row(str(index), _cell(item.get("name")), f"{item.get('count', 0):,}")
        console.print(Panel(table, title=f"[bold green]{field} Top {min(len(rows or []), 20)}[/]", border_style="green"))


def _agent_state_label(value: str) -> str:
    labels = {
        "intent_parsing": t("需求解析", "Intent"),
        "query_validation": t("语法校验", "Syntax"),
        "execute": t("资产查询", "Search"),
        "evaluate": t("结果评估", "Review"),
        "reflect": t("动态反思", "Reflect"),
        "query_repair": t("查询修复", "Repair"),
        "summarize": t("生成总结", "Summary"),
        "completed": t("完成", "Completed"),
        "failed": t("失败", "Failed"),
    }
    return labels.get(value, value)


def _agent_asset_page(run: AgentRun, *, tail: int | None = None) -> SearchPage:
    start = max(0, len(run.assets) - tail) if tail else 0
    assets = run.assets[start:]
    fields = run.fields or list(dict.fromkeys(key for asset in assets for key in asset))
    records = []
    confidence_labels = {
        "precision": t("高", "High"),
        "balanced": t("中", "Medium"),
        "hypothesis": t("待验证", "Unverified"),
        "recall": t("候选", "Candidate"),
    }
    for offset, asset in enumerate(assets):
        values = dict(asset)
        confidence_index = start + offset
        if confidence_index < len(run.asset_confidence):
            values["evidence"] = confidence_labels.get(run.asset_confidence[confidence_index], t("候选", "Candidate"))
        records.append(AssetRecord(values=values))
    if any("alive_status" in asset for asset in assets):
        fields = insert_alive_status_field(fields)
    if run.asset_confidence and "evidence" not in fields:
        fields = [*fields, "evidence"]
    return SearchPage(
        query=run.query or "",
        fields=fields,
        records=records,
    )


def _agent_query_table(run: AgentRun, *, compact: bool = False) -> Table:
    table = Table(box=box.SIMPLE_HEAVY, header_style="bold cyan", expand=True)
    table.add_column("#", justify="right", style="dim", no_wrap=True)
    table.add_column(t("来源", "Source"), no_wrap=True)
    table.add_column(t("策略", "Strategy"), no_wrap=True)
    table.add_column(t("查询目的", "Purpose"), max_width=30)
    table.add_column(t("FOFA 语句", "FOFA query"), ratio=3)
    if not compact:
        table.add_column(t("FOFA总量", "FOFA total"), justify="right", no_wrap=True)
        table.add_column(t("取样", "Sample"), justify="right", no_wrap=True)
        table.add_column(t("新增", "New"), justify="right", no_wrap=True)
    for index, item in enumerate(run.queries, start=1):
        source = {
            "planner": t("首轮规划", "Initial plan"),
            "entity_resolution": t("官网线索", "Site lead"),
            "library": t("规则库", "Rule library"),
        }.get(item.source, t(f"动态反思 R{item.source.rsplit('_', 1)[-1]}", f"Reflection R{item.source.rsplit('_', 1)[-1]}"))
        strategy = {
            "precision": t("精准", "Precision"),
            "balanced": t("均衡", "Balanced"),
            "hypothesis": t("待验证", "Hypothesis"),
            "recall": t("召回", "Recall"),
            "correction": t("修正", "Correction"),
        }.get(item.strategy, item.strategy)
        values = [str(index), source, strategy, _cell(item.purpose, 30), _cell(item.query, 140)]
        if not compact:
            available = str(item.available_count) if item.available_count is not None else "-"
            values.extend([available, str(item.result_count), str(item.new_assets)])
        table.add_row(*values)
    return table


def _website_candidate_table(run: AgentRun) -> Table:
    table = Table(box=box.SIMPLE_HEAVY, header_style="bold cyan", expand=True)
    table.add_column(t("状态", "Status"), no_wrap=True)
    table.add_column(t("域名", "Domain"), no_wrap=True)
    table.add_column(t("首选 URL", "Preferred URL"), ratio=2)
    table.add_column(t("证据", "Evidence"), ratio=2)
    status_labels = {
        "corroborated": t("交叉印证", "Corroborated"),
        "observed": t("FOFA 已观测", "Observed"),
        "candidate": t("待验证", "Candidate"),
    }
    evidence_labels = {
        "entity_resolution": t("实体解析", "Entity resolution"),
        "name_in_title": t("标题同名", "Title match"),
        "icp_observed": t("备案线索", "ICP clue"),
        "certificate_observed": t("证书线索", "Certificate clue"),
        "fofa_precision": t("精准查询", "Precision query"),
        "fofa_balanced": t("均衡查询", "Balanced query"),
        "fofa_hypothesis": t("域名假设", "Domain hypothesis"),
        "fofa_recall": t("召回查询", "Recall query"),
    }
    for item in run.website_candidates:
        table.add_row(
            status_labels.get(item.status, item.status),
            item.domain,
            _cell(item.url, 80),
            "、".join(evidence_labels.get(value, value) for value in item.evidence),
        )
    return table


def _step_clock(step: Any) -> str:
    started = getattr(step, "started_at", None)
    if started is None:
        return "-"
    return started.strftime("%H:%M:%S")


def _format_elapsed(seconds: int) -> str:
    hours, rem = divmod(max(0, seconds), 3600)
    minutes, secs = divmod(rem, 60)
    if hours:
        return t(f"{hours} 小时 {minutes:02d} 分 {secs:02d} 秒", f"{hours}h {minutes:02d}m {secs:02d}s")
    if minutes:
        return t(f"{minutes} 分 {secs:02d} 秒", f"{minutes}m {secs:02d}s")
    return t(f"{secs} 秒", f"{secs}s")


def _token_usage(run: AgentRun) -> tuple[int, int] | None:
    seen = False
    incoming = 0
    outgoing = 0
    for event in run.route_events:
        prompt = event.get("input_tokens")
        completion = event.get("output_tokens")
        if prompt is None and completion is None:
            continue
        seen = True
        incoming += int(prompt or 0)
        outgoing += int(completion or 0)
    if not seen:
        return None
    return incoming, outgoing


def render_run_usage(run: AgentRun) -> None:
    """Print total elapsed time and model token use once the agent run has finished."""
    if run.finished_at is None:
        return
    elapsed = _format_elapsed(int((run.finished_at - run.started_at).total_seconds()))
    usage = _token_usage(run)
    if usage is None:
        body = t(f"耗时 {elapsed} · 模型未返回 Token 用量", f"Elapsed {elapsed} · Token usage was not returned")
    else:
        incoming, outgoing = usage
        total = incoming + outgoing
        body = t(
            f"耗时 {elapsed} · Token {total:,}（输入 {incoming:,} · 输出 {outgoing:,}）",
            f"Elapsed {elapsed} · Tokens {total:,} (input {incoming:,} · output {outgoing:,})",
        )
    console.print(Panel(body, title=f"[bold]{t('任务用量', 'Run usage')}[/]", border_style="cyan", expand=False))


def build_agent_progress(run: AgentRun, latest_page: SearchPage | None = None) -> Group:
    """Build the transient live view shown while the Agent is still running."""
    grid = Table(box=box.SIMPLE, header_style="bold cyan", expand=True)
    grid.add_column(t("时间", "Time"), no_wrap=True)
    grid.add_column(t("阶段", "Stage"), no_wrap=True)
    grid.add_column(t("实时进度", "Progress"), ratio=3)
    for step in run.steps[-8:]:
        grid.add_row(_step_clock(step), _agent_state_label(step.state.value), step.detail)
    items: list[Any] = [Panel(grid, title=f"[bold cyan]{t('智能体实时执行中', 'Agent running')}[/]", border_style="cyan")]
    if run.queries:
        items.append(
            Panel(
                _agent_query_table(run, compact=True),
                title=(
                    f"[bold blue]{t('查询策略', 'Queries')} · {len(run.queries)} · "
                    f"{t(f'当前去重资产 {run.result_count:,} 条', f'{run.result_count:,} unique assets')}[/]"
                ),
                border_style="blue",
            )
        )
    elif run.query:
        items.append(
            Panel(
                f"[bold]{t('FOFA 语句', 'FOFA query')}[/]  {run.query}\n[bold]{t('当前已接收', 'Received')}[/]  {run.result_count:,}",
                border_style="blue",
            )
        )
    if latest_page and latest_page.records:
        page = latest_page.model_copy(update={"records": latest_page.records[-8:]})
        items.append(
            Panel(
                build_asset_table(page, display_rows=8),
                title=f"[bold green]{t(f'本页最新资产 · 累计 {run.result_count:,} 条', f'Latest rows · {run.result_count:,} total')}[/]",
                border_style="green",
            )
        )
    elif run.assets:
        page = _agent_asset_page(run, tail=8)
        items.append(
            Panel(
                build_asset_table(page, display_rows=8),
                title=f"[bold green]{t(f'最新资产 · 累计 {run.result_count:,} 条', f'Latest assets · {run.result_count:,} total')}[/]",
                border_style="green",
            )
        )
    return Group(*items)


def render_agent(run: AgentRun) -> None:
    state_style = "green" if run.error is None else "red"
    grid = Table(box=box.SIMPLE, header_style="bold cyan", expand=True)
    grid.add_column(t("时间", "Time"), no_wrap=True)
    grid.add_column(t("步骤", "Step"), no_wrap=True)
    grid.add_column(t("状态", "Status"))
    grid.add_column(t("说明", "Detail"), ratio=3)
    for index, step in enumerate(run.steps, start=1):
        grid.add_row(_step_clock(step), str(index), _agent_state_label(step.state.value), step.detail)
    console.print(
        Panel(
            grid,
            title=f"[bold {state_style}]{t('智能体', 'Agent')} · {_agent_state_label(run.state.value)}[/]",
            border_style=state_style,
        )
    )
    if run.action.value == "host_query" and run.result_data:
        render_host(run.result_data)
    elif run.action.value == "stat_query" and run.result_data:
        render_stats(run.result_data, run.query or "")
    if run.queries and run.action.value != "stat_query":
        console.print(
            Panel(
                _agent_query_table(run),
                title=(
                    f"[bold cyan]{t('FOFA 多维查询策略', 'FOFA queries')} · {len(run.queries)} · "
                    f"{t(f'去重结果 {run.result_count:,} 条', f'{run.result_count:,} unique')}[/]"
                ),
                border_style="cyan",
            )
        )
    elif run.query:
        console.print(
            Panel(
                f"[bold]{t('FOFA 语句', 'FOFA query')}[/]\n{run.query}\n\n[bold]{t('结果数', 'Results')}[/]  {run.result_count:,}",
                border_style="cyan",
            )
        )
    if run.website_candidates:
        console.print(
            Panel(
                _website_candidate_table(run),
                title=(
                    "[bold magenta]"
                    + t(
                        f"网站候选清单 · {len(run.website_candidates)} 个",
                        f"Website candidates · {len(run.website_candidates)}",
                    )
                    + "[/]"
                ),
                subtitle=t(
                    "交叉印证仍不等同于法律或组织归属确认",
                    "Corroboration is not legal or organizational ownership",
                ),
                border_style="magenta",
            )
        )
    if run.assets:
        page = _agent_asset_page(run)
        shown = len(run.assets)
        title = t(
            f"查询到的资产候选 · 展示 {shown:,} / {run.result_count:,} 条",
            f"Assets · showing {shown:,} / {run.result_count:,}",
        )
        console.print(Panel(build_asset_table(page, display_rows=shown), title=f"[bold green]{title}[/]", border_style="green"))
        if run.evidence_counts.get("recall"):
            console.print(
                "[yellow]"
                + t(
                    f"其中 {run.evidence_counts['recall']:,} 条仅由召回型语句命中，表示名称/内容相关候选，不等同于已确认归属。",
                    f"{run.evidence_counts['recall']:,} rows came only from recall queries. A name or body hit is not confirmed ownership.",
                )
                + "[/]"
            )
        if run.evidence_counts.get("hypothesis"):
            console.print(
                "[yellow]"
                + t(
                    f"其中 {run.evidence_counts['hypothesis']:,} 条来自官网域名假设验证，"
                    "仅说明候选域名在 FOFA 中存在；归属仍需结合官网内容、备案或权威来源复核。",
                    f"{run.evidence_counts['hypothesis']:,} rows came from a website-domain hypothesis. "
                    "That only means the domain is indexed. Ownership still needs the site, a filing, or another authoritative source.",
                )
                + "[/]"
            )
        if run.assets_truncated:
            console.print(
                "[dim]"
                + t(
                    f"终端结果为前 {shown:,} 条预览；本次查询实际返回 {run.result_count:,} 条。",
                    f"The terminal shows the first {shown:,} rows. This query returned {run.result_count:,}.",
                )
                + "[/]"
            )
    if run.summary:
        console.print(_summary_panel(run.summary))
    if run.error:
        render_error(
            run.error.get("code", "agent_error"),
            run.error.get("message", "智能体执行失败"),
            hint=run.error.get("hint"),
        )
        return
    if not run.shows_scan_decision():
        return
    decision = Table.grid(padding=(0, 2))
    decision.add_column(style="bold cyan")
    decision.add_column()
    decision.add_row(t("用户要求扫描", "User requested a scan"), t("是", "Yes") if run.scan_requested_by_user else t("否", "No"))
    decision.add_row(t("AI 建议扫描（参考）", "AI scan advice (advisory)"), t("是", "Yes") if run.scan_recommended else t("否", "No"))
    if run.scan_requested_by_user:
        decision_en = (
            "User instruction takes priority; prepare plan approval" if run.scan_targets
            else "User requested a scan; no valid targets are available"
        )
        decision.add_row(t("最终决策", "Final decision"), t(
            "用户指令优先，进入方案确认" if run.scan_targets else "用户要求扫描，当前没有有效候选目标",
            decision_en,
        ))
    if getattr(run, "scan_scope_note", ""):
        decision.add_row(t("扫描范围", "Scan scope"), run.scan_scope_note)
    decision.add_row(t("判断理由", "Reason"), run.scan_reason or "-")
    decision.add_row(t("候选目标", "Candidate targets"), f"{len(run.scan_targets):,}")
    decision.add_row(
        t(f"模板 ID（{len(run.scan_template_ids)}）", f"Template IDs ({len(run.scan_template_ids)})"),
        ", ".join(run.scan_template_ids) or "-",
    )
    decision.add_row(t("严重级别", "Severities"), ", ".join(run.scan_severities))
    console.print(Panel(decision, title=f"[bold]{t('扫描决策（尚未执行）', 'Scan decision (not run yet)')}[/]", border_style="yellow"))


def render_scan_approval(
    *,
    targets: list[str],
    template_ids: list[str],
    severities: list[str],
    reason: str,
    all_templates: bool = False,
    all_severities: bool = False,
) -> None:
    preview = "\n".join(f"  • {_cell(target, 100)}" for target in targets[:8])
    if len(targets) > 8:
        preview += f"\n  … 以及另外 {len(targets) - 8:,} 个目标"
    template_scope = "ALL（全部已安装模板）" if all_templates else ", ".join(template_ids)
    severity_scope = "ALL（全部严重级别）" if all_severities else ", ".join(severities)
    scope_warning = (
        "\n[bold red]范围警告：ALL 会运行当前 Nuclei 安装可加载的完整模板集合；耗时、请求量和潜在影响都会显著增加。[/]\n"
        if all_templates
        else ""
    )
    body = (
        f"[bold]AI 判断：[/]{reason or '-'}\n"
        f"[bold]目标数量：[/]{len(targets):,}\n"
        f"[bold]模板范围：[/]{template_scope}\n"
        f"[bold]严重级别：[/]{severity_scope}\n"
        f"{scope_warning}\n"
        f"[bold]目标预览[/]\n{preview}"
    )
    console.print(
        Panel(
            body,
            title="[bold yellow]⚠ Nuclei 执行审批[/]",
            subtitle="确认令牌仅绑定以上目标、模板范围、级别范围与有效期",
            border_style="yellow",
        )
    )


_SEVERITY_STYLE = {
    "critical": "bold red",
    "high": "red",
    "medium": "yellow",
    "low": "cyan",
    "info": "dim",
    "unknown": "white",
}


def _severity_label(name: str) -> str:
    labels = {
        "critical": t("严重", "Critical"),
        "high": t("高危", "High"),
        "medium": t("中危", "Medium"),
        "low": t("低危", "Low"),
        "info": t("信息", "Info"),
        "unknown": t("未知", "Unknown"),
    }
    return labels.get(name, name)


def build_nuclei_progress(
    event: NucleiProgressEvent | None,
    *,
    target_count: int,
    template_ids: list[str] | None = None,
) -> Panel:
    grid = Table.grid(padding=(0, 2))
    grid.add_column(style="bold cyan", no_wrap=True)
    grid.add_column()
    loaded = event.loaded_targets if event and event.loaded_targets is not None else target_count
    grid.add_row("扫描目标", f"{loaded:,} 个")
    if event and event.loaded_templates is not None:
        grid.add_row("已加载模板", f"{event.loaded_templates:,} 个")
    elif template_ids:
        grid.add_row("模板 ID", ", ".join(template_ids))
    grid.add_row("已发现命中", f"{event.findings if event else 0:,} 条")
    grid.add_row("已运行", f"{event.elapsed_seconds if event else 0:.0f} 秒")
    percent = event.percent if event else None
    grid.add_row("请求进度", f"{percent:.1f}%" if percent is not None else "等待引擎统计（不估算百分比）")
    requests = event.requests if event else None
    total = event.total_requests if event else None
    grid.add_row("已发请求", f"{requests:,} / {total:,}" if requests is not None and total is not None else str(requests or 0))
    grid.add_row("速率 / 错误", f"{event.rps or 0:g} req/s · {event.errors or 0} 错误" if event else "等待统计")
    grid.add_row("最新日志", _cell(event.line if event else "正在启动 Nuclei…", 100))
    return Panel(grid, title="[bold yellow]Nuclei 扫描进行中[/]", subtitle="Esc / Ctrl+C 停止扫描并返回", border_style="yellow")


def render_scan_selection(audit: dict) -> None:
    table = Table("目标", "决定", "理由", expand=True, header_style="bold cyan")
    labels = {"keep": ("保留", "green"), "exclude": ("排除", "yellow"), "duplicate": ("重复", "dim")}
    for row in audit.get("decisions", []):
        label, style = labels[row["action"]]
        table.add_row(Text(row["target"]), Text(label, style=style), Text(row["reason"]))
    console.print(Panel(table, title=f"AI 扫描筛选 · {audit['input_count']} → {audit['selected_count']} 个目标", border_style="cyan"))


def render_nuclei_results(result: NucleiScanResult, *, preview: int = 20) -> None:
    for warning in result.warnings:
        console.print(Text(warning, style="yellow"))
    summary = Table.grid(padding=(0, 2))
    summary.add_column(style="bold cyan", no_wrap=True)
    summary.add_column()
    summary.add_row("扫描目标", f"{(result.loaded_targets or result.target_count):,} 个")
    summary.add_row("命中条数", f"{len(result.findings):,} 条")
    summary.add_row("涉及站点", f"{result.host_count:,} 个")
    summary.add_row("耗时", f"{result.duration_seconds:.1f}s")
    if result.severity_counts:
        summary.add_row(
            "严重级别",
            "  ".join(
                f"[{_SEVERITY_STYLE.get(name, 'white')}]{_severity_label(name)} {count:,}[/]"
                for name, count in result.severity_counts.items()
            ),
        )
    title = "[bold green]✓ Nuclei 扫描完成[/]" if result.findings else "[bold green]✓ Nuclei 扫描完成 · 未发现命中[/]"
    console.print(Panel(summary, title=title, subtitle=result.headline(), border_style="green"))

    grouped = result.grouped()
    if grouped:
        table = Table(
            box=box.SIMPLE_HEAVY,
            header_style="bold cyan",
            row_styles=["", "dim"],
            expand=True,
            show_lines=False,
        )
        table.add_column("级别", no_wrap=True)
        table.add_column("站点", overflow="fold", min_width=24)
        table.add_column("检测项", overflow="fold")
        table.add_column("命中详情", overflow="fold", ratio=2)
        for hit in grouped[:preview]:
            style = _SEVERITY_STYLE.get(hit.severity, "white")
            details = ", ".join(hit.details) if hit.details else f"{hit.count} 条命中"
            table.add_row(
                f"[{style}]{_severity_label(hit.severity)}[/]",
                hit.target,
                hit.name or hit.template_id,
                _cell(details, 80),
            )
        extra = f" · 仅展示前 {preview:,} 个站点" if len(grouped) > preview else ""
        console.print(Panel(table, title=f"[bold]命中站点汇总 · {len(grouped):,} 个{extra}[/]", border_style="cyan"))
    if result.summary_path:
        console.print(f"[bold green]✓ 可读摘要：[/][cyan]{result.summary_path}[/]")
    console.print(f"[dim]原始 JSONL：{result.artifact}[/]")


def render_error(
    code: str,
    message: str,
    alternatives: list[str] | None = None,
    *,
    hint: str | None = None,
) -> None:
    config_path = config_write_path()
    hints = {
        "auth_failed": t(
            "FOFA 拒绝了当前密钥。程序优先使用环境变量 FOFA_API_KEY / FOFA_KEY，"
            "它会覆盖 config/settings.yaml。请对照 fofa.info 个人中心的 API Key，更新 shell 配置后重新打开终端。",
            "FOFA rejected the key. FOFA_API_KEY / FOFA_KEY override config/settings.yaml. "
            "Copy the key from the fofa.info account page, update the shell, and open a new terminal.",
        ),
        "quota_exhausted": t(
            "FOFA 查询额度不足，请检查账号用量或降低查询预算。",
            "The FOFA query quota is used up. Check the account or lower the query budget.",
        ),
        "permission_denied": t(
            "当前账号无权使用请求字段。FofaMap 不会静默降级，请确认替代字段后重试。",
            "This account cannot use the requested fields. FofaMap will not drop them silently.",
        ),
        "rate_limited": t(
            "触发 FOFA 限速；客户端已完成安全重试，请稍后再试或降低速率。",
            "FOFA rate-limited the request. Safe retries are finished; wait or lower the rate.",
        ),
        "invalid_query": t("请检查 FOFA 查询语法、引号与括号。", "Check the FOFA query syntax, quotes, and parentheses."),
        "transport_error": t(
            "网络或 FOFA 服务暂时不可用，请检查连接后重试。",
            "The network or FOFA is temporarily unavailable. Check the connection and retry.",
        ),
        "model_provider_not_configured": t(
            f"运行 `fofamap init`（也兼容 `python fofamap.py -init`）配置 AI 提供商。配置文件位置：{config_path}",
            f"Run `fofamap init` to configure an AI provider. Config file: {config_path}",
        ),
        "model_auth_failed": t(
            f"AI API 密钥无效、过期或未配置。运行 `fofamap init` 重新填写，或检查环境变量/系统钥匙串。配置文件：{config_path}",
            f"The AI API key is missing, expired, or rejected. Run `fofamap init` again. Config file: {config_path}",
        ),
        "model_not_found": t(
            "检查模型 ID、接口地址和协议；Ollama/LM Studio 还需确认服务已启动且模型已安装。",
            "Check the model ID, API address, and protocol. For Ollama or LM Studio, confirm the service and model are installed.",
        ),
        "model_transport_error": t(
            "检查网络、代理和接口地址；使用 Ollama/LM Studio 时确认本地服务端口可访问。",
            "Check the network, proxy, and API address. For Ollama or LM Studio, confirm the local port is reachable.",
        ),
        "model_rate_limited": t(
            "模型额度或速率已用尽，请检查供应商账户或 Token Plan 配额后重试。",
            "The model quota or rate is exhausted. Check the provider account and retry.",
        ),
        "model_request_error": t(
            "检查模型能力、上下文限制、接口协议与请求参数。",
            "Check the model capabilities, context limit, protocol, and request parameters.",
        ),
        "model_response_error": t(
            "模型未返回有效结构化结果，请更换支持结构化输出的模型或检查接口协议。",
            "The model did not return valid structured output. Use a model that supports it, or check the protocol.",
        ),
        "model_structured_output_error": t(
            "模型未返回有效结构化结果，请更换支持结构化输出的模型或检查接口协议。",
            "The model did not return valid structured output. Use a model that supports it, or check the protocol.",
        ),
        "model_credential_not_allowed": t(
            "服务端智能体使用标准 API 密钥；订阅模型应由官方宿主通过 MCP 调用。",
            "The server agent uses a standard API key. Subscription models should be called by the official host through MCP.",
        ),
    }
    lines = [f"[bold red]{message}[/]"]
    default_hint = hints.get(code)
    selected_hint = " ".join(dict.fromkeys(part for part in (hint, default_hint) if part)) or None
    if selected_hint:
        lines.append(f"\n[yellow]{t('如何修复：', 'How to fix: ')}[/]{selected_hint}")
    if alternatives:
        lines.append(f"\n[yellow]{t('可用替代字段：', 'Alternative fields: ')}[/]{', '.join(alternatives)}")
    console.print(Panel("".join(lines), title=f"[bold red]{t('错误', 'Error')} · {code}[/]", border_style="red"))
