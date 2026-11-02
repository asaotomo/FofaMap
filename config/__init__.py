"""Configuration loading with secret-safe environment and Keyring support."""

from __future__ import annotations

import json
import os
import sys
import warnings
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, Field


class FofaConfig(BaseModel):
    base_url: str = "https://fofa.info"
    email: str = ""
    api_key: str = ""
    fallback_api_keys: list[str] = Field(default_factory=list, exclude=True, repr=False)


class SearchConfig(BaseModel):
    smart_fields: bool = False
    fields: str = "host,protocol,ip,port,title,domain,country"
    size: int = Field(default=100, ge=1, le=10_000)
    full: bool = False
    start_page: int = Field(default=1, ge=1)
    end_page: int = Field(default=2, ge=1)
    max_pages: int = Field(default=10, ge=1)
    max_records: int = Field(default=10_000, ge=1)


class FastCheckConfig(BaseModel):
    check_alive: bool = False
    timeout: int = Field(default=5, ge=1, le=60)
    concurrency: int = Field(default=80, ge=1, le=500)


class SystemConfig(BaseModel):
    language: Literal["zh", "en"] = "zh"
    logger: bool = True
    sheet_merge: bool = True
    concurrency: int = Field(default=10, ge=1, le=100)
    requests_per_second: float = Field(default=2.0, gt=0, le=100)
    export_format: Literal["csv", "jsonl", "xlsx"] = "xlsx"
    output_dir: str = "results"
    artifact_retention_days: int = Field(default=7, ge=1)
    allow_private_network: bool = True
    scan_ai_dedupe: bool = False


class ProviderProfile(BaseModel):
    protocol: Literal["openai_responses", "openai_chat", "anthropic_messages", "ollama_native"]
    thinking_mode: Literal["auto", "required", "adaptive"] = "auto"
    base_url: str
    model: str = ""
    api_key_env: str = ""
    credential_kind: Literal["api_key", "subscription", "interactive_only", "none"] = "api_key"
    structured_output_mode: Literal["auto", "native", "prompt"] = "auto"
    search_enabled: bool = False
    reasoning_effort: str | None = None
    vision_enabled: bool = False
    max_output_tokens: int = Field(default=32768, ge=1, le=524288)
    timeout: float = Field(default=120.0, gt=0)
    api_key: str = Field(default="", exclude=True, repr=False)
    runtime_api_key: str = Field(default="", exclude=True, repr=False)


class RoutingConfig(BaseModel):
    default: str = ""
    planner: str = ""
    query_repair: str = ""
    reflector: str = ""
    summarizer: str = ""
    allow_cross_provider_fallback: bool = False
    fallbacks: list[str] = Field(default_factory=list)


class LegacyUserInfo(BaseModel):
    """Read-only compatibility view for v2 code; secrets are never persisted."""

    email: str = ""
    key: str = ""
    deepseek_api_key: str = ""
    base_url: str = "https://api.deepseek.com/v1"
    model: str = "deepseek-v4-flash"
    api_type: str = "deepseek"


class Config(BaseModel):
    fofa: FofaConfig = Field(default_factory=FofaConfig)
    search: SearchConfig = Field(default_factory=SearchConfig)
    fast_check: FastCheckConfig = Field(default_factory=FastCheckConfig)
    system: SystemConfig = Field(default_factory=SystemConfig)
    providers: dict[str, ProviderProfile] = Field(default_factory=dict)
    routing: RoutingConfig = Field(default_factory=RoutingConfig)
    userinfo: LegacyUserInfo = Field(default_factory=LegacyUserInfo)


def _read_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def _keyring_secret(email: str) -> str:
    try:
        import keyring  # type: ignore

        return keyring.get_password("fofamap", email or "default") or ""
    except Exception:
        return ""


