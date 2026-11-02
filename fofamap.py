"""FofaMap 命令行：完整保留 2.0 交互模型，面向人工操作。"""

from __future__ import annotations

import asyncio
import inspect
import ipaddress
import json
import os
import re
import secrets
import subprocess
import sys
import time
from collections.abc import AsyncIterator
from contextlib import nullcontext
from datetime import datetime
from pathlib import Path
from typing import Any

import rich_click as click
import yaml
from rich.live import Live
from rich.text import Text

from config import config_write_path, load_config, settings
from core.client import FofaClient
from core.exporter import StreamingXlsxWorkbook, export_pages, records_to_pages
from core.fields import field_catalog
from core.models import AssetRecord, FofaError, SearchPage, SearchRequest
from core.research import build_search_context
from core.showcase import SHOWCASE_PROMPTS, showcase_for
from core.version import VERSION
from utils.cli_ui import (
    build_agent_progress,
    build_nuclei_progress,
    console,
    print_banner,
    render_account,
    render_agent,
    render_deep_search,
    render_error,
    render_host,
    render_nuclei_results,
    render_query_overview,
    render_run_switches,
    render_run_usage,
    render_scan_approval,
    render_search_page,
    render_search_summary,
    render_stats,
    section,
)
from utils.helpers import FastChecker, IconHashCalculator, asset_probe_target, insert_alive_status_field
from utils.i18n import language, set_language, t
from utils.logger import logger

set_language(settings.system.language)

click.rich_click.TEXT_MARKUP = "rich"
click.rich_click.OPTIONS_PANEL_TITLE = "选项"
click.rich_click.ARGUMENTS_PANEL_TITLE = "参数"
click.rich_click.COMMANDS_PANEL_TITLE = "命令"
click.rich_click.ERRORS_PANEL_TITLE = "错误"
click.rich_click.ABORTED_TEXT = "已中止。"
_OPTION_GROUPS = [
    {
        "name": "🤖 智能体集成",
        "options": [
            "--agent",
            "--scope",
            "--list",
            "--uninstall",
            "--dry-run",
            "--server-command",
            "--project-root",
            "--force",
        ],
    },
    {
        "name": "🔮 查询与分析",
        "options": [
            "--ai-query",
            "--query",
            "--host-query",
            "--count-query",
            "--icon-query",
            "--icon-file",
            "--bat-query",
            "--rule",
        ],
    },
    {
        "name": "⚙️ 范围、字段与过滤",
        "options": [
            "--query-fields",
            "--smart-fields",
            "--pages",
            "--size",
            "--max-records",
            "--batch-group-size",
            "--full",
            "--dedupe-by",
            "--key-word",
            "--include",
            "--check-alive",
        ],
    },
    {
        "name": "💾 显示与导出",
        "options": [
            "--outfile",
            "--outdir",
            "--export-format",
            "--save",
            "--display-rows",
            "--output-format",
            "--json",
        ],
    },
    {
        "name": "🛡️ 扫描、报告与兼容",
        "options": [
            "--nuclei",
            "--nuclei-id",
            "--severity",
            "--scan-max-targets",
            "--report",
            "--report-file",
            "--batch",
            "--update",
            "--update-nuclei",
            "--help",
        ],
    },
]
click.rich_click.OPTION_GROUPS = {"fofamap.py": _OPTION_GROUPS, "fofamap": _OPTION_GROUPS}


_SUPPORT_LABELS = {
    "native": "原生",
    "compatibility": "兼容层",
    "tools-only": "仅工具",
    "compatible-bundle": "兼容包",
    "claude-compatible-plugin": "Claude 兼容插件",
    "native-plugin": "原生插件",
}
_SCOPE_LABELS = {"user": "用户级", "project": "项目级"}


def _support_label(value: str) -> str:
    return _SUPPORT_LABELS.get(value, value)


def _fields(value: str | None) -> list[str]:
    return [item.strip() for item in (value or settings.search.fields).split(",") if item.strip()]


def _deep_search_enabled(options: dict[str, Any]) -> bool:
    if not options.get("ai_query"):
        return False
    override = options.get("deepseek_search")
    if override is not None:
        return bool(override)
    provider = settings.providers.get("deepseek")
    return bool(provider and provider.search_enabled)


def _run_switch_flags(options: dict[str, Any]) -> dict[str, bool]:
    from core.agent import user_authorized_scan

    requested = user_authorized_scan(str(options.get("ai_query") or ""))
    return {
        "ai": bool(options.get("ai_query")),
        "check_alive": bool(options.get("check_alive")),
        "deep_search": _deep_search_enabled(options),
        "smart_fields": _use_smart_fields(options),
        "nuclei": bool(options.get("nuclei")) or requested,
        "scan_ai_dedupe": (bool(options.get("nuclei")) or requested) and (
            settings.system.scan_ai_dedupe if options.get("scan_ai_dedupe") is None else bool(options["scan_ai_dedupe"])
        ),
    }


def _use_smart_fields(options: dict[str, Any]) -> bool:
    if options.get("smart_fields") is True:
        return True
    if options.get("smart_fields") is False:
        return False
    if options.get("query_fields"):
        return False
    return bool(options.get("ai_query")) or settings.search.smart_fields


def _has_task(options: dict[str, Any]) -> bool:
    return bool(
        options.get("cmd")
        or options.get("query")
        or options.get("host_query")
        or options.get("count_query")
        or options.get("ai_query")
        or options.get("icon_query")
        or options.get("icon_file")
        or options.get("bat_query")
        or options.get("init_mode")
        or options.get("update")
        or options.get("update_nuclei")
        or options.get("setup_if_needed")
        or options.get("setup")
    )


AGENT_PROMPT_EXAMPLES: tuple[str, ...] = SHOWCASE_PROMPTS
AGENT_PROMPT_EXAMPLES_EN: tuple[str, ...] = (
    "Find Hikvision cameras in Guangzhou and count the ports",
    "Count Redis ports in Hefei",
    "Profile the host 203.0.113.10",
)


def _random_prompt_example(examples: tuple[str, ...] = AGENT_PROMPT_EXAMPLES) -> str:
    import random

    if language() == "en":
        return f"For example: {random.choice(AGENT_PROMPT_EXAMPLES_EN)}"
    return f"例如：{random.choice(examples)}"


def _wizard(options: dict[str, Any]) -> dict[str, Any] | None:
    """Restore the 2.0 arrow-key wizard while keeping the current safety settings."""
    from questionary import Choice, Separator, Style

    from utils import prompts as questionary

    hint_style = Style([("instruction", "fg:#8b93a7 italic nobold")])

    section(
        t("FofaMap 智能向导", "FofaMap wizard"),
        t("方向键选择，回车确认  ·  Esc / Ctrl+C 返回上一级", "Arrow keys to move, Enter to confirm  ·  Esc / Ctrl+C: back"),
    )
    while True:
        mode = questionary.select(
            t("请选择要执行的操作：", "Choose an action:"),
            choices=[
                Separator(t("── 资产查询 ──", "── Asset discovery ──")),
                Choice(t("1. AI 任务助手      自然语言查询、分析、报告", "1. AI task assistant     Ask, analyze and report"), "agent"),
                Choice(t("2. 资产搜索         输入 FOFA 查询语法", "2. Asset search          Enter FOFA query syntax"), "search"),
                Choice(
                    t("3. 主机详情         查看 IP / 域名及开放服务", "3. Host details          Inspect a host and its services"), "host"
                ),
                Choice(t("4. 分布统计         按端口、地区等汇总", "4. Distribution          Aggregate ports, regions and more"), "stats"),
                Choice(t("5. 更多查询方式     批量查询 / 网站图标反查", "5. More search methods   Batch queries / favicon search"), "more"),
                Separator(t("── 任务与工具 ──", "── Tasks and tools ──")),
                Choice(
                    t("6. 计划任务         创建、运行记录和报告", "6. Scheduled tasks       Create tasks, history and reports"), "schedule"
                ),
                Choice(
                    t("7. 查询参考         应用指纹 / 返回字段", "7. Query reference       App fingerprints / return fields"), "reference"
                ),
                Choice(
                    t("8. 设置与维护       账号 / 模型 / 偏好 / 更新", "8. Settings              Account / models / preferences / updates"),
                    "settings",
                ),
                Choice(t("0. 退出", "0. Exit"), "exit"),
            ],
            qmark="›",
            pointer="❯",
            show_back=False,
        ).ask()
        if mode not in {"more", "reference", "settings"}:
            break
        groups = {
            "more": (
                t("更多查询方式", "More search methods"),
                [
                    Choice(t("批量查询       从 TXT 文件读取查询语句", "Batch queries       Read queries from a TXT file"), "batch"),
                    Choice(t("网站图标反查   根据 favicon 查找相似资产", "Favicon search      Find assets sharing an icon"), "icon"),
                ],
            ),
            "reference": (
                t("查询参考", "Query reference"),
                [
                    Choice(t("应用指纹规则库   选取官方 app= 规则", "App fingerprints    Choose an official app= rule"), "rules"),
                    Choice(
                        t("返回字段说明     查询字段、用途与会员权限", "Return fields       Field meanings and membership limits"), "fields"
                    ),
                ],
            ),
            "settings": (
                t("设置与维护", "Settings and maintenance"),
                [
                    Separator(t("── 账号与模型 ──", "── Account and models ──")),
                    Choice(t("FOFA 账号与密钥   修改邮箱 / API Key", "FOFA credentials    Edit email / API key"), "credentials"),
                    Choice(
                        t("AI 模型配置       DeepSeek 推荐 / 切换提供商", "AI model setup      DeepSeek recommended / providers"),
                        "provider",
                    ),
                    Choice(t("账号状态          会员、权限与可用额度", "Account status      Membership, permissions and quota"), "account"),
                    Choice(
                        t("模型状态          已保存的接口与实时模型列表", "Model status        Saved endpoints and live catalogs"), "models"
                    ),
                    Separator(t("── 偏好与维护 ──", "── Preferences and maintenance ──")),
                    Choice(t("界面语言 / Language    中文 / English", "Interface language      English / 中文"), "language"),
                    Choice(
                        t("返回字段          智能选择 / 固定字段", "Returned fields     Smart / fixed fields"), "field_preferences"
                    ),
                    Choice(
                        t("使用偏好          存活检测、查询与导出", "Preferences         Alive checks, search and exports"), "preferences"
                    ),
                    Choice(t("配置引导          重新设置账号与模型", "Setup guide         Configure account and models"), "setup"),
                    Choice(
                        t("高级初始化        语言、账号和全部默认选项", "Advanced setup      Language, credentials and defaults"), "init"
                    ),
                    Choice(
                        t("检查 FofaMap 更新 从 GitHub 安装正式新版", "Update FofaMap      Install the latest stable release"), "update_app"
                    ),
                    Choice(
                        t("Nuclei 组件       检查安装 / 更新引擎与模板", "Nuclei component    Install/update engine and templates"),
                        "update_nuclei",
                    ),
                ],
            ),
        }
        title, choices = groups[mode]
        section(title)
        selected = questionary.select(t("请选择：", "Choose:"), choices=choices, qmark="›", pointer="❯").ask()
        if selected is None:
            continue
        mode = selected
        break
    if not mode or mode == "exit":
        console.print(f"[dim]{t('已退出。', 'Exited.')}[/]")
        return None
    if mode == "schedule":
        options.update(cmd="schedule", schedule_action="menu")
        return options
    if mode in {"setup", "update_app", "update_nuclei"}:
        options["cmd"] = mode
        return options
    if mode in {"account", "fields", "init", "models", "credentials", "provider", "preferences", "language", "field_preferences"}:
        options["cmd"] = mode
        return options
    options["_wizard_choice_made"] = True
    if mode == "rules":
        from core.rules import search_rules

        keyword = questionary.text(
            t(
                "搜索规则库（应用 / OA / 中间件，回车列出常用）：",
                "Search the rule library (app, OA, middleware; Enter lists common rules):",
            ),
            default="",
        ).ask()
        if keyword is None:
            return None
        matches = search_rules(keyword or "", limit=80)
        if not matches:
            console.print(
                f"[yellow]{t('没有匹配的内置规则。完整规则列表：', 'No bundled rule matched. Full list: ')}https://fofa.info/library[/]"
            )
            return None
        picked = questionary.select(
            t("选择一条官方 app= 规则：", "Choose an official app= rule:"),
            choices=[Choice(f"{rule.category} · {rule.name}    {rule.query}", rule.query) for rule in matches],
            qmark="›",
            pointer="❯",
        ).ask()
        if not picked:
            return None
        options["query"] = picked
        mode = "search"
    else:
        prompts = {
            "agent": (
                "ai_query",
                t("请描述需求：", "Describe your request:"),
                _random_prompt_example(),
            ),
            "search": (
                "query",
                t("请输入 FOFA 查询语法：", "FOFA query:"),
                t('例如：app="nginx" && country="CN"', 'For example: app="nginx" && country="CN"'),
            ),
            "host": ("host_query", t("请输入 IP 或域名：", "IP or domain:"), t("例如：8.8.8.8", "For example: 8.8.8.8")),
            "stats": ("count_query", t("请输入统计查询语法：", "Statistics query:"), t('例如：app="redis"', 'For example: app="redis"')),
            "icon": (
                "icon_query",
                t("请输入网站 URL：", "Website URL:"),
                t("例如：https://example.com", "For example: https://example.com"),
            ),
            "batch": (
                "bat_query",
                t("请输入批量查询 TXT 文件路径：", "Path to a batch query TXT file:"),
                t("每行一条 FOFA 查询语句", "One FOFA query per line"),
            ),
        }
        key, message, instruction = prompts[mode]
        if key == "ai_query":
            instruction = instruction.strip()
        value = questionary.text(message, instruction=instruction, style=hint_style, validate=lambda text: bool(text.strip())).ask()
        if not value:
            return None
        options[key] = value.strip()
    if mode in {"search", "agent", "icon", "batch"}:
        pages_text = questionary.text(
            t("最大查询页数：", "Maximum pages:"),
            default=str(settings.search.end_page),
            validate=lambda text: text.isdigit() and int(text) > 0,
        ).ask()
        if not pages_text:
            return None
        options["pages"] = int(pages_text)
        field_mode = questionary.select(
            t("本次返回字段：", "Fields for this query:"),
            choices=[
                Choice(
                    t("智能选择（按账号等级和任务自动挑选，无需模型）", "Smart selection (membership + task; no model needed)"), "smart"
                ),
                Choice(t("使用默认固定字段", "Use configured fixed fields"), "default"),
                Choice(t("手动指定本次字段", "Choose fields for this query"), "manual"),
            ],
            default="smart" if _use_smart_fields(options) else "default",
            qmark="›", pointer="❯",
        ).ask()
        if field_mode is None:
            return None
        options["smart_fields"] = field_mode == "smart"
        if field_mode == "manual":
            fields_value = questionary.text(t("返回字段：", "Returned fields:"), default=settings.search.fields).ask()
            if not fields_value:
                return None
            options["query_fields"] = fields_value
        advanced = questionary.confirm(
            t("是否调整历史数据和导出选项？", "Adjust historical data and export options?"),
            default=False,
        ).ask()
        if advanced is None:
            return None
        if advanced:
            full_value = questionary.confirm(t("查询 FOFA 历史数据？", "Include FOFA historical data?"), default=settings.search.full).ask()
            if full_value is None:
                return None
            options["full"] = full_value
            save_value = questionary.confirm(t("自动保存完整结果？", "Save the full result automatically?"), default=True).ask()
            if save_value is None:
                return None
            options["save"] = save_value
            if options["save"]:
                export_format = questionary.select(
                    t("导出格式：", "Export format:"), choices=["xlsx", "csv", "jsonl"], default=settings.system.export_format
                ).ask()
                if not export_format:
                    return None
                options["export_format"] = export_format
    if mode == "stats":
        stats_fields = questionary.text(t("统计维度：", "Statistic dimensions:"), default="country,port,org").ask()
        if not stats_fields:
            return None
        options["query_fields"] = stats_fields
    if mode in {"search", "icon", "batch"}:
        nuclei = questionary.confirm(t("是否同步开启 Nuclei 漏洞扫描？", "Also prepare a Nuclei scan?"), default=False).ask()
        if nuclei is None:
            return None
        if nuclei:
            options["nuclei"] = True
    if mode == "agent" and options.get("smart_fields") is None:
        options["smart_fields"] = True
    return options


def _local_yaml_security_notice() -> str:
    if os.name == "nt":
        return t("Windows 依赖当前用户目录 ACL，无法用 POSIX 0600 表示；建议优先使用系统钥匙串或环境变量",
                 "Windows uses your account directory permissions; prefer the system keychain or environment variables")
    return t("文件将设置为仅当前用户可读写（0600）", "Only the current user may read/write this file (0600)")


