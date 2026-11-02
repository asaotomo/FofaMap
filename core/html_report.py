"""Self-contained HTML atlas for an Agent reconnaissance run."""

from __future__ import annotations

import base64
import html
import math
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from core.agent import AgentRun
from core.report_interactions import TABLE_INTERACTIONS
from core.usage import run_usage_parts
from core.version import VERSION

_STUDIO_URL = "https://hx0studio.com/"
_GITHUB_URL = "https://github.com/asaotomo/FofaMap"
_PALETTE = ("#0071e3", "#5e5ce6", "#30b0c7", "#34c759", "#ff9f0a", "#ff375f", "#ac8e68", "#64d2ff")
_METRIC_COLORS = ("#0071e3", "#5e5ce6", "#30b0c7", "#ff9f0a", "#34c759", "#ff375f")

_CONFIDENCE = {
    "zh": {
        "precision": ("高", "high"),
        "balanced": ("中", "mid"),
        "hypothesis": ("待验证", "watch"),
        "recall": ("候选", "low"),
    },
    "en": {
        "precision": ("High", "high"),
        "balanced": ("Medium", "mid"),
        "hypothesis": ("Unverified", "watch"),
        "recall": ("Candidate", "low"),
    },
}
_STATE = {
    "zh": {
        "completed": "已完成",
        "failed": "未完成",
        "intent_parsing": "需求解析",
        "query_validation": "语法校验",
        "execute": "资产查询",
        "evaluate": "结果评估",
        "reflect": "动态反思",
        "query_repair": "语句修正",
        "summarize": "生成总结",
    },
    "en": {
        "completed": "Completed",
        "failed": "Incomplete",
        "intent_parsing": "Intent",
        "query_validation": "Validation",
        "execute": "Search",
        "evaluate": "Evaluation",
        "reflect": "Reflection",
        "query_repair": "Repair",
        "summarize": "Summary",
    },
}
_ACTION = {
    "zh": {"fofa_search": "资产检索", "host_query": "主机画像", "stat_query": "统计聚合", "icon_query": "图标检索"},
    "en": {"fofa_search": "Asset search", "host_query": "Host profile", "stat_query": "Statistics", "icon_query": "Icon search"},
}
_STRATEGY = {
    "zh": {"precision": "精准", "balanced": "均衡", "recall": "召回", "hypothesis": "假设"},
    "en": {"precision": "Precision", "balanced": "Balanced", "recall": "Recall", "hypothesis": "Hypothesis"},
}
_FIELDS = {
    "zh": {
        "host": "主机",
        "protocol": "协议",
        "ip": "IP",
        "port": "端口",
        "title": "标题",
        "server": "服务器",
        "product": "产品",
        "domain": "域名",
        "org": "组织",
        "icp": "备案",
        "country": "国家",
        "city": "城市",
        "region": "地区",
        "as": "ASN",
        "os": "系统",
    },
    "en": {
        "host": "Host",
        "protocol": "Protocol",
        "ip": "IP",
        "port": "Port",
        "title": "Title",
        "server": "Server",
        "product": "Product",
        "domain": "Domain",
        "org": "Organization",
        "icp": "ICP",
        "country": "Country",
        "city": "City",
        "region": "Region",
        "as": "ASN",
        "os": "OS",
    },
}
_SOURCE = {
    "zh": {"planner": "首轮规划", "entity_resolution": "官网线索", "php2shell": "暴露面补齐", "host": "宿主规划"},
    "en": {"planner": "Initial plan", "entity_resolution": "Site lead", "php2shell": "Exposure fill", "host": "Host plan"},
}
_SCAN = {
    "zh": {
        "not_requested": "未请求扫描",
        "recommendation_only_no_user_authorization": "仅有建议，尚未授权",
        "declined": "审批未通过",
        "cancelled": "用户停止扫描，结果不完整",
        "no_targets_after_selection": "筛选后无待扫描目标",
        "report_only": "仅生成报告，未扫描",
        "completed": "已执行",
        "blocked_by_agent_error": "因侦察失败而停止",
        "user_requested_agent_not_recommended": "用户要求，模型未推荐",
        "not_recommended_by_agent": "模型不建议扫描",
        "incomplete_or_empty_scan_plan": "扫描方案不完整",
    },
    "en": {
        "not_requested": "Scan not requested",
        "recommendation_only_no_user_authorization": "Recommended only, not authorized",
        "declined": "Approval declined",
        "cancelled": "Cancelled; partial scan only",
        "no_targets_after_selection": "No targets after selection",
        "report_only": "Report only; scan not executed",
        "completed": "Executed",
        "blocked_by_agent_error": "Stopped after reconnaissance failed",
        "user_requested_agent_not_recommended": "Requested by user, not recommended",
        "not_recommended_by_agent": "Model does not recommend a scan",
        "incomplete_or_empty_scan_plan": "Scan plan incomplete",
    },
}
_COPY = {
    "zh": {
        "html_lang": "zh-CN",
        "title": "FofaMap 测绘报告",
        "skip": "跳到报告正文",
        "nav": "报告目录",
        "overview": "概览",
        "charts": "图表",
        "analysis": "分析",
        "queries": "查询",
        "assets": "资产",
        "decision": "决策",
        "nav_meta": "安全报告",
        "studio": "Hx0 工作室",
        "slogan": "探索无极限",
        "logo_alt": "Hx0工作室 探索无极限",
        "export": "导出 CSV",
        "scope": "范围",
        "lang_switch": "EN",
        "eyebrow": "FofaMap 安全报告",
        "untitled": "未命名侦察任务",
        "no_model": "未接入模型。以下只呈现测绘事实。",
        "model_wrote": "分析由 {provider} {model} 撰写。",
        "lede": "结论只描述暴露面，指纹、标题和备案都不能单独证明漏洞存在。",
        "assets_unit": "项资产",
        "strategies_unit": "条策略",
        "primary": "主查询",
        "no_query": "无主查询",
        "sample": "样本资产",
        "sample_note": "本报告可逐条检视",
        "pulled": "取回资产",
        "pulled_note": "本次全部取回的记录",
        "domains": "域名",
        "domains_note": "去重后的域名",
        "ips": "IP",
        "ips_note": "去重后的地址",
        "largest": "最大语句规模",
        "largest_note": "单条查询在 FOFA 中的可见量",
        "high": "高置信",
        "high_note": "精准策略命中",
        "watch": "候选",
        "watch_note": "需要交叉验证",
        "evidence": "证据构成",
        "charts_title": "抽样分布",
        "charts_note": "以下图形只统计本次抽回的样本，不是该语句的全量分布。",
        "charts_full": "结果分布",
        "charts_full_note": "图形按本次全部取回的记录统计，并覆盖所选返回字段。",
        "charts_partial_note": "图形按本次全部取回的记录统计。主查询可见规模更大时，不能把取回部分写成该语句的全量分布。",
        "findings_h": "结果结论",
        "coverage_h": "抽样说明",
        "coverage_range_h": "结果范围",
        "coverage_full_body": "主查询可见 {visible}。本次取回 {pulled}。可见结果已全部纳入，结论按全部取回记录书写。",
        "coverage_stop_cap": "已达到本次取回上限，没有继续翻页。",
        "coverage_partial_limit": "图表和结论只统计取回记录，不能代表该语句的全量资产。",
        "coverage_visible": "主查询可见规模",
        "coverage_sampled": "本次抽查",
        "coverage_stop_user": "已达到本次抽样上限，没有继续翻页。",
        "coverage_stop_page": "分页窗口已用尽，可见结果没有抽完。",
        "coverage_stop_done": "可见结果已纳入本次样本。",
        "coverage_limit": "抽样只用于查看资产形态，不能代表该语句的全量资产。",
        "population_title": "总体分布",
        "population_note": "来自 FOFA 对主查询的统计，不是下面的抽样表。产品字段不能聚合，产品分布仍以抽样为准。",
        "population_note_full": "来自 FOFA 对主查询的统计，描述该语句的可见结果。产品字段不能聚合。",
        "query_chart": "语句可见量",
        "product_chart": "产品分布",
        "port_chart": "端口分布",
        "token_chart": "模型用量",
        "unknown": "未识别",
        "other": "其他",
        "analysis_title": "智能分析、点评与建议",
        "analysis_h": "分析",
        "review_h": "点评",
        "advice_h": "建议",
        "analysis_empty": "模型没有单独写出结论。",
        "review_empty": "模型没有按证据分列点评。",
        "advice_empty": "模型没有单独给出处置建议。",
        "analysis_fine": "以上文字来自已接入模型，只解释本次返回的测绘样本。指纹、标题和备案都不能单独证明漏洞存在。",
        "analysis_fine_full": "以上文字来自已接入模型，解释本次全部取回的记录。指纹、标题和备案都不能单独证明漏洞存在。",
        "brief": "测绘简报",
        "brief_note": "本次没有模型路由记录，下面是程序根据命中整理的简报。",
        "no_model_title": "分析",
        "no_model_note": "未接入可用模型",
        "no_model_body": "本次没有模型分析、点评或建议。下面各节只收录查询、资产、证据和扫描决策。",
        "query_title": "查询策略",
        "query_note": "{count} 条已执行语句。总量是 FOFA 可见规模，取样是本次实际拉回的记录。",
        "query_note_full": "{count} 条已执行语句。总量是 FOFA 可见规模，取回是本次实际拉回的记录。",
        "th_pulled": "取回",
        "th_source": "来源",
        "th_strategy": "策略",
        "th_purpose": "目的",
        "th_query": "语句",
        "th_visible": "可见量",
        "th_sample": "取样",
        "th_new": "新增",
        "reflect": "动态反思",
        "asset_title": "资产样本",
        "asset_note": "共 {count} 条进入本页。筛选只作用于这张表。",
        "asset_full": "资产清单",
        "asset_full_note": "共 {count} 条进入本页。筛选只作用于这张表。",
        "asset_empty": "未返回可展示资产。",
        "filter": "筛选",
        "filter_ph": "主机、标题、产品、端口",
        "evidence_col": "证据",
        "record": "记录",
        "truncated": "表内为前 {shown} 条样本，本次计数为 {total}。",
        "truncated_full": "表内为前 {shown} 条，分布和结论按全部取回的 {total} 条统计。",
        "showing": "显示",
        "rows": "条",
        "sites": "网站候选",
        "sites_note": "交叉印证表示多条 FOFA 线索一致，仍然不是法律或组织归属结论。",
        "status": "状态",
        "url": "URL",
        "confidence": "置信",
        "evidence_col2": "证据",
        "site_status": {"corroborated": "交叉印证", "observed": "已观测", "candidate": "待验证"},
        "host_title": "主机画像",
        "org": "组织",
        "region": "地域",
        "country": "国家/地区",
        "asn": "ASN",
        "category": "分类",
        "level": "等级",
        "missing": "未返回",
        "port": "端口",
        "protocol": "协议",
        "product": "产品",
        "updated": "更新时间",
        "stats_title": "统计聚合",
        "stats_total": "总量",
        "distinct_ip": "独立 IP",
        "distinct_ipc": "独立 C 段",
        "data_time": "数据时间",
        "value": "值",
        "count": "数量",
        "scan_title": "扫描决策",
        "findings_title": "漏洞扫描结果",
        "findings_empty": "已执行扫描，未发现命中。",
        "findings_note": "命中来自已授权的 Nuclei 扫描，仍需人工复核，不能单独写成已确认漏洞。",
        "fix_h": "修复建议",
        "th_sev": "严重级别",
        "th_site": "站点",
        "th_check": "检测项",
        "th_detail": "命中详情",
        "user_scan": "用户要求扫描",
        "model_scan": "模型建议扫描",
        "targets": "候选目标",
        "templates": "模板",
        "severity": "严重级别",
        "artifact": "产物",
        "yes": "是",
        "no": "否",
        "none": "无",
        "no_reason": "没有额外判断理由。",
        "started": "任务开始",
        "elapsed": "任务耗时",
        "tokens": "Token 消耗",
        "models_title": "模型路由",
        "models_note": "只记录本次任务实际调用的提供商和用量。",
        "models_empty": "本次没有模型调用记录。",
        "task": "任务",
        "provider": "提供商",
        "model": "模型",
        "fallback": "回退",
        "input": "输入",
        "output": "输出",
        "timeline": "执行过程",
        "steps": "步",
        "disclaimer": "FOFA 指纹表示暴露面，不等同于已确认漏洞。扫描结果需要授权人员复核。",
        "studio_line": f"本报告由 FofaMap V{VERSION} 生成。",
        "site_label": "官网",
        "github_label": "GitHub",
        "scope_title": "范围与读法",
        "scope_note": "先确认样本边界和证据等级，再读后面的模型简报。",
        "scope_note_full": "先看结果范围和证据等级，再读后面的模型结论。",
        "range_h": "本次范围",
        "fields_label": "返回字段",
        "sample_vs": "样本 / 计数",
        "listed_vs": "表内 / 取回",
        "visible_label": "最大可见量",
        "legend_h": "证据等级",
        "legend_precision": "精准：条件更收敛，适合优先复核。",
        "legend_balanced": "均衡：覆盖和噪声居中，需结合证书与备案。",
        "legend_hypothesis": "假设：线索还没有闭合。",
        "legend_recall": "召回：覆盖更宽，误报也更多。",
        "priority_h": "优先查看",
        "priority_empty": "本次没有可点名的资产样本。",
        "boundary_h": "处置边界",
        "boundary_body": "指纹、标题和备案只说明暴露面，不能单独写成已确认漏洞。需要验证时，应另行审批目标、模板和严重级别。",
        "lead": "本页样本 {sample} 条，任务计数 {count}。产品较集中的是 {products}。高置信 {high} 条，待交叉验证 {watch} 条。",
        "lead_plain": "本页样本 {sample} 条，任务计数 {count}。高置信 {high} 条，待交叉验证 {watch} 条。",
        "lead_full": "本次取回 {count} 条，已覆盖主查询可见结果。产品较集中的是 {products}。高置信 {high} 条，待交叉验证 {watch} 条。",
        "lead_full_plain": "本次取回 {count} 条，已覆盖主查询可见结果。高置信 {high} 条，待交叉验证 {watch} 条。",
        "lead_partial": "本次取回 {count} 条。产品较集中的是 {products}。高置信 {high} 条，待交叉验证 {watch} 条。",
        "lead_partial_plain": "本次取回 {count} 条。高置信 {high} 条，待交叉验证 {watch} 条。",
        "alive_note": "证书可达表示服务有响应但证书不受信，端口开放表示 TCP 连通。二者都不是已确认漏洞。",
    },
    "en": {
        "html_lang": "en",
        "title": "FofaMap asset report",
        "skip": "Skip to report",
        "nav": "Report",
        "overview": "Overview",
        "charts": "Charts",
        "analysis": "Analysis",
        "queries": "Queries",
        "assets": "Assets",
        "decision": "Decision",
        "nav_meta": "Security report",
        "studio": "Hx0 Studio",
        "slogan": "探索无极限",
        "logo_alt": "Hx0 Studio",
        "export": "Export CSV",
        "scope": "Scope",
        "lang_switch": "中文",
        "eyebrow": "FofaMap security report",
        "untitled": "Untitled reconnaissance",
        "no_model": "No model was connected. The sections below are observed facts only.",
        "model_wrote": "Briefing written by {provider} {model}.",
        "lede": "Findings describe exposure only. A fingerprint, title, or ICP filing does not by itself prove a vulnerability.",
        "assets_unit": "assets",
        "strategies_unit": "strategies",
        "primary": "Primary query",
        "no_query": "No primary query",
        "sample": "Sample assets",
        "sample_note": "Inspectable in this report",
        "pulled": "Retrieved assets",
        "pulled_note": "Every row retrieved for this run",
        "domains": "Domains",
        "domains_note": "Distinct domains",
        "ips": "IPs",
        "ips_note": "Distinct addresses",
        "largest": "Largest query",
        "largest_note": "Visible FOFA count of one query",
        "high": "High confidence",
        "high_note": "Precision hits",
        "watch": "Candidates",
        "watch_note": "Need corroboration",
        "evidence": "Evidence mix",
        "charts_title": "Sample distribution",
        "charts_note": "These charts count only the rows pulled for this run, not the full query.",
        "charts_full": "Result distribution",
        "charts_full_note": "Charts count every retrieved row and follow the fields selected for this query.",
        "charts_partial_note": "Charts count every retrieved row. A larger FOFA visible count is not included.",
        "findings_h": "Result",
        "coverage_range_h": "Result range",
        "coverage_full_body": (
            "Primary query visible {visible}. Retrieved {pulled}. "
            "The visible results are included, and the conclusion uses every retrieved row."
        ),
        "coverage_stop_cap": "The retrieval cap was reached, so paging stopped.",
        "coverage_partial_limit": "Charts and the conclusion count retrieved rows only. They are not the full query population.",
        "coverage_h": "Sampling note",
        "coverage_visible": "Visible on the primary query",
        "coverage_sampled": "Rows pulled",
        "coverage_stop_user": "The sample cap was reached, so paging stopped.",
        "coverage_stop_page": "The page window ended before the visible results were exhausted.",
        "coverage_stop_done": "The visible results are included in this sample.",
        "coverage_limit": "The sample shows asset shape only. It is not the full result set.",
        "population_title": "Population",
        "population_note": "FOFA statistics for the primary query, not the sample table. Product cannot be aggregated.",
        "population_note_full": "FOFA statistics for the primary query. Product cannot be aggregated.",
        "query_chart": "Visible query volume",
        "product_chart": "Products",
        "port_chart": "Ports",
        "token_chart": "Model usage",
        "unknown": "Unidentified",
        "other": "Other",
        "analysis_title": "Analysis, review, and recommendations",
        "analysis_h": "Analysis",
        "review_h": "Review",
        "advice_h": "Recommendations",
        "analysis_empty": "The model did not write a separate conclusion.",
        "review_empty": "The model did not separate the evidence review.",
        "advice_empty": "The model did not write recommendations.",
        "analysis_fine": (
            "This briefing comes from the connected model and explains only the returned sample. "
            "A fingerprint, title, or filing is not a confirmed vulnerability."
        ),
        "analysis_fine_full": (
            "This briefing comes from the connected model and explains every retrieved row. "
            "A fingerprint, title, or filing is not a confirmed vulnerability."
        ),
        "brief": "Survey brief",
        "brief_note": "No model route was recorded. The note below is assembled from the hits.",
        "no_model_title": "Analysis",
        "no_model_note": "No connected model",
        "no_model_body": (
            "No model analysis, review, or recommendation was produced. "
            "Later sections list queries, assets, evidence, and the scan decision."
        ),
        "query_title": "Query strategy",
        "query_note": "{count} queries ran. Visible is the FOFA count; sample is what this run pulled.",
        "query_note_full": "{count} queries ran. Visible is the FOFA count; retrieved is what this run pulled.",
        "th_pulled": "Retrieved",
        "th_source": "Source",
        "th_strategy": "Strategy",
        "th_purpose": "Purpose",
        "th_query": "Query",
        "th_visible": "Visible",
        "th_sample": "Sample",
        "th_new": "New",
        "reflect": "Reflection",
        "asset_title": "Asset sample",
        "asset_note": "{count} rows are on this page. The filter applies only to this table.",
        "asset_full": "Asset list",
        "asset_full_note": "{count} rows are on this page. The filter applies only to this table.",
        "asset_empty": "No assets to display.",
        "filter": "Filter",
        "filter_ph": "Host, title, product, port",
        "evidence_col": "Evidence",
        "record": "Record",
        "truncated": "The table shows the first {shown} rows. This run counted {total}.",
        "truncated_full": "The table lists the first {shown} rows. Charts and the conclusion use all {total} retrieved rows.",
        "showing": "Showing",
        "rows": "rows",
        "sites": "Website candidates",
        "sites_note": "Corroborated means several FOFA clues agree. It is not a legal or ownership finding.",
        "status": "Status",
        "url": "URL",
        "confidence": "Confidence",
        "evidence_col2": "Evidence",
        "site_status": {"corroborated": "Corroborated", "observed": "Observed", "candidate": "Unverified"},
        "host_title": "Host profile",
        "org": "Organization",
        "region": "Region",
        "country": "Country",
        "asn": "ASN",
        "category": "Category",
        "level": "Level",
        "missing": "Not returned",
        "port": "Port",
        "protocol": "Protocol",
        "product": "Product",
        "updated": "Updated",
        "stats_title": "Aggregate statistics",
        "stats_total": "Total",
        "distinct_ip": "Distinct IPs",
        "distinct_ipc": "Distinct C segments",
        "data_time": "Data time",
        "value": "Value",
        "count": "Count",
        "scan_title": "Scan decision",
        "findings_title": "Vulnerability scan results",
        "findings_empty": "The scan finished with no findings.",
        "fix_h": "Remediation",
        "findings_note": (
            "Findings come from an authorized Nuclei scan and still need human review. "
            "They are not confirmed vulnerabilities by themselves."
        ),
        "th_sev": "Severity",
        "th_site": "Site",
        "th_check": "Check",
        "th_detail": "Detail",
        "user_scan": "User requested a scan",
        "model_scan": "Model recommends a scan",
        "targets": "Candidate targets",
        "templates": "Templates",
        "severity": "Severities",
        "artifact": "Artifact",
        "yes": "Yes",
        "no": "No",
        "none": "None",
        "no_reason": "No additional reason was recorded.",
        "started": "Started",
        "elapsed": "Elapsed",
        "tokens": "Tokens",
        "models_title": "Model route",
        "models_note": "Providers and token counts for this run only.",
        "models_empty": "No model calls were recorded.",
        "task": "Task",
        "provider": "Provider",
        "model": "Model",
        "fallback": "Fallback",
        "input": "Input",
        "output": "Output",
        "timeline": "Execution",
        "steps": "steps",
        "disclaimer": "A FOFA fingerprint is exposure, not a confirmed vulnerability. Scan results need review by an authorized person.",
        "studio_line": f"Generated by FofaMap V{VERSION}.",
        "site_label": "Website",
        "github_label": "GitHub",
        "scope_title": "Scope and how to read this",
        "scope_note": "Check the sample boundary and evidence grades before the model briefing.",
        "scope_note_full": "Check the result range and evidence grades before the model briefing.",
        "range_h": "This run",
        "fields_label": "Returned fields",
        "sample_vs": "Sample / count",
        "listed_vs": "Listed / retrieved",
        "visible_label": "Largest visible count",
        "legend_h": "Evidence grades",
        "legend_precision": "Precision: tighter query, review these first.",
        "legend_balanced": "Balanced: mix of coverage and noise; check certificates and filings.",
        "legend_hypothesis": "Hypothesis: the lead is not closed.",
        "legend_recall": "Recall: wider coverage, more noise.",
        "priority_h": "Review first",
        "priority_empty": "This run has no named asset sample.",
        "boundary_h": "Decision boundary",
        "boundary_body": (
            "A fingerprint, title, or filing shows exposure only. It is not a confirmed vulnerability. "
            "Verification needs a separate approval of targets, templates, and severities."
        ),
        "lead": (
            "This page holds {sample} sampled rows and the run counted {count}. "
            "Products cluster around {products}. High confidence: {high}. Still to corroborate: {watch}."
        ),
        "lead_plain": (
            "This page holds {sample} sampled rows and the run counted {count}. High confidence: {high}. Still to corroborate: {watch}."
        ),
        "lead_full": (
            "This run retrieved {count} rows and covered the visible primary query. "
            "Products cluster around {products}. High confidence: {high}. Still to corroborate: {watch}."
        ),
        "lead_full_plain": (
            "This run retrieved {count} rows and covered the visible primary query. High confidence: {high}. Still to corroborate: {watch}."
        ),
        "lead_partial": (
            "This run retrieved {count} rows. Products cluster around {products}. High confidence: {high}. Still to corroborate: {watch}."
        ),
        "lead_partial_plain": ("This run retrieved {count} rows. High confidence: {high}. Still to corroborate: {watch}."),
        "alive_note": (
            "Certificate reachable means the service responded with an untrusted certificate. "
            "Port open means TCP connected. Neither is a confirmed vulnerability."
        ),
    },
}
_SKIP_FIELDS = {"body", "header", "banner", "icon", "structinfo"}
_CHART_ORDER = (
    "domain",
    "country",
    "country_name",
    "region",
    "city",
    "port",
    "protocol",
    "base_protocol",
    "server",
    "product",
    "product_category",
    "os",
    "title",
    "status_code",
    "org",
    "asn",
    "as",
    "icp",
    "alive_status",
)
_CHART_TITLES = {
    "zh": {
        "domain": "网站分布",
        "country": "国家分布",
        "country_name": "国家或地区",
        "region": "区域分布",
        "city": "城市分布",
        "port": "端口分布",
        "protocol": "协议分布",
        "base_protocol": "传输协议",
        "server": "服务分布",
        "product": "产品分布",
        "product_category": "产品类别",
        "os": "系统分布",
        "title": "标题分布",
        "status_code": "状态码分布",
        "org": "组织分布",
        "asn": "ASN 分布",
        "as": "ASN 分布",
        "icp": "备案分布",
        "asset_type": "资产类型",
        "fid": "特征 ID",
        "alive_status": "存活结果",
    },
    "en": {
        "domain": "Websites",
        "country": "Countries",
        "country_name": "Countries and regions",
        "region": "Regions",
        "city": "Cities",
        "port": "Ports",
        "protocol": "Protocols",
        "base_protocol": "Transport",
        "server": "Services",
        "product": "Products",
        "product_category": "Product categories",
        "os": "Operating systems",
        "title": "Titles",
        "status_code": "Status codes",
        "org": "Organizations",
        "asn": "ASN",
        "as": "ASN",
        "icp": "ICP filings",
        "asset_type": "Asset types",
        "fid": "FID",
        "alive_status": "Alive check",
    },
}
_ALIVE_LABELS = {
    "zh": {
        "TLS": "证书可达",
        "Open": "端口开放",
        "Timeout": "超时",
        "ConnErr": "连接失败",
        "DNS": "解析失败",
        "Error": "探测失败",
        "N/A": "无地址",
    },
    "en": {
        "TLS": "Certificate reachable",
        "Open": "Port open",
        "Timeout": "Timeout",
        "ConnErr": "Connection failed",
        "DNS": "DNS failed",
        "Error": "Probe failed",
        "N/A": "No address",
    },
}
_SECTION_GROUP = {
    "结论": "analysis",
    "Conclusion": "analysis",
    "数据分析": "analysis",
    "Data analysis": "analysis",
    "高置信资产": "review",
    "High-confidence assets": "review",
    "风险与暴露面": "review",
    "Exposure": "review",
    "证据边界与噪声": "review",
    "Evidence limits": "review",
    "覆盖缺口": "review",
    "Coverage gaps": "review",
    "处置优先级": "advice",
    "Priority actions": "advice",
}


