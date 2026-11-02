"""Offline schedule dashboard and run history, with all reports kept as relative links."""

# ruff: noqa: E501 - self-contained CSS/SVG/HTML literals retain readable tag boundaries

from __future__ import annotations

import html
import uuid
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING
from urllib.parse import quote
from zoneinfo import ZoneInfo

from config import settings
from core.liveness import resolve_liveness
from utils.datetime_compat import parse_iso_datetime

if TYPE_CHECKING:
    from core.schedules import ScheduleStore


CSS = r"""
:root{--bg:#f4f6fa;--ink:#172639;--muted:#6a788b;--line:#e4eaf1;--blue:#1367e8;--green:#14846e;--navy:#142a43;--shadow:0 8px 30px #1b3b5910}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:14px/1.65 -apple-system,BlinkMacSystemFont,"Segoe UI","PingFang SC","Microsoft YaHei",sans-serif}
a{color:inherit;text-decoration:none}a:focus-visible,button:focus-visible,input:focus-visible,select:focus-visible,summary:focus-visible{outline:3px solid #7bb4ff;outline-offset:4px}
.top{background:var(--navy);color:#fff;border-bottom:1px solid #ffffff18}.top-inner{max-width:1260px;margin:auto;display:flex;align-items:center;justify-content:space-between;padding:18px 32px}
.brand{font-size:18px;font-weight:760;letter-spacing:-.5px}.brand span{color:#7fdbcf}.top-note{color:#aec0d5;font-size:12px}.wrap{max-width:1260px;padding:34px 32px 28px;margin:auto}
.eyebrow{color:var(--blue);font-size:11px;font-weight:750;letter-spacing:2px;margin-bottom:8px}.hero{display:flex;justify-content:space-between;gap:24px;align-items:flex-end;margin:5px 0 26px}
h1{font-size:clamp(25px,3vw,36px);line-height:1.35;letter-spacing:-1px;margin:0 0 12px}h2{font-size:18px;letter-spacing:-.3px;margin:0}h3{font-size:19px;line-height:1.5;margin:0}.lead,.muted{color:var(--muted)}.lead{max-width:820px;margin:0}.stamp{font-size:12px;white-space:nowrap;color:var(--muted)}
.metrics{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:16px;margin:24px 0}.metric{background:white;border:1px solid var(--line);border-radius:14px;padding:20px 22px;box-shadow:var(--shadow)}.metric-label{font-size:12px;color:var(--muted)}.metric-value{font-size:30px;line-height:1.4;font-weight:760;font-variant-numeric:tabular-nums;letter-spacing:-1px;margin:7px 0 2px}.metric-note{font-size:11px;color:var(--muted)}
.toolbar{display:flex;justify-content:space-between;gap:16px;align-items:center;margin:28px 0 16px}.tools{display:flex;gap:10px}input,select{font:inherit;color:var(--ink);border:1px solid #dbe3ec;border-radius:9px;padding:10px 12px;background:#fff}input{width:250px}input::placeholder{color:#8a96a6}.grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:18px}
.card,.panel{background:#fff;border:1px solid var(--line);border-radius:16px;box-shadow:var(--shadow)}.card{padding:23px;display:flex;flex-direction:column;gap:17px;transition:box-shadow .15s,border-color .15s}.card:hover{border-color:#b7cde7;box-shadow:0 10px 35px #1b3b591a}.card-top{display:flex;align-items:flex-start;justify-content:space-between;gap:16px}.card h3 a:hover{color:var(--blue)}.desc{color:var(--muted);font-size:13px;margin:7px 0 0;overflow-wrap:anywhere}.card .desc{display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden;min-height:42px}
.badge{display:inline-flex;align-items:center;gap:6px;white-space:nowrap;padding:4px 9px;border-radius:6px;font-size:11px;font-weight:650;background:#eef3f8;color:#657486}.badge:before{content:"";width:5px;height:5px;border-radius:50%;background:currentColor}.active,.completed{color:#10735c;background:#eaf7f0}.failed{color:#ba3c48;background:#fff0f1}.running{color:#1d67d6;background:#eaf2ff}.paused{color:#9d6b16;background:#fff6e4}.cancelled,.stopped,.deleted{color:#707b8b;background:#f0f2f5}
.card-body{display:grid;grid-template-columns:115px minmax(0,1fr);gap:20px;align-items:center}.asset-count{font-size:34px;font-weight:760;letter-spacing:-1.5px;line-height:1.2;font-variant-numeric:tabular-nums}.overline{font-size:11px;color:var(--muted);margin-bottom:9px}.chart{width:100%;display:block;height:auto}.chart text{font:10px sans-serif;fill:#8592a2}.chart-note{font-size:11px;color:#8592a2;margin-top:4px}.mini-meta{display:flex;gap:8px;flex-wrap:wrap;color:#6b7b8f;font-size:11px}.tag{border:1px solid var(--line);border-radius:5px;padding:3px 7px;background:#fbfcfe}
.next{display:flex;justify-content:space-between;gap:12px;font-size:12px;color:var(--muted);padding-top:14px;border-top:1px solid var(--line)}.next strong{color:var(--ink);font-weight:560;font-variant-numeric:tabular-nums}.card-actions{display:flex;justify-content:space-between;align-items:center;gap:12px}.link{color:var(--blue);font-weight:620;font-size:12px}.btn{display:inline-flex;align-items:center;justify-content:center;border:1px solid #dce5f0;background:#fff;border-radius:7px;padding:6px 10px;font-size:11px;font-weight:620;color:#526982;white-space:nowrap}.btn:hover{border-color:#96bdf2;background:#f1f7ff}.primary{color:#fff;background:var(--blue);border-color:var(--blue)}.primary:hover{color:#fff;background:#0755ca}.downloads{display:flex;gap:6px;flex-wrap:wrap}.small{font-size:11px}
.panel{padding:23px;margin-top:20px}.panel-heading{display:flex;justify-content:space-between;align-items:center;gap:14px;margin-bottom:20px}.panel-heading p{margin:4px 0 0;font-size:12px;color:var(--muted)}.big-chart{max-width:1100px;margin:auto}.context{display:flex;gap:8px;flex-wrap:wrap;margin:18px 0}.breadcrumbs{font-size:12px;color:var(--muted);margin-bottom:25px}.breadcrumbs a{color:var(--blue)}
.table-scroll{overflow:auto;margin:0 -3px}table{width:100%;border-collapse:collapse;white-space:nowrap}th{text-align:left;font-size:11px;font-weight:650;color:#73839a;padding:12px 14px;background:#f7f9fc;border-top:1px solid var(--line);border-bottom:1px solid var(--line)}td{padding:17px 14px;border-bottom:1px solid #edf1f6;font-size:12px;vertical-align:middle}tbody tr:last-child td{border-bottom:0}tbody tr:hover{background:#fafcff}.date{font-weight:590;font-variant-numeric:tabular-nums}.subline{font-size:10px;color:#8a97a7;margin-top:4px}.number{font-size:15px;font-weight:700;font-variant-numeric:tabular-nums}.delta{display:inline-flex;gap:9px;font-variant-numeric:tabular-nums}.plus{color:#14846e}.minus{color:#d46c52}.changed{color:#4f76bd}.warning{color:#a97a27;font-size:10px;margin-top:4px}.error-detail{max-width:300px;white-space:normal;color:#b74a54;overflow-wrap:anywhere;font-size:11px}.empty{border:1px dashed #cfdae7;border-radius:14px;text-align:center;padding:42px;color:var(--muted);grid-column:1/-1}.empty strong{display:block;color:#405773;margin-bottom:6px}.foot{display:flex;justify-content:space-between;gap:20px;align-items:flex-start;color:#8a96a7;font-size:11px;margin:28px 0 4px;padding-top:18px;border-top:1px solid #dfe7f0}.foot a{color:#4a769f}.archive{margin-top:28px}.archive summary{cursor:pointer;color:#61728a;font-size:13px;font-weight:650;padding:12px 0}.archive .grid{margin-top:10px}.archive .card{background:#fafbfd}.notice{border-left:3px solid #8aaee2;background:#edf4ff;color:#4f6d91;padding:11px 14px;font-size:12px;border-radius:5px;margin:16px 0}.hidden,[hidden]{display:none!important}.print-only{display:none}
@media(max-width:900px){.grid{grid-template-columns:1fr}.hero{align-items:flex-start;flex-direction:column;gap:8px}.metric{padding:16px}.metrics{gap:10px}.metric-value{font-size:26px}.toolbar{align-items:flex-start}.tools{flex-wrap:wrap}input{width:200px}}
@media(max-width:600px){.wrap{padding:24px 16px}.top-inner{padding:15px 16px}.top-note{display:none}.metrics{grid-template-columns:repeat(2,minmax(0,1fr))}.hero h1{font-size:25px}.toolbar{flex-direction:column;gap:10px}.tools{width:100%}input{flex:1;min-width:120px}.panel,.card{padding:18px}.card-body{grid-template-columns:94px minmax(0,1fr);gap:12px}.card h3{font-size:17px}.asset-count{font-size:30px}.next{flex-direction:column;gap:3px}.foot{flex-direction:column;gap:7px}.card-actions{flex-wrap:wrap}.panel-heading{align-items:flex-start;flex-direction:column}.stamp{white-space:normal}}
@media print{.top{background:#fff;color:#172639}.tools,.archive summary{display:none}.wrap{max-width:none;padding:12px}.card,.panel,.metric{box-shadow:none;break-inside:avoid}.grid{display:block}.card{margin-bottom:14px}.foot{font-size:9px}.table-scroll{overflow:visible}table{white-space:normal}}
"""
SCRIPT = r"""
(()=>{const q=document.querySelector('[data-search]'),s=document.querySelector('[data-state]');
function filter(){const text=(q?.value||'').trim().toLocaleLowerCase(),state=s?.value||'';
let visible=0;for(const card of document.querySelectorAll('[data-task-card]')){card.hidden=!(card.dataset.search.includes(text)&&(!state||card.dataset.state===state));if(!card.hidden)visible++;}
const empty=document.querySelector('[data-filter-empty]');if(empty)empty.hidden=visible>0||(!text&&!state);
const archive=document.querySelector('.archive');if(archive&&(text||state==='deleted'))archive.open=true;}
q?.addEventListener('input',filter);s?.addEventListener('change',filter);})();
"""
STATE = {
    "active": "启用",
    "paused": "暂停",
    "stopped": "停止",
    "deleted": "已删除",
    "completed": "已完成",
    "failed": "失败",
    "running": "执行中",
    "cancelled": "已取消",
}