_SECRET_FIELD_NAMES = {"api_key", "key", "token", "secret", "password"}
_SETTINGS_ACTIONS = {
    "init", "credentials", "provider", "preferences", "setup", "language", "field_preferences", "update_app", "update_nuclei"
}


def _contains_secret(value: Any) -> bool:
    if isinstance(value, dict):
        return any(str(name).lower() in _SECRET_FIELD_NAMES or _contains_secret(item) for name, item in value.items())
    if isinstance(value, list):
        return any(_contains_secret(item) for item in value)
    return False


def _save_setup_config(path: Path, data: dict[str, Any], *, allow_secrets: bool = False) -> None:
    """Persist setup data, requiring explicit opt-in before writing credentials."""
    if _contains_secret(data) and not allow_secrets:
        raise ValueError("配置文件不得包含密钥；请使用环境变量、系统钥匙串或容器密钥")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")
    if os.name != "nt":
        path.chmod(0o600)


def _store_keyring(service: str, username: str, secret: str) -> bool:
    if not secret:
        return True
    try:
        import keyring

        keyring.set_password(service, username, secret)
        return True
    except Exception:
        return False


def _keyring_unavailable_reason() -> str:
    try:
        import keyring
    except ModuleNotFoundError:
        return (
            f"当前 Python 未安装 keyring：{sys.executable}。可运行 `"
            f"{sys.executable} -m pip install keyring`，或使用项目 `.venv/bin/python`。"
        )
    except Exception as exc:
        return f"无法加载系统钥匙串：{type(exc).__name__}: {exc}"
    try:
        backend = keyring.get_keyring()
        backend_name = f"{backend.__class__.__module__}.{backend.__class__.__name__}"
        return f"钥匙串后端 {backend_name} 未能保存密钥；请检查系统钥匙串权限或解锁状态。"
    except Exception as exc:
        return f"无法初始化钥匙串后端：{type(exc).__name__}: {exc}"


def _model_choice_label(item: dict[str, Any]) -> str:
    parts = [str(item.get("id") or "")]
    if item.get("context_window"):
        parts.append(f"上下文 {item['context_window']}")
    if item.get("max_output_tokens"):
        parts.append(f"最大输出 {item['max_output_tokens']}")
    if item.get("effort"):
        parts.append("思考 " + "/".join(str(level) for level in item["effort"]))
    elif item.get("thinking"):
        parts.append("可开关思考")
    if item.get("vision"):
        parts.append("多模态")
    return " · ".join(parts)


def _discover_models_for_setup(
    protocol: str,
    base_url: str,
    api_key_env: str,
    api_key: str,
    credential_kind: str,
) -> list[dict[str, Any]]:
    from config import ProviderProfile
    from providers.http import HttpModelProvider

    async def _load() -> list[dict[str, Any]]:
        profile = ProviderProfile(
            protocol=protocol,
            base_url=base_url,
            api_key_env=api_key_env,
            credential_kind=credential_kind if credential_kind in {"api_key", "none"} else "api_key",
            runtime_api_key=api_key,
        )
        provider = HttpModelProvider("setup", profile, execution_mode="interactive")
        try:
            return await provider.discover_catalog()
        finally:
            await provider.aclose()

    try:
        return asyncio.run(_load())
    except Exception as exc:
        console.print(f"[yellow]暂时无法获取模型列表：{exc}。可以继续手填模型 ID。[/]")
        return []


def _ask_thinking_mode(questionary: Any, selected: dict[str, Any]) -> str | None:
    """Return disabled, a published effort, or an empty string when the model has no thinking control.

    None means the user cancelled the prompt.
    """
    from questionary import Choice

    levels = [str(level).strip() for level in selected.get("effort") or [] if str(level).strip()]
    if levels:
        required = bool(selected.get("thinking_required"))
        message = (
            t("该模型始终开启思考，请选择强度。", "This model always reasons. Choose its effort.")
            if required else t("思考模式。关闭后直接作答；其余档位按接口公布的强度思考。",
                               "Thinking mode. Off answers directly; other levels use the effort published by the API.")
        )
        return questionary.select(
            message,
            choices=[*([Choice(t("关闭", "Off"), "disabled")] if not required else []), *[Choice(level, level) for level in levels]],
            default=levels[0] if required else "disabled",
        ).ask()
    if selected.get("thinking"):
        enabled = questionary.confirm(
            t(
                "开启思考模式？关闭后模型直接作答，不输出思考过程。",
                "Enable thinking mode? Off answers directly and does not emit a reasoning trace.",
            ),
            default=False,
        ).ask()
        if enabled is None:
            return None
        return "enabled" if enabled else "disabled"
    return ""


def _ask_interface_language(questionary: Any) -> str | None:
    """Ask before the rest of setup so later prompts follow the choice. Default is Chinese."""
    from questionary import Choice

    selected = questionary.select(
        "界面语言 / Interface language:",
        choices=[Choice("中文", "zh"), Choice("English", "en")],
        default=settings.system.language if settings.system.language in {"zh", "en"} else "zh",
    ).ask()
    if selected is None:
        return None
    return set_language(selected)


def _interactive_init() -> int:
    """安全初始化向导：优先系统钥匙串，明确确认后才写入 YAML。"""
    from questionary import Choice

    from utils import prompts as questionary

    interface_language = _ask_interface_language(questionary)
    if interface_language is None:
        return 130
    section(
        t("FofaMap 安全初始化向导", "FofaMap setup"),
        t("优先系统钥匙串，可确认写入本地 YAML", "Prefer the system keychain; write local YAML only after confirmation"),
    )
    email = questionary.text(
        t("FOFA 邮箱（当前接口可选）：", "FOFA email (optional for the current API):"),
        default=settings.fofa.email,
    ).ask()
    if email is None:
        return 130
    key = questionary.password(
        t("FOFA API 密钥（优先保存到系统钥匙串）：", "FOFA API key (saved to the system keychain when possible):")
    ).ask()
    if key is None:
        return 130
    provider_name = questionary.select(
        t("选择 AI 提供商（普通命令行查询不需要 AI）：", "AI provider (a plain FOFA query does not need one):"),
        choices=[
            Choice(t("DeepSeek（推荐）", "DeepSeek (Recommended)"), "deepseek"),
            Choice("ChatGPT / OpenAI", "openai"),
            Choice("Claude / Anthropic", "anthropic"),
            Choice("Grok / xAI", "xai"),
            Choice("Gemini", "gemini"),
            Choice("Kimi / Moonshot", "kimi"),
            Choice("MiniMax", "minimax"),
            Choice("小米 MiMo", "mimo"),
            Choice("硅基流动 SiliconFlow", "siliconflow"),
            Choice("智谱", "zhipu"),
            Choice(t("Ollama 本地模型", "Ollama local model"), "ollama"),
            Choice(t("LM Studio 本地模型", "LM Studio local model"), "lmstudio"),
            Choice(t("自定义 OpenAI 兼容接口", "Custom OpenAI-compatible API"), "custom"),
            Choice(t("暂不配置 AI", "Skip AI for now"), ""),
        ],
    ).ask()
    if provider_name is None:
        return 130
    from providers.registry import MODEL_PRESETS

    presets = {
        name: (
            spec["protocol"],
            spec["base_url"],
            (spec.get("models") or [""])[0],
            spec.get("api_key_env") or "",
            "none" if spec["protocol"] in {"ollama_native"} or name in {"ollama", "lmstudio"} else "api_key",
        )
        for name, spec in MODEL_PRESETS.items()
    }
    presets["custom"] = ("openai_chat", "https://api.example.com/v1", "", "CUSTOM_MODEL_API_KEY", "api_key")
    providers: dict[str, Any] = {}
    routing: dict[str, Any] = {
        "default": "",
        "planner": "",
        "query_repair": "",
        "reflector": "",
        "summarizer": "",
        "allow_cross_provider_fallback": False,
        "fallbacks": [],
    }
    provider_key = ""
    provider_key_env = ""
    if provider_name:
        protocol, default_url, default_model, provider_key_env, credential_kind = presets[provider_name]
        if provider_name == "custom":
            protocol = questionary.select(
                t("接口协议：", "API protocol:"),
                choices=["openai_chat", "openai_responses", "anthropic_messages", "ollama_native"],
                default=protocol,
            ).ask()
            if protocol is None:
                return 130
        base_url = questionary.text(t("接口地址：", "API address:"), default=default_url).ask()
        if base_url is None:
            return 130
        if credential_kind != "none":
            provider_key = (
                questionary.password(
                    t(
                        f"{provider_name} API 密钥（优先保存到系统钥匙串，可留空）：",
                        f"{provider_name} API key (keychain first, may be left empty):",
                    )
                ).ask()
                or ""
            )
        fetch_models = questionary.confirm(
            t("从接口获取可用模型，再选择模型和能力？", "Fetch models from the API, then choose a model and its capabilities?"),
            default=True,
        ).ask()
        if fetch_models is None:
            return 130
        catalog: list[dict[str, Any]] = []
        if fetch_models:
            catalog = _discover_models_for_setup(protocol, base_url, provider_key_env, provider_key, credential_kind)
        selected: dict[str, Any] = {}
        max_output_tokens = 32768
        if catalog:
            picked = questionary.select(
                t("选择模型（名称和参数来自接口）：", "Choose a model (names and limits come from the API):"),
                choices=[Choice(_model_choice_label(item), item["id"]) for item in catalog],
                default=default_model if any(item["id"] == default_model for item in catalog) else catalog[0]["id"],
            ).ask()
            if picked is None:
                return 130
            model = picked
            selected = next(item for item in catalog if item["id"] == model)
            if isinstance(selected.get("max_output_tokens"), int) and selected["max_output_tokens"] > 0:
                max_output_tokens = min(int(selected["max_output_tokens"]), 524288)
        else:
            model = questionary.text(
                t("模型 ID（可填任意未来模型）：", "Model ID (any current or future model):"),
                default=default_model,
            ).ask()
            if model is None:
                return 130
        from providers.registry import preset_model_traits

        selected = {**preset_model_traits(model), **selected}
        reasoning_effort = _ask_thinking_mode(questionary, selected)
        if reasoning_effort is None:
            return 130
        if not reasoning_effort:
            reasoning_effort = None
        vision_enabled = False
        if selected.get("vision"):
            vision_choice = questionary.confirm(
                t(
                    "该模型支持多模态输入。是否开启？开启后发送图标或截图时会附带图像，资产查询仍只提交文本。关闭后只发送文本。",
                    "This model accepts images. Icons and screenshots are sent as images; "
                    "asset queries stay text-only. Off sends text only.",
                ),
                default=False,
            ).ask()
            if vision_choice is None:
                return 130
            vision_enabled = bool(vision_choice)
        search_enabled = False
        if provider_name == "deepseek":
            search_choice = questionary.confirm(
                t(
                    "开启 DeepSeek Search？关闭后只使用对话模型，不调用网页检索。之后可在向导的「修改模型」里改。",
                    "Enable DeepSeek Search? Off uses the chat model only. Change it later from Change models in the wizard.",
                ),
                default=False,
            ).ask()
            if search_choice is None:
                return 130
            search_enabled = bool(search_choice)
        providers[provider_name] = {
            "protocol": protocol,
            "base_url": base_url,
            "model": model,
            "api_key_env": provider_key_env,
            "credential_kind": credential_kind,
            "structured_output_mode": "prompt" if provider_name == "deepseek" else "auto",
            "search_enabled": search_enabled,
            "reasoning_effort": reasoning_effort,
            "vision_enabled": vision_enabled,
            "max_output_tokens": max_output_tokens,
            "timeout": 120,
        }
        routing.update(
            {
                "default": provider_name,
                "planner": provider_name,
                "query_repair": provider_name,
                "reflector": provider_name,
                "summarizer": provider_name,
            }
        )
    fields = questionary.text(t("默认返回字段：", "Default returned fields:"), default=settings.search.fields).ask()
    size_text = questionary.text(
        t("每页结果数：", "Rows per page:"),
        default=str(settings.search.size),
        validate=lambda value: value.isdigit() and 1 <= int(value) <= 10_000,
    ).ask()
    pages_text = questionary.text(
        t("默认查询页数：", "Default page count:"),
        default=str(settings.search.end_page),
        validate=lambda value: value.isdigit() and 1 <= int(value) <= 10_000,
    ).ask()
    export_format = questionary.select(
        t("默认导出格式：", "Default export format:"),
        choices=["xlsx", "csv", "jsonl"],
        default="xlsx",
    ).ask()
    if fields is None or size_text is None or pages_text is None or export_format is None:
        return 130
    full = questionary.confirm(
        t("是否默认搜索全部历史数据？", "Search all historical data by default?"),
        default=settings.search.full,
    ).ask()
    if full is None:
        return 130
    check_alive = questionary.confirm(
        t("是否默认开启存活检测？", "Turn on alive checks by default?"),
        default=settings.fast_check.check_alive,
    ).ask()
    if check_alive is None:
        return 130
    timeout_text = str(settings.fast_check.timeout)
    if check_alive:
        timeout_text = questionary.text(
            t("存活检测超时（秒）：", "Alive-check timeout (seconds):"),
            default=str(settings.fast_check.timeout),
            validate=lambda value: value.isdigit() and 1 <= int(value) <= 60,
        ).ask()
        if timeout_text is None:
            return 130
    concurrency_text = questionary.text(
        t("异步并发数：", "Async concurrency:"),
        default=str(settings.system.concurrency),
        validate=lambda value: value.isdigit() and 1 <= int(value) <= 100,
    ).ask()
    if concurrency_text is None:
        return 130
    sheet_merge = questionary.confirm(
        t("批量查询是否合并到同一个 Excel？", "Merge a batch query into one Excel file?"),
        default=settings.system.sheet_merge,
    ).ask()
    if sheet_merge is None:
        return 130
    output_dir = questionary.text(t("默认导出目录：", "Default export directory:"), default=settings.system.output_dir).ask()
    if output_dir is None:
        return 130
    config_data = {
        "fofa": {"base_url": settings.fofa.base_url, "email": email or ""},
        "search": {
            "fields": fields or settings.search.fields,
            "size": int(size_text),
            "full": bool(full),
            "start_page": 1,
            "end_page": int(pages_text),
            "max_pages": max(int(pages_text), settings.search.max_pages),
            "max_records": settings.search.max_records,
        },
        "fast_check": {
            "check_alive": bool(check_alive),
            "timeout": int(timeout_text),
        },
        "system": {
            "language": interface_language,
            "logger": settings.system.logger,
            "sheet_merge": bool(sheet_merge),
            "concurrency": int(concurrency_text),
            "requests_per_second": settings.system.requests_per_second,
            "export_format": export_format,
            "output_dir": output_dir or settings.system.output_dir,
            "artifact_retention_days": settings.system.artifact_retention_days,
            "allow_private_network": settings.system.allow_private_network,
            "scan_ai_dedupe": settings.system.scan_ai_dedupe,
        },
        "providers": providers,
        "routing": routing,
    }
    target = config_write_path()
    from providers.registry import apply_model_traits

    for raw_profile in providers.values():
        apply_model_traits(raw_profile)
    fofa_key_saved = _store_keyring("fofamap", email or "default", key or "")
    provider_key_saved = _store_keyring("fofamap-provider", provider_key_env, provider_key)
    failed_fofa_key = bool(key and not fofa_key_saved)
    failed_provider_key = bool(provider_key and not provider_key_saved)
    secrets_in_yaml = False
    if failed_fofa_key or failed_provider_key:
        labels = []
        if failed_fofa_key:
            labels.append("FOFA_API_KEY")
        if failed_provider_key:
            labels.append(provider_key_env)
        secrets_in_yaml = bool(
            questionary.confirm(
                f"系统钥匙串不可用：{_keyring_unavailable_reason()}\n"
                f"是否将 {', '.join(labels)} 写入本地配置 {target}？\n"
                f"默认配置路径已加入 Git 忽略规则；{_local_yaml_security_notice()}；"
                "自定义路径请自行确认忽略规则。文件中仍是明文密钥。",
                default=True,
            ).ask()
        )
        if secrets_in_yaml:
            config_data["security"] = {"local_yaml_secrets_confirmed": True}
            if failed_fofa_key:
                config_data["fofa"]["api_key"] = key
            if failed_provider_key and provider_name:
                config_data["providers"][provider_name]["api_key"] = provider_key
    _save_setup_config(target, config_data, allow_secrets=secrets_in_yaml)
    console.print(f"[bold green]✓ {t('配置已写入：', 'Configuration written:')}[/][cyan]{target}[/]")
    if secrets_in_yaml:
        console.print(
            "[bold yellow]⚠ 密钥已按你的确认写入本地 YAML。请勿提交或分享该文件；"
            f"{_local_yaml_security_notice()}。若使用自定义配置路径，请确认它已被 Git 忽略。[/]"
        )
    else:
        if failed_fofa_key:
            console.print("[yellow]FOFA 密钥未保存；请在启动前设置 FOFA_API_KEY。[/]")
        if failed_provider_key:
            console.print(f"[yellow]AI 密钥未保存；请在启动前设置 {provider_key_env}。[/]")
    console.print(f"[dim]{t('重新启动 FofaMap 后，新配置生效。', 'Restart FofaMap for the new configuration to take effect.')}[/]")
    return 0


