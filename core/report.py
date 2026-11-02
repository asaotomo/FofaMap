"""Deterministic Markdown reports for CLI Agent runs and approved scans."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from core.agent import AgentRun
from core.html_report import _agg_label, _chart_title, _plain_list, _product_columns, write_html_report
from core.scanner import format_nuclei_summary_markdown, load_nuclei_result
from core.usage import run_usage_parts
from utils.cli_ui import normalize_summary_markdown


def _safe(value: Any) -> str:
    return str(value or "").replace("\r", " ").replace("\n", " ").replace("|", "\\|")


def write_agent_report(
    run: AgentRun,
    destination: Path,
    *,
    scan_status: str = "not_requested",
    scan_error: str | None = None,
    language: str = "zh",
) -> Path:
    destination.parent.mkdir(parents=True, exist_ok=True)
    en = language == "en"

    def L(zh: str, english: str) -> str:
        return english if en else zh

    if run.finished_at is None:
        run.finished_at = datetime.now()
    usage = run_usage_parts(run, "en" if en else "zh")
    lines = [
        L("# FofaMap AI 资产侦察报告", "# FofaMap AI asset report"),
        "",
        f"- {L('生成时间：', 'Generated: ')}{datetime.now().astimezone().isoformat(timespec='seconds')}",
        f"- {L('任务开始：', 'Started: ')}{usage['started']}",
        f"- {L('任务耗时：', 'Elapsed: ')}{usage['elapsed']}",
        f"- {L('Token 消耗：', 'Tokens: ')}{usage['tokens']}",
        f"- {L('Run ID：', 'Run ID: ')}`{run.id}`",
        f"- {L('状态：', 'Status: ')}`{run.state.value}`",
        f"- {L('动作：', 'Action: ')}`{run.action.value}`",
        f"- {L('用户需求：', 'Request: ')}{_safe(run.intent)}",
        f"- {L('FOFA 查询：', 'FOFA query: ')}`{_safe(run.query)}`",
        f"- {L('结果数量：', 'Result count: ')}{run.result_count:,}",
    ]
    if run.steps:
        lines.extend(
            [
                "",
                L("## 执行过程", "## What ran"),
                "",
                L("| # | 开始时间 | 阶段 | 说明 |", "| # | Started | Stage | Detail |"),
                "|---|---|---|---|",
            ]
        )
    for index, step in enumerate(run.steps, start=1):
        lines.append(f"| {index} | {step.started_at:%H:%M:%S} | {_safe(step.state.value)} | {_safe(step.detail)} |")
    if run.liveness:
        probe = run.liveness
        lines.extend(["", L("## 存活检测", "## Liveness checks"), ""])
        if probe.get("enabled"):
            lines.extend(
                [
                    f"- {L('检测目标', 'Checked targets')}：{probe.get('checked', 0)}；"
                    f"{L('有响应', 'Responsive')}：{probe.get('responsive', 0)}；"
                    f"{L('未响应', 'No response')}：{probe.get('unresponsive', 0)}；"
                    f"{L('安全策略拦截', 'Blocked')}：{probe.get('blocked', 0)}。",
                    L(
                        "- HTTP 4xx/5xx 仍表示服务有响应；TLS 表示证书校验失败；Open 表示 TCP 连通。未响应不等于资产已下线。",
                        "- HTTP 4xx/5xx is still a response; TLS means certificate verification failed; "
                        "Open means TCP connected. No response does not prove removal.",
                    ),
                ]
            )
        else:
            lines.append(L("本轮未启用存活检测。", "Liveness was not enabled for this run."))
    if run.queries:
        lines.extend(
            [
                "",
                L("## 多维查询策略", "## Query plan"),
                "",
                L(
                    "| # | 来源 | 策略 | 查询目的 | FOFA 查询 | FOFA 总量 | 取样 | 去重新增 |",
                    "| # | Source | Strategy | Purpose | FOFA query | FOFA total | Sample | New |",
                ),
                "|---:|---|---|---|---|---:|---:|---:|",
            ]
        )
        for index, item in enumerate(run.queries, start=1):
            round_no = item.source.rsplit("_", 1)[-1]
            source = {
                "planner": L("首轮规划", "Initial plan"),
                "entity_resolution": L("官网线索", "Official-site lead"),
            }.get(item.source, L(f"动态反思 R{round_no}", f"Reflection R{round_no}"))
            lines.append(
                f"| {index} | {source} | {_safe(item.strategy)} | {_safe(item.purpose)} | `{_safe(item.query)}` | "
                f"{item.available_count if item.available_count is not None else '-'} | {item.result_count:,} | "
                f"{item.new_assets:,} |"
            )
    if run.website_candidates:
        lines.extend(
            [
                "",
                L("## 网站候选清单", "## Website candidates"),
                "",
                L("| 状态 | 域名 | 首选 URL | 证据 |", "| Status | Domain | Preferred URL | Evidence |"),
                "|---|---|---|---|",
            ]
        )
        status_labels = {
            "corroborated": L("交叉印证", "Corroborated"),
            "observed": L("FOFA 已观测", "Seen in FOFA"),
            "candidate": L("待验证", "Unverified"),
        }
        for item in run.website_candidates:
            lines.append(
                f"| {status_labels.get(item.status, item.status)} | `{_safe(item.domain)}` | "
                f"{_safe(item.url)} | {_safe(', '.join(item.evidence))} |"
            )
        lines.extend(
            [
                "",
                L(
                    "> 交叉印证表示 FOFA 中存在多种一致线索，仍不等同于法律或组织归属确认。",
                    "> Corroborated means several FOFA clues agree. It is not legal or organizational confirmation.",
                ),
            ]
        )
    if run.action.value == "host_query" and run.result_data:
        data = run.result_data
        country = _safe(data.get("country_name"))
        code = _safe(data.get("country_code"))
        region = f"{country}（{code}）" if country and code else country or code
        if en and country and code:
            region = f"{country} ({code})"
        lines.extend(
            [
                "",
                L("## 主机聚合画像", "## Host profile"),
                "",
                f"- {L('Host：', 'Host: ')}{_safe(data.get('host') or run.target)}",
                f"- {L('IP：', 'IP: ')}{_safe(data.get('ip'))}",
                f"- {L('ASN：', 'ASN: ')}{_safe(data.get('asn'))}",
                f"- {L('组织：', 'Organization: ')}{_safe(data.get('org'))}",
                f"- {L('国家/地区：', 'Country: ')}{region}",
                f"- {L('更新时间：', 'Updated: ')}{_safe(data.get('update_time'))}",
            ]
        )
        for key, label in (
            ("protocol", L("协议", "Protocols")),
            ("port", L("端口", "Ports")),
            ("category", L("分类", "Categories")),
            ("product", L("组件", "Products")),
        ):
            shown = _plain_list(data.get(key))
            if shown:
                lines.append(f"- {label}{L('：', ': ')}{_safe(shown)}")
        lines.extend(
            ["", L("| 端口 | 协议 | 组件 | 分类 | 等级 |", "| Port | Protocol | Product | Category | Level |"), "|---:|---|---|---|---|"]
        )
        for port in data.get("ports") or []:
            if not isinstance(port, dict):
                continue
            names, categories, levels = _product_columns(port.get("products"))
            lines.append(
                f"| {_safe(port.get('port'))} | {_safe(port.get('protocol'))} | {_safe(names)} | {_safe(categories)} | {_safe(levels)} |"
            )
    elif run.action.value == "stat_query" and run.result_data:
        data = run.result_data
        distinct = data.get("distinct") if isinstance(data.get("distinct"), dict) else {}
        total = data.get("size") if data.get("size") is not None else run.result_count
        lines.extend(["", L("## 统计聚合结果", "## Aggregate statistics"), "", f"- {L('统计总量：', 'Total: ')}{int(total):,}"])
        if distinct.get("ip") is not None:
            lines.append(f"- {L('独立 IP：', 'Distinct IPs: ')}{int(distinct['ip']):,}")
        if distinct.get("ipc") is not None:
            lines.append(f"- {L('独立 C 段：', 'Distinct C-segments: ')}{int(distinct['ipc']):,}")
        if data.get("lastupdatetime"):
            lines.append(f"- {L('数据时间：', 'Data time: ')}{_safe(data.get('lastupdatetime'))}")
        chart_language = "en" if en else "zh"
        for field, rows in (data.get("aggs") or {}).items():
            lines.extend(
                [
                    "",
                    f"### {_chart_title(str(field), chart_language)}",
                    "",
                    L("| # | 值 | 数量 |", "| # | Value | Count |"),
                    "|---:|---|---:|",
                ]
            )
            for index, item in enumerate((rows or [])[:20], start=1):
                if not isinstance(item, dict):
                    continue
                lines.append(f"| {index} | {_safe(_agg_label(item))} | {int(item.get('count') or 0):,} |")
    else:
        lines.extend(["", L("## 查询到的资产候选", "## Asset candidates"), ""])
    if run.action.value not in {"host_query", "stat_query"} and run.assets:
        asset_fields = (run.fields or list(dict.fromkeys(key for asset in run.assets for key in asset)))[:8]
        if run.asset_confidence:
            asset_fields = [*asset_fields, L("归属证据", "Attribution")]
        lines.extend(
            [
                "| # | " + " | ".join(_safe(field) for field in asset_fields) + " |",
                "|---:|" + "|".join("---" for _ in asset_fields) + "|",
            ]
        )
        confidence_labels = {
            "precision": L("高", "High"),
            "balanced": L("中", "Medium"),
            "hypothesis": L("待验证", "Unverified"),
            "recall": L("候选", "Candidate"),
        }
        evidence_field = L("归属证据", "Attribution")
        for index, asset in enumerate(run.assets, start=1):
            values = [
                confidence_labels.get(run.asset_confidence[index - 1], L("候选", "Candidate"))
                if field == evidence_field and index <= len(run.asset_confidence)
                else asset.get(field)
                for field in asset_fields
            ]
            lines.append(f"| {index} | " + " | ".join(_safe(value) for value in values) + " |")
        if run.evidence_counts.get("recall"):
            lines.extend(
                [
                    "",
                    L(
                        f"> {run.evidence_counts['recall']:,} 条仅由召回型语句命中，属于名称/内容相关候选，不等同于已确认归属。",
                        f"> {run.evidence_counts['recall']:,} rows matched only a recall query. "
                        "They are name or content candidates, not confirmed ownership.",
                    ),
                ]
            )
        if run.evidence_counts.get("hypothesis"):
            lines.extend(
                [
                    "",
                    L(
                        f"> {run.evidence_counts['hypothesis']:,} 条来自官网域名假设验证；仅证明候选域名在 FOFA 中存在，"
                        "仍需结合官网内容、备案或权威来源复核归属。",
                        f"> {run.evidence_counts['hypothesis']:,} rows come from an official-domain hypothesis. "
                        "They only show the domain exists in FOFA and still need an independent check.",
                    ),
                ]
            )
        if run.assets_truncated:
            lines.extend(
                [
                    "",
                    L(
                        f"> 仅展示前 {len(run.assets):,} 条；本次查询实际返回 {run.result_count:,} 条。",
                        f"> Showing the first {len(run.assets):,} rows. The query returned {run.result_count:,}.",
                    ),
                ]
            )
    elif run.action.value not in {"host_query", "stat_query"}:
        lines.append(L("未返回可展示资产。", "No assets to show."))
    if run.uses_model_summary():
        lines.extend(["", L("## AI 总结", "## AI summary"), "", normalize_summary_markdown(run.summary), ""])
    elif run.summary_source == "local" and run.action.value in {"host_query", "stat_query"} and run.summary:
        lines.extend(["", L("## 结构化解读", "## Structured interpretation"), "", normalize_summary_markdown(run.summary), ""])
    yes = L("是", "Yes")
    no = L("否", "No")
    if run.shows_scan_decision(scan_error=scan_error):
        lines.extend(["", L("## 扫描决策", "## Scan decision"), ""])
        lines.extend(
            [
                f"- {L('用户是否明确要求扫描：', 'User explicitly requested a scan: ')}{yes if run.scan_requested_by_user else no}",
                f"- {L('AI 是否建议扫描：', 'AI recommended a scan: ')}{yes if run.scan_recommended else no}",
                "- " + L("决策优先级：用户明确指令优先，AI 建议仅供参考。",
                         "Decision priority: explicit user instructions take priority; AI advice is advisory."),
                *([f"- {L('扫描范围：', 'Scan scope: ')}{_safe(run.scan_scope_note)}"] if run.scan_scope_note else []),
                f"- {L('判断理由：', 'Reason: ')}{_safe(run.scan_reason) or '-'}",
                f"- {L('目标数量：', 'Target count: ')}{len(run.scan_targets):,}",
                f"- {L('模板 ID：', 'Template IDs: ')}{', '.join(run.scan_template_ids) or '-'}",
                f"- {L('严重级别：', 'Severities: ')}{', '.join(run.scan_severities)}",
                f"- {L('执行状态：', 'Status: ')}`{scan_status}`",
                f"- {L('扫描产物：', 'Scan artifact: ')}{run.scan_artifact or '-'}",
            ]
        )
        if scan_error:
            lines.append(f"- {L('扫描错误：', 'Scan error: ')}{_safe(scan_error)}")
        if run.scan_selection.get("enabled"):
            audit = run.scan_selection
            lines.extend(["", L("### AI 扫描目标筛选与去重", "### AI scan target selection"), "",
                          f"{audit.get('input_count', 0)} → {audit.get('selected_count', 0)}", "",
                          "| Target | Decision | Reason |", "|---|---|---|"])
            for row in audit.get("decisions", []):
                lines.append(f"| {_safe(row.get('target', ''))} | {_safe(row.get('action', ''))} | {_safe(row.get('reason', ''))} |")
    scan_section = _nuclei_report_section(run.scan_artifact, target_count=len(run.scan_targets), language=language)
    if scan_section:
        lines.extend(["", *scan_section])
    advice = (run.scan_advice or "").strip()
    if advice:
        lines.extend(["", L("## 修复建议", "## Remediation"), "", advice, ""])
    if run.route_events:
        lines.extend(
            [
                "",
                L("## 模型路由与用量", "## Model routing and usage"),
                "",
                L("| 任务 | 提供商 | 模型 | 回退 | 输入 | 输出 |", "| Task | Provider | Model | Fallback | Input | Output |"),
                "|---|---|---|---|---:|---:|",
            ]
        )
    for event in run.route_events:
        lines.append(
            "| {task} | {provider} | {model} | {fallback} | {input} | {output} |".format(
                task=_safe(event.get("task")),
                provider=_safe(event.get("provider")),
                model=_safe(event.get("model")),
                fallback=yes if event.get("fallback") else no,
                input=event.get("input_tokens") or "-",
                output=event.get("output_tokens") or "-",
            )
        )
    lines.extend(
        [
            "",
            L(
                "> FOFA 指纹代表资产暴露信息，不等同于已确认漏洞。Nuclei 结果也应由授权人员复核。",
                "> A FOFA fingerprint is exposure, not a confirmed vulnerability. Nuclei hits still need an authorized review.",
            ),
            "",
        ]
    )
    destination.write_text("\n".join(lines), encoding="utf-8")
    _write_html_editions(run, destination, scan_status=scan_status, scan_error=scan_error, language=language)
    run.report_artifact = str(destination.resolve())
    return destination


def _write_html_editions(
    run: AgentRun,
    destination: Path,
    *,
    scan_status: str,
    scan_error: str | None,
    language: str,
) -> None:
    chinese = destination.with_suffix(".html")
    english = destination.with_name(f"{destination.stem}.en.html")
    if language == "both":
        editions = (("zh", chinese, english.name), ("en", english, chinese.name))
    elif language == "en":
        editions = (("en", chinese, None),)
    else:
        editions = (("zh", chinese, None),)
    for edition, path, alternate in editions:
        write_html_report(
            run,
            path,
            scan_status=scan_status,
            scan_error=scan_error,
            language=edition,
            alternate_href=alternate,
        )


def _nuclei_report_section(artifact: str | None, *, target_count: int, language: str = "zh") -> list[str]:
    if not artifact:
        return []
    path = Path(artifact)
    if path.suffix != ".jsonl" or not path.is_file():
        return []
    try:
        result = load_nuclei_result(path, target_count=target_count)
    except OSError:
        return []
    markdown = format_nuclei_summary_markdown(result)
    body = markdown.splitlines()
    if body and body[0].startswith("# "):
        body[0] = "## Nuclei scan results" if language == "en" else "## Nuclei 扫描结果"
    return body