def write_html_report(
    run: AgentRun,
    destination: Path,
    *,
    scan_status: str = "not_requested",
    scan_error: str | None = None,
    language: str = "zh",
    alternate_href: str | None = None,
) -> Path:
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        render_html_report(
            run,
            scan_status=scan_status,
            scan_error=scan_error,
            language=language,
            alternate_href=alternate_href,
        ),
        encoding="utf-8",
    )
    return destination


def render_html_report(
    run: AgentRun,
    *,
    scan_status: str = "not_requested",
    scan_error: str | None = None,
    language: str = "zh",
    alternate_href: str | None = None,
) -> str:
    lang = "en" if language == "en" else "zh"
    text = _COPY[lang]
    generated = datetime.now().astimezone().strftime("%Y-%m-%d %H:%M")
    model = _model_event(run)
    show_analysis = run.uses_model_summary() or (
        run.summary_source == "local" and run.action.value in {"host_query", "stat_query"} and bool(run.summary)
    )
    show_decision = run.shows_scan_decision(scan_error=scan_error)
    parts = [
        _document_start(run, generated, text, alternate_href, show_analysis=show_analysis, show_decision=show_decision),
        _hero(run, generated, model, lang, text),
        _metrics(run, text),
        _dossier(run, lang, text),
        _population(run, text),
        _charts(run, lang, text),
        _analysis(run, model, text),
        _queries(run, lang, text),
        _assets(run, lang, text),
        _websites(run, text),
        _host_or_stats(run, text),
        _scan(run, scan_status, scan_error, text) if show_decision else "",
        _models(run, text),
        _timeline(run, lang, text),
        _document_end(text),
    ]
    return "\n".join(part for part in parts if part)