def _int_between(low: int, high: int):
    def validate(value: str) -> bool:
        return value.isdigit() and low <= int(value) <= high

    return validate


def _editable_document() -> tuple[Path, dict[str, Any]]:
    """Return the writable settings file, seeding it from the example when needed."""
    import config

    path = config.configuration_problem or config_write_path()
    if path.is_file():
        try:
            load_config(path)
            loaded = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
            return path, loaded if isinstance(loaded, dict) else {}
        except (ValueError, TypeError, AttributeError, yaml.YAMLError):
            import shutil

            backup = path.with_name(f"{path.name}.broken-{datetime.now():%Y%m%d%H%M%S}-{secrets.token_hex(3)}")
            shutil.copy2(path, backup)
            if os.name != "nt":
                backup.chmod(0o600)
            console.print(t("损坏的配置已备份：", "Damaged configuration backed up: "), str(backup), markup=False)
            return path, {}
    example = path.with_name("settings.example.yaml")
    if example.is_file():
        loaded = yaml.safe_load(example.read_text(encoding="utf-8")) or {}
        return path, loaded if isinstance(loaded, dict) else {}
    return path, {}


def _apply_document(path: Path, data: dict[str, Any]) -> None:
    data.setdefault("system", {}).setdefault("language", settings.system.language)
    _save_setup_config(path, data, allow_secrets=_contains_secret(data))
    fresh = load_config(path)
    import config

    config.configuration_problem = None
    for name in type(settings).model_fields:
        setattr(settings, name, getattr(fresh, name))
    set_language(settings.system.language)
    marker = Path(__file__).resolve().parent / ".fofamap-language"
    if marker.is_file() and not marker.is_symlink():
        try:
            marker.write_text(settings.system.language + "\n", encoding="ascii")
        except OSError:
            console.print(t("[dim]界面语言已保存；安装器语言记录暂时无法更新。[/]",
                            "[dim]Interface language saved; the installer language record could not be updated.[/]"))
    console.print(f"[bold green]✓ {t('配置已写入：', 'Configuration written:')}[/][cyan]{path}[/]")
    console.print(f"[dim]{t('当前这次运行已使用新配置。', 'This run is already using the new configuration.')}[/]")


def _edit_credentials() -> int:
    """Change the FOFA email and API key without repeating the full setup wizard."""
    from utils import prompts as questionary

    section(t("修改 FOFA 账号", "FOFA account"), t("邮箱和 API 密钥", "Email and API key"))
    env_had_key = bool(os.environ.get("FOFA_API_KEY") or os.environ.get("FOFA_KEY"))
    current_email = settings.fofa.email or ""
    console.print(
        f"{t('当前邮箱：', 'Current email: ')}[cyan]{current_email or t('未填写', 'empty')}[/]  "
        f"{t('密钥：', 'Key: ')}[cyan]{t('已配置', 'configured') if settings.fofa.api_key else t('未配置', 'not configured')}[/]"
    )
    email = questionary.text(
        t("FOFA 邮箱（当前接口可选，回车保持不变）：", "FOFA email (optional; Enter keeps the current value):"),
        default=current_email,
    ).ask()
    if email is None:
        console.print(f"[dim]{t('已取消，返回向导。', 'Cancelled. Back to the wizard.')}[/]")
        return 130
    key = questionary.password(t("新的 FOFA API 密钥（留空则不修改）：", "New FOFA API key (leave empty to keep the current one):")).ask()
    if key is None:
        console.print(f"[dim]{t('已取消，返回向导。', 'Cancelled. Back to the wizard.')}[/]")
        return 130
    email = email.strip()
    key = key.strip()
    import config
    if email == current_email and not key and not config.configuration_problem and config.config_write_path().is_file():
        console.print(f"[dim]{t('账号没有变化。', 'The account is unchanged.')}[/]")
        return 0
    path, data = _editable_document()
    fofa = data.setdefault("fofa", {})
    if not isinstance(fofa, dict):
        fofa = {}
        data["fofa"] = fofa
    fofa["email"] = email
    fofa.setdefault("base_url", settings.fofa.base_url)
    if key:
        saved = _store_keyring("fofamap", email or "default", key)
        if saved:
            fofa.pop("api_key", None)
            fofa.pop("key", None)
        else:
            write_yaml = questionary.confirm(
                f"{t('系统钥匙串不可用：', 'The system keychain is unavailable: ')}{_keyring_unavailable_reason()}\n"
                f"{t('是否把 FOFA API 密钥写入本地配置', 'Write the FOFA API key into the local file ')}{path}？\n"
                f"{_local_yaml_security_notice()}",
                default=True,
            ).ask()
            if write_yaml is None:
                console.print(f"[dim]{t('已取消，返回向导。', 'Cancelled. Back to the wizard.')}[/]")
                return 130
            if not write_yaml:
                console.print(f"[yellow]{t('密钥未保存。', 'The key was not saved.')}[/]")
                return 0
            data["security"] = {"local_yaml_secrets_confirmed": True}
            fofa["api_key"] = key
        os.environ["FOFA_API_KEY"] = key
        if env_had_key:
            notice = t(
                "本次运行已改用新密钥。若启动脚本里也写了 FOFA_API_KEY，下次启动请一起改，否则旧环境变量会盖过这里。",
                "This run is using the new key. If a startup script also sets FOFA_API_KEY, "
                "update it too or the old value wins on the next launch.",
            )
            console.print(f"[yellow]{notice}[/]")
    if email:
        os.environ["FOFA_EMAIL"] = email
    elif "FOFA_EMAIL" in os.environ:
        os.environ.pop("FOFA_EMAIL", None)
    _apply_document(path, data)
    return 0


def _provider_presets() -> dict[str, tuple[str, str, str, str, str]]:
    from providers.registry import MODEL_PRESETS

    presets = {
        name: (
            spec["protocol"],
            spec["base_url"],
            (spec.get("models") or [""])[0],
            spec.get("api_key_env") or "",
            "none" if spec["protocol"] in {"ollama_native"} or name in {"ollama", "lmstudio"} else "api_key",
        )
        for name, spec in MODEL_PRESETS.items()
    }
    presets["custom"] = ("openai_chat", "https://api.example.com/v1", "", "CUSTOM_MODEL_API_KEY", "api_key")
    return presets


def _provider_choices() -> list[Any]:
    from questionary import Choice

    return [
        Choice(t("DeepSeek（推荐）", "DeepSeek (Recommended)"), "deepseek"),
        Choice("ChatGPT / OpenAI", "openai"),
        Choice("Claude / Anthropic", "anthropic"),
        Choice("Grok / xAI", "xai"),
        Choice("Gemini", "gemini"),
        Choice("Kimi / Moonshot", "kimi"),
        Choice("MiniMax", "minimax"),
        Choice("小米 MiMo", "mimo"),
        Choice("硅基流动 SiliconFlow", "siliconflow"),
        Choice("GLM / 智谱", "zhipu"),
        Choice(t("Ollama 本地模型", "Ollama local model"), "ollama"),
        Choice(t("LM Studio 本地模型", "LM Studio local model"), "lmstudio"),
        Choice(t("自定义 OpenAI 兼容接口", "Custom OpenAI-compatible API"), "custom"),
    ]


def _ask_model_identity(questionary: Any, *, default_model: str, catalog: list[dict[str, Any]]) -> tuple[str, dict[str, Any]] | None:
    from questionary import Choice

    from providers.registry import preset_model_traits

    if catalog:
        picked = questionary.select(
            t("选择模型（名称和参数来自接口）：", "Choose a model (names and limits come from the API):"),
            choices=[Choice(_model_choice_label(item), item["id"]) for item in catalog],
            default=default_model if any(item.get("id") == default_model for item in catalog) else catalog[0]["id"],
        ).ask()
        if picked is None:
            return None
        selected = next(item for item in catalog if item["id"] == picked)
        return picked, {**preset_model_traits(picked), **selected}
    model = questionary.text(t("模型 ID（可填任意未来模型）：", "Model ID (any current or future model):"), default=default_model).ask()
    if model is None:
        return None
    return model, preset_model_traits(model)


def _store_provider_key(questionary: Any, path: Path, raw: dict[str, Any], provider_name: str, provider_key: str) -> bool | None:
    """Save a provider key. None means the user cancelled."""
    key_env = str(raw.get("api_key_env") or "")
    if not provider_key:
        return True
    saved = _store_keyring("fofamap-provider", key_env, provider_key) if key_env else False
    if saved:
        raw.pop("api_key", None)
        raw.pop("key", None)
        if key_env:
            os.environ[key_env] = provider_key
        return True
    write_yaml = questionary.confirm(
        f"{t('系统钥匙串不可用：', 'The system keychain is unavailable: ')}{_keyring_unavailable_reason()}\n"
        f"{t('是否把模型密钥写入本地配置', 'Write the model key into the local file ')}{path}？\n"
        f"{_local_yaml_security_notice()}",
        default=True,
    ).ask()
    if write_yaml is None:
        return None
    if not write_yaml:
        console.print(f"[yellow]{t('模型密钥未保存。', 'The model key was not saved.')} {provider_name}[/]")
        return False
    raw["api_key"] = provider_key
    if key_env:
        os.environ[key_env] = provider_key
    return True


def _activate_provider(data: dict[str, Any], provider_name: str) -> None:
    """The model just saved is the one the next AI task should call."""
    data["routing"] = {
        "default": provider_name,
        "planner": provider_name,
        "query_repair": provider_name,
        "reflector": provider_name,
        "summarizer": provider_name,
        "allow_cross_provider_fallback": False,
        "fallbacks": [],
    }


def _revise_provider(questionary: Any, path: Path, data: dict[str, Any], provider_name: str) -> int:
    providers = data.setdefault("providers", {})
    raw = providers.get(provider_name)
    if not isinstance(raw, dict):
        console.print(f"[yellow]{t('这个模型的配置无法读取。', 'This model configuration cannot be read.')}[/]")
        return 0
    section(provider_name, raw.get("model") or t("未设置模型", "no model"))
    change_model = questionary.confirm(t("更换模型 ID？", "Change the model ID?"), default=False).ask()
    if change_model is None:
        console.print(f"[dim]{t('已取消，返回向导。', 'Cancelled. Back to the wizard.')}[/]")
        return 130
    from providers.registry import apply_model_traits, preset_model_traits

    selected: dict[str, Any] = preset_model_traits(str(raw.get("model") or ""))
    model = str(raw.get("model") or "")
    if change_model:
        fetch_models = questionary.confirm(
            t("从接口获取可用模型，再选择模型和能力？", "Fetch models from the API, then choose a model and its capabilities?"),
            default=True,
        ).ask()
        if fetch_models is None:
            console.print(f"[dim]{t('已取消，返回向导。', 'Cancelled. Back to the wizard.')}[/]")
            return 130
        catalog: list[dict[str, Any]] = []
        if fetch_models:
            catalog = _discover_models_for_setup(
                str(raw.get("protocol") or "openai_chat"),
                str(raw.get("base_url") or ""),
                str(raw.get("api_key_env") or ""),
                os.environ.get(str(raw.get("api_key_env") or ""), ""),
                str(raw.get("credential_kind") or "api_key"),
            )
        identity = _ask_model_identity(questionary, default_model=model, catalog=catalog)
        if identity is None:
            console.print(f"[dim]{t('已取消，返回向导。', 'Cancelled. Back to the wizard.')}[/]")
            return 130
        model, selected = identity
        if isinstance(selected.get("max_output_tokens"), int) and selected["max_output_tokens"] > 0:
            raw["max_output_tokens"] = min(int(selected["max_output_tokens"]), 524288)
    raw["model"] = model
    raw["thinking_mode"] = selected.get("thinking_mode", "auto")
    reasoning = _ask_thinking_mode(questionary, selected)
    if reasoning is None:
        console.print(f"[dim]{t('已取消，返回向导。', 'Cancelled. Back to the wizard.')}[/]")
        return 130
    if reasoning == "":
        from questionary import Choice

        current = str(raw.get("reasoning_effort") or "disabled")
        reasoning = questionary.select(
            t(
                "思考模式。关闭后直接作答；其余档位按接口公布的强度思考。",
                "Thinking mode. Off answers directly; other levels use the effort published by the API.",
            ),
            choices=[
                Choice(t("关闭", "Off"), "disabled"),
                Choice("low", "low"),
                Choice("high", "high"),
                Choice("max", "max"),
            ],
            default=current if current in {"disabled", "low", "high", "max"} else "disabled",
        ).ask()
        if reasoning is None:
            console.print(f"[dim]{t('已取消，返回向导。', 'Cancelled. Back to the wizard.')}[/]")
            return 130
    raw["reasoning_effort"] = None if not reasoning else reasoning
    apply_model_traits(raw)
    if selected.get("vision"):
        vision_choice = questionary.confirm(
            t("该模型支持多模态输入。是否开启？关闭后只发送文本。", "This model accepts images. Off sends text only."),
            default=bool(raw.get("vision_enabled")),
        ).ask()
        if vision_choice is None:
            console.print(f"[dim]{t('已取消，返回向导。', 'Cancelled. Back to the wizard.')}[/]")
            return 130
        raw["vision_enabled"] = bool(vision_choice)
    if provider_name == "deepseek":
        search_choice = questionary.confirm(
            t(
                "开启 DeepSeek Search？关闭后只使用对话模型，不调用网页检索。",
                "Enable DeepSeek Search? Off uses the chat model only and does not search the web.",
            ),
            default=bool(raw.get("search_enabled")),
        ).ask()
        if search_choice is None:
            console.print(f"[dim]{t('已取消，返回向导。', 'Cancelled. Back to the wizard.')}[/]")
            return 130
        raw["search_enabled"] = bool(search_choice)
    provider_key = questionary.password(
        t("新的模型 API 密钥（留空则不修改）：", "New model API key (leave empty to keep the current one):")
    ).ask()
    if provider_key is None:
        console.print(f"[dim]{t('已取消，返回向导。', 'Cancelled. Back to the wizard.')}[/]")
        return 130
    stored = _store_provider_key(questionary, path, raw, provider_name, provider_key.strip())
    if stored is None:
        console.print(f"[dim]{t('已取消，返回向导。', 'Cancelled. Back to the wizard.')}[/]")
        return 130
    if provider_key.strip() and stored:
        key_env = str(raw.get("api_key_env") or "")
        if key_env and os.environ.get(key_env):
            notice = t(
                f"本次运行已改用新的模型密钥。若启动脚本里也写了 {key_env}，下次启动请一起改。",
                f"This run is using the new model key. If a startup script also sets {key_env}, update it too.",
            )
            console.print(f"[yellow]{notice}[/]")
    if stored and provider_key.strip() and raw.get("api_key"):
        data["security"] = {"local_yaml_secrets_confirmed": True}
    _activate_provider(data, provider_name)
    _apply_document(path, data)
    console.print(f"[bold green]✓ {t('之后的 AI 任务使用：', 'Later AI tasks use: ')}[/][cyan]{provider_name}[/]")
    return 0