def esc(value) -> str:
    return html.escape(str(value), quote=True)


def badge(state: str) -> str:
    key = state if state in STATE else "unknown"
    return f'<span class="badge {key}">{esc(STATE.get(state, state))}</span>'


def metric(label, value, note):
    return f'<div class="metric"><div class="metric-label">{esc(label)}</div><div class="metric-value">{esc(value)}</div><div class="metric-note">{esc(note)}</div></div>'


def document(title: str, body: str) -> str:
    return (
        '<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
        f"<title>{esc(title)}</title><style>{CSS}</style></head><body>"
        '<header class="top"><div class="top-inner"><a class="brand" href="https://hx0studio.com/">Fofa<span>Map</span>'
        '</a><span class="top-note">ASSET OBSERVATORY &nbsp; / &nbsp; 计划任务报告</span></div></header>'
        f'<main class="wrap">{body}<footer class="foot"><span>FOFA 索引变化不等于服务实时上下线。存活结果仅代表该轮探测。</span>'
        '<a href="https://hx0studio.com/">Hx0 Studio ↗</a></footer></main>'
        f"<script>{SCRIPT}</script></body></html>"
    )


def write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(f".index-{uuid.uuid4()}.tmp")
    temp.write_text(content, encoding="utf-8")
    temp.replace(path)