def _document_start(
    run: AgentRun,
    generated: str,
    text: dict[str, Any],
    alternate_href: str | None,
    *,
    show_analysis: bool = False,
    show_decision: bool = False,
) -> str:
    title = _esc(run.intent or text["title"])
    detail_id = {"host_query": "host", "stat_query": "stats"}.get(run.action.value, "assets")
    detail_label = text["host_title"] if detail_id == "host" else text["stats_title"] if detail_id == "stats" else text["assets"]
    chart_id = detail_id if detail_id != "assets" else "charts"
    switch = ""
    if alternate_href:
        switch = f'<a class="lang" href="{_esc(alternate_href)}">{text["lang_switch"]}</a>'
    return f"""<!DOCTYPE html>
<html lang="{text["html_lang"]}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="author" content="Hx0 Studio">
<title>{text["title"]} · {title}</title>
<style>
{CSS}
</style>
</head>
<body>
<a class="skip" href="#overview">{text["skip"]}</a>
<header class="nav">
  <div class="nav-inner">
    <a class="brand" href="#overview">{_img("hx0-mark.png", "nav-mark", text["logo_alt"])}FofaMap</a>
    <nav class="rail" aria-label="{text["nav"]}">
      <a href="#overview">{text["overview"]}</a>
      <a href="#scope">{text["scope"]}</a>
      <a href="#{chart_id}">{text["charts"]}</a>
      {f'<a href="#analysis">{text["analysis"]}</a>' if show_analysis else ""}
      <a href="#{detail_id}">{detail_label}</a>
      {f'<a href="#decision">{text["decision"]}</a>' if show_decision else ""}
    </nav>
    <a class="studio" href="{_STUDIO_URL}" target="_blank" rel="noopener noreferrer">{text["studio"]}</a>
    {switch}
    <p class="nav-meta">{text["nav_meta"]} · v{VERSION}</p>
  </div>
</header>
<div class="sheet">
<div class="ribbon" aria-hidden="true"></div>
<main>"""


def _hero(run: AgentRun, generated: str, model: dict[str, Any] | None, lang: str, text: dict[str, Any]) -> str:
    state = _label(_STATE[lang], run.state.value if hasattr(run.state, "value") else run.state)
    action = _label(_ACTION[lang], run.action.value if hasattr(run.action, "value") else run.action)
    if model and run.uses_model_summary():
        model_line = text["model_wrote"].format(
            provider=_esc(model.get("provider") or ("模型" if lang == "zh" else "model")),
            model=_esc(model.get("model") or ""),
        )
    elif run.route_events:
        model_line = (
            "The model was called; the report uses a structured interpretation of the returned data."
            if lang == "en"
            else "已调用模型；本报告采用基于返回数据的结构化解读。"
        )
    else:
        model_line = text["no_model"]
    slices = _evidence_slices(run, lang)
    meta = f"{state} · {action} · {_num(run.result_count)} {text['assets_unit']} · {_num(len(run.queries))} {text['strategies_unit']}"
    evidence_panel = f"<p>{text['evidence']}</p>{_donut(slices, center=text['evidence'])}{_legend(slices)}"
    if run.action.value in {"stat_query", "host_query"}:
        label = text["stats_title"] if run.action.value == "stat_query" else text["host_title"]
        note = "Indexed observations, not verified vulnerabilities" if lang == "en" else "索引观测结果，不代表已验证漏洞"
        evidence_panel = f'<p>{label}</p><div class="readout">{_num(run.result_count)}</div><p>{note}</p>'
    return f"""
<section class="hero" id="overview">
  <div class="letterhead">
    {_linked_logo("hx0-lockup.png", text["logo_alt"])}
    <div class="letterhead-side">
      <strong>{text["studio"]}</strong>
      <span>{text["slogan"]}</span>
      <a href="{_STUDIO_URL}" target="_blank" rel="noopener noreferrer">{_STUDIO_URL}</a>
    </div>
  </div>
  <div class="hero-grid">
  <div class="hero-copy">
    <p class="eyebrow">{text["eyebrow"]} · {generated}</p>
    <h1>{_esc(run.intent or text["untitled"])}</h1>
    <p class="lede">{model_line} {text["lede"]}</p>
    <p class="meta">{meta}</p>
    <p class="kicker">{text["primary"]}</p>
    <p class="query">{_esc(run.query or text["no_query"])}</p>
    <p class="runid">Run {_esc(run.id)}</p>
    <p class="meta">{_usage_line(run, lang, text)}</p>
  </div>
  <aside class="hero-chart">
    {evidence_panel}
  </aside>
  </div>
</section>"""


def _metrics(run: AgentRun, text: dict[str, Any]) -> str:
    domains = {str(asset.get("domain") or "").strip() for asset in run.assets if asset.get("domain")}
    ips = {str(asset.get("ip") or "").strip() for asset in run.assets if asset.get("ip")}
    largest = max((item.available_count or 0 for item in run.queries), default=0)
    evidence = run.evidence_counts or {}
    asset_label = text["sample"] if _result_mode(run) == "sample" else text["pulled"]
    asset_note = text["sample_note"] if _result_mode(run) == "sample" else text["pulled_note"]
    cards = [
        ("sample", asset_label, _num(run.result_count or len(run.assets)), asset_note),
        ("domains", text["domains"], _num(len(domains)), text["domains_note"]),
        ("ips", text["ips"], _num(len(ips)), text["ips_note"]),
        ("largest", text["largest"], _num(largest), text["largest_note"]),
        ("high", text["high"], _num(evidence.get("precision", 0)), text["high_note"]),
        ("watch", text["watch"], _num(evidence.get("recall", 0) + evidence.get("hypothesis", 0)), text["watch_note"]),
    ]
    if run.action.value == "stat_query":
        aggs = run.result_data.get("aggs") or {}
        cards = [
            ("total", text["stats_total"], _num(run.result_count), text["stats_title"]),
            ("dimensions", "Dimensions" if text["html_lang"] == "en" else "统计维度", _num(len(aggs)), "Top 5 / dimension"),
            ("ip", text["distinct_ip"], _num((run.result_data.get("distinct") or {}).get("ip")), text["stats_title"]),
        ]
    elif run.action.value == "host_query":
        ports = [row for row in run.result_data.get("ports") or [] if isinstance(row, dict)]
        protocols = {row.get("protocol") for row in ports if row.get("protocol")}
        cards = [
            ("hosts", text["host_title"], "1", _esc(run.target or "")),
            ("ports", text["port"], _num(len(ports)), text["host_title"]),
            ("protocols", text["protocol"], _num(len(protocols)), text["host_title"]),
        ]
    body = "".join(
        f'<article style="--accent:{_METRIC_COLORS[index]}"><p>{label}</p><strong>{value}</strong><span>{note}</span></article>'
        for index, (_key, label, value, note) in enumerate(cards)
    )
    return f'<section class="metrics" aria-label="{text["overview"]}">{body}</section>'


def _result_mode(run: AgentRun) -> str:
    if getattr(run, "sampled", False):
        return "sample"
    _visible, _pulled, reason = _coverage_facts(run)
    return "full" if reason == "complete" else "partial"


def _coverage_facts(run: AgentRun) -> tuple[int, int, str]:
    visible = int(getattr(run, "population_size", 0) or 0)
    if not visible and run.queries:
        chosen = next((item for item in run.queries if run.query and item.query == run.query), run.queries[0])
        visible = int(chosen.available_count or 0)
    sampled = int(run.result_count or 0)
    reason = str(getattr(run, "sample_stop_reason", "") or "")
    if reason not in {"complete", "user_limit", "page_window"}:
        if visible <= sampled or visible == 0:
            reason = "complete"
        elif sampled and visible > sampled * 20:
            reason = "user_limit"
        elif visible > sampled:
            reason = "page_window"
        else:
            reason = "complete"
    return visible, sampled, reason


def _population(run: AgentRun, text: dict[str, Any]) -> str:
    aggs = getattr(run, "population_aggs", None) or {}
    if not isinstance(aggs, dict) or not aggs:
        return ""
    blocks = []
    for field, rows in aggs.items():
        ranked = [(str(item.get("name") or ""), int(item.get("count") or 0)) for item in (rows or [])[:8] if isinstance(item, dict)]
        if not ranked:
            continue
        blocks.append(_chart_card(_chart_title(str(field), "zh" if text["html_lang"] == "zh-CN" else "en"), _bars(_colored(ranked))))
    if not blocks:
        return ""
    note = text["population_note"] if _result_mode(run) == "sample" else text["population_note_full"]
    return f"""
<section id="population">
  <div class="section-head"><h2>{text["population_title"]}</h2><p>{note}</p></div>
  <div class="chart-grid">{"".join(blocks)}</div>
</section>"""


def _charts(run: AgentRun, lang: str, text: dict[str, Any]) -> str:
    mode = _result_mode(run)
    title = text["charts_title"] if mode == "sample" else text["charts_full"]
    note = {
        "sample": text["charts_note"],
        "full": text["charts_full_note"],
    }.get(mode, text["charts_partial_note"])
    panels: list[str] = []
    queries = []
    for index, item in enumerate(run.queries[:6]):
        label = (item.purpose or item.query or f"#{index + 1}").strip()
        queries.append((_trim(label, 28), int(item.available_count or item.result_count or 0), _PALETTE[index % len(_PALETTE)]))
    if any(value for _label, value, _color in queries):
        panels.append(_chart_card(text["query_chart"], _bars(queries)))
    for field in _chart_fields(run):
        ranked = _distribution(run, field, unknown=text["unknown"], other=text["other"])
        if field == "alive_status":
            ranked = [(_alive_label(name, lang, text), count) for name, count in ranked]
        if ranked:
            panels.append(_chart_card(_chart_title(field, lang), _bars(_colored(ranked))))
    tokens = []
    for index, event in enumerate(run.route_events):
        total = int(event.get("input_tokens") or 0) + int(event.get("output_tokens") or 0)
        if total <= 0:
            continue
        tokens.append((str(event.get("task") or "model"), total, _PALETTE[index % len(_PALETTE)]))
    if tokens:
        panels.append(_chart_card(text["token_chart"], _bars(tokens)))
    conclusion = _conclusion(run, lang, text)
    if not panels and not conclusion:
        return ""
    findings = ""
    if conclusion:
        findings = f'<article class="note analysis"><h3>{text["findings_h"]}</h3>{_conclusion_list(conclusion, lang)}</article>'
    return f"""
<section id="charts">
  <div class="section-head"><h2>{title}</h2><p>{note}</p></div>
  {findings}
  <div class="chart-grid">{"".join(panels)}</div>
</section>"""


