"""Interface language. Chinese is the default; English is chosen in setup."""

from __future__ import annotations

_LANGUAGE = "zh"


def language() -> str:
    return _LANGUAGE


def set_language(value: str | None) -> str:
    global _LANGUAGE
    _LANGUAGE = "en" if str(value or "").strip().lower() == "en" else "zh"
    return _LANGUAGE


def t(zh: str, en: str) -> str:
    return en if _LANGUAGE == "en" else zh