def _add_provider(questionary: Any, path: Path, data: dict[str, Any]) -> int:
    from questionary import Choice

    provider_name = questionary.select(
        t("选择要添加的 AI 提供商：", "Choose an AI provider to add:"),
        choices=_provider_choices(),
    ).ask()
    if not provider_name:
        console.print(f"[dim]{t('已取消，返回向导。', 'Cancelled. Back to the wizard.')}[/]")
        return 130
    presets = _provider_presets()
    protocol, default_url, default_model, provider_key_env, credential_kind = presets[provider_name]
    if provider_name == "custom":
        protocol = questionary.select(
            t("接口协议：", "API protocol:"),
            choices=["openai_chat", "openai_responses", "anthropic_messages", "ollama_native"],
            default=protocol,
        ).ask()
        if protocol is None:
            console.print(f"[dim]{t('已取消，返回向导。', 'Cancelled. Back to the wizard.')}[/]")
            return 130
    base_url = questionary.text(t("接口地址：", "API address:"), default=default_url).ask()
    if base_url is None:
        console.print(f"[dim]{t('已取消，返回向导。', 'Cancelled. Back to the wizard.')}[/]")
        return 130
    provider_key = ""
    if credential_kind != "none":
        entered = questionary.password(t(f"{provider_name} API 密钥（可留空）：", f"{provider_name} API key (may be left empty):")).ask()
        if entered is None:
            console.print(f"[dim]{t('已取消，返回向导。', 'Cancelled. Back to the wizard.')}[/]")
            return 130
        provider_key = entered.strip()
    fetch_models = questionary.confirm(
        t("从接口获取可用模型，再选择模型和能力？", "Fetch models from the API, then choose a model and its capabilities?"),
        default=bool(provider_key) or credential_kind == "none",
    ).ask()
    if fetch_models is None:
        console.print(f"[dim]{t('已取消，返回向导。', 'Cancelled. Back to the wizard.')}[/]")
        return 130
    catalog: list[dict[str, Any]] = []
    if fetch_models:
        catalog = _discover_models_for_setup(protocol, base_url, provider_key_env, provider_key, credential_kind)
    identity = _ask_model_identity(questionary, default_model=default_model, catalog=catalog)
    if identity is None:
        console.print(f"[dim]{t('已取消，返回向导。', 'Cancelled. Back to the wizard.')}[/]")
        return 130
    model, selected = identity
    reasoning = _ask_thinking_mode(questionary, selected)
    if reasoning is None:
        console.print(f"[dim]{t('已取消，返回向导。', 'Cancelled. Back to the wizard.')}[/]")
        return 130
    if reasoning == "":
        reasoning = questionary.select(
            t(
                "思考模式。关闭后直接作答；其余档位按接口公布的强度思考。",
                "Thinking mode. Off answers directly; other levels use the effort published by the API.",
            ),
            choices=[
                Choice(t("关闭", "Off"), "disabled"),
                Choice("low", "low"),
                Choice("high", "high"),
                Choice("max", "max"),
            ],
            default="disabled",
        ).ask()
        if reasoning is None:
            console.print(f"[dim]{t('已取消，返回向导。', 'Cancelled. Back to the wizard.')}[/]")
            return 130
    search_enabled = False
    if provider_name == "deepseek":
        search_choice = questionary.confirm(
            t(
                "开启 DeepSeek Search？关闭后只使用对话模型，不调用网页检索。",
                "Enable DeepSeek Search? Off uses the chat model only and does not search the web.",
            ),
            default=False,
        ).ask()
        if search_choice is None:
            console.print(f"[dim]{t('已取消，返回向导。', 'Cancelled. Back to the wizard.')}[/]")
            return 130
        search_enabled = bool(search_choice)
    raw: dict[str, Any] = {
        "protocol": protocol,
        "base_url": base_url,
        "model": model,
        "api_key_env": provider_key_env,
        "credential_kind": credential_kind,
        "structured_output_mode": "prompt" if provider_name == "deepseek" else "auto",
        "search_enabled": search_enabled,
        "reasoning_effort": None if not reasoning else reasoning,
        "vision_enabled": False,
        "max_output_tokens": 32768,
        "timeout": 120,
    }
    from providers.registry import apply_model_traits

    apply_model_traits(raw)
    if isinstance(selected.get("max_output_tokens"), int) and selected["max_output_tokens"] > 0:
        raw["max_output_tokens"] = min(int(selected["max_output_tokens"]), 524288)
    stored = _store_provider_key(questionary, path, raw, provider_name, provider_key.strip())
    if stored is None:
        console.print(f"[dim]{t('已取消，返回向导。', 'Cancelled. Back to the wizard.')}[/]")
        return 130
    if stored and provider_key.strip() and raw.get("api_key"):
        data["security"] = {"local_yaml_secrets_confirmed": True}
    providers = data.setdefault("providers", {})
    if not isinstance(providers, dict):
        providers = {}
        data["providers"] = providers
    providers[provider_name] = raw
    _activate_provider(data, provider_name)
    _apply_document(path, data)
    console.print(f"[bold green]✓ {t('之后的 AI 任务使用：', 'Later AI tasks use: ')}[/][cyan]{provider_name}[/]")
    return 0


def _edit_provider() -> int:
    """Add or change a configured model, including thinking mode and DeepSeek Search."""
    from questionary import Choice

    from utils import prompts as questionary

    section(t("修改模型", "Models"), t("模型、思考模式、DeepSeek Search", "Model, thinking mode, DeepSeek Search"))
    path, data = _editable_document()
    from providers.registry import PRESETS_CHECKED_AT, sync_builtin_profiles

    refreshed = sync_builtin_profiles(data)
    if refreshed:
        _apply_document(path, data)
        console.print(t("官方默认配置已更新：", "Official defaults updated: "), ", ".join(refreshed), markup=False)
    console.print(t("默认模型核验日期：", "Default models verified: "), PRESETS_CHECKED_AT, markup=False)
    providers = data.get("providers") if isinstance(data.get("providers"), dict) else {}
    labels = []
    for name, raw in sorted(providers.items(), key=lambda item: item[0] != "deepseek"):
        if not isinstance(raw, dict):
            continue
        model = raw.get("model") or t("未设置模型", "no model")
        search = t("检索开", "search on") if raw.get("search_enabled") else t("检索关", "search off")
        effort = raw.get("reasoning_effort")
        if effort in {"disabled", "none", "off"} or (not effort and name == "deepseek"):
            effort = t("关闭", "off")
        elif not effort:
            effort = t("接口默认", "API default")
        display_name = t("DeepSeek（推荐）", "DeepSeek (Recommended)") if name == "deepseek" else name
        labels.append(Choice(f"{display_name} · {model} · {search} · {t('思考', 'thinking')} {effort}", name))
    labels.append(Choice(t("添加模型", "Add a model"), "__add__"))
    labels.append(Choice(t("返回", "Back"), ""))
    picked = questionary.select(t("选择要修改的模型：", "Choose a model to edit:"), choices=labels).ask()
    if not picked:
        return 0
    if picked == "__add__":
        return _add_provider(questionary, path, data)
    return _revise_provider(questionary, path, data, picked)


def _edit_language() -> int:
    from utils import prompts

    selected = _ask_interface_language(prompts)
    if selected is None:
        return 130
    path, data = _editable_document()
    data.setdefault("system", {})["language"] = selected
    if os.environ.get("FOFAMAP_LANGUAGE") in {"zh", "en"}:
        os.environ["FOFAMAP_LANGUAGE"] = selected
    _apply_document(path, data)
    return 0


def _edit_field_preferences() -> int:
    from questionary import Choice

    from utils import prompts

    selected = prompts.select(
        t("默认返回字段：", "Default returned fields:"),
        choices=[
            Choice(t("智能选择（无需模型）", "Smart selection (no model required)"), "smart"),
            Choice(t("固定字段（手动指定）", "Fixed fields (specify columns)"), "fixed"),
        ],
        default="smart" if settings.search.smart_fields else "fixed",
    ).ask()
    if selected is None:
        return 130
    path, data = _editable_document()
    search = data.setdefault("search", {})
    search["smart_fields"] = selected == "smart"
    if selected == "fixed":
        fields = prompts.text(t("返回字段：", "Returned fields:"), default=settings.search.fields).ask()
        if not fields:
            return 130
        search["fields"] = fields.strip()
    _apply_document(path, data)
    return 0


def _edit_preferences() -> int:
    """Change the settings used by ordinary searches: alive checks, pages, history, and export."""
    from questionary import Choice

    from utils import prompts as questionary

    section(
        t("修改常用配置", "Common settings"),
        t("存活检测、页数、历史数据和导出", "Alive checks, pages, historical data, and export"),
    )
    check_alive = questionary.confirm(
        t("默认开启存活检测？", "Turn on alive checks by default?"),
        default=settings.fast_check.check_alive,
    ).ask()
    if check_alive is None:
        console.print(f"[dim]{t('已取消，返回向导。', 'Cancelled. Back to the wizard.')}[/]")
        return 130
    scan_ai_dedupe = questionary.confirm(
        t("默认开启 AI 扫描目标筛选与去重？", "Enable AI scan target selection by default?"),
        default=settings.system.scan_ai_dedupe,
    ).ask()
    if scan_ai_dedupe is None:
        return 130
    timeout_text = str(settings.fast_check.timeout)
    if check_alive:
        timeout_text = questionary.text(
            t("存活检测超时（秒）：", "Alive-check timeout (seconds):"),
            default=str(settings.fast_check.timeout),
            validate=_int_between(1, 60),
        ).ask()
        if timeout_text is None:
            console.print(f"[dim]{t('已取消，返回向导。', 'Cancelled. Back to the wizard.')}[/]")
            return 130
    pages_text = questionary.text(
        t("默认查询页数：", "Default page count:"),
        default=str(settings.search.end_page),
        validate=_int_between(1, 10_000),
    ).ask()
    size_text = questionary.text(
        t("每页结果数：", "Rows per page:"),
        default=str(settings.search.size),
        validate=_int_between(1, 10_000),
    ).ask()
    full = questionary.confirm(
        t("默认查询 FOFA 历史数据？", "Include FOFA historical data by default?"),
        default=settings.search.full,
    ).ask()
    fields = questionary.text(t("默认返回字段：", "Default returned fields:"), default=settings.search.fields).ask()
    export_format = questionary.select(
        t("默认导出格式：", "Default export format:"),
        choices=["xlsx", "csv", "jsonl"],
        default=settings.system.export_format,
    ).ask()
    output_dir = questionary.text(t("默认导出目录：", "Default export directory:"), default=settings.system.output_dir).ask()
    language = questionary.select(
        t("界面语言：", "Interface language:"),
        choices=[Choice("中文", "zh"), Choice("English", "en")],
        default=settings.system.language if settings.system.language in {"zh", "en"} else "zh",
    ).ask()
    if None in {pages_text, size_text, full, fields, export_format, output_dir, language}:
        console.print(f"[dim]{t('已取消，返回向导。', 'Cancelled. Back to the wizard.')}[/]")
        return 130
    path, data = _editable_document()
    search = data.setdefault("search", {})
    if not isinstance(search, dict):
        search = {}
        data["search"] = search
    search["fields"] = fields or settings.search.fields
    search["size"] = int(size_text)
    search["full"] = bool(full)
    search["end_page"] = int(pages_text)
    search["max_pages"] = max(int(pages_text), int(search.get("max_pages") or pages_text))
    fast_check = data.setdefault("fast_check", {})
    if not isinstance(fast_check, dict):
        fast_check = {}
        data["fast_check"] = fast_check
    fast_check["check_alive"] = bool(check_alive)
    fast_check["timeout"] = int(timeout_text)
    system = data.setdefault("system", {})
    if not isinstance(system, dict):
        system = {}
        data["system"] = system
    system["language"] = language
    system["scan_ai_dedupe"] = bool(scan_ai_dedupe)
    system["export_format"] = export_format
    system["output_dir"] = output_dir or settings.system.output_dir
    _apply_document(path, data)
    return 0


def _machine_output(options: dict[str, Any]) -> bool:
    return options.get("output_format") in {"json", "jsonl"}


def _emit_json(value: Any, mode: str) -> None:
    payload = value.model_dump(mode="json") if hasattr(value, "model_dump") else value
    if mode == "jsonl" and isinstance(payload, dict) and isinstance(payload.get("records"), list):
        for record in payload["records"]:
            click.echo(json.dumps(record, ensure_ascii=False))
    else:
        click.echo(json.dumps(payload, ensure_ascii=False, indent=2 if mode == "json" else None))


def _run_slug(query: str) -> str:
    return re.sub(r"[^\w-]+", "_", query, flags=re.UNICODE).strip("_")[:36] or "fofa_result"


def _new_run_dir(query: str, outdir: str | None = None, stamp: str | None = None) -> tuple[Path, str]:
    stamp = stamp or datetime.now().strftime("%Y%m%d_%H%M%S")
    root = Path(outdir or settings.system.output_dir).expanduser()
    run_dir = root / f"{_run_slug(query)}_{stamp}"
    run_dir.mkdir(parents=True, exist_ok=True)
    return run_dir, stamp


def _ensure_run_dir(options: dict[str, Any], query: str) -> Path:
    existing = options.get("_run_dir")
    if existing:
        path = Path(existing)
        path.mkdir(parents=True, exist_ok=True)
        return path
    if options.get("outfile"):
        parent = Path(options["outfile"]).expanduser().parent
        run_dir = parent if str(parent) != "." else Path(options.get("outdir") or settings.system.output_dir).expanduser()
        run_dir.mkdir(parents=True, exist_ok=True)
        options["_run_dir"] = str(run_dir)
        options["_run_stamp"] = options.get("_run_stamp") or datetime.now().strftime("%Y%m%d_%H%M%S")
        return run_dir
    label = "batch" if (options.get("bat_query") or options.get("_batch")) else query
    run_dir, stamp = _new_run_dir(label, options.get("outdir"), options.get("_run_stamp"))
    options["_run_dir"] = str(run_dir)
    options["_run_stamp"] = stamp
    return run_dir


def _default_export_path(query: str, format_name: str, outdir: str | None = None) -> Path:
    run_dir, stamp = _new_run_dir(query, outdir)
    return run_dir / f"{_run_slug(query)}_{stamp}.{format_name}"


def _query_export_path(options: dict[str, Any], query: str, index: int, total: int) -> tuple[Path, str]:
    requested = options.get("outfile")
    format_name = options.get("export_format") or settings.system.export_format
    if requested:
        path = Path(requested).expanduser()
        format_name = options.get("export_format") or path.suffix.lstrip(".") or format_name
        if total > 1 and not options.get("_merge_xlsx"):
            path = path.with_name(f"{path.stem}_{index}{path.suffix or f'.{format_name}'}")
        elif not path.suffix:
            path = path.with_suffix(f".{format_name}")
        return path, format_name
    run_dir = _ensure_run_dir(options, query)
    stamp = options.get("_run_stamp") or datetime.now().strftime("%Y%m%d_%H%M%S")
    slug = _run_slug(query)
    if total > 1:
        return run_dir / f"{slug}_{index}_{stamp}.{format_name}", format_name
    return run_dir / f"{slug}_{stamp}.{format_name}", format_name


def _search_window(options: dict[str, Any]) -> tuple[int, int]:
    """Return (start_page, max_pages). `-p` is a page count; config end_page is the last page."""
    start = settings.search.start_page
    if options.get("pages"):
        return start, int(options["pages"])
    return start, max(1, settings.search.end_page - start + 1)


def _record_url(values: dict[str, Any]) -> str | None:
    from core.nuclei_protocols import asset_scan_target

    return asset_scan_target(values)


def _needs_alive_probe(asset: dict[str, Any]) -> bool:
    """Empty FOFA placeholders must not count as a completed HTTP probe."""
    if "alive_status" not in asset:
        return True
    value = asset.get("alive_status")
    return value is None or str(value).strip() == ""


def _assets_have_status_code(assets: list[dict[str, Any]], fields: list[str]) -> bool:
    return "status_code" in fields and all("status_code" in asset for asset in assets)


async def _maybe_await(value: Any) -> Any:
    if inspect.isawaitable(value):
        return await value
    return value


async def _apply_alive_and_local_filters(
    assets: list[dict[str, Any]],
    *,
    fields: list[str],
    options: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[str]]:
    """Apply include, optional HTTP alive checks, then keyword search. Same order as classic mode."""
    include = {item.strip() for item in (options.get("include") or "").split(",") if item.strip()}
    check_alive = bool(options.get("check_alive"))
    needles = [item.strip().lower() for item in (options.get("key_word") or "").split(",") if item.strip()]
    if not assets or (not include and not check_alive and not needles):
        return assets, fields
    has_status_code = _assets_have_status_code(assets, fields)
    if include and has_status_code:
        assets = [asset for asset in assets if str(asset.get("status_code")) in include]
    if (check_alive or (include and not has_status_code)) and assets:
        pending = [asset for asset in assets if _needs_alive_probe(asset)]
        if pending:
            urls = [asset_probe_target(asset) for asset in pending]
            alive = await FastChecker.check_alive([url for url in urls if url], timeout=settings.fast_check.timeout)
            for asset, url in zip(pending, urls, strict=True):
                asset["alive_status"] = alive.get(url, "N/A") if url else "N/A"
        fields = insert_alive_status_field(fields)
        if include and not has_status_code:
            assets = [asset for asset in assets if str(asset.get("alive_status")) in include]
    if needles:
        assets = [asset for asset in assets if any(needle in str(asset).lower() for needle in needles)]
    return assets, fields