def _analysis(run: AgentRun, model: dict[str, Any] | None, text: dict[str, Any]) -> str:
    summary = (run.summary or "").strip()
    local = run.summary_source == "local" and run.action.value in {"host_query", "stat_query"}
    if not summary or (not local and (not model or not run.uses_model_summary())):
        return ""
    groups = _group_summary(summary)
    panels = [
        (text["analysis_h"], "analysis", groups.get("analysis") or ""),
        (text["review_h"], "review", groups.get("review") or ""),
        (text["advice_h"], "advice", groups.get("advice") or ""),
    ]
    written = [(title, key, html_body) for title, key, html_body in panels if html_body.strip()]
    if not written:
        return ""
    body = "".join(f'<article class="note {key}"><h3>{title}</h3>{html_body}</article>' for title, key, html_body in written)
    if local:
        heading = "Structured interpretation" if text["html_lang"] == "en" else "结构化解读"
        who = "Computed from returned data; no model attribution." if text["html_lang"] == "en" else "根据返回数据生成，不作为模型分析。"
    else:
        heading = text["analysis_title"]
        who = f"{_esc(model.get('provider') or '')} · {_esc(model.get('model') or '')}"
    return f"""
<section id="analysis">
  <div class="section-head"><h2>{heading}</h2><p>{who}</p></div>
  <div class="notes">{body}</div>
  <p class="fine">{text["analysis_fine"] if _result_mode(run) == "sample" else text["analysis_fine_full"]}</p>
</section>"""


def _queries(run: AgentRun, lang: str, text: dict[str, Any]) -> str:
    if not run.queries:
        return ""
    rows = []
    for index, item in enumerate(run.queries, start=1):
        source = _SOURCE[lang].get(item.source) or f"{text['reflect']} {item.source}"
        rows.append(
            "<tr>"
            f"<td>{index}</td><td>{_esc(source)}</td>"
            f'<td><span class="tag {_strategy_tone(item.strategy)}">{_esc(_label(_STRATEGY[lang], item.strategy))}</span></td>'
            f"<td>{_esc(item.purpose)}</td><td><code>{_esc(item.query)}</code></td>"
            f"<td>{_num(item.available_count)}</td><td>{_num(item.result_count)}</td><td>{_num(item.new_assets)}</td>"
            "</tr>"
        )
    mode = _result_mode(run)
    note = text["query_note"] if mode == "sample" else text["query_note_full"]
    pulled = text["th_sample"] if mode == "sample" else text["th_pulled"]
    return f"""
<section id="queries">
  <div class="section-head"><h2>{text["query_title"]}</h2><p>{note.format(count=len(run.queries))}</p></div>
  {
        _table_block(
            "<table><thead><tr><th>#</th>"
            f"<th>{text['th_source']}</th><th>{text['th_strategy']}</th><th>{text['th_purpose']}</th>"
            f"<th>{text['th_query']}</th><th>{text['th_visible']}</th><th>{pulled}</th><th>{text['th_new']}</th>"
            f"</tr></thead><tbody>{''.join(rows)}</tbody></table>",
            label=text["export"],
            filename="fofamap-queries.csv",
            table_id="query-table",
        )
    }
</section>"""


def _assets(run: AgentRun, lang: str, text: dict[str, Any]) -> str:
    if run.action.value in {"host_query", "stat_query"} or not run.assets:
        if run.action.value not in {"host_query", "stat_query"}:
            return (
                f'<section id="assets"><div class="section-head"><h2>{text["asset_title"]}</h2><p>{text["asset_empty"]}</p></div></section>'
            )
        return ""
    fields = [field for field in (run.fields or _infer_fields(run.assets)) if field not in _SKIP_FIELDS][:12]
    if "host" not in fields:
        fields = ["host", *fields]
    labels = _FIELDS[lang]
    head = "".join(f"<th>{_esc(labels.get(field, field) if field not in {'#', '证据'} else field)}</th>" for field in ["#", *fields])
    head += f"<th>{text['evidence_col']}</th>"
    rows = []
    for index, asset in enumerate(run.assets, start=1):
        rank = run.asset_confidence[index - 1] if index <= len(run.asset_confidence) else ""
        label, tone = _CONFIDENCE[lang].get(rank, (text["record"], "mid"))
        cells = "".join(f"<td>{_cell(asset.get(field))}</td>" for field in fields)
        blob = " ".join(str(asset.get(field) or "") for field in fields).replace("\n", " ")
        rows.append(f'<tr data-q="{_esc(blob.lower())}"><td>{index}</td>{cells}<td><span class="tag {tone}">{label}</span></td></tr>')
    mode = _result_mode(run)
    note = ""
    if run.assets_truncated:
        template = text["truncated"] if mode == "sample" else text["truncated_full"]
        note = f'<p class="fine">{template.format(shown=f"{len(run.assets):,}", total=f"{run.result_count:,}")}</p>'
    heading = text["asset_title"] if mode == "sample" else text["asset_full"]
    heading_note = text["asset_note"] if mode == "sample" else text["asset_full_note"]
    return f"""
<section id="assets">
  <div class="section-head">
    <h2>{heading}</h2>
    <p>{heading_note.format(count=f"{len(run.assets):,}")}</p>
  </div>
  <label class="filter">{text["filter"]} <input id="asset-filter" type="search" placeholder="{text["filter_ph"]}"></label>
  <p class="fine" id="asset-count" data-showing="{text["showing"]}" data-unit="{text["rows"]}"></p>
  {
        _table_block(
            f'<table id="asset-table"><thead><tr>{head}</tr></thead><tbody>{"".join(rows)}</tbody></table>',
            label=text["export"],
            filename="fofamap-assets.csv",
            table_id="asset-table",
            field_labels=[(field, labels.get(field, field)) for field in fields],
        )
    }
  {note}
</section>"""


def _websites(run: AgentRun, text: dict[str, Any]) -> str:
    if not run.website_candidates:
        return ""
    labels = text["site_status"]
    rows = []
    for item in run.website_candidates:
        rows.append(
            "<tr>"
            f"<td>{_esc(labels.get(item.status, item.status))}</td>"
            f"<td><code>{_esc(item.domain)}</code></td>"
            f"<td>{_esc(item.url)}</td>"
            f"<td>{_esc(item.confidence)}</td>"
            f"<td>{_esc('；'.join(item.evidence))}</td>"
            "</tr>"
        )
    return f"""
<section id="websites">
  <div class="section-head"><h2>{text["sites"]}</h2><p>{text["sites_note"]}</p></div>
  {
        _table_block(
            "<table><thead><tr>"
            f"<th>{text['status']}</th><th>{text['domains']}</th><th>{text['url']}</th>"
            f"<th>{text['confidence']}</th><th>{text['evidence_col2']}</th>"
            f"</tr></thead><tbody>{''.join(rows)}</tbody></table>",
            label=text["export"],
            filename="fofamap-websites.csv",
            table_id="website-table",
        )
    }
</section>"""


def _report_lang(text: dict[str, Any]) -> str:
    return "zh" if text.get("html_lang") == "zh-CN" else "en"


def _plain_list(value: Any) -> str:
    if isinstance(value, list):
        return ", ".join(str(item) for item in value if item not in (None, ""))
    if value in (None, ""):
        return ""
    return str(value)


def _agg_label(item: dict[str, Any]) -> str:
    name = str(item.get("name") or "")
    regions = item.get("regions")
    if not isinstance(regions, list):
        return name
    tops = [str(region.get("name")) for region in regions[:3] if isinstance(region, dict) and region.get("name")]
    if not tops:
        return name
    nested = "、".join(tops)
    return f"{name}（{nested}）" if name else nested


def _product_columns(products: Any) -> tuple[str, str, str]:
    names: list[str] = []
    categories: list[str] = []
    levels: list[str] = []
    for product in products or []:
        if not isinstance(product, dict):
            continue
        name = str(product.get("product") or product.get("name") or "").strip()
        category = str(product.get("category") or "").strip()
        level = product.get("level")
        if name:
            names.append(name)
        if category:
            categories.append(category)
        if level not in (None, ""):
            levels.append(str(level))
    return ", ".join(names), ", ".join(categories), ", ".join(levels)


def _count_chart(title: str, labels: list[str]) -> str:
    counts: dict[str, int] = {}
    for label in labels:
        if label:
            counts[label] = counts.get(label, 0) + 1
    ranked = sorted(counts.items(), key=lambda item: (-item[1], item[0]))[:8]
    if len(ranked) < 2:
        return ""
    return _chart_card(title, _bars(_colored(ranked)))


def _host_section(run: AgentRun, text: dict[str, Any]) -> str:
    data = run.result_data
    lang = _report_lang(text)
    country = str(data.get("country_name") or "")
    code = str(data.get("country_code") or "")
    if country and code:
        region = f"{country} · {code}"
    else:
        region = country or code or str(text["missing"])
    asn = data.get("asn")
    facts = [
        f"<li>IP {_esc(data.get('ip') or text['missing'])}</li>",
        f"<li>{text['asn']} {_esc(asn if asn not in (None, '') else text['missing'])}</li>",
        f"<li>{text['org']} {_esc(data.get('org') or text['missing'])}</li>",
        f"<li>{text['country']} {_esc(region)}</li>",
        f"<li>{text['updated']} {_esc(data.get('update_time') or text['missing'])}</li>",
    ]
    for key, label in (
        ("protocol", text["protocol"]),
        ("port", text["port"]),
        ("category", text["category"]),
        ("product", text["product"]),
    ):
        shown = _plain_list(data.get(key))
        if shown:
            facts.append(f"<li>{label} {_esc(shown)}</li>")
    protocols: list[str] = []
    products: list[str] = []
    rows = []
    for port in data.get("ports") or []:
        if not isinstance(port, dict):
            continue
        name, category, level = _product_columns(port.get("products"))
        protocol = str(port.get("protocol") or "")
        if protocol:
            protocols.append(protocol)
        for product in port.get("products") or []:
            if isinstance(product, dict):
                label = str(product.get("product") or product.get("name") or "").strip()
                if label:
                    products.append(label)
        rows.append(
            "<tr>"
            f"<td>{_esc(port.get('port'))}</td><td>{_esc(protocol)}</td>"
            f"<td>{_esc(name)}</td><td>{_esc(category)}</td><td>{_esc(level)}</td>"
            "</tr>"
        )
    charts = _count_chart(_chart_title("protocol", lang), protocols) + _count_chart(_chart_title("product", lang), products)
    table = ""
    if rows:
        table = _table_block(
            "<table><thead><tr>"
            f"<th>{text['port']}</th><th>{text['protocol']}</th><th>{text['product']}</th>"
            f"<th>{text['category']}</th><th>{text['level']}</th>"
            f"</tr></thead><tbody>{''.join(rows)}</tbody></table>",
            label=text["export"],
            filename="fofamap-host-ports.csv",
            table_id="host-port-table",
        )
    return f"""
<section id="host">
  <div class="section-head"><h2>{text["host_title"]}</h2><p>{_esc(data.get("host") or run.target)}</p></div>
  <ul class="facts">{"".join(facts)}</ul>
  {charts}
  {table}
</section>"""


def _stats_section(run: AgentRun, text: dict[str, Any]) -> str:
    data = run.result_data
    lang = _report_lang(text)
    distinct = data.get("distinct") if isinstance(data.get("distinct"), dict) else {}
    total = data.get("size") if data.get("size") is not None else run.result_count
    facts = [f"<li>{text['stats_total']} {_num(total)}</li>"]
    if distinct.get("ip") is not None:
        facts.append(f"<li>{text['distinct_ip']} {_num(distinct.get('ip'))}</li>")
    if distinct.get("ipc") is not None:
        facts.append(f"<li>{text['distinct_ipc']} {_num(distinct.get('ipc'))}</li>")
    if data.get("lastupdatetime"):
        facts.append(f"<li>{text['data_time']} {_esc(data.get('lastupdatetime'))}</li>")
    blocks = []
    for field, rows in (data.get("aggs") or {}).items():
        items = [item for item in (rows or []) if isinstance(item, dict)]
        ranked = [(_agg_label(item), int(item.get("count") or 0)) for item in items[:8]]
        body = "".join(
            f"<tr><td>{index}</td><td>{_esc(_agg_label(item))}</td><td>{_num(item.get('count'))}</td></tr>"
            for index, item in enumerate(items[:20], start=1)
        )
        title = _chart_title(str(field), lang)
        chart = _chart_card(title, _bars(_colored(ranked))) if ranked else f"<h3>{_esc(title)}</h3>"
        table = f"<table><thead><tr><th>#</th><th>{text['value']}</th><th>{text['count']}</th></tr></thead><tbody>{body}</tbody></table>"
        framed = _table_block(
            table,
            label=text["export"],
            filename=f"fofamap-stats-{_slug(str(field))}.csv",
            table_id=f"stats-{_slug(str(field))}",
        )
        blocks.append(f"{chart}{framed}")
    note = f"<code>{_esc(run.query)}</code>" if run.query else ""
    return f"""
<section id="stats">
  <div class="section-head"><h2>{text["stats_title"]}</h2><p>{note}</p></div>
  <ul class="facts">{"".join(facts)}</ul>
  {"".join(blocks)}
</section>"""


