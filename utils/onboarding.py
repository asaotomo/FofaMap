"""Interactive credential checks. Machine interfaces never call this module."""

from __future__ import annotations

import asyncio
import os
import sys
from collections.abc import Callable

from config import settings
from core.client import FofaClient
from core.models import FofaError, FofaErrorCode
from providers.base import ProviderError
from utils.cli_ui import console, section
from utils.i18n import t


def can_prompt() -> bool:
    """A usable keyboard is sufficient; PowerShell/tee can capture stdout."""
    return bool(sys.stdin is not None and sys.stdin.isatty())


def first_run() -> bool:
    import config

    return bool(config.configuration_problem or not config._default_read_path(os.environ).is_file())


def setup(edit_account: Callable[[], int], edit_model: Callable[[], int], *, force: bool = False) -> bool:
    initial = first_run()
    section(t("账号与模型配置引导", "Account and model setup"), t("第 1/2 步 · FOFA 账号", "Step 1/2 · FOFA account"))
    if not ensure_account(edit_account, configure_first=initial or force):
        return False
    section(t("账号与模型配置引导", "Account and model setup"), t("第 2/2 步 · AI 模型（可选）", "Step 2/2 · AI model (optional)"))
    return ensure_model(edit_model, first_run=initial or force or not (settings.routing.planner or settings.routing.default))


async def check_account() -> None:
    async with FofaClient(max_retries=0) as client:
        await asyncio.wait_for(client.account(), timeout=15)


async def check_model() -> None:
    """Check credentials and the catalog without generating billable completions."""
    from providers.registry import ProviderRegistry

    registry = ProviderRegistry(settings, execution_mode="interactive")
    try:
        name = settings.routing.planner or settings.routing.default
        provider = registry.get(name)
        provider._api_key()
        models = await asyncio.wait_for(provider.discover_models(), timeout=15)
        if provider.profile.model and models and provider.profile.model not in models:
            raise ProviderError("The configured model is absent from the provider catalog", code="model_not_found")
    finally:
        await registry.aclose()


def ensure_account(edit: Callable[[], int], *, configure_first: bool = False) -> bool:
    from utils import prompts

    if not settings.fofa.api_key or configure_first:
        heading = (
            t("首次使用 · 配置 FOFA 账号", "First run · Set up your FOFA account")
            if first_run() else t("配置 FOFA 账号", "Set up your FOFA account")
        )
        section(heading)
        console.print(
            t(
                "请先填写 FOFA API Key。邮箱可选，保存后会立即验证。",
                "Enter your FOFA API key first. Email is optional; the saved key is verified immediately.",
            )
        )
        if edit() == 130 or not settings.fofa.api_key:
            return False
    while True:
        try:
            with console.status(t("正在验证 FOFA 账号…", "Checking your FOFA account…")):
                asyncio.run(check_account())
            console.print(f"[green]✓ {t('FOFA 账号验证通过。', 'FOFA account verified.')}[/]")
            return True
        except FofaError as exc:
            invalid = exc.code == FofaErrorCode.AUTH_FAILED
            # Do not print provider error bodies: they may echo credentials.
            notice = (
                t("FOFA 密钥无效或已过期，请重新配置。", "The FOFA key is invalid or expired. Please configure it again.")
                if invalid else t("FOFA 暂时无法验证：", "FOFA could not be checked: ") + exc.code.value
            )
            console.print(f"[yellow]{notice}[/]")
            if invalid:
                previous = (settings.fofa.email, settings.fofa.api_key)
                if edit() == 130 or previous == (settings.fofa.email, settings.fofa.api_key):
                    return False
                continue
        except (TimeoutError, OSError):
            console.print(f"[yellow]{t('FOFA 连接超时或网络不可用。', 'FOFA timed out or the network is unavailable.')}[/]")
        from questionary import Choice

        answer = prompts.select(
            t("下一步：", "Next step:"),
            choices=[
                Choice(t("重试验证", "Retry verification"), "retry"),
                Choice(t("修改账号配置", "Edit account settings"), "edit"),
                Choice(t("稍后验证，进入菜单", "Check later and open the menu"), "later"),
            ],
        ).ask()
        if answer == "later":
            return True
        if answer is None or (answer == "edit" and edit() == 130):
            return False


def ensure_model(edit: Callable[[], int], *, required: bool = False, first_run: bool = False) -> bool:
    from utils import prompts

    if not (settings.routing.planner or settings.routing.default):
        if not required:
            if not first_run:
                return True
            configure = prompts.confirm(
                t(
                    "是否继续配置 AI 模型？也可稍后配置，先使用 FOFA 查询。",
                    "Configure an AI model now? You can also set it up later and use FOFA queries first.",
                ),
                default=True,
            ).ask()
            if not configure:
                return True
        section(t("配置 AI 模型", "Set up an AI model"))
        if edit() == 130 or not (settings.routing.planner or settings.routing.default):
            return not required
    while True:
        try:
            with console.status(t("正在检查模型凭证和接口…", "Checking model credentials and endpoint…")):
                asyncio.run(check_model())
            console.print(f"[green]✓ {t('模型接口验证通过。', 'Model endpoint verified.')}[/]")
            return True
        except ProviderError as exc:
            if exc.code in {"model_auth_failed", "model_not_found", "model_provider_not_configured", "model_credential_not_allowed"}:
                notice = t(
                    "模型或凭证缺失、失效或不适用于当前模式，请重新配置。",
                    "The model or credentials are missing, invalid, or unsuitable for this mode. Please configure them again.",
                )
                console.print(f"[yellow]{notice}[/]")
                previous = settings.model_dump()
                previous_env = dict(os.environ)
                if edit() == 130 or (previous == settings.model_dump() and previous_env == dict(os.environ)):
                    return not required
                continue
            # Some compatible APIs do not expose /models. A catalog failure
            # must not label a working completion model as expired.
            notice = t(
                "暂时无法验证模型目录，将在 AI 任务中验证。", "Model catalog could not be checked; the AI task will verify the model."
            )
            console.print(f"[yellow]{notice}[/]")
            return True
        except (TimeoutError, OSError):
            console.print(f"[yellow]{t('模型检查超时，可先使用 FOFA 查询。', 'Model check timed out. FOFA queries remain available.')}[/]")
            return True
