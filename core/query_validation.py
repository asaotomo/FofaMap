"""Local FOFA expression parser; no network requests or field entitlement guesses."""

from __future__ import annotations

import re

from core.syntax import QUERY_FIELDS

FIELDS = {item["field"] for item in QUERY_FIELDS} | {"base_protocol", "cert.issuer.cn", "asset_type"}
BOOLEAN_FIELDS = {name for name in FIELDS if name.startswith("is_") or ".is_" in name}
NUMBER_FIELDS = {
    "port", "asn", "status_code", "icon_hash", "header_hash", "banner_hash", "sdk_hash", "port_size", "port_size_gt", "port_size_lt",
}


class QuerySyntaxError(ValueError):
    pass


def validate_query(query: str) -> list[str]:
    if not query.strip():
        return ["query is empty"]
    if len(query) > 4096:
        return ["query exceeds 4096 characters"]
    if any(ord(char) < 32 or ord(char) == 127 for char in query):
        return ["query contains control characters"]
    tokens = []
    position = 0
    try:
        while position < len(query):
            if query[position].isspace():
                position += 1
                continue
            start = position
            char = query[position]
            if char == '"':
                position += 1
                while position < len(query):
                    if query[position] == "\\":
                        position += 2
                        continue
                    if query[position] == '"':
                        break
                    position += 1
                if position >= len(query):
                    raise QuerySyntaxError("unbalanced double quote")
                position += 1
                tokens.append(("value", query[start:position], start))
                continue
            op = next((op for op in ("&&", "||", "==", "!=", "*=", "=", "(", ")") if query.startswith(op, position)), None)
            if op:
                tokens.append(("op", op, position))
                position += len(op)
                continue
            if char in "&|!<>*":
                raise QuerySyntaxError(f"unsupported operator near character {position + 1}: {char}")
            while position < len(query) and not query[position].isspace() and query[position] not in '"&|!=()*<>':
                position += 1
            if position == start:
                raise QuerySyntaxError(f"unexpected character at {position + 1}")
            tokens.append(("word", query[start:position], start))
        index = 0

        def expression(depth=0):
            nonlocal index
            if depth > 64:
                raise QuerySyntaxError("query nesting exceeds 64 levels")
            term(depth)
            while index < len(tokens) and tokens[index][1] in {"&&", "||"}:
                index += 1
                term(depth)

        def term(depth):
            nonlocal index
            if index >= len(tokens):
                raise QuerySyntaxError("missing expression after operator")
            token = tokens[index]
            if token[1] == "(":
                index += 1
                expression(depth + 1)
                if index >= len(tokens) or tokens[index][1] != ")":
                    raise QuerySyntaxError("unbalanced parentheses")
                index += 1
                return
            if token[0] not in {"word", "value"}:
                raise QuerySyntaxError(f"missing operand near {token[1]}")
            index += 1
            if index < len(tokens) and tokens[index][1] in {"=", "==", "!=", "*="}:
                field = token[1]
                if token[0] != "word" or field not in FIELDS:
                    raise QuerySyntaxError(f"unknown FOFA query field: {field}; read fofa_syntax")
                index += 1
                if index >= len(tokens) or tokens[index][0] not in {"word", "value"}:
                    raise QuerySyntaxError(f"missing value for {field}")
                value = tokens[index]
                index += 1
                if value[0] != "value":
                    valid_bool = field in BOOLEAN_FIELDS and value[1] in {"true", "false"}
                    valid_number = field in NUMBER_FIELDS and re.fullmatch(r"-?\d+", value[1])
                    if not valid_bool and not valid_number:
                        raise QuerySyntaxError(f"{field} requires a double-quoted string value")

        expression()
        if index != len(tokens):
            raise QuerySyntaxError(f"missing logical operator or unexpected token: {tokens[index][1]}")
        return []
    except QuerySyntaxError as exc:
        return [str(exc)]