def _host_or_stats(run: AgentRun, text: dict[str, Any]) -> str:
    if run.action.value == "host_query" and run.result_data:
        return _host_section(run, text)
    if run.action.value == "stat_query" and run.result_data:
        return _stats_section(run, text)
    return ""


def _scan(run: AgentRun, scan_status: str, scan_error: str | None, text: dict[str, Any]) -> str:
    status = _SCAN["zh" if text["html_lang"] == "zh-CN" else "en"].get(scan_status, scan_status)
    error = f'<p class="warn">{_esc(scan_error)}</p>' if scan_error else ""
    templates = _esc(", ".join(run.scan_template_ids) or "—")
    severities = _esc(", ".join(run.scan_severities) or "—")
    tone = {
        "completed": "high",
        "recommendation_only_no_user_authorization": "mid",
        "declined": "watch",
        "blocked_by_agent_error": "watch",
    }.get(scan_status, "low")
    yes = text["yes"]
    no = text["no"]
    artifact = _esc(run.scan_artifact or text["none"])
    scope_facts = ""
    if run.scan_protocols:
        scope_facts += f"<li>Protocols: {_esc(', '.join(run.scan_protocols))}</li>"
    if run.scan_limits:
        scope_facts += f"<li>Limits: {_esc(str(run.scan_limits))}</li>"
    selection = ""
    if run.scan_selection.get("enabled"):
        rows = "".join(
            f"<tr><td>{_esc(row.get('target', ''))}</td><td>{_esc(row.get('action', ''))}</td><td>{_esc(row.get('reason', ''))}</td></tr>"
            for row in run.scan_selection.get("decisions", [])
        )
        selection = ('<h3>AI target selection / 扫描目标筛选</h3><table><thead>'
                     '<tr><th>Target</th><th>Decision</th><th>Reason</th></tr></thead>')
        selection += f"<tbody>{rows}</tbody></table>"
    return f"""
<section id="decision">
  <div class="section-head scan-head"><h2>{text["scan_title"]}</h2><span class="tag {tone}">{_esc(status)}</span></div>
  <ul class="facts">
    <li>{text["user_scan"]} {yes if run.scan_requested_by_user else no}</li>
    <li>{text["model_scan"]} {yes if run.scan_recommended else no}</li>
    <li>{text["targets"]} {_num(len(run.scan_targets))}</li>
    <li>{text["templates"]} {templates}</li>
    <li>{text["severity"]} {severities}</li>
    {scope_facts}
  </ul>
  <p class="artifact">{text["artifact"]} <code>{artifact}</code></p>
  <p class="scan-reason">{_esc(run.scan_reason or text["no_reason"])}</p>
  {error}
  {selection}
  {_scan_findings(run, text, "zh" if text["html_lang"] == "zh-CN" else "en")}
</section>"""


def _usage_line(run: AgentRun, lang: str, text: dict[str, Any]) -> str:
    usage = run_usage_parts(run, lang)
    return (
        f"{text['started']} {_esc(usage['started'])}"
        f" · {text['elapsed']} {_esc(usage['elapsed'])}"
        f" · {text['tokens']} {_esc(usage['tokens'])}"
    )


def _models(run: AgentRun, text: dict[str, Any]) -> str:
    if not run.route_events:
        return ""
    lang = "zh" if text["html_lang"] == "zh-CN" else "en"
    rows = []
    for event in run.route_events:
        rows.append(
            "<tr>"
            f"<td>{_esc(event.get('task'))}</td><td>{_esc(event.get('provider'))}</td>"
            f"<td>{_esc(event.get('model'))}</td><td>{text['yes'] if event.get('fallback') else text['no']}</td>"
            f"<td>{_num(event.get('input_tokens'))}</td><td>{_num(event.get('output_tokens'))}</td>"
            "</tr>"
        )
    return f"""
<section id="models">
  <div class="section-head"><h2>{text["models_title"]}</h2><p>{text["models_note"]}</p></div>
  <p class="meta">{_usage_line(run, lang, text)}</p>
  {
        _table_block(
            "<table><thead><tr>"
            f"<th>{text['task']}</th><th>{text['provider']}</th><th>{text['model']}</th>"
            f"<th>{text['fallback']}</th><th>{text['input']}</th><th>{text['output']}</th>"
            f"</tr></thead><tbody>{''.join(rows)}</tbody></table>",
            label=text["export"],
            filename="fofamap-models.csv",
            table_id="model-table",
        )
    }
</section>"""


def _timeline(run: AgentRun, lang: str, text: dict[str, Any]) -> str:
    if not run.steps:
        return ""
    items = "".join(
        f"<li><time>{step.started_at:%H:%M:%S}</time> <span>{_esc(_label(_STATE[lang], step.state.value))}</span>{_esc(step.detail)}</li>"
        for step in run.steps
    )
    return f"""
<details class="timeline">
  <summary>{text["timeline"]} · {len(run.steps)} {text["steps"]}</summary>
  <ol>{items}</ol>
</details>"""


def _conclusion_list(conclusion: str, lang: str) -> str:
    separator = ". " if lang == "en" else "。"
    ending = "." if lang == "en" else "。"
    parts = [part.strip() for part in conclusion.split(separator) if part.strip()]
    items = []
    for part in parts:
        sentence = part if part.endswith(("。", ".", "！", "!", "？", "?")) else f"{part}{ending}"
        items.append(f"<li>{_esc(sentence)}</li>")
    return f'<ul class="conclusion">{"".join(items)}</ul>'


def _document_end(text: dict[str, Any]) -> str:
    mark = _img("hx0-mark.png", "footer-mark", text["logo_alt"])
    return f"""
</main>
<footer>
  <div class="footer-brand">
    {mark}
    <div class="footer-id">
      <strong>{text["studio"]}</strong>
      <span>{text["slogan"]}</span>
    </div>
    <nav class="footer-links" aria-label="{text["studio"]}">
      <a href="{_STUDIO_URL}" target="_blank" rel="noopener noreferrer">{text["site_label"]}</a>
      <a href="{_GITHUB_URL}" target="_blank" rel="noopener noreferrer">{text["github_label"]}</a>
    </nav>
  </div>
  <p class="footer-line">{text["studio_line"]}</p>
  <div class="footer-meta">
    <p>{text["disclaimer"]}</p>
    <p>FofaMap v{VERSION}</p>
  </div>
</footer>
</div>
<script>
const filter = document.getElementById("asset-filter");
const table = document.getElementById("asset-table");
const count = document.getElementById("asset-count");
if (filter && table && count) {{
  const rows = [...table.tBodies[0].rows];
  const paint = () => {{
    const needle = filter.value.trim().toLowerCase();
    let shown = 0;
    for (const row of rows) {{
      const hit = !needle || (row.dataset.q || "").includes(needle);
      row.hidden = !hit;
      if (hit) shown += 1;
    }}
    count.textContent = count.dataset.showing + " " + shown + " / " + rows.length + " " + count.dataset.unit;
  }};
  filter.addEventListener("input", paint);
  paint();
}}
document.querySelectorAll(".export").forEach((button) => {{
  button.addEventListener("click", () => {{
    const target = document.getElementById(button.dataset.target || "");
    if (!target) return;
    const lines = [];
    for (const row of target.rows) {{
      if (row.hidden) continue;
      const cells = [...row.cells].map((cell) => {{
        const raw = cell.querySelector(".sort-column")?.dataset.label
          ?? cell.querySelector("[data-export]")?.dataset.export ?? cell.innerText;
        let value = raw.replace(/\\s+/g, " ").trim().replaceAll('"', '""');
        if (/^[=+@-]/.test(value)) value = "'" + value;
        return /[",\\n]/.test(value) ? '"' + value + '"' : value;
      }});
      lines.push(cells.join(","));
    }}
    const blob = new Blob(["\\ufeff" + lines.join("\\r\\n")], {{type: "text/csv;charset=utf-8"}});
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = button.dataset.filename || "fofamap.csv";
    link.click();
    URL.revokeObjectURL(url);
  }});
}});
{TABLE_INTERACTIONS}
</script>
</body>
</html>"""


def _dossier(run: AgentRun, lang: str, text: dict[str, Any]) -> str:
    if run.action.value in {"host_query", "stat_query"}:
        note = (
            "Aggregate buckets show only the published top five per dimension, not a complete asset inventory. "
            "Host profiles describe indexed services. Neither establishes ownership or a vulnerability."
            if lang == "en"
            else "统计聚合只提供各维度前五名，不是完整资产清单；主机画像描述索引中观察到的服务。两者均不能单独证明资产归属或漏洞。"
        )
        return (
            f'<section id="scope"><div class="section-head"><h2>{text["scope_title"]}</h2></div>'
            f'<aside class="boundary"><p>{note}</p></aside></section>'
        )
    labels = _FIELDS[lang]
    names = [labels.get(field, field) for field in (run.fields or []) if field not in _SKIP_FIELDS]
    joiner = ", " if lang == "en" else "、"
    sep = ": " if lang == "en" else "："
    field_line = joiner.join(names) or "—"
    largest = max((item.available_count or 0 for item in run.queries), default=0)
    evidence = run.evidence_counts or {}
    high = int(evidence.get("precision", 0) or 0)
    watch = int(evidence.get("recall", 0) or 0) + int(evidence.get("hypothesis", 0) or 0)
    products = _tally(run.assets, "product", unknown=text["unknown"], other=text["other"])
    product_line = joiner.join(name for name, _count in products[:3])
    values = {"sample": _num(len(run.assets)), "count": _num(run.result_count), "high": _num(high), "watch": _num(watch)}
    mode = _result_mode(run)
    if mode == "sample":
        lead_key, plain_key = "lead", "lead_plain"
    elif mode == "full":
        lead_key, plain_key = "lead_full", "lead_full_plain"
    else:
        lead_key, plain_key = "lead_partial", "lead_partial_plain"
    lead = text[lead_key].format(products=product_line, **values) if product_line else text[plain_key].format(**values)
    visible, sampled, reason = _coverage_facts(run)
    period = ". " if lang == "en" else "。"
    if mode == "sample":
        stop = {
            "user_limit": text["coverage_stop_user"],
            "page_window": text["coverage_stop_page"],
        }.get(reason, text["coverage_stop_done"])
        coverage_title = text["coverage_h"]
        coverage_body = (
            f"{text['coverage_visible']}{sep}{_num(visible)}{period}"
            f"{text['coverage_sampled']}{sep}{_num(sampled)}{period}{stop} {text['coverage_limit']}"
        )
    elif mode == "full":
        coverage_title = text["coverage_range_h"]
        coverage_body = text["coverage_full_body"].format(visible=_num(visible), pulled=_num(sampled))
    else:
        stop = {
            "user_limit": text["coverage_stop_cap"],
            "page_window": text["coverage_stop_page"],
        }.get(reason, text["coverage_stop_cap"])
        coverage_title = text["coverage_range_h"]
        coverage_body = (
            f"{text['coverage_visible']}{sep}{_num(visible)}{period}"
            f"{text['coverage_sampled']}{sep}{_num(sampled)}{period}{stop} {text['coverage_partial_limit']}"
        )
    coverage = f'<aside class="boundary coverage"><strong>{coverage_title}</strong><p>{coverage_body}</p></aside>'
    scope_note = text["scope_note"] if mode == "sample" else text["scope_note_full"]
    listed = text["sample_vs"] if mode == "sample" else text["listed_vs"]
    return f"""
<section id="scope">
  <div class="section-head"><h2>{text["scope_title"]}</h2><p>{scope_note}</p></div>
  <p class="lead-note">{lead}</p>
  <div class="scope-grid">
    <article>
      <h3>{text["range_h"]}</h3>
      <ul>
        <li>{text["fields_label"]}{sep}{_esc(field_line)}</li>
        <li>{listed}{sep}{_num(len(run.assets))} / {_num(run.result_count)}</li>
        <li>{text["visible_label"]}{sep}{_num(largest)}</li>
      </ul>
    </article>
    <article>
      <h3>{text["legend_h"]}</h3>
      <ul>
        <li>{text["legend_precision"]}</li>
        <li>{text["legend_balanced"]}</li>
        <li>{text["legend_hypothesis"]}</li>
        <li>{text["legend_recall"]}</li>
      </ul>
    </article>
    <article class="wide">
      <h3>{text["priority_h"]}</h3>
      {_priority_cards(run, lang, text)}
    </article>
  </div>
  {coverage}
  <aside class="boundary"><strong>{text["boundary_h"]}</strong><p>{text["boundary_body"]}</p></aside>
</section>"""