async def _apply_agent_result_filters(run: Any, options: dict[str, Any], *, machine: bool) -> None:
    """Honor --check-alive / -i / -k on AI reconnaissance results before export and scan."""
    if run.error or not run.assets:
        return
    if not options.get("check_alive") and not options.get("include") and not options.get("key_word"):
        return
    if not any(_needs_alive_probe(asset) for asset in run.assets) and not options.get("key_word"):
        return
    before = len(run.assets)
    confidence = list(run.asset_confidence)
    if len(confidence) != before:
        confidence = (confidence + [""] * before)[:before]
    identity = [id(asset) for asset in run.assets]
    status = None
    if not machine and (options.get("check_alive") or options.get("include")):
        status = console.status(f"[cyan]正在对 {before} 条 AI 资产做存活检测与过滤…[/]", spinner="dots")
        status.start()
    try:
        filtered, fields = await _apply_alive_and_local_filters(
            run.assets,
            fields=list(run.fields),
            options=options,
        )
    finally:
        if status:
            status.stop()
    kept_ids = {id(asset) for asset in filtered}
    run.assets = filtered
    run.fields = fields
    run.asset_confidence = [value for asset_id, value in zip(identity, confidence, strict=True) if asset_id in kept_ids]
    run.result_count = len(run.assets)
    run.evidence_counts = {
        strategy: sum(1 for value in run.asset_confidence if value == strategy)
        for strategy in ("precision", "balanced", "hypothesis", "recall")
        if any(value == strategy for value in run.asset_confidence)
    }
    if options.get("include") or options.get("key_word"):
        run.scan_targets = []
        for asset in run.assets:
            target = _record_url(asset)
            if target and target not in run.scan_targets:
                run.scan_targets.append(target)
    from core.agent import AgentState, AgentStep

    run.steps.append(
        AgentStep(
            state=AgentState.EVALUATE,
            detail=f"存活检测与本地过滤完成：{before} 条 → {len(run.assets)} 条",
        )
    )


async def _decorate_pages(
    pages: AsyncIterator[SearchPage],
    *,
    options: dict[str, Any],
    counters: dict[str, Any],
) -> AsyncIterator[SearchPage]:
    machine = _machine_output(options)
    async for page in pages:
        counters["pages"] += 1
        values = [record.values for record in page.records]
        values, page.fields = await _apply_alive_and_local_filters(values, fields=page.fields, options=options)
        page.records = [AssetRecord(values=item) for item in values]
        for record in page.records:
            target = _record_url(record.values)
            if target and target not in counters["targets"]:
                counters["targets"].append(target)
                if options.get("nuclei") and len(counters.setdefault("scan_assets", [])) < (options.get("scan_max_targets") or 200):
                    counters["scan_assets"].append({key: value for key, value in record.values.items() if key in {
                        "host", "ip", "port", "protocol", "title", "domain", "product", "server", "alive", "status_code", "evidence"
                    }})
        counters["records"] += len(page.records)
        if machine:
            _emit_json(page, options["output_format"])
        else:
            render_search_page(page, counters["pages"], options.get("display_rows") or min(100, len(page.records)))
        yield page


def _note_credential_fallback(client: FofaClient, machine: bool) -> None:
    if machine or not client.used_fallback_key:
        return
    console.print(
        "[yellow]环境变量中的 FOFA_API_KEY 已被 FOFA 拒绝，本次已改用配置文件里的密钥。"
        "请把 shell 中的 FOFA_API_KEY 更新为同一把 Key，并重新打开终端。[/]"
    )


async def _account(client: FofaClient, machine: bool) -> dict[str, Any]:
    if machine:
        return await client.account()
    with console.status("[cyan]正在验证 FOFA 账号与能力…[/]", spinner="dots"):
        data = await client.account()
    if not machine:
        render_account(data)
        _note_credential_fallback(client, machine)
    return data


async def _run_searches(client: FofaClient, queries: list[str], options: dict[str, Any]) -> None:
    from core.scans import default_nuclei_template_ids

    if _use_smart_fields(options):
        from core.fields import account_tier, merge_return_fields

        user_info = getattr(client, "user_info", None) or {}
        tier = account_tier(user_info.get("vip_level", user_info.get("level")))
        intent = str(options.get("ai_query") or options.get("icon_query") or " ".join(queries))
        fields = merge_return_fields([], account_tier_name=tier, intent=f"{intent} {' '.join(queries)}")
    else:
        fields = _fields(options.get("query_fields"))
    start_page, pages = _search_window(options)
    size = options.get("size") or settings.search.size
    save = options.get("save", True)
    format_name = options.get("export_format") or settings.system.export_format
    merge_xlsx = bool(save and settings.system.sheet_merge and format_name == "xlsx" and len(queries) > 1)
    options["_merge_xlsx"] = merge_xlsx
    if save and not options.get("outfile"):
        options["_batch"] = len(queries) > 1
        _ensure_run_dir(options, "batch" if len(queries) > 1 else queries[0])
    workbook: StreamingXlsxWorkbook | None = None
    if merge_xlsx:
        if options.get("outfile"):
            merge_path, _ = _query_export_path({**options, "_merge_xlsx": True}, queries[0], 1, 1)
        else:
            run_dir = _ensure_run_dir(options, "batch")
            stamp = options.get("_run_stamp") or datetime.now().strftime("%Y%m%d_%H%M%S")
            merge_path = run_dir / f"batch_merge_{stamp}.xlsx"
        workbook = StreamingXlsxWorkbook(merge_path)
    all_targets: list[str] = []
    try:
        for index, query in enumerate(queries, start=1):
            if not _machine_output(options):
                section("FOFA 资产检索", f"任务 {index}/{len(queries)}")
                render_query_overview(query, fields, pages, size, bool(options.get("full")), **_run_switch_flags(options))
            request = SearchRequest(
                query=query,
                fields=fields,
                size=size,
                full=options.get("full", False),
                page=start_page,
                max_pages=pages,
                max_records=options.get("max_records") or settings.search.max_records,
                dedupe_by=_fields(options.get("dedupe_by")) if options.get("dedupe_by") else [],
            )
            counters: dict[str, Any] = {"pages": 0, "records": 0, "targets": []}
            started = time.monotonic()
            decorated = _decorate_pages(client.iter_search(request), options=options, counters=counters)
            artifact: Path | None = None
            status = None if _machine_output(options) else console.status("[cyan]正在请求 FOFA 连续分页…[/]", spinner="dots")
            if status:
                status.start()
            try:
                if workbook is not None:
                    workbook.start_sheet(_run_slug(query) if len(queries) > 1 else "FOFA assets")
                    async for page in decorated:
                        workbook.write_page(page)
                    artifact = workbook.destination
                elif save:
                    artifact, _ = await export_pages(
                        decorated,
                        *_query_export_path(options, query, index, len(queries)),
                    )
                else:
                    async for _ in decorated:
                        pass
            finally:
                if status:
                    status.stop()
            all_targets.extend(url for url in counters["targets"] if url not in all_targets)
            if not _machine_output(options):
                render_search_summary(
                    records=counters["records"],
                    pages=counters["pages"],
                    artifact=str(artifact) if artifact else None,
                    elapsed=time.monotonic() - started,
                )
            if options.get("nuclei"):
                scan_dir = Path(options.get("_run_dir") or options.get("outdir") or settings.system.output_dir)
                scan_status, _, _ = await _approve_and_execute_scan(
                    targets=counters["targets"][: options.get("scan_max_targets") or 200],
                    template_ids=list(options.get("nuclei_ids") or default_nuclei_template_ids()),
                    severities=[item.strip() for item in (options.get("severity") or "medium,high,critical").split(",") if item.strip()],
                    reason="用户通过经典模式 -n/--nuclei 明确请求对本次 FOFA 结果执行扫描。",
                    options=options,
                    machine=_machine_output(options),
                    directory_name=str((scan_dir / f"nuclei_{index}_{datetime.now().strftime('%Y%m%d_%H%M%S')}").resolve()),
                    selection_context={"intent": options.get("ai_query") or query, "assets": counters.get("scan_assets", [])},
                )
                if scan_status in {"declined", "cancelled"}:
                    options["_scan_cancelled"] = True
                    return
    finally:
        if workbook is not None:
            workbook.close()
    run_dir_value = options.get("_run_dir")
    if save and run_dir_value and all_targets:
        targets_path = Path(run_dir_value) / "targets.txt"
        targets_path.write_text("\n".join(all_targets) + "\n", encoding="utf-8")


def _normalize_batch_query(value: str) -> str:
    candidate = value.strip()
    try:
        ipaddress.ip_address(candidate)
        return f'ip="{candidate}"'
    except ValueError:
        pass
    if re.fullmatch(r"(?=.{1,253}$)(?:[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?\.)+[A-Za-z]{2,63}", candidate):
        return f'domain="{candidate.lower()}"'
    return candidate


def _load_batch(path_value: str) -> list[str]:
    path = Path(path_value).expanduser()
    if not path.is_file():
        raise click.ClickException(f"批量查询文件不存在：{path}")
    return [
        _normalize_batch_query(line)
        for line in path.read_text(encoding="utf-8-sig").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]


def _combine_batch_queries(queries: list[str], group_size: int = 100, max_query_length: int = 4096) -> list[str]:
    """Combine homogeneous IP/domain clues into bounded OR expressions."""
    if group_size <= 1:
        return list(dict.fromkeys(queries))
    homogeneous: dict[str, list[str]] = {"ip": [], "domain": []}
    custom: list[str] = []
    pattern = re.compile(r'^(ip|domain)="([^"\\]+)"$')
    for query in dict.fromkeys(queries):
        match = pattern.fullmatch(query)
        if match:
            homogeneous[match.group(1)].append(query)
        else:
            custom.append(query)

    combined: list[str] = []
    for field in ("ip", "domain"):
        chunk: list[str] = []
        for query in homogeneous[field]:
            candidate = f"({' || '.join([*chunk, query])})"
            if chunk and (len(chunk) >= group_size or len(candidate) > max_query_length):
                combined.append(chunk[0] if len(chunk) == 1 else f"({' || '.join(chunk)})")
                chunk = []
            chunk.append(query)
        if chunk:
            combined.append(chunk[0] if len(chunk) == 1 else f"({' || '.join(chunk)})")
    return [*combined, *custom]


def _prompt_scan_action() -> Any:
    from questionary import Choice

    from utils import prompts as questionary

    return questionary.select(
        "请选择下一步：",
        choices=[
            Choice("🚀 执行扫描", "execute"),
            Choice("✏️ 修改模板 / 严重级别", "modify"),
            Choice(t("⌨ 自定义扫描参数", "Customize scan parameters"), "custom"),
            Choice(t("🎯 切换 AI 目标筛选与去重", "Toggle AI target selection"), "selection"),
            Choice("📄 仅生成报告，不扫描", "report"),
        ],
        qmark="›",
        pointer="❯",
    ).ask_async()


async def _prompt_scan_modify(
    template_ids: list[str],
    severities: list[str],
    *,
    all_templates: bool = False,
    all_severities: bool = False,
) -> tuple[list[str], list[str], bool, bool] | None:
    from core.scans import ALLOWED_SEVERITIES, nuclei_id_allowlist
    from utils import prompts as questionary

    allowed_ids = sorted(nuclei_id_allowlist())
    ids_text = await questionary.text(
        "模板 ID（逗号分隔；all = 全部模板）：",
        default="all" if all_templates else ",".join(template_ids or allowed_ids[:1]),
        instruction=f" 允许：all, {', '.join(allowed_ids)}",
    ).ask_async()
    if ids_text is None:
        return None
    parsed_ids = [item.strip() for item in ids_text.split(",") if item.strip()]
    selected_all_templates = any(item.lower() == "all" for item in parsed_ids)
    if selected_all_templates:
        parsed_ids = []
    elif not parsed_ids or any(item not in nuclei_id_allowlist() for item in parsed_ids):
        console.print("[yellow]模板 ID 不在允许列表中，已保持原方案。[/]")
        return template_ids, severities, all_templates, all_severities
    sev_text = await questionary.text(
        "严重级别（逗号分隔；all = 全部级别）：",
        default="all" if all_severities else ",".join(severities or ["medium", "high", "critical"]),
        instruction=f" 允许：all, {', '.join(sorted(ALLOWED_SEVERITIES))}",
    ).ask_async()
    if sev_text is None:
        return None
    parsed_severities = [item.strip().lower() for item in sev_text.split(",") if item.strip()]
    selected_all_severities = "all" in parsed_severities
    if selected_all_severities:
        parsed_severities = []
    elif not parsed_severities or any(item not in ALLOWED_SEVERITIES for item in parsed_severities):
        console.print("[yellow]严重级别无效，已保持原方案。[/]")
        return parsed_ids, severities, selected_all_templates, all_severities
    return parsed_ids, parsed_severities, selected_all_templates, selected_all_severities


