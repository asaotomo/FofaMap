"""Stable public contracts shared by CLI, REST, MCP and agents."""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, model_validator


class FofaErrorCode(str, Enum):
    AUTH_FAILED = "auth_failed"
    QUOTA_EXHAUSTED = "quota_exhausted"
    PERMISSION_DENIED = "permission_denied"
    RATE_LIMITED = "rate_limited"
    INVALID_QUERY = "invalid_query"
    TRANSPORT_ERROR = "transport_error"
    INVALID_RESPONSE = "invalid_response"
    CURSOR_EXPIRED = "cursor_expired"


class FofaError(Exception):
    def __init__(
        self,
        code: FofaErrorCode,
        message: str,
        *,
        retryable: bool = False,
        alternatives: list[str] | None = None,
        status_code: int | None = None,
        api_code: int | None = None,
    ):
        super().__init__(message)
        self.code = code
        self.message = message
        self.retryable = retryable
        self.alternatives = alternatives or []
        self.status_code = status_code
        self.api_code = api_code

    def as_dict(self) -> dict[str, Any]:
        return {
            "code": self.code.value,
            "message": self.message,
            "retryable": self.retryable,
            "alternatives": self.alternatives,
            "status_code": self.status_code,
            "api_code": self.api_code,
        }


class SearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=4096)
    fields: list[str] = Field(default_factory=lambda: ["host", "protocol", "ip", "port", "title"])
    size: int = Field(default=100, ge=1, le=10_000)
    full: bool = False
    cursor: str | None = None
    continuous: bool = False
    page: int = Field(default=1, ge=1)
    max_records: int = Field(default=10_000, ge=1, le=1_000_000)
    max_pages: int = Field(default=10, ge=1, le=10_000)
    cost_budget: int | None = Field(default=None, ge=0)
    dedupe_by: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def normalize_fields(self) -> SearchRequest:
        self.fields = list(dict.fromkeys(field.strip() for field in self.fields if field.strip()))
        if not self.fields:
            raise ValueError("fields 至少需要包含一个字段")
        return self


class AssetRecord(BaseModel):
    values: dict[str, Any]

    @classmethod
    def from_row(cls, fields: list[str], row: list[Any] | tuple[Any, ...]) -> AssetRecord:
        if len(row) != len(fields):
            raise FofaError(
                FofaErrorCode.INVALID_RESPONSE,
                f"FOFA 为 {len(fields)} 个字段返回了 {len(row)} 个值，拒绝错位行",
            )
        return cls(values=dict(zip(fields, row, strict=True)))


class SearchPage(BaseModel):
    records: list[AssetRecord] = Field(default_factory=list)
    fields: list[str]
    total: int | None = None
    next_cursor: str | None = None
    page: int | None = None
    consumed: int | float | None = None
    query: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class QueryValidation(BaseModel):
    valid: bool
    query: str
    errors: list[str] = Field(default_factory=list)


class ExportRequest(BaseModel):
    search: SearchRequest
    format: str = Field(default="jsonl", pattern="^(jsonl|csv|xlsx)$")
    filename: str | None = None