def _priority_cards(run: AgentRun, lang: str, text: dict[str, Any]) -> str:
    if not run.assets:
        return f"<p>{text['priority_empty']}</p>"
    rank_order = {"precision": 0, "balanced": 1, "hypothesis": 2, "recall": 3}
    paired = []
    for index, asset in enumerate(run.assets):
        rank = run.asset_confidence[index] if index < len(run.asset_confidence) else "recall"
        paired.append((rank_order.get(rank, 3), asset, rank))
    cards = []
    for _score, asset, rank in sorted(paired, key=lambda item: item[0])[:4]:
        label, tone = _CONFIDENCE[lang].get(rank, (text["record"], "mid"))
        host = asset.get("host") or asset.get("ip") or "—"
        detail = asset.get("product") or asset.get("server") or asset.get("title") or "—"
        port = asset.get("port") or "—"
        cards.append(
            f'<article class="pick"><span class="tag {tone}">{_esc(label)}</span>'
            f"<strong>{_cell(host)}</strong><em>{_cell(detail)} · {_cell(port)}</em></article>"
        )
    return f'<div class="picks">{"".join(cards)}</div>'


def _table_block(
    table: str,
    *,
    label: str,
    filename: str,
    table_id: str,
    field_labels: list[tuple[str, str]] | None = None,
) -> str:
    if not table.strip():
        return ""
    if f'id="{table_id}"' not in table:
        table = table.replace("<table", f'<table id="{table_id}"', 1)
    english = label == _COPY["en"]["export"]
    hint = "Sort columns · Shift+click for multiple" if english else "点击列名排序 · Shift 点击多列"
    reset = "Original order" if english else "恢复原顺序"
    field_controls = ""
    if field_labels:
        options = "".join(
            f'<option value="{index}" data-field="{_esc(_slug(field))}">{_esc(title)}</option>'
            for index, (field, title) in enumerate(field_labels, start=1)
        )
        field_label = "Field" if english else "字段"
        export_label = "Export unique TXT" if english else "导出去重 TXT"
        field_controls = (
            f'<label class="column-picker">{field_label} <select id="{_esc(table_id)}-column">{options}</select></label>'
            f'<button type="button" class="export-column" data-target="{_esc(table_id)}" '
            f'data-select="{_esc(table_id)}-column">{export_label}</button>'
        )
    return (
        '<div class="table-block">'
        f'<p class="fine table-hint">{hint}</p>'
        '<div class="table-tools">'
        f'{field_controls}<button type="button" class="reset-order" data-reset="{_esc(table_id)}">{reset}</button>'
        f'<button type="button" class="export" data-target="{_esc(table_id)}" '
        f'data-filename="{_esc(filename)}">{_esc(label)}</button>'
        "</div>"
        f'<div class="table-wrap">{table}</div>'
        "</div>"
    )


def _linked_logo(name: str, alt: str) -> str:
    image = _img(name, "lockup", alt)
    if not image:
        return ""
    return f'<a class="logo-link" href="{_STUDIO_URL}" target="_blank" rel="noopener noreferrer">{image}</a>'


def _img(name: str, class_name: str, alt: str) -> str:
    src = _logo(name)
    if not src:
        return ""
    return f'<img class="{class_name}" src="{src}" alt="{_esc(alt)}">'


def _logo(name: str) -> str:
    cached = _LOGO_CACHE.get(name)
    if cached is not None:
        return cached
    path = Path(__file__).resolve().parent / "assets" / name
    if not path.is_file():
        _LOGO_CACHE[name] = ""
        return ""
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    _LOGO_CACHE[name] = f"data:image/png;base64,{encoded}"
    return _LOGO_CACHE[name]


def _slug(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_-]+", "-", value).strip("-").lower()
    return cleaned or "field"


_LOGO_CACHE: dict[str, str] = {}


def _evidence_slices(run: AgentRun, lang: str) -> list[tuple[str, int, str]]:
    evidence = run.evidence_counts or {}
    order = (
        ("precision", "#34c759"),
        ("balanced", "#ff9f0a"),
        ("hypothesis", "#ff375f"),
        ("recall", "#5e5ce6"),
    )
    slices = []
    for key, color in order:
        count = int(evidence.get(key, 0) or 0)
        if count:
            slices.append((_CONFIDENCE[lang][key][0], count, color))
    return slices


def _donut(slices: list[tuple[str, int, str]], *, center: str) -> str:
    total = sum(value for _name, value, _color in slices)
    radius = 46
    circ = 2 * math.pi * radius
    offset = 0.0
    rings: list[str] = []
    if total <= 0:
        rings.append(f'<circle cx="70" cy="70" r="{radius}" fill="none" stroke="#e6e8ee" stroke-width="14"/>')
    else:
        active = [item for item in slices if item[1] > 0]
        gap = 2.5 if len(active) > 1 else 0
        for name, value, color in active:
            length = max(circ * value / total - gap, 1)
            rings.append(
                f'<circle cx="70" cy="70" r="{radius}" fill="none" stroke="{color}" stroke-width="14" '
                f'stroke-dasharray="{length:.2f} {circ - length:.2f}" stroke-dashoffset="{(-offset):.2f}" '
                f'transform="rotate(-90 70 70)"><title>{_esc(name)} {_num(value)}</title></circle>'
            )
            offset += circ * value / total
    return (
        f'<svg class="donut" viewBox="0 0 140 140" role="img" aria-label="{_esc(center)}">'
        f"{''.join(rings)}"
        f'<text x="70" y="74" text-anchor="middle" fill="#1d1d1f" font-size="22" font-weight="600">{_num(total)}</text>'
        "</svg>"
    )


def _legend(slices: list[tuple[str, int, str]]) -> str:
    if not slices:
        return "<ul class='legend'><li><i style='background:#e6e8ee'></i>—</li></ul>"
    items = "".join(f"<li><i style='background:{color}'></i>{_esc(name)} <b>{_num(value)}</b></li>" for name, value, color in slices)
    return f"<ul class='legend'>{items}</ul>"


def _chart_card(title: str, body: str) -> str:
    return f'<article class="chart"><h3>{_esc(title)}</h3>{body}</article>'


def _bars(rows: list[tuple[str, int, str]]) -> str:
    peak = max((value for _label, value, _color in rows), default=0) or 1
    parts = []
    for label, value, color in rows:
        width = 0 if value <= 0 else max(3, round(value / peak * 100))
        parts.append(
            '<div class="bar-row">'
            f'<span class="bar-name">{_esc(label)}</span>'
            f'<span class="bar-track"><span class="bar-fill" style="width:{width}%;background:{color}"></span></span>'
            f'<span class="bar-num">{_num(value)}</span>'
            "</div>"
        )
    return "".join(parts)


def _colored(rows: list[tuple[str, int]]) -> list[tuple[str, int, str]]:
    return [(label, value, _PALETTE[index % len(_PALETTE)]) for index, (label, value) in enumerate(rows)]


def _chart_title(field: str, lang: str) -> str:
    return _CHART_TITLES.get(lang, _CHART_TITLES["zh"]).get(field, field)


def _alive_label(name: str, lang: str, text: dict[str, Any]) -> str:
    if name == "__other__":
        return str(text["other"])
    if str(name).startswith("Blocked"):
        return "已拦截" if lang == "zh" else "Blocked"
    return _ALIVE_LABELS.get(lang, _ALIVE_LABELS["zh"]).get(str(name), str(name))


def _chart_fields(run: AgentRun) -> list[str]:
    selected = {str(field) for field in (run.fields or [])}
    available = {str(field) for field in (getattr(run, "field_tallies", {}) or {})}
    for asset in run.assets:
        available.update(str(key) for key in asset)
    if any(asset.get("alive_status") not in (None, "") for asset in run.assets):
        available.add("alive_status")
    chosen: list[str] = []
    for field in _CHART_ORDER:
        has_values = field in available or (field == "domain" and "host" in available)
        if not has_values:
            continue
        if field == "alive_status" or not selected or field in selected or (field == "domain" and "host" in selected):
            chosen.append(field)
    return chosen


def _distribution(
    run: AgentRun,
    field: str,
    *,
    unknown: str,
    other: str,
    limit: int = 8,
) -> list[tuple[str, int]]:
    counts = dict((getattr(run, "field_tallies", {}) or {}).get(field) or {})
    if not counts:
        return _tally(run.assets, field, unknown=unknown, other=other, limit=limit)
    extra = int(counts.pop("__other__", 0) or 0)
    ranked = sorted(((name, count) for name, count in counts.items() if name), key=lambda item: (-item[1], item[0]))
    if not ranked:
        return [(other, extra)] if extra else []
    if len(ranked) <= limit and not extra:
        return ranked
    head = ranked[: limit - 1]
    rest = sum(count for _name, count in ranked[limit - 1 :]) + extra
    return [*head, (other, rest)]


def _conclusion(run: AgentRun, lang: str, text: dict[str, Any]) -> str:
    if not run.assets and not (getattr(run, "field_tallies", None) or {}):
        return ""
    visible, pulled, _reason = _coverage_facts(run)
    mode = _result_mode(run)
    sentences: list[str] = []
    if lang == "zh":
        if mode == "sample":
            sentences.append(f"本次为抽样，取回 {_num(pulled)} 条，主查询可见 {_num(visible)} 条。")
        elif mode == "full":
            sentences.append(f"本次取回 {_num(pulled)} 条，已覆盖主查询可见结果。")
        else:
            sentences.append(f"本次取回 {_num(pulled)} 条，主查询可见 {_num(visible)} 条。结论只统计取回记录。")
    elif mode == "sample":
        sentences.append(f"This is a sample of {_num(pulled)} rows. The primary query shows {_num(visible)}.")
    elif mode == "full":
        sentences.append(f"Retrieved {_num(pulled)} rows, covering the visible primary query.")
    else:
        sentences.append(
            f"Retrieved {_num(pulled)} rows. The primary query shows {_num(visible)}. The conclusion counts retrieved rows only."
        )
    mentioned = 0
    for field in ("domain", "port", "protocol", "server", "city", "country"):
        ranked = _distribution(run, field, unknown=text["unknown"], other=text["other"])
        if not ranked or ranked[0][0] in {text["other"], text["unknown"]}:
            continue
        name, count = ranked[0]
        title = _chart_title(field, lang)
        if lang == "zh":
            sentences.append(f"{title}里最多的是 {name}（{_num(count)} 条）。")
        else:
            sentences.append(f"Most common {title}: {name} ({_num(count)}).")
        mentioned += 1
        if mentioned >= 3:
            break
    alive = _distribution(run, "alive_status", unknown=text["unknown"], other=text["other"])
    if run.liveness:
        if run.liveness.get("enabled"):
            checked, responsive = run.liveness.get("checked", 0), run.liveness.get("responsive", 0)
            sentences.append(
                f"本轮新检测 {checked} 个目标，其中 {responsive} 个有响应。"
                if lang == "zh"
                else f"Fresh checks covered {checked} targets; {responsive} responded."
            )
        else:
            sentences.append("本轮未启用存活检测。" if lang == "zh" else "Liveness was not enabled for this run.")
    if alive:
        parts = [f"{_alive_label(name, lang, text)} {_num(count)}" for name, count in alive if name != text["other"]]
        if lang == "zh":
            sentences.append(f"存活检测：{'，'.join(parts)}。{text['alive_note']}")
        else:
            sentences.append(f"Alive check: {', '.join(parts)}. {text['alive_note']}")
    return "".join(sentences) if lang == "zh" else " ".join(sentences)


_SEVERITY_EN = {
    "critical": "Critical",
    "high": "High",
    "medium": "Medium",
    "low": "Low",
    "info": "Info",
    "unknown": "Unknown",
}


def _scan_advice_block(run: AgentRun, text: dict[str, Any]) -> str:
    advice = (run.scan_advice or "").strip()
    if not advice:
        return ""
    return f'<article class="note advice"><h3>{text["fix_h"]}</h3>{_markdown(advice)}</article>'


