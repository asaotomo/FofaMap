"""Application logging; stderr keeps MCP stdio stdout protocol-clean."""

from __future__ import annotations

import logging
import re
import sys


class _RedactRequestSecrets(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        message = record.getMessage()
        record.msg = re.sub(
            r"(?i)([?&](?:key|api_key|email|access_token|token|next)=)[^\s&\"<>]+",
            r"\1[redacted]",
            message,
        )
        record.args = ()
        return True


# MCP may configure the root logger at INFO. HTTPX request URLs contain FOFA credentials.
for _name in ("httpx", "httpcore"):
    _http_logger = logging.getLogger(_name)
    _http_logger.setLevel(logging.WARNING)
    _http_logger.addFilter(_RedactRequestSecrets())


class _Logger:
    def __init__(self) -> None:
        self._logger = logging.getLogger("fofamap")
        self._logger.addFilter(_RedactRequestSecrets())
        if not self._logger.handlers:
            handler = logging.StreamHandler(sys.stderr)
            handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
            self._logger.addHandler(handler)
        self._logger.setLevel(logging.INFO)

    def debug(self, message: object) -> None:
        self._logger.debug(message)

    def info(self, message: object) -> None:
        self._logger.info(message)

    def warning(self, message: object) -> None:
        self._logger.warning(message)

    def error(self, message: object) -> None:
        self._logger.error(message)

    def ai(self, message: object) -> None:
        self._logger.info("[agent] %s", message)

    def set_enabled(self, enabled: bool) -> None:
        """Honor config/system.logger without touching MCP stdout."""
        self._logger.disabled = not enabled
        self._logger.setLevel(logging.INFO if enabled else logging.CRITICAL + 1)


logger = _Logger()