async def _approve_and_execute_scan(
    *,
    targets: list[str],
    template_ids: list[str],
    severities: list[str],
    reason: str,
    options: dict[str, Any],
    machine: bool,
    directory_name: str,
    selection_context: dict | None = None,
    router: Any | None = None,
) -> tuple[str, str | None, str | None]:
    """Execute an exact typed plan only after an interactive, one-time approval."""
    from utils.scan_runtime import ScanCancelled
    if not targets:
        return "no_targets", None, None
    if machine:
        return "approval_required_interactive_cli", None, None
    if os.getenv("FOFAMAP_ENABLE_SCANNING", "").lower() == "false":
        console.print("[yellow]扫描计划已生成，但管理员通过 FOFAMAP_ENABLE_SCANNING=false 禁止了主动扫描。[/]")
        return "disabled_by_administrator", None, None
    from core.scans import align_scan_severities

    current_all_templates = any(item.strip().lower() == "all" for item in template_ids)
    current_all_severities = any(item.strip().lower() == "all" for item in severities)
    current_ids = [] if current_all_templates else list(template_ids)
    current_severities = [] if current_all_severities else align_scan_severities(current_ids, severities)
    original_targets = list(targets)
    selection_enabled = options.get("scan_ai_dedupe")
    if selection_enabled is None:
        selection_enabled = settings.system.scan_ai_dedupe
    selection_done = False
    context = selection_context if selection_context is not None else {}
    context["targets"] = targets
    while True:
        if selection_enabled and not selection_done:
            from core.scan_selection import select_with_model
            from utils.scan_runtime import ScanCancelled, cancellable_scan

            owned_registry = None
            try:
                selection_router = router
                if selection_router is None:
                    from providers.registry import ProviderRegistry, ProviderRouter

                    owned_registry = ProviderRegistry(settings, execution_mode="interactive")
                    selection_router = ProviderRouter(owned_registry)
                console.print("[cyan]AI 正在按任务筛选扫描目标 · Esc / Ctrl+C 取消[/]")
                audit = await cancellable_scan(select_with_model(
                    str(context.get("intent") or options.get("ai_query") or options.get("query") or reason),
                    original_targets, context.get("assets", []), selection_router,
                ))
                context["selection"] = audit
                targets = audit["targets"]
                context["targets"] = targets
                folder = Path(directory_name)
                if not folder.is_absolute():
                    folder = Path(options.get("_run_dir") or options.get("outdir") or settings.system.output_dir) / folder
                folder.mkdir(parents=True, exist_ok=True)
                (folder / "scan-selection.json").write_text(json.dumps(audit, ensure_ascii=False, indent=2), encoding="utf-8")
                from utils.cli_ui import render_scan_selection

                render_scan_selection(audit)
                selection_done = True
                if not targets:
                    console.print(t(
                        "AI 筛选排除了全部目标。用户扫描指令优先，恢复原始候选，请重新确认精确范围。",
                        "AI selection excluded every target. Your request takes priority; "
                        "restoring the original candidates for approval.",
                    ))
                    targets = original_targets
                    context["targets"] = targets
                    context["selection"]["user_request_overrode_empty_selection"] = True
                    context["selection"]["targets"] = targets
                    selection_enabled = False
                    continue
            except (ScanCancelled, asyncio.CancelledError):
                return "declined", None, None
            except Exception as exc:
                console.print(Text(f"AI 筛选未完成：{exc}。请重试或关闭筛选后重新确认方案。", style="yellow"))
                selection_done = True
                context["selection_error"] = str(exc)
                targets = original_targets
                # No execution from the failed selection. The next menu action must be explicit.
            finally:
                if owned_registry is not None:
                    await owned_registry.aclose()
        console.print(t("AI 扫描目标筛选与去重：", "AI target selection: ") + ("[green]开启[/]" if selection_enabled else "[dim]关闭[/]"))
        advanced = ("nuclei_headless", "nuclei_code", "nuclei_file", "nuclei_oast")
        if options.get("nuclei_protocols") or any(options.get(name) for name in advanced):
            console.print(
                f"Nuclei protocols: {', '.join(options.get('nuclei_protocols') or []) or 'template-defined'} · "
                f"headless={bool(options.get('nuclei_headless'))} · code={bool(options.get('nuclei_code'))} · "
                f"file={bool(options.get('nuclei_file'))} · OAST={bool(options.get('nuclei_oast'))}"
            )
        from core.scanner import build_nuclei_command
        from core.scans import ScanPlanRequest

        try:
            preview_plan = ScanPlanRequest(
                targets=targets,
                template_ids=current_ids,
                severities=current_severities,
                templates=options.get("_custom_scan_templates", []),
                all_templates=current_all_templates,
                all_severities=current_all_severities,
                protocols=list(options.get("nuclei_protocols") or []),
                enable_headless=bool(options.get("nuclei_headless")),
                enable_code=bool(options.get("nuclei_code")),
                enable_file=bool(options.get("nuclei_file")),
                allow_oast=bool(options.get("nuclei_oast")),
                **options.get("_custom_scan_limits", {}),
            )
            import shlex

            console.print(
                t("推荐/最终命令：", "Recommended/final command: ")
                + shlex.join(build_nuclei_command("nuclei", preview_plan, Path("APPROVED_TARGETS.txt"), Path("nuclei.jsonl")))
            )
        except ValueError as exc:
            return "failed", None, str(exc)
        render_scan_approval(
            targets=targets,
            template_ids=current_ids,
            severities=current_severities,
            reason=reason,
            all_templates=current_all_templates,
            all_severities=current_all_severities,
        )
        action = await _maybe_await(_prompt_scan_action()) or "cancel"
        if action == "selection":
            selection_enabled = not selection_enabled
            options["scan_ai_dedupe"] = selection_enabled
            selection_done = False
            context.pop("selection_error", None)
            targets = original_targets
            if not selection_enabled:
                context["selection"] = {"enabled": False, "targets": targets}
                context["targets"] = targets
            continue
        if action == "custom":
            from core.nuclei_guide import customize_plan
            from core.scans import ScanPlanRequest
            from utils import prompts as questionary

            parameters = await questionary.text(
                t("输入 Nuclei 参数：", "Nuclei parameters:"),
                instruction="-rl 5 -c 2 -timeout 10 -retries 0 -pt tcp -id redis-detect",
            ).ask_async()
            if parameters is not None:
                try:
                    base = ScanPlanRequest(
                        targets=targets,
                        template_ids=current_ids,
                        severities=current_severities,
                        templates=options.get("_custom_scan_templates", []),
                        protocols=list(options.get("nuclei_protocols") or []),
                        all_templates=current_all_templates,
                        all_severities=current_all_severities,
                        **options.get("_custom_scan_limits", {}),
                    )
                    custom = customize_plan(base, parameters)
                    current_ids, current_severities = custom.template_ids, custom.severities
                    options["_custom_scan_templates"] = custom.templates
                    current_all_templates, current_all_severities = custom.all_templates, custom.all_severities
                    options["nuclei_protocols"] = custom.protocols
                    for option, value in (
                        ("nuclei_headless", custom.enable_headless),
                        ("nuclei_code", custom.enable_code),
                        ("nuclei_file", custom.enable_file),
                        ("nuclei_oast", custom.allow_oast),
                    ):
                        options[option] = value
                    options["_custom_scan_limits"] = {
                        key: getattr(custom, key) for key in ("rate_limit", "concurrency", "request_timeout", "retries", "max_duration")
                    }
                except ValueError as exc:
                    console.print(f"[yellow]{exc}[/]")
            continue
        if action == "modify":
            modified = await _maybe_await(
                _prompt_scan_modify(
                    current_ids,
                    current_severities,
                    all_templates=current_all_templates,
                    all_severities=current_all_severities,
                )
            )
            if modified is None:
                continue
            current_ids, current_severities, current_all_templates, current_all_severities = modified
            if not current_all_severities:
                current_severities = align_scan_severities(current_ids, current_severities)
            continue
        if action == "report":
            return "report_only", None, None
        if action != "execute":
            return "declined", None, None
        if selection_enabled and context.get("selection_error"):
            console.print("[yellow]AI 筛选失败，尚不能执行。请切换关闭筛选或重新开启重试，再确认范围。[/]")
            continue
        break
    from core.scanner import NucleiScanner
    from core.scans import ScanApproval, ScanPlanRequest
    from service.store import JobStore

    store = approved = scan_root = None
    try:
        if not await _ensure_scan_component(machine=machine):
            return "component_install_declined", None, None
        from service.paths import database_url

        store = JobStore(database_url())
        approval = ScanApproval(
            store,
            secret=os.getenv("FOFAMAP_SCAN_APPROVAL_SECRET") or secrets.token_urlsafe(32),
            allow_private=settings.system.allow_private_network,
        )
        request = ScanPlanRequest(
            targets=targets,
            template_ids=current_ids,
            templates=options.get("_custom_scan_templates", []),
            severities=current_severities,
            all_templates=current_all_templates,
            all_severities=current_all_severities,
            protocols=list(options.get("nuclei_protocols") or []),
            **options.get("_custom_scan_limits", {}),
            enable_headless=bool(options.get("nuclei_headless")),
            enable_code=bool(options.get("nuclei_code")),
            enable_file=bool(options.get("nuclei_file")),
            allow_oast=bool(options.get("nuclei_oast")),
        )
        context["approved_plan"] = request.model_dump(mode="json")
        job, token = approval.create(request)
        approved = approval.consume(job["id"], token)
        store.update(approved["id"], status="running")
        output = Path(directory_name)
        scan_root = (
            output
            if output.is_absolute()
            else Path(options.get("_run_dir") or options.get("outdir") or settings.system.output_dir) / directory_name
        )

        last_print = 0.0

        def on_progress(event) -> None:
            nonlocal last_print
            if console.is_terminal:
                live.update(build_nuclei_progress(
                    event,
                    target_count=len(request.targets),
                    template_ids=["ALL（全部已安装模板）"] if current_all_templates else current_ids,
                ), refresh=True)
            elif time.monotonic() - last_print >= 5:
                console.print(f"Nuclei: {event.elapsed_seconds:.0f}s · requests={event.requests or 0} · matches={event.findings}")
                last_print = time.monotonic()

        with Live(
            build_nuclei_progress(
                None,
                target_count=len(request.targets),
                template_ids=["ALL（全部已安装模板）"] if current_all_templates else current_ids,
            ),
            console=console,
            auto_refresh=False,
            screen=True,
            transient=True,
        ) if console.is_terminal else nullcontext() as live:
            from utils.scan_runtime import cancellable_scan

            result = await cancellable_scan(NucleiScanner().run_plan(request, scan_root, on_progress=on_progress))
        artifact = str(result.artifact.resolve())
        store.update(approved["id"], status="completed", artifact_path=artifact)
        render_nuclei_results(result)
        return "completed", artifact, None
    except (ScanCancelled, asyncio.CancelledError):
        partial = scan_root / "nuclei.jsonl" if scan_root else None
        artifact = str(partial.resolve()) if partial and partial.is_file() else None
        if store is not None and approved is not None:
            store.update(approved["id"], status="cancelled", artifact_path=artifact,
                         error={"code": "cancelled", "message": "User cancelled; partial findings are not a completed scan"})
        console.print("[yellow]扫描已停止，子进程已回收；已生成的部分结果保留。[/]")
        return "cancelled", artifact, None
    except Exception as exc:
        from core.tool_errors import error_payload

        payload = error_payload(exc, tool="interactive_nuclei")
        error = payload["message"]
        partial = scan_root / "nuclei.jsonl" if scan_root else None
        artifact = str(partial.resolve()) if partial and partial.is_file() else None
        if store is not None and approved is not None:
            store.update(approved["id"], status="failed", error=payload, artifact_path=artifact)
        console.print(f"[bold red]Nuclei 扫描未完成：[/]{error}")
        return "failed", artifact, error


async def _ensure_scan_component(*, machine: bool = False) -> str | None:
    from core.nuclei_install import ensure_installed, needs_setup
    from core.scanner import resolve_nuclei_executable
    from utils import prompts as questionary
    from utils.onboarding import can_prompt

    executable = resolve_nuclei_executable()
    if not needs_setup(executable):
        return executable
    manual = t(
        "可从 https://github.com/projectdiscovery/nuclei/releases 下载对应平台程序，放入 PATH 或用 FOFAMAP_NUCLEI 指定路径。",
        "Download your platform binary from https://github.com/projectdiscovery/nuclei/releases, add it to PATH or set FOFAMAP_NUCLEI.",
    )
    if machine or not can_prompt():
        console.print(
            t(
                "Nuclei 尚未就绪，需要先取得安装同意，或手动安装。",
                "Nuclei needs setup; obtain installation consent or install it manually.",
            )
        )
        console.print(manual)
        return None
    accepted = await questionary.confirm(
        t(
            "Nuclei 或官方模板尚未安装完整。是否自动下载安装？Y=官方下载并继续，N=自行安装：",
            "Nuclei or its official templates need setup. Download automatically? Y=official download and continue; N=install manually:",
        ),
        default=False,
    ).ask_async()
    if accepted is not True:
        console.print(
            t(
                "已跳过安装，本次不执行扫描；查询结果与报告会保留。",
                "Installation skipped. This scan will not run; query results and reports are retained.",
            )
        )
        console.print(manual)
        return None
    return await ensure_installed(consent=True, progress=lambda message: console.print(message, markup=False))


def _print_run_usage(run: Any, router: Any) -> None:
    """Close the AI task with elapsed time and the tokens recorded on this router."""
    events = getattr(router, "events", None)
    if events is not None:
        run.route_events = [event.model_dump(mode="json") for event in events]
    run.finished_at = datetime.now()
    render_run_usage(run)


async def _export_agent_assets(run: Any, options: dict[str, Any]) -> Path | None:
    if not options.get("save", True) or not run.assets:
        return None
    fields = list(run.fields or [])
    if not fields:
        fields = list(dict.fromkeys(key for asset in run.assets for key in asset))
    records = [AssetRecord(values={field: asset.get(field) for field in fields}) for asset in run.assets]
    query = run.query or run.intent or "agent"
    path, format_name = _query_export_path(options, query, 1, 1)
    artifact, _ = await export_pages(records_to_pages(records, fields, query), path, format_name)
    if not _machine_output(options):
        extra = (
            t("（预览截断，完整计数见报告）", " (preview truncated; the report has the full count)")
            if getattr(run, "assets_truncated", False)
            else ""
        )
        console.print(f"[bold green]✓ {t('资产结果已导出：', 'Assets exported:')}[/][cyan]{artifact}[/]{extra}")
    return artifact


async def _agent_scan_and_report(run: Any, options: dict[str, Any], machine: bool, router: Any | None = None) -> tuple[str, str | None]:
    """Apply deterministic authorization, one-time approval and reporting around an AI scan recommendation."""
    from core.report import write_agent_report
    from core.scans import default_nuclei_template_ids

    if options.get("save", True) and not options.get("outfile"):
        _ensure_run_dir(options, run.query or run.intent or "agent")
    await _export_agent_assets(run, options)

    scan_status = "not_requested"
    scan_error: str | None = None
    if options.get("nuclei"):
        run.scan_requested_by_user = True
    override_ids = list(options.get("nuclei_ids") or [])
    if override_ids:
        run.scan_template_ids = list(dict.fromkeys(override_ids))
    override_severities = [item.strip().lower() for item in (options.get("severity") or "").split(",") if item.strip()]
    if override_severities:
        run.scan_severities = list(dict.fromkeys(override_severities))

    if run.error:
        scan_status = "blocked_by_agent_error"
    elif run.scan_requested_by_user and run.scan_targets:
        reason = run.scan_reason
        if not run.scan_recommended:
            scan_status = "user_requested_agent_not_recommended"
            reason = "用户明确要求扫描，但 AI 未推荐该范围。仍可执行、修改或仅生成报告。" + (
                f" AI 判断：{run.scan_reason}" if run.scan_reason else ""
            )
        template_ids = list(run.scan_template_ids or default_nuclei_template_ids())
        scan_root = Path(options.get("_run_dir") or options.get("outdir") or settings.system.output_dir)
        selection_context = {"intent": run.intent, "assets": [
            {**row, **({"confidence": run.asset_confidence[index]} if index < len(run.asset_confidence) else {})}
            for index, row in enumerate(run.assets)
        ]}
        scan_status, run.scan_artifact, scan_error = await _approve_and_execute_scan(
            targets=run.scan_targets[: options.get("scan_max_targets") or 200],
            template_ids=template_ids,
            severities=run.scan_severities,
            reason=reason,
            options=options,
            machine=machine,
            directory_name=str((scan_root / "nuclei").resolve()),
            selection_context=selection_context,
            router=router,
        )
        run.scan_selection = selection_context.get("selection", {})
        if "targets" in selection_context:
            run.scan_targets = selection_context["targets"]
        approved_plan = selection_context.get("approved_plan")
        if approved_plan:
            run.scan_template_ids = approved_plan["template_ids"] or (["all"] if approved_plan["all_templates"] else [])
            run.scan_severities = approved_plan["severities"] or (["all"] if approved_plan["all_severities"] else [])
            run.scan_protocols = approved_plan["protocols"]
            run.scan_limits = {
                key: approved_plan[key] for key in ("rate_limit", "concurrency", "request_timeout", "retries", "max_duration")
            }
    elif run.scan_recommended and not run.scan_requested_by_user:
        scan_status = "recommendation_only_no_user_authorization"
    elif run.scan_requested_by_user and not run.scan_targets:
        scan_status = "no_scan_targets"
    elif run.scan_requested_by_user and not run.scan_ready:
        scan_status = "incomplete_or_empty_scan_plan"

    if router is not None and scan_status == "completed" and run.scan_artifact:
        from core.agent import generate_scan_advice
        from providers.base import ProviderError

        try:
            await generate_scan_advice(
                run,
                router,
                language="en" if options.get("report_lang") == "en" else "zh",
            )
        except ProviderError as exc:
            if not machine:
                console.print(f"[yellow]模型未写出修复建议：{exc}[/]")

    if options.get("report", True):
        report_path = options.get("report_file")
        if report_path:
            destination = Path(report_path).expanduser()
        else:
            stamp = options.get("_run_stamp") or datetime.now().strftime("%Y%m%d_%H%M%S")
            destination = Path(options.get("_run_dir") or options.get("outdir") or settings.system.output_dir) / f"report_{stamp}.md"
        if router is not None:
            events = getattr(router, "events", None)
            if events is not None:
                run.route_events = [event.model_dump(mode="json") for event in events]
        run.finished_at = datetime.now()
        artifact = write_agent_report(
            run,
            destination,
            scan_status=scan_status,
            scan_error=scan_error,
            language=options.get("report_lang") or "zh",
        )
        run.report_artifact = str(artifact)
        if not machine:
            console.print(f"[bold green]✓ {t('AI 侦察报告已生成：', 'AI report written:')}[/][cyan]{artifact}[/]")
            html_artifact = artifact.with_suffix(".html")
            if html_artifact.is_file():
                console.print(f"[bold green]✓ {t('HTML 测绘报告已生成：', 'HTML report written:')}[/][cyan]{html_artifact}[/]")
            english_html = artifact.with_name(f"{artifact.stem}.en.html")
            if english_html.is_file():
                console.print(f"[bold green]✓ English HTML report：[/][cyan]{english_html}[/]")
    return scan_status, scan_error


