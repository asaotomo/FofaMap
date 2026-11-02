"""Consistent Esc/Ctrl+C cancellation for synchronous and asynchronous terminal prompts."""

from __future__ import annotations

import sys

import questionary as _questionary
from prompt_toolkit.key_binding import KeyBindings, merge_key_bindings
from prompt_toolkit.utils import get_cwidth
from questionary import Choice

from utils.i18n import t


def _prepare(question):
    app = getattr(question, "application", None)
    if app is None:
        return question
    bindings = KeyBindings()

    @bindings.add("escape")
    @bindings.add("c-c", eager=True)
    def cancel(event):
        event.app.exit(result=None)

    app.key_bindings = merge_key_bindings([app.key_bindings, bindings]) if app.key_bindings else bindings
    app.timeoutlen = 0.25
    app.ttimeoutlen = 0.1
    return question


def _hint(kwargs):
    _terminal_output(kwargs)
    original = kwargs.get("instruction")
    if original:
        kwargs["instruction"] = " ".join(original.splitlines()).strip()
    else:
        kwargs.pop("instruction", None)
    return kwargs


def _terminal_output(kwargs):
    if "output" not in kwargs and not sys.stdout.isatty() and sys.stderr.isatty():
        from prompt_toolkit.output.defaults import create_output

        kwargs["output"] = create_output(stdout=sys.stderr)
    return kwargs


def select(message, choices, **kwargs):
    choices = list(choices)
    show_back = kwargs.pop("show_back", True)
    if show_back and not any(isinstance(choice, Choice) and choice.value is None for choice in choices):
        back = Choice(t("↩ 返回上一级", "↩ Back"))
        back.value = None
        choices.append(back)
    return _prepare(_questionary.select(message, choices=choices, **_hint(kwargs)))


def text(message, **kwargs):
    _terminal_output(kwargs)
    original = " ".join(str(kwargs.get("instruction") or "").splitlines()).strip()
    supplied = dict(kwargs)
    question = _questionary.text(message, **_hint(kwargs))
    if original.startswith(("例如", "For example")) and getattr(question, "application", None) is not None:
        from prompt_toolkit.document import Document
        from prompt_toolkit.lexers import SimpleLexer
        from prompt_toolkit.shortcuts import PromptSession
        from questionary.prompts.common import build_validator
        from questionary.styles import merge_styles_default

        default = supplied.pop("default", "")
        validate = supplied.pop("validate", None)
        style = supplied.pop("style", None)
        qmark = supplied.pop("qmark", "?")
        supplied.pop("instruction", None)
        supplied.setdefault("lexer", SimpleLexer("fg:#e2e8f0"))
        def prompt_tokens():
            heading = " " + message.strip() + "  "
            columns = question.application.output.get_size().columns
            available = max(0, columns - get_cwidth(qmark + heading) - 1)
            example = original
            if get_cwidth(example) > available:
                example = ""
                for char in original:
                    if get_cwidth(example + char + "…") > available:
                        break
                    example += char
                example = example + "…" if available else ""
            return [
                ("class:qmark", qmark),
                ("class:question", heading),
                ("fg:#8b93a7 italic", example),
                ("", "\n"),
                ("fg:#67e8f9 nobold", "  › "),
            ]

        session = PromptSession(prompt_tokens, style=merge_styles_default([style]), validator=build_validator(validate), **supplied)
        session.default_buffer.reset(Document(default))
        question.application = session.app
    return _prepare(question)


def password(message, **kwargs):
    return _prepare(_questionary.password(message, **_hint(kwargs)))


def confirm(message, **kwargs):
    # confirm does not accept an instruction option on every supported Questionary version.
    return _prepare(_questionary.confirm(message, **_terminal_output(kwargs)))