def user_config_path(*, environ: dict[str, str] | None = None, home: Path | None = None, platform: str | None = None) -> Path:
    """Return a writable per-user config path without adding a platformdirs dependency."""
    env = os.environ if environ is None else environ
    user_home = Path.home() if home is None else home
    current_platform = sys.platform if platform is None else platform
    if current_platform == "win32":
        root = Path(env.get("APPDATA") or user_home / "AppData" / "Roaming")
        return root / "FofaMap" / "settings.yaml"
    if current_platform == "darwin":
        return user_home / "Library" / "Application Support" / "FofaMap" / "settings.yaml"
    root = Path(env.get("XDG_CONFIG_HOME") or user_home / ".config")
    return root / "fofamap" / "settings.yaml"


def config_write_path(
    *,
    environ: dict[str, str] | None = None,
    cwd: Path | None = None,
    home: Path | None = None,
    platform: str | None = None,
) -> Path:
    """Choose the init destination: explicit path, source checkout, then user config."""
    env = os.environ if environ is None else environ
    if env.get("FOFAMAP_CONFIG"):
        return Path(env["FOFAMAP_CONFIG"]).expanduser()
    working_directory = Path.cwd() if cwd is None else cwd
    if (working_directory / "config" / "settings.example.yaml").is_file():
        return working_directory / "config" / "settings.yaml"
    return user_config_path(environ=env, home=home, platform=platform)


def _default_read_path(env: dict[str, str]) -> Path:
    if env.get("FOFAMAP_CONFIG"):
        return Path(env["FOFAMAP_CONFIG"]).expanduser()
    project_config = Path.cwd() / "config" / "settings.yaml"
    if project_config.is_file():
        return project_config
    per_user = user_config_path(environ=env)
    if per_user.is_file():
        return per_user
    # Read-only migration fallback for old source layouts.
    return Path(__file__).with_name("settings.yaml")