def chart(runs: list[dict], zone: ZoneInfo, *, large: bool = False) -> str:
    records = [r for r in reversed(runs) if r["status"] == "completed" and r.get("result") and r["result"].get("count") is not None][-30:]
    if not records:
        return (
            '<div class="empty"><strong>等待首份快照</strong>完成测绘后展示数量趋势</div>'
            if large
            else '<div class="chart-note">完成首轮后生成趋势</div>'
        )
    values = [int(r["result"]["count"]) for r in records]
    width, height, pad = (1040, 240, 38) if large else (320, 94, 12)
    chart_top, chart_bottom = 12, height - (32 if large else 18)
    low, high = min(values), max(values)
    spread = max(1, high - low)
    lower = max(0, low - spread * 0.25)
    upper = high + spread * 0.25

    def x(index):
        return pad + (width - 2 * pad) * (index / max(1, len(values) - 1)) if len(values) > 1 else width / 2

    def y(value):
        return chart_bottom - (value - lower) / max(1, upper - lower) * (chart_bottom - chart_top)

    coords = [(x(i), y(v)) for i, v in enumerate(values)]
    points = " ".join(f"{a:.1f},{b:.1f}" for a, b in coords)
    grid = "".join(
        f'<line x1="{pad}" y1="{chart_top + (chart_bottom - chart_top) * i / 2:.1f}" x2="{width - pad}" y2="{chart_top + (chart_bottom - chart_top) * i / 2:.1f}" stroke="#e9eef5" stroke-dasharray="3 5"/>'
        for i in range(3)
    )
    area = (
        f'<polygon points="{coords[0][0]:.1f},{chart_bottom} {points} {coords[-1][0]:.1f},{chart_bottom}" fill="#eaf2ff"/>'
        if len(values) > 1
        else ""
    )
    labels = ""
    if large:
        for i in sorted({0, len(values) // 2, len(values) - 1}):
            at = parse_iso_datetime(records[i]["finished_at"]).astimezone(zone).strftime("%m-%d %H:%M")
            labels += f'<text x="{x(i):.1f}" y="{height - 6}" text-anchor="middle">{esc(at)}</text>'
        labels += f'<text x="{pad}" y="{chart_top + 9}">{max(values):,} 条</text>'
    circles = "".join(
        f'<circle cx="{a:.1f}" cy="{b:.1f}" r="{3 if large else 2.8}" fill="#1367e8"><title>{esc(parse_iso_datetime(records[i]["finished_at"]).astimezone(zone).strftime("%Y-%m-%d %H:%M:%S"))} · {values[i]:,} 条</title></circle>'
        for i, (a, b) in enumerate(coords)
    )
    return (
        f'<svg class="chart" viewBox="0 0 {width} {height}" role="img" aria-label="历史资产数量趋势">'
        f"<title>最近 {len(values)} 期资产数量："
        + ", ".join(map(str, values))
        + f"</title>{grid}{area}"
        + (
            f'<polyline points="{points}" fill="none" stroke="#1367e8" stroke-width="2.4" stroke-linejoin="round"/>'
            if len(values) > 1
            else ""
        )
        + circles
        + labels
        + "</svg>"
        + f'<div class="chart-note">最近 {len(values)} 期 · '
        + ("首期快照，等待后续对比" if len(values) == 1 else f"{min(values):,}–{max(values):,} 条；完整口径见每期报告")
        + "</div>"
    )


def links(result: dict, task_root: Path, *, prefix: str = "") -> str:
    buttons = []
    for key, label in [("html", "HTML 报告"), ("markdown", "MD"), ("json", "JSON")]:
        filename = result.get("reports", {}).get(key)
        if not filename:
            continue
        try:
            relative = Path(filename).resolve().relative_to(task_root.resolve())
        except ValueError:
            continue
        css = "btn primary" if key == "html" else "btn"
        buttons.append(f'<a class="{css}" href="{prefix}{quote(relative.as_posix())}">{label}</a>')
    return '<div class="downloads">' + "".join(buttons) + "</div>" if buttons else '<span class="muted small">暂无报告</span>'


def delta(result: dict) -> str:
    changes = result.get("changes")
    if result.get("baseline"):
        return '<span class="muted">首次基线</span>'
    if not changes:
        return '<span class="muted">—</span>'
    content = (
        f'<span class="delta"><span class="plus">+{int(changes.get("added", 0)):,}</span>'
        f'<span class="minus">−{int(changes.get("removed", 0)):,}</span><span class="changed">Δ{int(changes.get("changed", 0)):,}</span></span>'
    )
    if result.get("comparable") is not True:
        content += '<div class="warning">查询范围或取回窗口不同，仅供参考</div>'
    return content


def liveness(result: dict) -> str:
    probe = result.get("liveness") or {}
    if not probe.get("enabled"):
        return '<span class="muted">未检测</span>'
    return f'<strong>{int(probe.get("responsive", 0)):,}</strong><span class="muted"> / {int(probe.get("checked", 0)):,} 有响应</span>'


def write_index(store: ScheduleStore, root: Path) -> Path:
    from core.schedules import ScheduleRequest, timing_label

    root.mkdir(parents=True, exist_ok=True)
    schedules = store.list(include_deleted=True)
    cards, archives = [], []
    total_runs = 0
    success_runs = 0
    latest_sum = 0
    active_count = 0
    for item in schedules:
        spec = ScheduleRequest.model_validate(item["spec"])
        zone = ZoneInfo(spec.timing.timezone)
        task_root = root / item["id"]
        runs = store.runs(item["id"], 365)
        successful = [r for r in runs if r["status"] == "completed" and r.get("result")]
        latest = runs[0] if runs else {}
        last_good = successful[0] if successful else {}
        result = last_good.get("result") or {}

        def at(value, zone=zone):
            return parse_iso_datetime(value).astimezone(zone).strftime("%Y-%m-%d %H:%M:%S") if value else "—"

        count = result.get("count")
        count_label = f"{count:,}" if isinstance(count, int) else "—"
        enabled, reason = resolve_liveness(spec.task, spec.check_alive, settings.fast_check.check_alive)
        alive_label = "存活检测：开启" if enabled else "存活检测：关闭"
        if reason == "global_default":
            alive_label += "（默认）"
        tags = f'<span class="tag">{esc(timing_label(spec.timing))}</span><span class="tag">{esc(spec.timing.timezone)}</span><span class="tag">{esc(alive_label)}</span>'
        next_at = at(item.get("next_run")) if item["enabled"] else "—"
        all_rows = []
        for row in runs:
            data = row.get("result") or {}
            num = data.get("count")
            number = f"{num:,}" if isinstance(num, int) else "—"
            duration = "—"
            if row.get("finished_at"):
                seconds = max(0, round((parse_iso_datetime(row["finished_at"]) - parse_iso_datetime(row["started_at"])).total_seconds()))
                duration = f"{seconds // 60}分{seconds % 60}秒" if seconds >= 60 else f"{seconds}秒"
            action = links(data, task_root)
            if row.get("error"):
                action = f'<div class="error-detail">{esc(row["error"])}</div>'
            elif row["status"] == "running":
                action = '<span class="muted">报告生成后可查看</span>'
            all_rows.append(
                f'<tr><td><div class="date">{esc(at(row["started_at"]))}</div><div class="subline">{esc(row["id"][:8])}</div></td>'
                f'<td>{badge(row["status"])}</td><td><span class="number">{number}</span></td><td>{delta(data)}</td>'
                f'<td>{liveness(data)}</td><td class="muted">{duration}</td><td>{action}</td></tr>'
            )
        total = len(runs)
        done = len(successful)
        task_metrics = metric("最近成功资产数", count_label, "FOFA 索引记录，按端点去重") + metric(
            "累计执行", f"{total:,}", f"已完成 {done:,} 期 · 历史最多展示 365 期"
        )
        if result.get("liveness", {}).get("enabled"):
            probe = result["liveness"]
            task_metrics += metric(
                "最近存活检测", f"{probe.get('responsive', 0):,}", f"已检测 {probe.get('checked', 0):,} 个目标；有响应数量"
            )
        else:
            task_metrics += metric("最近存活检测", "—", "最近成功轮次未启用检测")
        task_metrics += metric("当前周期", timing_label(spec.timing), spec.timing.timezone)
        title = spec.name
        notice = '<div class="notice">此任务已删除，不再调度；历史报告与执行记录保留。</div>' if item["deleted_at"] else ""
        task_body = (
            '<nav class="breadcrumbs"><a href="../index.html">← 返回报告总目录</a> &nbsp; / &nbsp; 任务历史</nav>'
            f'<div class="hero"><div><div class="eyebrow">TASK HISTORY</div><h1>{esc(title)}</h1><p class="lead">{esc(spec.task)}</p>'
            f'<div class="context">{badge(item["control_status"])}{tags}</div></div></div>{notice}<div class="metrics">{task_metrics}</div>'
            '<section class="panel"><div class="panel-heading"><div><h2>资产数量趋势</h2><p>最近 30 期成功快照；每一期均可追溯至独立报告。</p></div>'
            f'<span class="small muted">下次执行：{esc(next_at)}</span></div><div class="big-chart">{chart(runs, zone, large=True)}</div></section>'
            '<section class="panel"><div class="panel-heading"><div><h2>执行历史</h2><p>新增 + · 减少 − · 字段变化 Δ；存活探测变化单独记录。</p></div>'
            f'<span class="small muted">时间均为 {esc(spec.timing.timezone)}</span></div><div class="table-scroll"><table>'
            "<thead><tr><th>执行时间</th><th>状态</th><th>资产数</th><th>快照差异</th><th>存活检测</th><th>耗时</th><th>报告</th></tr></thead><tbody>"
            + (
                "".join(all_rows)
                if all_rows
                else '<tr><td colspan="7"><div class="empty"><strong>任务已就绪，等待首次执行</strong>首份报告生成后会显示在这里。</div></td></tr>'
            )
            + "</tbody></table></div></section>"
        )
        write(task_root / "index.html", document(title, task_body))
        card = (
            f'<article class="card" data-task-card data-state="{esc(item["control_status"])}" data-search="{esc((spec.name + " " + spec.task).lower())}">'
            f'<div class="card-top"><div><div class="overline">任务 {esc(item["id"][:8])}</div><h3><a href="{item["id"]}/index.html">{esc(title)}</a></h3></div>{badge(item["control_status"])}</div>'
            f'<p class="desc">{esc(spec.task)}</p><div class="card-body"><div><div class="overline">最近成功资产数</div><div class="asset-count">{count_label}</div>'
            f'<div class="chart-note">{done} 期成功快照</div></div><div>{chart(runs, zone)}</div></div><div class="mini-meta">{tags}</div>'
            f'<div class="next"><span>下次执行 <strong>{esc(next_at)}</strong></span><span>最近 {badge(latest.get("status", "待执行"))}</span></div>'
            f'<div class="card-actions"><a class="link" href="{item["id"]}/index.html">查看执行历史 →</a>{links(result, task_root, prefix=item["id"] + "/")}</div></article>'
        )
        (archives if item["deleted_at"] else cards).append(card)
        if not item["deleted_at"]:
            total_runs += len(runs)
            success_runs += len(successful)
            latest_sum += int(count or 0)
            active_count += int(bool(item["enabled"]))
    summary = (
        metric("管理中的任务", f"{len(cards):,}", f"其中 {active_count:,} 个已启用")
        + metric("成功执行", f"{success_runs:,}", f"共 {total_runs:,} 次执行记录")
        + metric("最近快照记录", f"{latest_sum:,}", "各任务最近成功记录之和，跨任务未去重")
        + metric("历史归档", f"{len(archives):,}", "已删除任务的报告仍可追溯")
    )
    stamp = datetime.now(ZoneInfo("Asia/Shanghai")).strftime("%Y-%m-%d %H:%M:%S")
    body = (
        '<div class="hero"><div><div class="eyebrow">SCHEDULED INTELLIGENCE</div><h1>计划任务报告总目录</h1>'
        '<p class="lead">追踪每轮测绘、资产变化与存活结果。所有报告按任务归档，随执行自动更新。</p></div>'
        f'<div class="stamp">目录更新 {stamp} · 上海时间</div></div><div class="metrics">{summary}</div>'
        '<div class="toolbar"><h2>任务概览</h2><div class="tools"><input data-search type="search" placeholder="搜索任务名称或需求" aria-label="搜索任务">'
        '<select data-state aria-label="筛选任务状态"><option value="">全部状态</option><option value="active">启用</option><option value="paused">暂停</option><option value="stopped">停止</option><option value="deleted">已删除</option></select></div></div>'
        '<div class="grid">'
        + (
            "".join(cards)
            if cards
            else '<div class="empty"><strong>暂无计划任务。</strong>在 FofaMap 主菜单的「计划任务」中创建任务。</div>'
        )
        + '</div><div class="empty" data-filter-empty hidden><strong>没有匹配的任务</strong>请调整搜索词或状态筛选。</div>'
        + (
            f'<details class="archive"><summary>已删除任务的历史报告 · {len(archives)} 个归档</summary><div class="grid">'
            + "".join(archives)
            + "</div></details>"
            if archives
            else ""
        )
    )
    write(root / "index.html", document("FofaMap 计划任务报告总目录", body))
    return root / "index.html"
