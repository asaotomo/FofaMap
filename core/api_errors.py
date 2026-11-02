"""FOFA error identifiers shared by the client and public tool envelopes."""

import re

# 40070 was observed in the independent 2026-11-02 live retest.
# 40870 is retained only for compatibility with earlier integrations.
CURSOR_EXPIRED_CODES = frozenset({40070, 40870})
_API_CODE = re.compile(r"^\s*\[(-?\d+)\]|(?<!\d)(40070|40870|-700|820\d{3}|45012)(?!\d)")


def api_error_code(message: str) -> int | None:
    match = _API_CODE.search(message)
    return int(next(group for group in match.groups() if group is not None)) if match else None
