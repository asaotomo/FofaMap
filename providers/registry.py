"""Provider presets and explicit, auditable task routing."""

from __future__ import annotations

from typing import Any

from config import Config
from providers.base import ModelResult, ProviderError, RouteEvent
from providers.http import HttpModelProvider

MODEL_PRESETS: dict[str, dict[str, Any]] = {
    "openai": {
        "protocol": "openai_responses",
        "base_url": "https://api.openai.com/v1",
        "api_key_env": "OPENAI_API_KEY",
        "models": ["gpt-6.1-sol", "gpt-6-astra", "gpt-6.1-terra", "gpt-6-luna"],
    },
    "deepseek": {
        "protocol": "openai_chat",
        "base_url": "https://api.deepseek.com/v1",
        "api_key_env": "DEEPSEEK_API_KEY",
        "models": ["deepseek-flash", "deepseek-v4-pro"],
        "search": True,
    },
    "anthropic": {
        "protocol": "anthropic_messages",
        "base_url": "https://api.anthropic.com",
        "api_key_env": "ANTHROPIC_API_KEY",
        "models": ["claude-opus-5-5", "claude-fable-5-1", "claude-sonnet-5-5", "claude-haiku-5-5"],
    },
    "xai": {
        "protocol": "openai_chat",
        "base_url": "https://api.x.ai/v1",
        "api_key_env": "XAI_API_KEY",
        "models": ["grok-4.7"],
    },
    "gemini": {
        "protocol": "openai_chat",
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai",
        "api_key_env": "GEMINI_API_KEY",
        "models": ["gemini-4-argon"],
    },
    "kimi": {
        "protocol": "openai_chat",
        "base_url": "https://api.moonshot.cn/v1",
        "api_key_env": "MOONSHOT_API_KEY",
        "models": ["kimi-k3.1-pro", "kimi-k3.1-pro-highspeed", "kimi-k3"],
    },
    "minimax": {
        "protocol": "openai_chat",
        "base_url": "https://api.minimax.cn/v1",
        "api_key_env": "MINIMAX_API_KEY",
        "models": ["MiniMax-M3.1-Flash", "MiniMax-M3"],
    },
    "mimo": {
        "protocol": "openai_chat",
        "base_url": "https://api.xiaomimimo.com/v1",
        "api_key_env": "MIMO_API_KEY",
        "models": ["mimo-v2.6-pro", "mimo-v2.6-flash"],
    },
    "siliconflow": {
        "protocol": "openai_chat",
        "base_url": "https://api.siliconflow.cn/v1",
        "api_key_env": "SILICONFLOW_API_KEY",
        "models": ["deepseek-ai/DeepSeek-V4-Flash", "deepseek-ai/DeepSeek-V4-Pro", "zai-org/GLM-5.2", "Pro/moonshotai/Kimi-K2.6"],
    },
    "zhipu": {
        "protocol": "openai_chat",
        "base_url": "https://open.bigmodel.cn/api/paas/v4",
        "api_key_env": "ZHIPU_API_KEY",
        "models": ["glm-5.3"],
    },
    "ollama": {
        "protocol": "ollama_native",
        "base_url": "http://127.0.0.1:11434",
        "api_key_env": "",
        "models": [],
    },
    "lmstudio": {
        "protocol": "openai_chat",
        "base_url": "http://127.0.0.1:1234/v1",
        "api_key_env": "",
        "models": [],
    },
}

PRESETS_CHECKED_AT = "2026-11-02"
RECOMMENDED_PROVIDER = "deepseek"
MODEL_PRESETS = {RECOMMENDED_PROVIDER: MODEL_PRESETS[RECOMMENDED_PROVIDER],
                 **{name: spec for name, spec in MODEL_PRESETS.items() if name != RECOMMENDED_PROVIDER}}

# Explicit facts from vendor documentation, not model-name pattern guesses.
_REQUIRED_THINKING = {
    "gpt-6.1-sol": ["low", "medium", "high", "xhigh", "max"],
    "gpt-6-astra": ["low", "medium", "high", "xhigh", "max"],
    "kimi-k3.1-pro": ["low", "high", "max"],
    "kimi-k3.1-pro-highspeed": ["low", "high", "max"],
    "glm-5.3": ["low", "high", "max"],
    "MiniMax-M3.1-Flash": ["low", "medium", "high", "xhigh", "max"],
}
_ADAPTIVE_THINKING = {
    "claude-opus-5-5": ["low", "medium", "high", "max"],
    "claude-fable-5-1": ["low", "medium", "high", "max"],
    "claude-sonnet-5-5": ["low", "medium", "high"],
    "claude-haiku-5-5": ["low", "medium", "high"],
}
_OLD_DEFAULTS = {
    "openai": {"gpt-5.6", "gpt-5.6-sol", "gpt-5.6-terra", "gpt-5.6-luna"},
    "anthropic": {"claude-opus-5", "claude-sonnet-5", "claude-fable-5"},
    "kimi": {"kimi-k2.5", "kimi-k2.6"},
    "minimax": {"MiniMax-M3"},
    "mimo": {"mimo-v2.5", "mimo-v2.5-pro"},
    "zhipu": {"glm-5.2"},
    "xai": {"grok-4.6"},
}