def _scan_findings(run: AgentRun, text: dict[str, Any], lang: str) -> str:
    advice = _scan_advice_block(run, text)
    artifact = str(run.scan_artifact or "")
    path = Path(artifact)
    if path.suffix != ".jsonl" or not path.is_file():
        return f'<div class="scan-findings">{advice}</div>' if advice else ""
    from core.scanner import SEVERITY_LABELS, load_nuclei_result

    try:
        result = load_nuclei_result(path, target_count=len(run.scan_targets))
    except OSError:
        return f'<div class="scan-findings">{advice}</div>' if advice else ""
    labels = SEVERITY_LABELS if lang == "zh" else _SEVERITY_EN
    counts = [(labels.get(name, name), count) for name, count in result.severity_counts.items()]
    chart = _chart_card(text["th_sev"], _bars(_colored(counts))) if counts else ""
    rows = []
    for hit in result.grouped()[:40]:
        rows.append(
            "<tr>"
            f'<td class="tight">{_esc(labels.get(hit.severity, hit.severity))}</td>'
            f"<td>{_esc(hit.target)}</td>"
            f"<td>{_esc(hit.name or hit.template_id)}<br><small>{_esc(hit.protocol or 'template-defined')}</small></td>"
            f"<td>{_detail_pills(hit.details, hit.count)}</td>"
            "</tr>"
        )
    if lang == "zh":
        headline = result.headline()
    elif result.findings:
        headline = (
            f"Scanned {result.loaded_targets or result.target_count} targets, "
            f"{len(result.findings)} findings across {result.host_count} sites."
        )
    else:
        headline = f"Scanned {result.loaded_targets or result.target_count} targets, no findings."
    warnings = "".join(f'<p class="warn">{_esc(warning)}</p>' for warning in result.warnings)
    if not result.completed:
        headline = result.headline() if lang == "zh" else f"Scan incomplete; {len(result.findings)} partial matches recorded."
    elif lang == "en" and result.warnings and not result.findings:
        headline = "No matches recorded; network/request anomalies make coverage inconclusive."
    table = ""
    if rows:
        table = _table_block(
            "<table><thead><tr>"
            f'<th class="tight">{text["th_sev"]}</th><th>{text["th_site"]}</th>'
            f"<th>{text['th_check']}</th><th>{text['th_detail']}</th>"
            f"</tr></thead><tbody>{''.join(rows)}</tbody></table>",
            label=text["export"],
            filename="fofamap-nuclei.csv",
            table_id="nuclei-table",
        )
    empty = "" if rows else f"<p>{text['findings_empty']}</p>"
    return f"""
<div class="scan-findings">
  {warnings}
  <h3>{text["findings_title"]}</h3>
  <p>{_esc(headline)}</p>
  {chart}
  {table}
  {empty}
  {advice}
  <p class="fine">{text["findings_note"]}</p>
</div>"""


def _detail_pills(details: tuple[str, ...], count: int) -> str:
    labels = tuple(item for item in details if item) or ((str(count),) if count else ())
    if not labels:
        return ""
    chips = "".join(f"<span>{_esc(item)}</span>" for item in labels)
    return f'<div class="pills">{chips}</div>'


def _tally(assets: list[dict[str, Any]], field: str, *, unknown: str, other: str, limit: int = 6) -> list[tuple[str, int]]:
    counts: dict[str, int] = {}
    for asset in assets:
        raw = asset.get(field)
        if isinstance(raw, list):
            raw = "、".join(str(item) for item in raw if item)
        text = str(raw or "").strip() or unknown
        counts[_trim(text, 28)] = counts.get(_trim(text, 28), 0) + 1
    ranked = sorted(counts.items(), key=lambda item: (-item[1], item[0]))
    if not ranked or (len(ranked) == 1 and ranked[0][0] == unknown):
        return []
    if len(ranked) <= limit:
        return ranked
    head = ranked[: limit - 1]
    rest = sum(count for _name, count in ranked[limit - 1 :])
    return [*head, (other, rest)]


def _strategy_tone(strategy: str) -> str:
    return {"precision": "high", "balanced": "mid", "hypothesis": "watch", "recall": "low"}.get(strategy, "mid")


def _trim(value: str, limit: int) -> str:
    text = " ".join(value.split())
    if len(text) <= limit:
        return text
    return text[: limit - 1] + "…"


def _model_event(run: AgentRun) -> dict[str, Any] | None:
    events = [event for event in run.route_events if event.get("model")]
    for event in events:
        if event.get("task") == "summarizer":
            return event
    return events[-1] if events else None


def _group_summary(summary: str) -> dict[str, str]:
    sections = _split_sections(summary)
    grouped: dict[str, list[str]] = {"analysis": [], "review": [], "advice": []}
    loose: list[str] = []
    for title, body in sections:
        key = _SECTION_GROUP.get(title)
        rendered = _markdown(body)
        block = f"<h4>{_inline(title)}</h4>{rendered}" if title else rendered
        if key:
            grouped[key].append(block)
        else:
            loose.append(block)
    if loose:
        grouped["analysis"] = loose + grouped["analysis"]
    return {key: "".join(value) for key, value in grouped.items() if value}


def _split_sections(summary: str) -> list[tuple[str, str]]:
    sections: list[tuple[str, str]] = []
    title = ""
    buffer: list[str] = []
    for line in summary.splitlines():
        if line.startswith("## "):
            if title or buffer:
                sections.append((title, "\n".join(buffer).strip()))
            title = line[3:].strip()
            buffer = []
        else:
            buffer.append(line)
    if title or any(line.strip() for line in buffer):
        sections.append((title, "\n".join(buffer).strip()))
    return sections


def _markdown(text: str) -> str:
    parts: list[str] = []
    lines = text.splitlines()
    index = 0
    while index < len(lines):
        line = lines[index].rstrip()
        if not line.strip():
            index += 1
            continue
        if line.startswith("### "):
            parts.append(f"<h4>{_inline(line[4:])}</h4>")
            index += 1
            continue
        if re.match(r"\d+\.\s+", line):
            items: list[str] = []
            while index < len(lines) and re.match(r"\d+\.\s+", lines[index]):
                items.append(re.sub(r"^\d+\.\s+", "", lines[index].strip()))
                index += 1
            parts.append("<ol>" + "".join(f"<li>{_inline(item)}</li>" for item in items) + "</ol>")
            continue
        if line.startswith("- "):
            items = []
            while index < len(lines) and lines[index].startswith("- "):
                items.append(lines[index][2:].strip())
                index += 1
            parts.append("<ul>" + "".join(f"<li>{_inline(item)}</li>" for item in items) + "</ul>")
            continue
        paragraph = [line.strip()]
        index += 1
        while index < len(lines) and lines[index].strip() and not _starts_block(lines[index]):
            paragraph.append(lines[index].strip())
            index += 1
        parts.append(f"<p>{_inline(' '.join(paragraph))}</p>")
    return "".join(parts) or "<p></p>"


def _starts_block(line: str) -> bool:
    return line.startswith(("- ", "### ", "## ")) or bool(re.match(r"\d+\.\s+", line))


def _inline(text: str) -> str:
    escaped = html.escape(text, quote=True)
    escaped = re.sub(r"`([^`]+)`", r"<code>\1</code>", escaped)
    escaped = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", escaped)
    return escaped


def _infer_fields(assets: list[dict[str, Any]]) -> list[str]:
    fields: list[str] = []
    for asset in assets:
        for key in asset:
            if key not in fields and key not in _SKIP_FIELDS:
                fields.append(key)
    return fields[:12]


def _cell(value: Any) -> str:
    if value in (None, "", [], {}):
        return "<span class='muted'>—</span>"
    text = str(value).replace("\r", " ").replace("\n", " ")
    if len(text) > 180:
        return f'<span data-export="{_esc(text)}" title="{_esc(text)}">{_esc(text[:177])}…</span>'
    return _esc(text)


def _label(table: dict[str, str], value: Any) -> str:
    text = "" if value is None else str(value)
    return table.get(text, text)


def _esc(value: Any) -> str:
    return html.escape("" if value is None else str(value), quote=True)


def _num(value: Any) -> str:
    if value in (None, ""):
        return "—"
    try:
        return f"{int(value):,}"
    except (TypeError, ValueError):
        return _esc(value)