async def _main_async(**options: Any) -> int:
    action = options.get("cmd")
    machine = _machine_output(options)
    if action == "schedule":
        from core.schedules import ScheduleRequest, write_schedule_index
        from service.scheduler import run_due, schedule_store

        try:
            schedules = schedule_store()
            operation = options.get("schedule_action") or "list"
            if operation in {"create", "update"}:
                if options.get("schedule_spec"):
                    request = ScheduleRequest.model_validate_json(options["schedule_spec"].read_text(encoding="utf-8"))
                else:
                    if not all(options.get(key) for key in ("schedule_name", "schedule_task", "schedule_when")):
                        raise click.UsageError("Provide --schedule-name, --schedule-task, --schedule-when (or --schedule-spec JSON)")
                    request = ScheduleRequest(
                        name=options["schedule_name"],
                        task=options["schedule_task"],
                        when=options["schedule_when"],
                        timezone=options["schedule_timezone"],
                        queries=list(options.get("schedule_queries") or []),
                        check_alive=options.get("check_alive") if options.get("_explicit_check_alive") else None,
                    )
                if operation == "update" and not options.get("schedule_id"):
                    raise click.UsageError("--schedule-id is required")
                item = schedules.update(options["schedule_id"], request) if operation == "update" else schedules.create(request)
                payload = {"schedule": item, "worker": schedules.worker_status()}
            elif operation == "run-due":
                payload = {"runs": await run_due(schedules)}
            elif operation in {"pause", "resume", "stop", "delete", "history"}:
                if not options.get("schedule_id"):
                    raise click.UsageError("--schedule-id is required")
                if operation == "history":
                    payload = {"runs": schedules.runs(options["schedule_id"])}
                elif operation == "stop":
                    payload = {"schedule": schedules.stop(options["schedule_id"])}
                elif operation == "delete":
                    payload = {"schedule": schedules.delete(options["schedule_id"])}
                else:
                    payload = {"schedule": schedules.set_enabled(options["schedule_id"], operation == "resume")}
            else:
                payload = {"schedules": schedules.list(), "worker": schedules.worker_status()}
            index = write_schedule_index(schedules, Path(settings.system.output_dir).resolve() / "schedules")
            payload["index"] = str(index)
            _emit_json(payload, options["output_format"] if machine else "json")
            return 0
        except (ValueError, KeyError) as exc:
            raise click.ClickException(str(exc)) from exc
    if action == "integrate":
        from core.integrations import (
            HOSTS,
            IntegrationError,
            export_skill,
            import_skill,
            integrate_host,
            integration_status,
            supported_hosts,
        )

        if options.get("check_stale"):
            requested = options.get("integration_agent")
            if not requested:
                raise click.UsageError("--check-stale requires --agent <name|all>")
            if options.get("export_skill") or options.get("import_skill") or options.get("uninstall_integration"):
                raise click.UsageError("--check-stale cannot be combined with installation/export/removal")
            targets = [host.id for host in HOSTS] if requested == "all" else [requested]
            states = [integration_status(target, scope=options["integration_scope"], root=options.get("project_root"))
                      for target in targets]
            ok = all(state["ok"] for state in states)
            _emit_json({"ok": ok, "integrations": states}, options["output_format"] if machine else "json")
            return 0 if ok else 1

        if options.get("export_skill") and options.get("import_skill"):
            raise click.UsageError("Choose --export-skill or --import-skill")
        if options.get("export_skill"):
            if options.get("dry_run"):
                _emit_json({"planned_skill_archive": str(options["export_skill"])}, options["output_format"] if machine else "json")
                return 0
            try:
                path = export_skill(options["export_skill"])
            except IntegrationError as exc:
                raise click.ClickException(str(exc)) from exc
            _emit_json({"skill_archive": str(path)}, options["output_format"] if machine else "json")
            return 0
        if options.get("import_skill"):
            if not options.get("integration_agent") or options["integration_agent"] == "all":
                raise click.UsageError("--import-skill requires one --agent target")
            try:
                changes = import_skill(
                    options["import_skill"],
                    options["integration_agent"],
                    scope=options["integration_scope"],
                    root=options.get("project_root"),
                    force=bool(options.get("force_integration")),
                    dry_run=bool(options.get("dry_run")),
                )
            except IntegrationError as exc:
                raise click.ClickException(str(exc)) from exc
            _emit_json({"skill_changes": changes}, options["output_format"] if machine else "json")
            return 0

        if options.get("list_integrations"):
            payload = {"hosts": supported_hosts()}
            if machine:
                _emit_json(payload, options["output_format"])
            else:
                section("智能体集成支持矩阵", "MCP 与 Skill")
                for host in payload["hosts"]:
                    console.print(
                        f"[bold cyan]{host['id']:<20}[/] MCP：[green]{_support_label(host['mcp'])}[/]  "
                        f"Skill：[green]{_support_label(host['skills'])}[/]"
                    )
                    if host["notes"]:
                        console.print(f"  [dim]{host['notes']}[/]")
            return 0
        requested = options.get("integration_agent")
        if not requested:
            raise click.UsageError("integrate 需要 --agent <name|all>，或使用 --list 查看支持矩阵。")
        targets = [host.id for host in HOSTS] if requested == "all" else [requested]
        root = Path(options["project_root"]).expanduser() if options.get("project_root") else Path.cwd()
        try:
            results = [
                integrate_host(
                    target,
                    scope=options.get("integration_scope") or "user",
                    root=root,
                    server_command=options.get("server_command"),
                    uninstall=bool(options.get("uninstall_integration")),
                    dry_run=bool(options.get("dry_run")),
                    force=bool(options.get("force_integration")),
                ).as_dict()
                for target in targets
            ]
        except IntegrationError as exc:
            raise click.ClickException(str(exc)) from exc
        payload = {"integrations": results}
        if machine:
            _emit_json(payload, options["output_format"])
        else:
            verb = "预览" if options.get("dry_run") else ("卸载" if options.get("uninstall_integration") else "安装")
            section(
                f"智能体集成{verb}",
                f"范围：{_SCOPE_LABELS.get(options.get('integration_scope') or 'user', options.get('integration_scope') or 'user')}",
            )
            for result in results:
                console.print(
                    f"[bold green]✓ {result['target']}[/] · MCP {_support_label(result['mcp_support'])} · "
                    f"Skill {_support_label(result['skill_support'])}"
                )
                for change in result["changes"]:
                    console.print(f"  [dim]{change}[/]")
                for note in result["notes"]:
                    console.print(f"  [yellow]{note}[/]")
                if result["deeplink"]:
                    console.print(f"  [cyan]{result['deeplink']}[/]")
        return 0
    if action == "init":
        if machine:
            _emit_json({"config": "config/settings.example.yaml", "secrets": ".env.example"}, options["output_format"])
            return 0
        # Defensive fallback for programmatic callers. The normal human CLI
        # executes this synchronously before entering asyncio (see main()).
        return await asyncio.to_thread(_interactive_init)
    if action == "models":
        from providers.registry import ProviderRegistry

        registry = ProviderRegistry(settings, execution_mode="interactive")
        try:
            catalog: dict[str, Any] = {}
            for name, provider in registry.providers.items():
                try:
                    catalog[name] = await provider.discover_catalog()
                except Exception as exc:
                    catalog[name] = {"error": str(exc)}
        finally:
            await registry.aclose()
        if machine:
            _emit_json(catalog, options["output_format"])
        else:
            section("模型目录", "名称、上下文和输出上限来自各接口实时返回")
            for name, rows in catalog.items():
                console.print(f"\n[bold cyan]{name}[/]")
                if isinstance(rows, dict):
                    console.print(f"  [yellow]{rows.get('error')}[/]")
                    continue
                if not rows:
                    console.print("  [dim]接口没有返回模型[/]")
                for item in rows:
                    console.print(f"  {_model_choice_label(item)}")
        return 0
    if action == "fields":
        catalog = field_catalog()
        if machine:
            _emit_json(catalog, options["output_format"])
        else:
            section("FOFA 字段目录", f"版本 {catalog['version']} · {catalog.get('source', '')}")
            console.print("[bold cyan]基础返回字段[/]\n" + ", ".join(catalog["base"]))
            if catalog.get("compat"):
                console.print("\n[bold yellow]兼容返回字段（非官方附录，按需自行指定）[/]\n" + ", ".join(catalog["compat"]))
            for tier, fields in catalog["tiers"].items():
                console.print(f"\n[bold green]{tier}[/]\n" + ", ".join(fields))
            if catalog.get("memberships"):
                console.print(f"\n[bold cyan]会员等级与 API 权限[/]  [dim]{catalog.get('membership_source', '')}[/]")
                for item in catalog["memberships"]:
                    host = "是" if item["host_api"] else "否"
                    stats = "是" if item["stats_api"] else "否"
                    extra = f" · {item['notes']}" if item.get("notes") else ""
                    console.print(
                        f"  vip_level={item['vip_level']:<3} {item['name']:<8}  "
                        f"主机聚合 {host} · 统计聚合 {stats} · {item['requests_per_second']:g} req/s{extra}"
                    )
            console.print("\n[dim]查询语法请运行 `fofamap syntax`；规则库请运行 `fofamap rules`。[/]")
        return 0
    if action == "syntax":
        from core.syntax import syntax_catalog

        catalog = syntax_catalog()
        if machine:
            _emit_json(catalog, options["output_format"])
        else:
            section("FOFA 官方查询语法", catalog["source"])
            for item in catalog["operators"]:
                console.print(f"[bold cyan]{item['op']:<4}[/] {item['meaning']}")
            console.print()
            for item in catalog["query_fields"]:
                console.print(f"[bold]{item['field']:<16}[/] {item['example']:<42} [dim]{item['meaning']}[/]")
            for note in catalog["notes"]:
                console.print(f"[dim]· {note}[/]")
        return 0
    if action == "rules":
        from core.rules import rules_catalog

        catalog = rules_catalog(options.get("key_word") or options.get("rule") or "", category=options.get("rule_category") or "")
        if machine:
            _emit_json(catalog, options["output_format"])
        else:
            section("FOFA 规则库参考集",
                    f"{catalog['count']}/{catalog['total']} 条 · {catalog['official_category_count']} 类 · {catalog['source']}")
            console.print(f"[dim]{catalog['note']}[/]")
            if options.get("rule_categories"):
                console.print(f"[cyan]核验日期 {catalog['checked_at']} · 已核验 {catalog['verified_count']} · "
                              f"旧版待复核 {catalog['legacy_count']}[/]")
                for item in catalog["category_summary"]:
                    console.print(f"  [bold cyan]{item['name']:<18}[/] {item['count']:>4} 条 · 已核验 {item['verified']}")
                return 0
            for category, rules in catalog["categories"].items():
                console.print(f"\n[bold green]{category}[/]")
                for rule in rules:
                    status = "" if rule["verified"] else " [dim](legacy，未复核)[/]"
                    console.print(f"  [bold cyan]{rule['name']:<20}[/] {rule['query']}{status}")
        return 0
    if action == "serve":
        from service.api import main as serve

        serve()
        return 0
    if options.get("update_nuclei"):
        executable = await _ensure_scan_component(machine=machine)
        if not executable:
            return 130
        from core.nuclei_guide import command_guide
        from core.scanner import nuclei_subprocess_env

        for flag in ("-update", "-ut"):
            updated = subprocess.run([executable, flag], check=False, env=nuclei_subprocess_env())  # noqa: S603
            if updated.returncode:
                raise click.ClickException(f"Nuclei update failed: {flag} (exit {updated.returncode})")
        await command_guide(refresh=True)
        console.print(t("Nuclei 更新后已刷新本机命令指南。", "Nuclei command guide refreshed after the update."))
        return 0

    queries: list[str] = []
    if options.get("query"):
        queries.append(options["query"])
    if options.get("bat_query"):
        batch_queries = _load_batch(options["bat_query"])
        queries.extend(_combine_batch_queries(batch_queries, options.get("batch_group_size") or 100))
    if options.get("icon_query"):
        if not machine:
            section("图标哈希计算", options["icon_query"])
        try:
            icon_query = await IconHashCalculator.get_hash(options["icon_query"])
        except ValueError as exc:
            raise click.ClickException(str(exc)) from exc
        if not icon_query:
            raise click.ClickException("无法获取网站图标或计算哈希。")
        if not machine:
            console.print(f"[green]✓[/] 已生成 FOFA 语句：[bold cyan]{icon_query}[/]")
        queries.append(icon_query)
    if options.get("icon_file"):
        try:
            icon_query = IconHashCalculator.from_file(options["icon_file"])
        except ValueError as exc:
            raise click.ClickException(str(exc)) from exc
        if not machine:
            section("本地图标哈希计算", options["icon_file"])
            console.print(f"[green]✓[/] 已生成 FOFA 语句：[bold cyan]{icon_query}[/]")
        queries.append(icon_query)

    async with FofaClient() as client:
        if action == "account":
            data = await client.account()
            if machine:
                _emit_json(data, options["output_format"])
            else:
                render_account(data)
                _note_credential_fallback(client, machine)
            return 0
        await _account(client, machine)
        if options.get("host_query"):
            data = await client.host_profile(
                str(options["host_query"]).strip().strip("'\""),
                detail=bool(options.get("host_detail", True)),
            )
            if machine:
                _emit_json(data, options["output_format"])
            else:
                section("主机聚合查询")
                render_host(data)
            return 0
        if options.get("count_query"):
            data = await client.stats(
                options["count_query"],
                _fields(options.get("query_fields") or "country,port,org"),
                size=options.get("size") or 5,
            )
            if machine:
                _emit_json(data, options["output_format"])
            else:
                section("FOFA 统计聚合")
                render_stats(data, options["count_query"])
            return 0
        if options.get("ai_query"):
            from core.agent import FofaAgent
            from providers.registry import ProviderRegistry, ProviderRouter

            task_started = datetime.now()

            registry = ProviderRegistry(settings, execution_mode="interactive")
            router = ProviderRouter(registry)
            search_override = options.get("deepseek_search")
            if search_override is not None and "deepseek" in registry.providers:
                registry.providers["deepseek"].profile.search_enabled = bool(search_override)
            search_context = ""
            providers = getattr(registry, "providers", {})
            profile_for_task = getattr(router, "_profile_for_task", None)
            planner_name = profile_for_task("planner") if callable(profile_for_task) else ""
            planner = providers.get(planner_name) if planner_name else None
            if planner is not None and planner.profile.search_enabled and showcase_for(str(options["ai_query"])) is None:
                try:
                    brief = await build_search_context(router, planner, str(options["ai_query"]))
                    search_context = brief.notes
                    if not machine and brief.reason:
                        render_deep_search(brief.reason, notes=bool(brief.notes))
                except Exception as exc:
                    if not machine:
                        render_deep_search(
                            "",
                            failed=t(
                                f"深度搜索暂不可用，继续使用对话模型：{exc}",
                                f"Deep search is unavailable. Continuing with the chat model: {exc}",
                            ),
                        )
            live: Live | None = None
            live_started = False
            latest_page: SearchPage | None = None
            if not machine:
                section(
                    t("AI 智能侦察", "AI reconnaissance"),
                    t("实时展示执行阶段、查询语句和资产结果", "Live stages, queries, and assets"),
                )
                render_run_switches(**_run_switch_flags(options))
                live = Live("", console=console, refresh_per_second=8, transient=True)

            def on_progress(agent_run, _step) -> None:
                nonlocal live_started
                if live is None:
                    return
                live.update(build_agent_progress(agent_run, latest_page), refresh=True)
                if not live_started:
                    live.start(refresh=True)
                    live_started = True

            async def on_page(agent_run, page, _page_number) -> None:
                nonlocal latest_page
                if options.get("check_alive") or options.get("include") or options.get("key_word"):
                    values = [record.values for record in page.records]
                    values, fields = await _apply_alive_and_local_filters(
                        values,
                        fields=list(agent_run.fields or page.fields),
                        options=options,
                    )
                    agent_run.fields = fields
                    page.fields = fields
                    page.records = [AssetRecord(values=item) for item in values]
                latest_page = page
                on_progress(agent_run, None)

            need_page_observer = (not machine) or bool(options.get("check_alive") or options.get("include") or options.get("key_word"))
            try:
                try:
                    from core.exposure import wants_sample

                    run = await FofaAgent(client, router).run(
                        options["ai_query"],
                        scan_requested=bool(options.get("nuclei")),
                        max_records=options.get("max_records") or settings.search.max_records,
                        max_pages=_search_window(options)[1],
                        fields=None if _use_smart_fields(options) else _fields(options.get("query_fields")),
                        smart_fields=_use_smart_fields(options),
                        on_progress=on_progress if not machine else None,
                        on_page=on_page if need_page_observer else None,
                        search_context=search_context,
                        report_language="en" if options.get("report_lang") == "en" else "zh",
                        sample=wants_sample(str(options.get("ai_query") or "")),
                    )
                    run.started_at = task_started
                finally:
                    if live is not None and live_started:
                        live.stop()
                await _apply_agent_result_filters(run, options, machine=machine)
                if not machine:
                    render_agent(run)
                if run.error:
                    if options.get("_interactive_recovery") and not run.assets and not run.result_count:
                        error = run.error
                        from core.models import FofaErrorCode
                        from providers.base import ProviderError

                        if error.get("code") in {
                            "model_auth_failed", "model_not_found", "model_provider_not_configured", "model_credential_not_allowed"
                        }:
                            raise ProviderError("Model configuration requires repair", code=error["code"])
                        if error.get("code") == "auth_failed":
                            raise FofaError(FofaErrorCode.AUTH_FAILED, "FOFA credentials require repair")
                    if not machine:
                        _print_run_usage(run, router)
                    if machine:
                        _emit_json(run, options["output_format"])
                    return 2
                scan_status, _ = await _agent_scan_and_report(run, options, machine, router)
                if not machine:
                    _print_run_usage(run, router)
                if machine:
                    _emit_json(run, options["output_format"])
                return 130 if scan_status in {"declined", "cancelled"} else 0
            finally:
                await registry.aclose()
        if queries:
            await _run_searches(client, queries, options)
            return 130 if options.get("_scan_cancelled") else 0
    raise click.UsageError("请选择向导任务，或提供 -q/-ai/-hq/-cq/-ico/-bq 参数。")


