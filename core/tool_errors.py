"""Safe, actionable MCP error envelopes usable by both 2.0 and newer clients."""

import asyncio
import json
import re
from functools import wraps

from core.api_errors import CURSOR_EXPIRED_CODES, api_error_code
from core.models import FofaError


def redact(message: str) -> str:
    message = re.sub(r"(?i)([?&](?:key|email|api_key|token|access_token)=)[^\s&\"<>]+", r"\1[redacted]", message)
    message = re.sub(r'''(?i)(["']?(?:approval_token|api_key|access_token)["']?\s*[:=]\s*["']?)[^\s,'"}]+''',
                     r"\1[redacted]", message)
    return message[:2000]


def error_payload(exc: Exception, *, tool: str = "") -> dict:
    if isinstance(exc, FofaError):
        data = exc.as_dict()
        code = data["code"]
        api_code = exc.api_code if exc.api_code is not None else api_error_code(exc.message)
        if api_code in CURSOR_EXPIRED_CODES:
            code = "cursor_expired"
        action = {
            "cursor_expired": "restart_search",
            "auth_failed": "configure_credentials",
            "quota_exhausted": "stop_and_check_quota",
            "permission_denied": "check_membership",
            "rate_limited": "retry_with_backoff",
            "invalid_query": "repair_query",
            "transport_error": "retry_with_backoff",
        }.get(code, "inspect_response")
        return {"error": True, **data, "message": redact(exc.message), "code": code, "api_code": api_code, "action": action, "tool": tool}
    if isinstance(exc, KeyError):
        return {
            "error": True,
            "code": "not_found",
            "message": redact(f"Job or schedule not found: {exc.args[0] if exc.args else 'unknown'}"),
            "retryable": False,
            "action": "check_id",
            "tool": tool,
        }
    if isinstance(exc, asyncio.TimeoutError):
        return {
            "error": True,
            "code": "deadline_exceeded",
            "message": "Operation deadline exceeded",
            "retryable": True,
            "action": "check_job_status",
            "tool": tool,
        }
    message = redact(str(exc))
    code = "invalid_argument" if isinstance(exc, ValueError) or type(exc).__name__ == "ToolError" else "operation_failed"
    action = "correct_parameters"
    if "invalid fofa query" in message.lower():
        code, action = "invalid_query", "repair_query"
    elif "scanning is disabled" in message:
        code, action = "scanning_disabled", "configure_scanning"
    elif "allowlist" in message:
        code, action = "scope_not_allowed", "choose_allowed_templates"
    elif "approval" in message or "token" in message:
        code, action = "approval_required", "obtain_new_approval"
    return {"error": True, "code": code, "message": message or type(exc).__name__, "retryable": False, "action": action, "tool": tool}


def tool_guard(fn):
    from mcp.server.mcpserver.exceptions import ToolError

    @wraps(fn)
    async def guarded(*args, **kwargs):
        try:
            return await fn(*args, **kwargs)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            payload = error_payload(exc, tool=fn.__name__)
            # ToolError is the SDK-supported portable isError path. JSON is deliberately preserved in text.
            raise ToolError(json.dumps(payload, ensure_ascii=False)) from None

    return guarded