CSS = """
:root {
  --text: #1d1d1f;
  --muted: #6e6e73;
  --line: #e3e6ee;
  --canvas: #e8edf5;
  --card: #fff;
  --blue: #0071e3;
  --ink: #0b1220;
  --sans: -apple-system, BlinkMacSystemFont, "SF Pro Text", "Helvetica Neue", sans-serif;
  --mono: "SF Mono", ui-monospace, Menlo, monospace;
}
* { box-sizing: border-box; }
html { scroll-behavior: smooth; scroll-padding-top: 88px; }
a:focus-visible, button:focus-visible, summary:focus-visible { outline: 3px solid var(--blue); outline-offset: 4px; }
section:target { animation: section-arrive .8s ease-out; }
@keyframes section-arrive { from { background-color: #edf5ff; } to { background-color: transparent; } }
body {
  margin: 0;
  color: var(--text);
  background:
    radial-gradient(880px 420px at 0% -10%, rgba(0, 113, 227, .22), transparent 58%),
    radial-gradient(720px 380px at 100% 0%, rgba(94, 92, 230, .18), transparent 55%),
    radial-gradient(640px 360px at 90% 100%, rgba(48, 176, 199, .16), transparent 50%),
    var(--canvas);
  font-family: var(--sans);
  font-size: 16px;
  line-height: 1.5;
  -webkit-font-smoothing: antialiased;
}
.skip { position: absolute; left: 16px; top: -40px; background: #fff; padding: 6px 10px; }
.skip:focus { top: 8px; }
.nav {
  position: sticky; top: 0; z-index: 20;
  background: rgba(255, 255, 255, .78);
  backdrop-filter: saturate(180%) blur(20px);
  border-bottom: 1px solid rgba(15, 23, 42, .08);
}
.nav-inner {
  width: min(1120px, calc(100% - 32px));
  margin: 0 auto; min-height: 54px;
  display: flex; align-items: center; gap: 18px;
}
.brand { display: flex; align-items: center; gap: 8px; color: var(--ink); font-weight: 700; letter-spacing: -.03em; text-decoration: none; }
.nav-mark { width: 22px; height: 28px; object-fit: contain; }
.letterhead {
  display: flex; align-items: flex-end; justify-content: space-between; gap: 24px;
  margin-bottom: 22px; padding-bottom: 16px; border-bottom: 1px solid var(--line);
}
.logo-link { display: inline-block; line-height: 0; }
.lockup { height: 148px; width: auto; display: block; }
.letterhead-side { text-align: right; }
.letterhead-side strong, .letterhead-side span { display: block; }
.letterhead-side strong { font-size: 20px; letter-spacing: -.03em; }
.letterhead-side span { margin-top: 2px; font-size: 15px; font-weight: 700; }
.letterhead-side a, .studio-lockup a { color: var(--blue); text-decoration: none; font-size: 13px; }
.letterhead-side a:hover, .studio-lockup a:hover { text-decoration: underline; }
.hero-grid { display: grid; grid-template-columns: minmax(0, 1.5fr) 280px; gap: 28px; align-items: center; }
.lead-note { margin: 0 0 12px; font-size: 16px; }
.scope-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
.scope-grid article, .boundary {
  padding: 14px 16px; border-radius: 16px; border: 1px solid var(--line);
  background: linear-gradient(180deg, #f8fbff, #fff 55%);
}
.scope-grid h3 { margin: 0 0 8px; font-size: 16px; }
.scope-grid ul { margin: 0; padding-left: 1.1rem; }
.scope-grid li { margin: 4px 0; font-size: 14px; }
.scope-grid .wide { grid-column: 1 / -1; }
.picks { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 10px; }
.pick { padding: 12px; border-radius: 14px; background: #fff; border: 1px solid var(--line); }
.pick strong, .pick em { display: block; }
.pick strong { margin-top: 8px; font-size: 13px; overflow-wrap: anywhere; }
.pick em { margin-top: 4px; color: var(--muted); font-style: normal; font-size: 12px; }
.boundary { margin-top: 12px; }
.coverage { background: linear-gradient(180deg, rgba(255, 159, 10, .12), #fff 55%); border-color: rgba(255, 159, 10, .28); }
.boundary strong { display: block; margin-bottom: 4px; }
.boundary p { margin: 0; font-size: 14px; }
.table-tools { display: flex; justify-content: flex-end; align-items: center; flex-wrap: wrap; gap: 8px; margin: 0 0 8px; }
.table-hint { margin: 0 0 8px; font-size: 12px; }
.column-picker { display: inline-flex; align-items: center; gap: 6px; font-size: 12px; color: var(--muted); }
.column-picker select { max-width: 180px; padding: 5px 8px; border: 1px solid var(--line); border-radius: 8px; background: #fff; }
.sort-column { border: 0; padding: 0; background: transparent; color: inherit; font: inherit; text-align: inherit; cursor: pointer; }
th[aria-sort="ascending"], th[aria-sort="descending"] { color: var(--blue); }
.export-column, .reset-order {
  border: 1px solid var(--line); border-radius: 999px; padding: 6px 12px;
  background: #fff; color: var(--text); font: inherit; font-size: 12px; cursor: pointer;
}
.export {
  border: 1px solid rgba(0, 113, 227, .28); background: #fff; color: var(--blue);
  border-radius: 999px; padding: 6px 12px; font: inherit; font-size: 12px; font-weight: 700; cursor: pointer;
}
.export:hover { background: #f3f8ff; }
.rail { display: flex; gap: 16px; flex: 1; }
.rail a, .studio, .lang { color: var(--text); text-decoration: none; font-size: 13px; }
.rail a:hover, .studio:hover, .lang:hover { color: var(--blue); }
.studio { font-weight: 600; }
.lang {
  border: 1px solid var(--line); border-radius: 999px; padding: 3px 10px;
  background: #fff;
}
.nav-meta { margin: 0; color: var(--muted); font-size: 12px; white-space: nowrap; }
.sheet {
  width: min(1080px, calc(100% - 32px));
  margin: 24px auto 56px;
  background: #fff;
  border-radius: 24px;
  box-shadow: 0 18px 50px rgba(15, 23, 42, .08);
  overflow: hidden;
}
.ribbon { height: 6px; background: linear-gradient(90deg, #0071e3, #5e5ce6 46%, #30b0c7 74%, #34c759); }
main { padding: 32px 44px 8px; }
.hero { padding: 0; }
.eyebrow, .kicker, .runid, .fine, .section-head p, .lede, .meta, .hero-chart p { color: var(--muted); }
.eyebrow { margin: 0 0 8px; font-size: 12px; font-weight: 700; letter-spacing: .08em; text-transform: uppercase; color: var(--blue); }
.hero h1 {
  margin: 0; max-width: 16em;
  font-size: clamp(32px, 4vw, 46px); font-weight: 700; letter-spacing: -.03em; line-height: 1.08;
}
.lede { max-width: 40rem; margin: 12px 0 0; font-size: 17px; line-height: 1.45; }
.meta { margin: 14px 0 0; font-size: 14px; }
.kicker { margin: 18px 0 8px; font-size: 12px; font-weight: 700; letter-spacing: .04em; }
.query {
  margin: 0; padding: 12px 14px; border-radius: 12px;
  background: #f4f7fb; border: 1px solid #e6ebf3;
  font-family: var(--mono); font-size: 12px; line-height: 1.55; overflow-wrap: anywhere;
}
.runid { margin: 8px 0 0; font-size: 12px; font-family: var(--mono); }
.hero-chart {
  padding: 14px 14px 10px; border-radius: 18px;
  background: linear-gradient(180deg, rgba(0, 113, 227, .08), rgba(94, 92, 230, .05));
  border: 1px solid rgba(0, 113, 227, .12);
}
.hero-chart p { margin: 0 0 4px; text-align: center; font-size: 12px; font-weight: 700; letter-spacing: .04em; }
.donut { width: 148px; height: 148px; display: block; margin: 0 auto; }
.legend { list-style: none; margin: 8px 0 0; padding: 0; display: flex; flex-wrap: wrap; gap: 6px 12px; justify-content: center; }
.legend li { font-size: 12px; color: var(--muted); display: flex; align-items: center; gap: 6px; }
.legend i { width: 8px; height: 8px; border-radius: 99px; display: inline-block; }
.legend b { color: var(--text); font-weight: 650; }
.readout { font-size: clamp(36px, 5vw, 64px); font-weight: 750; color: var(--blue); text-align: center; margin: 18px 0; }
.metrics { display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; margin-top: 22px; }
.metrics article {
  padding: 14px 16px 12px; border-radius: 16px;
  background: #f8fafc; border: 1px solid var(--line); border-top: 3px solid var(--accent);
}
.metrics p, .metrics span { margin: 0; color: var(--muted); font-size: 12px; }
.metrics strong {
  display: block; margin: 2px 0; color: var(--ink);
  font-size: 28px; font-weight: 700; letter-spacing: -.03em; font-variant-numeric: tabular-nums;
}
section { margin-top: 28px; padding-top: 22px; border-top: 1px solid var(--line); }
.hero, .metrics { margin-top: 0; padding-top: 0; border-top: none; }
.metrics { margin-top: 22px; }
.section-head { margin: 0 0 14px; }
.section-head h2 { margin: 0; font-size: 26px; font-weight: 700; letter-spacing: -.02em; }
.section-head p { margin: 4px 0 0; font-size: 14px; max-width: 42rem; }
.chart-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
#charts { display: flex; flex-direction: column; gap: 18px; }
#charts > .section-head { margin: 0; }
#charts > .note.analysis { margin: 0; padding: 18px 20px 16px; }
#charts .conclusion { margin: 10px 0 0; padding: 0; list-style: none; display: flex; flex-direction: column; gap: 8px; }
#charts .conclusion li { margin: 0; font-size: 15px; line-height: 1.65; }
.chart {
  padding: 14px 16px 10px; border-radius: 16px;
  background: linear-gradient(180deg, #f8fbff, #fff 48%);
  border: 1px solid var(--line);
}
.chart h3 { margin: 0 0 10px; font-size: 15px; font-weight: 700; }
.bar-row { display: grid; grid-template-columns: minmax(72px, 28%) 1fr auto; gap: 8px; align-items: center; margin: 7px 0; }
.bar-name, .bar-num { font-size: 12px; }
.bar-name { color: var(--text); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.bar-num { color: var(--muted); font-variant-numeric: tabular-nums; }
.bar-track { height: 8px; border-radius: 99px; background: #e8edf4; overflow: hidden; }
.bar-fill { display: block; height: 100%; border-radius: 99px; }
.notes { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
.note { border-radius: 16px; padding: 16px 18px 8px; border: 1px solid var(--line); }
.note.analysis { grid-column: 1 / -1; background: linear-gradient(180deg, rgba(0, 113, 227, .09), #fff 46%); }
.note.review { background: linear-gradient(180deg, rgba(94, 92, 230, .09), #fff 50%); }
.note.advice { background: linear-gradient(180deg, rgba(52, 199, 89, .12), #fff 50%); }
.note.empty { background: #f8fafc; }
.note h3 { margin: 0 0 8px; font-size: 20px; font-weight: 700; letter-spacing: -.02em; }
.note h4 { margin: 14px 0 4px; font-size: 15px; }
.note p, .note li { font-size: 15px; }
.note ol, .note ul { margin: 8px 0 0; padding-left: 1.15rem; }
.note li + li { margin-top: 6px; }
.note code, td code { font-family: var(--mono); font-size: .86em; overflow-wrap: anywhere; }
.fine { margin: 12px 0 0; font-size: 13px; color: var(--muted); }
.warn { color: #d70015; font-size: 15px; }
.filter { display: flex; align-items: center; gap: 10px; margin: 0 0 8px; font-size: 14px; color: var(--muted); }
.filter input {
  height: 36px; min-width: min(320px, 68vw); border: 1px solid var(--line); border-radius: 10px;
  background: #f4f7fb; color: var(--text); padding: 0 12px; font: inherit; font-size: 15px;
}
.filter input:focus { outline: 2px solid var(--blue); background: #fff; }
.table-wrap { max-height: 640px; overflow: auto; border: 1px solid var(--line); border-radius: 14px; }
table { width: 100%; border-collapse: collapse; font-size: 13px; }
th, td { padding: 10px 12px; border-bottom: 1px solid var(--line); text-align: left; vertical-align: top; }
th { color: var(--muted); font-size: 12px; font-weight: 700; background: #f6f8fc; }
tr:last-child td { border-bottom: none; }
tbody tr:hover td { background: #f8fbff; }
code { font-family: var(--mono); }
.tag { display: inline-block; border-radius: 999px; padding: 2px 8px; font-size: 12px; font-weight: 700; }
.tag.high { color: #1d7a32; background: rgba(52, 199, 89, .18); }
.tag.mid { color: #9a5b00; background: rgba(255, 159, 10, .2); }
.tag.watch { color: #c41e3a; background: rgba(255, 55, 95, .14); }
.tag.low { color: #4b45c6; background: rgba(94, 92, 230, .14); }
.muted { color: var(--muted); }
.facts { display: flex; flex-wrap: wrap; gap: 8px; list-style: none; margin: 0 0 12px; padding: 0; }
.facts li {
  background: #f4f7fb; border: 1px solid var(--line); border-radius: 999px;
  padding: 6px 12px; font-size: 13px; line-height: 1.35;
}
.section-head.scan-head { display: flex; align-items: center; justify-content: space-between; gap: 16px; margin-bottom: 16px; }
.section-head.scan-head h2 { margin: 0; }
#decision .facts { margin: 0; gap: 10px; }
#decision .artifact, #decision .scan-reason { margin: 14px 0 0; font-size: 14px; line-height: 1.5; }
#decision .artifact { color: var(--muted); overflow-wrap: anywhere; }
#decision .artifact code { font-size: 12px; }
.scan-findings { display: flex; flex-direction: column; gap: 16px; margin-top: 22px; }
.scan-findings > h3 { margin: 0; font-size: 20px; font-weight: 700; letter-spacing: -.02em; }
.scan-findings > p { margin: 0; line-height: 1.5; }
.scan-findings .table-block { display: flex; flex-direction: column; gap: 10px; }
.scan-findings .table-tools, .scan-findings .fine, .scan-findings .note { margin: 0; }
.scan-findings .note h3 { margin-bottom: 8px; }
th.tight, td.tight { white-space: nowrap; width: 1%; }
.pills { display: flex; flex-wrap: wrap; gap: 6px; }
.pills span {
  display: inline-block; padding: 3px 8px; border-radius: 999px;
  background: #f4f7fb; border: 1px solid var(--line); font-size: 12px; line-height: 1.4;
}
.timeline { margin-top: 16px; padding: 12px 16px; border-radius: 14px; background: #f6f8fc; border: 1px solid var(--line); }
.timeline summary { cursor: pointer; font-size: 15px; font-weight: 700; }
.timeline ol { margin: 10px 0 4px; padding-left: 1.2rem; }
.timeline li { margin: 7px 0; font-size: 14px; }
.timeline span { display: inline-block; min-width: 88px; margin-right: 8px; color: var(--blue); font-size: 12px; font-weight: 700; }
footer {
  margin: 8px 28px 28px; padding: 18px 20px 14px;
  border: 1px solid var(--line); border-radius: 18px;
  background: linear-gradient(180deg, #f7faff, #fff 48%);
  color: var(--muted); font-size: 12px;
}
.footer-brand { display: flex; align-items: center; gap: 14px; }
.footer-mark { width: 34px; height: 44px; object-fit: contain; flex: none; }
.footer-id strong, .footer-id span { display: block; }
.footer-id strong { color: var(--ink); font-size: 16px; letter-spacing: -.02em; }
.footer-id span { margin-top: 2px; color: var(--text); font-size: 13px; font-weight: 650; }
.footer-links { display: flex; gap: 8px; margin-left: auto; }
.footer-links a {
  color: var(--blue); text-decoration: none; font-size: 13px; font-weight: 650;
  border: 1px solid rgba(0, 113, 227, .22); border-radius: 999px; padding: 6px 12px; background: #fff;
}
.footer-links a:hover { background: #f3f8ff; }
.footer-line { margin: 14px 0 0; color: var(--text); font-size: 13px; }
.footer-meta {
  display: flex; justify-content: space-between; align-items: baseline; gap: 16px;
  margin-top: 12px; padding-top: 12px; border-top: 1px solid var(--line);
}
.footer-meta p { margin: 0; line-height: 1.5; }
.studio-lockup { display: flex; gap: 16px; align-items: center; margin-bottom: 12px; color: var(--text); }
.studio-lockup .lockup { height: 108px; }
.studio-lockup strong, .studio-lockup span { display: block; }
.studio-lockup strong { font-size: 16px; }
.studio-lockup span { margin: 2px 0 4px; font-weight: 700; }
.studio-lockup p { margin: 4px 0 0; }
@media (max-width: 860px) {
  main { padding: 24px 20px 8px; }
  footer { margin: 16px; }
  .footer-brand, .footer-meta { flex-wrap: wrap; }
  .footer-links { margin-left: 0; }
  .hero-grid, .chart-grid, .notes, .metrics, .scope-grid, .picks { grid-template-columns: 1fr; }
  .letterhead { align-items: flex-start; flex-direction: column; }
  .letterhead-side { text-align: left; }
  .lockup { height: 112px; }
  .rail { display: none; }
  .hero h1 { font-size: 30px; }
  .sheet { width: min(100% - 16px, 1080px); border-radius: 18px; }
}
@media (prefers-reduced-motion: reduce) { html { scroll-behavior: auto; } section:target { animation: none; } }
@media print {
  .nav, .filter, .table-tools, .table-hint { display: none; }
  .table-wrap { max-height: none; overflow: visible; border-radius: 0; }
  tr, .chart, .metrics article { break-inside: avoid; }
  thead { display: table-header-group; }
  body { background: #fff; }
  .sheet { box-shadow: none; margin: 0; width: auto; }
}
"""