def load_config(path: str | Path | None = None, environ: dict[str, str] | None = None) -> Config:
    env = os.environ if environ is None else environ
    config_path = Path(path) if path else _default_read_path(env)
    data = _read_yaml(config_path)
    local_yaml_secrets_confirmed = bool((data.get("security") or {}).get("local_yaml_secrets_confirmed"))

    legacy = data.get("userinfo") or {}
    fofa_data = dict(data.get("fofa") or {})
    yaml_email = fofa_data.get("email") or legacy.get("email") or ""
    yaml_key = fofa_data.get("api_key") or fofa_data.get("key") or legacy.get("key") or ""
    if yaml_key and not local_yaml_secrets_confirmed:
        warnings.warn(
            "YAML 中的 FOFA API 密钥已过时且不安全；请改用 FOFA_API_KEY、系统钥匙串或容器密钥。",
            DeprecationWarning,
            stacklevel=2,
        )

    email = env.get("FOFA_EMAIL", yaml_email)
    env_key = env.get("FOFA_API_KEY") or env.get("FOFA_KEY") or ""
    ordered: list[str] = []
    for candidate in (env_key, _keyring_secret(email), yaml_key):
        if candidate and candidate not in ordered:
            ordered.append(candidate)
    api_key = ordered[0] if ordered else ""
    fofa_data.update({"email": email, "api_key": api_key, "fallback_api_keys": ordered[1:]})
    data["fofa"] = fofa_data

    providers_json = env.get("FOFAMAP_PROVIDERS_JSON")
    if providers_json:
        data["providers"] = json.loads(providers_json)
    elif not data.get("providers") and legacy:
        legacy_type = str(legacy.get("api_type") or "deepseek").strip().lower()
        provider_name, protocol, default_url, key_env, credential_kind = {
            "deepseek": ("deepseek", "openai_chat", "https://api.deepseek.com/v1", "DEEPSEEK_API_KEY", "api_key"),
            "openai": ("openai", "openai_chat", "https://api.openai.com/v1", "OPENAI_API_KEY", "api_key"),
            "ollama": ("ollama", "ollama_native", "http://127.0.0.1:11434", "", "none"),
            "lmstudio": ("lmstudio", "openai_chat", "http://127.0.0.1:1234/v1", "", "none"),
        }.get(
            legacy_type,
            ("legacy", "openai_chat", "https://api.deepseek.com/v1", "MODEL_API_KEY", "api_key"),
        )
        legacy_model_key = str(legacy.get("deepseek_api_key") or legacy.get("api_key") or "")
        if legacy_model_key:
            warnings.warn(
                "旧版 YAML 中的模型 API 密钥已过时且不安全；请迁移到提供商环境变量或系统钥匙串。",
                DeprecationWarning,
                stacklevel=2,
            )
        data["providers"] = {
            provider_name: {
                "protocol": protocol,
                "base_url": legacy.get("base_url") or default_url,
                "model": legacy.get("model") or "",
                "api_key_env": key_env,
                "credential_kind": credential_kind,
                "structured_output_mode": "prompt" if provider_name == "deepseek" else "auto",
                "runtime_api_key": legacy_model_key,
            }
        }
        if not data.get("routing"):
            data["routing"] = {
                "default": provider_name,
                "planner": provider_name,
                "query_repair": provider_name,
                "reflector": provider_name,
                "summarizer": provider_name,
                "allow_cross_provider_fallback": False,
                "fallbacks": [],
            }
    for provider_name, provider_data in (data.get("providers") or {}).items():
        if (
            isinstance(provider_data, dict)
            and (provider_data.get("api_key") or provider_data.get("key"))
            and not local_yaml_secrets_confirmed
        ):
            warnings.warn(
                f"提供商 {provider_name!r} 的模型 API 密钥写在配置文件中；请确保该文件私有且已被 Git 忽略。",
                DeprecationWarning,
                stacklevel=2,
            )
            provider_data["api_key"] = provider_data.get("api_key") or provider_data.get("key")
    system_data = dict(data.get("system") or {})
    if env.get("FOFAMAP_LANGUAGE") in {"zh", "en"}:
        system_data["language"] = env["FOFAMAP_LANGUAGE"]
    if "FOFAMAP_ALLOW_PRIVATE_NETWORK" in env:
        system_data["allow_private_network"] = env["FOFAMAP_ALLOW_PRIVATE_NETWORK"].lower() == "true"
    if "FOFAMAP_ARTIFACT_RETENTION_DAYS" in env:
        system_data["artifact_retention_days"] = int(env["FOFAMAP_ARTIFACT_RETENTION_DAYS"])
    data["system"] = system_data

    # v2 read compatibility only. New code consumes settings.fofa/providers.
    legacy_profile = next(iter((data.get("providers") or {}).values()), {})
    data["userinfo"] = {
        "email": email,
        "key": api_key,
        "deepseek_api_key": env.get("DEEPSEEK_API_KEY", ""),
        "base_url": legacy_profile.get("base_url", legacy.get("base_url", "https://api.deepseek.com/v1")),
        "model": legacy_profile.get("model", legacy.get("model", "deepseek-v4-flash")),
        "api_type": legacy.get("api_type", "deepseek"),
    }
    return Config.model_validate(data)


configuration_problem: Path | None = None


def load_runtime_config() -> Config:
    """Keep the CLI available so a damaged configuration can be repaired."""
    global configuration_problem
    try:
        loaded = load_config()
    except (ValueError, TypeError, AttributeError, OSError, yaml.YAMLError):
        configuration_problem = _default_read_path(os.environ)
        preferred = os.environ.get("FOFAMAP_LANGUAGE")
        if preferred not in {"zh", "en"}:
            try:
                preferred = (_read_yaml(configuration_problem).get("system") or {}).get("language")
            except (ValueError, TypeError, AttributeError, OSError, yaml.YAMLError):
                preferred = None
        return Config(system=SystemConfig(language="en" if preferred == "en" else "zh"))
    configuration_problem = None
    return loaded


settings = load_runtime_config()