def preset_model_traits(model: str) -> dict[str, Any]:
    if model in _ADAPTIVE_THINKING:
        return {"thinking": True, "thinking_required": True, "thinking_mode": "adaptive", "effort": _ADAPTIVE_THINKING[model]}
    if model in _REQUIRED_THINKING:
        return {"thinking": True, "thinking_required": True, "thinking_mode": "required", "effort": _REQUIRED_THINKING[model]}
    return {}


def apply_model_traits(raw: dict[str, Any]) -> None:
    traits = preset_model_traits(str(raw.get("model") or ""))
    if not traits:
        return
    raw["thinking_mode"] = traits["thinking_mode"]
    if traits.get("thinking_required") and raw.get("reasoning_effort") not in traits["effort"]:
        raw["reasoning_effort"] = "low"


def sync_builtin_profiles(data: dict[str, Any]) -> list[str]:
    """Refresh shipped defaults on the model settings page, retaining keys and routing."""
    providers = data.setdefault("providers", {})
    changed = []
    for name, spec in MODEL_PRESETS.items():
        if name in {"ollama", "lmstudio"}:
            continue  # Installed local models are selected by their own server.
        raw = providers.get(name)
        if raw is None:
            raw = {
                "protocol": spec["protocol"], "base_url": spec["base_url"],
                "model": (spec.get("models") or [""])[0], "api_key_env": spec["api_key_env"],
                "structured_output_mode": "prompt" if name == "deepseek" else "auto",
            }
            providers[name] = raw
            apply_model_traits(raw)
            changed.append(name)
        elif isinstance(raw, dict):
            # Custom gateways and explicitly selected future model IDs remain intact.
            if str(raw.get("base_url", "")).rstrip("/") != spec["base_url"].rstrip("/"):
                continue
            before = dict(raw)
            if raw.get("model") in _OLD_DEFAULTS.get(name, set()):
                raw["model"] = spec["models"][0]
            apply_model_traits(raw)
            if raw != before:
                changed.append(name)
    return changed


class ProviderRegistry:
    def __init__(self, config: Config, *, execution_mode: str = "service") -> None:
        self.config = config
        self.execution_mode = execution_mode
        self.providers = {
            name: HttpModelProvider(name, profile, execution_mode=execution_mode) for name, profile in config.providers.items()
        }

    def get(self, name: str) -> HttpModelProvider:
        if name not in self.providers:
            raise ProviderError(
                f"AI 提供商 {name!r} 尚未配置。",
                code="model_provider_not_configured",
                hint="运行 `fofamap init` 重新配置 AI 提供商、模型 ID 和 API 密钥。",
            )
        return self.providers[name]

    async def aclose(self) -> None:
        for provider in self.providers.values():
            await provider.aclose()


class ProviderRouter:
    def __init__(self, registry: ProviderRegistry) -> None:
        self.registry = registry
        self.events: list[RouteEvent] = []

    def _profile_for_task(self, task: str) -> str:
        routing = self.registry.config.routing
        configured = getattr(routing, task, "")
        if task == "reflector" and not configured:
            configured = routing.query_repair
        return configured or routing.default

    async def generate(self, task: str, *, system: str, prompt: str, schema: dict[str, Any] | None = None) -> ModelResult:
        primary = self._profile_for_task(task)
        if not primary:
            raise ProviderError(
                f"任务 {task!r} 没有配置可用的 AI 提供商。",
                code="model_provider_not_configured",
                hint="运行 `fofamap init`，选择 AI 提供商并配置默认模型。",
            )
        candidates = [primary]
        routing = self.registry.config.routing
        if routing.allow_cross_provider_fallback:
            candidates.extend(name for name in routing.fallbacks if name != primary)
        last_error: Exception | None = None
        for index, name in enumerate(candidates):
            provider = self.registry.get(name)
            try:
                result = await provider.generate(system=system, prompt=prompt, schema=schema)
                self.events.append(
                    RouteEvent(
                        task=task,
                        provider=name,
                        model=result.model,
                        reason="configured task route" if index == 0 else f"fallback after: {last_error}",
                        fallback=index > 0,
                        input_tokens=result.input_tokens,
                        output_tokens=result.output_tokens,
                    )
                )
                return result
            except ProviderError as exc:
                last_error = exc
                if index == 0 and (not routing.allow_cross_provider_fallback or not exc.retryable):
                    raise
        raise last_error or ProviderError("all configured providers failed")