@click.command(context_settings={"help_option_names": ["-h", "--help"], "max_content_width": 120})
@click.version_option(VERSION, "-V", "--version", prog_name="FofaMap")
@click.argument(
    "cmd", required=False, type=click.Choice(["account", "fields", "syntax", "rules", "serve", "init", "integrate", "models", "schedule"])
)
@click.option(
    "--agent",
    "integration_agent",
    type=click.Choice(
        [
            "all",
            "cursor",
            "codex",
            "claude",
            "claude-code",
            "opencode",
            "deepseek-harness",
            "deepseek",
            "dsh",
            "lmstudio",
            "lm-studio",
            "openclaw",
            "hermes",
            "grok",
            "gork",
        ]
    ),
    help="安装目标；all 表示全部支持的智能体",
)
@click.option(
    "--scope",
    "integration_scope",
    type=click.Choice(["user", "project"]),
    default="user",
    show_default=True,
    help="用户级或项目级",
)
@click.option(
    "--schedule-action",
    type=click.Choice(["menu", "create", "update", "list", "pause", "resume", "stop", "delete", "history", "run-due"]),
    default="list",
)
@click.option("--schedule-name", help="计划任务名称")
@click.option("--schedule-task", help="计划任务测绘需求")
@click.option("--schedule-when", help="例如每10分钟、每天早上8点、每周一9点、明天15:00")
@click.option("--schedule-timezone", default="Asia/Shanghai", help="IANA 任务时区")
@click.option("--schedule-query", "schedule_queries", multiple=True, help="固定 FOFA 查询，可重复；用于跨期可比")
@click.option("--schedule-id", help="暂停、恢复或查看历史的任务 ID")
@click.option("--schedule-spec", type=click.Path(exists=True, dir_okay=False, path_type=Path), help="完整计划任务 JSON")
@click.option("--export-skill", type=click.Path(path_type=Path), help="导出可导入的 .skill 包")
@click.option("--import-skill", type=click.Path(exists=True, dir_okay=False, path_type=Path), help="仅向指定宿主导入 .skill")
@click.option("--check-stale", is_flag=True, help="只读核对已安装 Skill 的版本和内容哈希；不一致时非零退出")
@click.option("--list", "list_integrations", is_flag=True, help="列出 MCP 与 Skill 支持情况")
@click.option("--uninstall", "uninstall_integration", is_flag=True, help="仅移除 FofaMap 管理的配置与文件")
@click.option("--dry-run", is_flag=True, help="只显示将发生的集成变更")
@click.option(
    "--server-command",
    default=None,
    help="覆盖宿主启动 MCP 的命令；默认自动写入当前 Python 与 mcp_server.py 的绝对路径",
)
@click.option("--project-root", type=click.Path(file_okay=False, path_type=Path), help="项目级安装时的项目根目录")
@click.option("--force", "force_integration", is_flag=True, help="备份后替换同名、非 FofaMap 管理的 Skill/插件")
@click.option("-init", "--init", "init_mode", is_flag=True, help="启动安全初始化向导（兼容旧用法）")
@click.option("-ai", "--ai-query", prompt="请描述 AI 侦察需求", prompt_required=False, help="AI 智能侦察（兼容 2.0）")
@click.option("-q", "--query", prompt="请输入 FOFA 查询语法", prompt_required=False, help="FOFA 标准查询（兼容 2.0）")
@click.option("-hq", "--host-query", prompt="请输入 IP 或域名", prompt_required=False, help="主机聚合画像（兼容 2.0）")
@click.option("--host-detail/--no-host-detail", default=True, help="Host 聚合是否返回端口详情（官方 detail 参数）")
@click.option("--rule-categories", is_flag=True, help="配合 rules 列出全部分类和数量，不查询资产")
@click.option("--rule-category", help="配合 rules 按分类筛选，例如 工业控制 / 人工智能 / OA系统")
@click.option("--rule", help="按 FOFA 规则库名称生成 app= 查询，例如 ThinkPHP / 致远OA")
@click.option("-cq", "--count-query", prompt="请输入统计查询语法", prompt_required=False, help="统计聚合查询（兼容 2.0）")
@click.option("-ico", "--icon-query", prompt="请输入网站 URL", prompt_required=False, help="计算网站图标哈希并反查")
@click.option("--icon-file", help="计算本地图标文件哈希并反查（最大 4 MiB）")
@click.option("-bq", "--bat-query", prompt="请输入批量查询文件", prompt_required=False, help="每行一条查询语句的 TXT 文件")
@click.option("-f", "--query-fields", help="逗号分隔的返回字段；与 --smart-fields 同时出现时以智能选择为准")
@click.option(
    "--smart-fields/--no-smart-fields",
    default=None,
    help="按账号等级和任务智能选择返回字段与字段数；AI 模式默认开启",
)
@click.option("-p", "--pages", type=click.IntRange(1, 10_000), default=None, help="最大查询页数")
@click.option("--size", type=click.IntRange(1, 10_000), default=None, help="检索每页条数；统计聚合时为每个维度 Top N（官方默认 5）")
@click.option("--max-records", type=click.IntRange(1, 1_000_000), default=None, help="本次最多返回记录数")
@click.option(
    "--batch-group-size",
    type=click.IntRange(1, 100),
    default=100,
    show_default=True,
    help="批量 IP/域名每组组合成一条 OR 查询；1 表示不组合",
)
@click.option("--full/--no-full", default=None, help="是否查询历史数据（默认跟随配置）")
@click.option("--dedupe-by", help="明确的逗号分隔去重键")
@click.option("-k", "--key-word", help="在本地结果中筛选关键词，逗号表示任一匹配；-q 与 -ai 均支持")
@click.option("-i", "--include", help="仅保留指定状态码，例如 200,403；-q 与 -ai 均支持")
@click.option(
    "--check-alive/--no-check-alive",
    default=settings.fast_check.check_alive,
    help="对结果做安全的 HTTP 存活检测；-q 与 -ai 均支持",
)
@click.option("-o", "--outfile", help="完整结果导出路径")
@click.option("--outdir", help="默认导出目录")
@click.option("--export-format", type=click.Choice(["xlsx", "csv", "jsonl"]), help="导出文件格式")
@click.option("--save/--no-save", default=True, help="自动保存完整结果（默认开启）")
@click.option("--display-rows", type=click.IntRange(1, 500), default=100, help="每页终端展示行数（默认完整展示 100 条）")
@click.option("--output-format", type=click.Choice(["table", "json", "jsonl"]), default="table", help="终端输出格式")
@click.option("--json", "json_output", is_flag=True, help="等价于 --output-format json")
@click.option("-n", "--nuclei", is_flag=True, help="查询后生成精确 Nuclei 计划并请求执行审批")
@click.option("--scan-ai-dedupe/--no-scan-ai-dedupe", default=None, help="审批前由 AI 按任务筛选和去重候选；保留审计理由")
@click.option(
    "--nuclei-id",
    "nuclei_ids",
    multiple=True,
    help="覆盖 AI 方案的 Nuclei 模板 ID，可重复；输入 all 使用全部已安装模板",
)
@click.option(
    "--nuclei-protocol",
    "nuclei_protocols",
    multiple=True,
    type=click.Choice(["http", "tcp", "dns", "ssl", "headless", "websocket", "whois", "javascript", "code", "file"]),
    help="Nuclei 模板协议，可重复；非 Web 目标保留真实端口",
)
@click.option("--nuclei-headless", is_flag=True, help="在审批方案中启用 Headless 模板")
@click.option("--nuclei-code", is_flag=True, help="在审批方案中启用可信 Code 模板")
@click.option("--nuclei-file", is_flag=True, help="在审批方案中启用 File 模板")
@click.option("--nuclei-oast", is_flag=True, help="在审批方案中启用 OAST 外带交互")
@click.option("--severity", help="Nuclei 严重级别，例如 medium,high,critical；输入 all 使用全部级别")
@click.option("--scan-max-targets", type=click.IntRange(1, 10_000), default=200, help="单次审批最多扫描目标数")
@click.option(
    "--deepseek-search/--no-deepseek-search",
    default=None,
    help="本次是否调用 DeepSeek Search。默认跟随配置里的 search_enabled。",
)
@click.option("--report/--no-report", default=True, help="AI 模式自动生成 Markdown 报告")
@click.option("--report-file", help="AI Markdown 报告路径")
@click.option(
    "--report-lang",
    type=click.Choice(["zh", "en", "both"]),
    default=None,
    help="HTML 报告语言。不传则跟随配置里的界面语言，默认中文；both 表示中英各一份。",
)
@click.option("-batch", "--batch", is_flag=True, help="兼容 2.0 无人值守标记（不会跳过扫描审批）")
@click.option("--update", is_flag=True, help="从 GitHub 检查并安装最新版 FofaMap，保留配置与报告")
@click.option("-up", "--update-nuclei", is_flag=True, help="更新 Nuclei 与模板")
@click.option("--setup-if-needed", is_flag=True, hidden=True)
@click.option("--setup", is_flag=True, help="打开账号与模型配置引导，保存后立即验证")
def main(**options: Any) -> None:
    """FOFA 资产检索、导出、MCP 与多模型智能体。无参数启动交互式向导。"""
    from utils.stdio import configure_windows_stdio

    configure_windows_stdio()
    set_language(settings.system.language)
    context = click.get_current_context()
    from click.core import ParameterSource

    options["_explicit_check_alive"] = context.get_parameter_source("check_alive") == ParameterSource.COMMANDLINE
    report_language_explicit = options.get("report_lang") is not None
    if options.get("report_lang") not in {"zh", "en", "both"}:
        options["report_lang"] = "en" if settings.system.language == "en" else "zh"
    if options.pop("json_output"):
        options["output_format"] = "json"
    if options.pop("init_mode"):
        options["cmd"] = "init"
    mapped_from_rule = False
    if options.get("rule") and not options.get("query") and options.get("cmd") != "rules":
        from core.rules import resolve_rule_query

        try:
            options["query"] = resolve_rule_query(options["rule"]).query
            mapped_from_rule = True
        except ValueError as exc:
            raise click.ClickException(str(exc)) from exc
    full_from_cli = options.get("full")
    explicit_alive = any(arg in sys.argv for arg in ("--check-alive", "--no-check-alive"))
    if options.get("full") is None:
        options["full"] = settings.search.full
    logger.set_enabled(settings.system.logger)
    machine = _machine_output(options)
    if not machine:
        print_banner()
        if mapped_from_rule:
            console.print(f"[green]✓[/] 规则库已映射为：[bold cyan]{options['query']}[/]")
    from utils.onboarding import can_prompt
    from utils.onboarding import setup as guided_setup
    from utils.self_update import update_cli as update_application

    settings_handlers = {
        "init": _interactive_init,
        "credentials": _edit_credentials,
        "provider": _edit_provider,
        "preferences": _edit_preferences,
        "language": _edit_language,
        "field_preferences": _edit_field_preferences,
        "setup": lambda: 0 if guided_setup(_edit_credentials, _edit_provider, force=True) else 130,
        "update_app": lambda: update_application(machine=False),
        "update_nuclei": lambda: asyncio.run(_main_async(**{**options, "cmd": None, "update_nuclei": True})),
    }
    interactive = not machine and can_prompt()
    options["_interactive_recovery"] = interactive
    account_checked = False
    model_checked = False
    try:
        if options.get("update"):
            from utils.self_update import update_cli

            raise SystemExit(update_cli(machine=machine))
        if options.get("setup_if_needed") or options.get("setup"):
            if not interactive:
                notice = t(
                    "请在交互终端运行 fofamap --setup，打开账号与模型配置引导。",
                    "Run fofamap --setup in an interactive terminal to open account and model setup.",
                )
                if machine:
                    _emit_json({"setup_required": True, "command": "fofamap --setup", "message": notice}, options["output_format"])
                else:
                    console.print(notice)
                return
            from utils.onboarding import setup

            if not setup(_edit_credentials, _edit_provider, force=bool(options.get("setup"))):
                raise SystemExit(130)
            return
        while True:
            needs_account = (
                not _has_task(options)
                or options.get("cmd") == "account"
                or any(
                    options.get(key) for key in ("query", "host_query", "count_query", "ai_query", "icon_query", "icon_file", "bat_query")
                )
            )
            if interactive and needs_account and not account_checked:
                from utils.onboarding import ensure_account, ensure_model, first_run, setup

                initial = first_run()
                if not _has_task(options):
                    if not setup(_edit_credentials, _edit_provider):
                        raise SystemExit(130)
                    model_checked = True
                else:
                    if not ensure_account(_edit_credentials, configure_first=initial):
                        raise SystemExit(130) from None
                    if initial or options.get("ai_query"):
                        if not ensure_model(_edit_provider, first_run=initial, required=bool(options.get("ai_query"))):
                            raise SystemExit(130)
                        model_checked = True
                account_checked = True
            if not _has_task(options):
                draft_options = dict(options)
                wizard_options = _wizard(draft_options)
                if wizard_options is None:
                    if draft_options.pop("_wizard_choice_made", False):
                        continue
                    return
                options = wizard_options
                options.pop("_wizard_choice_made", None)
                options["_from_wizard"] = True
            action = options.get("cmd")
            if (
                interactive
                and options.get("ai_query")
                and (not model_checked or not (settings.routing.planner or settings.routing.default))
            ):
                from utils.onboarding import ensure_model

                if not ensure_model(_edit_provider, required=True):
                    raise SystemExit(130)
                model_checked = True
            if not machine and action == "schedule" and options.get("schedule_action") == "menu":
                from utils.schedule_ui import schedule_menu

                schedule_menu()
                options["cmd"] = None
                options["schedule_action"] = "list"
                continue
            # questionary/prompt_toolkit manages its own event loop. Running the
            # init wizard inside asyncio.run() causes a nested-loop RuntimeError.
            if not machine and action in _SETTINGS_ACTIONS:
                code = settings_handlers[action]()
                if action == "init" and not options.get("_from_wizard"):
                    raise SystemExit(code)
                options["cmd"] = None
                account_checked = action not in {"credentials", "init", "setup"} and account_checked
                model_checked = action not in {"provider", "init", "setup"} and model_checked
                if not report_language_explicit:
                    options["report_lang"] = language()
                if full_from_cli is None:
                    options["full"] = settings.search.full
                if not explicit_alive:
                    options["check_alive"] = settings.fast_check.check_alive
                continue
            from providers.base import ProviderError

            try:
                code = asyncio.run(_main_async(**options))
            except FofaError as exc:
                from core.models import FofaErrorCode

                if not interactive or exc.code != FofaErrorCode.AUTH_FAILED:
                    raise
                from utils.onboarding import ensure_account

                console.print(t("FOFA 账号已失效，进入配置。", "FOFA credentials expired. Opening setup."))
                if _edit_credentials() == 130 or not ensure_account(_edit_credentials):
                    raise SystemExit(130) from None
                account_checked = True
                continue
            except ProviderError as exc:
                if not interactive or exc.code not in {
                    "model_auth_failed",
                    "model_not_found",
                    "model_provider_not_configured",
                    "model_credential_not_allowed",
                }:
                    raise
                from utils.onboarding import ensure_model

                console.print(t("模型无法使用，进入模型配置。", "The model is unavailable. Opening model setup."))
                if _edit_provider() == 130 or not ensure_model(_edit_provider, required=True):
                    raise SystemExit(130) from None
                model_checked = True
                continue
            if code == 130 and options.get("_from_wizard"):
                for key in (
                    "cmd",
                    "query",
                    "host_query",
                    "count_query",
                    "ai_query",
                    "icon_query",
                    "icon_file",
                    "bat_query",
                    "update",
                    "update_nuclei",
                ):
                    options[key] = None
                continue
            break
    except FofaError as exc:
        if machine:
            _emit_json({"error": exc.as_dict()}, options["output_format"])
        else:
            render_error(exc.code.value, exc.message, exc.alternatives)
        raise SystemExit(2) from exc
    except KeyboardInterrupt:
        if not machine:
            console.print("\n[yellow]操作已取消。[/]")
        raise SystemExit(130) from None
    raise SystemExit(code)


if __name__ == "__main__":
    main()
