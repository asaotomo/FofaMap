"""Single asynchronous FOFA API client with explicit errors and cursor paging."""

from __future__ import annotations

import asyncio
import base64
import hashlib
import random
import time
from collections.abc import AsyncIterator
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Any
from urllib.parse import quote
from weakref import WeakKeyDictionary

import httpx

from config import load_config, settings
from core.api_errors import CURSOR_EXPIRED_CODES, api_error_code
from core.fields import fofa_request_fields, search_page_size
from core.membership import capability_error, capped_requests_per_second, membership_from_account
from core.models import AssetRecord, FofaError, FofaErrorCode, SearchPage, SearchRequest
from core.version import VERSION
from utils.logger import logger


class _RateLimiter:
    def __init__(self, requests_per_second: float):
        self._interval = 1.0 / requests_per_second
        self._next = 0.0
        self._lock = asyncio.Lock()

    async def wait(self) -> None:
        async with self._lock:
            now = time.monotonic()
            if self._next > now:
                await asyncio.sleep(self._next - now)
            self._next = max(now, self._next) + self._interval


# Share endpoint limits across short-lived MCP clients, separately for each loop/account.
_API_LIMITERS: WeakKeyDictionary = WeakKeyDictionary()


def _endpoint_limiter(base_url: str, key: str, endpoint: str) -> _RateLimiter:
    loop = asyncio.get_running_loop()
    pool = _API_LIMITERS.setdefault(loop, {})
    identity = (base_url, hashlib.sha256(key.encode()).hexdigest(), endpoint)
    if identity not in pool:
        pool[identity] = _RateLimiter(0.2 if endpoint == "stats" else 1.0)
    return pool[identity]


class FofaClient:
    MAX_RETRY_DELAY = 30.0

    def __init__(
        self,
        *,
        api_key: str | None = None,
        email: str | None = None,
        base_url: str | None = None,
        client: httpx.AsyncClient | None = None,
        max_retries: int = 3,
        requests_per_second: float | None = None,
        concurrency: int | None = None,
    ) -> None:
        # Re-read credentials for each new client so Keyring/config rotation works without a server restart.
        current = load_config() if api_key is None and client is None else settings
        self.base_url = (base_url or current.fofa.base_url).rstrip("/")
        self.email = current.fofa.email if email is None else email
        self.key = current.fofa.api_key if api_key is None else api_key
        source = current.fofa.fallback_api_keys if api_key is None else []
        self._fallback_keys = [item for item in source if item and item != self.key]
        self.used_fallback_key = False
        self.max_retries = max_retries
        self._client = client
        self._owns_client = client is None
        self._configured_rps = requests_per_second or settings.system.requests_per_second
        self._limiter = _RateLimiter(self._configured_rps)
        self._semaphore = asyncio.Semaphore(concurrency or settings.system.concurrency)
        self.user_info: dict[str, Any] | None = None
        self.headers = {"User-Agent": f"FofaMap/{VERSION}"}
        self.cursor_page_fallback: str | None = None
        self.request_count = 0
        self.fetched_records = 0
        self.reported_charge: float | None = None

    async def __aenter__(self) -> FofaClient:
        await self._get_client()
        return self

    async def __aexit__(self, *_: object) -> None:
        await self.aclose()

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(http2=True, verify=True, timeout=httpx.Timeout(60.0), follow_redirects=False)
        return self._client

    async def aclose(self) -> None:
        if self._owns_client and self._client is not None:
            await self._client.aclose()
            self._client = None

    def _auth_params(self) -> dict[str, str]:
        if not self.key:
            raise FofaError(FofaErrorCode.AUTH_FAILED, "未配置 FOFA_API_KEY")
        params = {"key": self.key, "lang": "zh-CN"}
        if self.email:
            params["email"] = self.email
        return params

    @staticmethod
    def _classify_error(message: str, status_code: int | None = None, api_code: int | None = None) -> FofaError:
        api_code = api_code if api_code is not None else api_error_code(message)
        if api_code in CURSOR_EXPIRED_CODES:
            return FofaError(FofaErrorCode.CURSOR_EXPIRED, message, status_code=status_code, api_code=api_code)
        lower = message.lower() + (f" {api_code}" if api_code is not None else "")
        if any(x in lower for x in ("额度", "余额", "quota", "点数", "820031")):
            return FofaError(FofaErrorCode.QUOTA_EXHAUSTED, message, status_code=status_code)
        if any(x in lower for x in ("权限", "permission", "820001", "无权")):
            return FofaError(
                FofaErrorCode.PERMISSION_DENIED,
                message,
                alternatives=["host", "ip", "port", "protocol", "title"],
                status_code=status_code,
            )
        if status_code in {401, 403} or any(x in lower for x in ("-700", "账号无效", "401", "鉴权", "认证", "api key", "unauthorized")):
            return FofaError(FofaErrorCode.AUTH_FAILED, message, status_code=status_code)
        if status_code == 429 or any(x in lower for x in ("45012", "频率", "速度过快", "rate limit")):
            return FofaError(FofaErrorCode.RATE_LIMITED, message, retryable=True, status_code=status_code)
        if status_code is not None and status_code >= 500:
            return FofaError(FofaErrorCode.TRANSPORT_ERROR, message, retryable=True, status_code=status_code)
        if status_code == 400 or any(x in lower for x in ("语法", "query", "qbase64", "查询条件", "820027", "不支持的聚合字段")):
            return FofaError(FofaErrorCode.INVALID_QUERY, message, status_code=status_code)
        return FofaError(FofaErrorCode.INVALID_RESPONSE, message, status_code=status_code)

    @staticmethod
    def _expired_cursor(exc: FofaError) -> bool:
        text = str(exc)
        return (exc.code is FofaErrorCode.CURSOR_EXPIRED or exc.api_code in CURSOR_EXPIRED_CODES
                or api_error_code(text) in CURSOR_EXPIRED_CODES or "游标无效" in text or "游标过期" in text)

    async def _request(self, path: str, params: dict[str, Any]) -> dict[str, Any]:
        try:
            return await self._request_once(path, params)
        except FofaError as exc:
            if exc.code is not FofaErrorCode.AUTH_FAILED or not self._fallback_keys:
                raise
            self.key = self._fallback_keys.pop(0)
            self.used_fallback_key = True
            return await self._request(path, params)

    async def _request_once(self, path: str, params: dict[str, Any]) -> dict[str, Any]:
        client = await self._get_client()
        request_params = {**self._auth_params(), **params}
        last_error: FofaError | None = None
        for attempt in range(self.max_retries + 1):
            try:
                endpoint = "stats" if path == "/api/v1/search/stats" else "host" if path.startswith("/api/v1/host/") else None
                if path in {"/api/v1/search/all", "/api/v1/search/next"}:
                    endpoint = "search"
                await self._limiter.wait()
                async with self._semaphore:
                    if endpoint:
                        await _endpoint_limiter(self.base_url, self.key, endpoint).wait()
                    self.request_count += 1
                    response = await client.get(f"{self.base_url}{path}", params=request_params, headers=self.headers)
                if response.status_code == 429 or response.status_code >= 500:
                    retry_after = response.headers.get("Retry-After")
                    delay = self._retry_after_seconds(retry_after, 0.5 * (2**attempt))
                    last_error = self._classify_error(response.text[:500] or "FOFA 请求失败", response.status_code)
                    if attempt < self.max_retries:
                        await asyncio.sleep(delay + random.uniform(0, max(0.05, delay * 0.2)))
                        continue
                    raise last_error
                try:
                    data = response.json()
                except ValueError as exc:
                    raise FofaError(FofaErrorCode.INVALID_RESPONSE, "FOFA 返回了非 JSON 响应", status_code=response.status_code) from exc
                if response.is_error or data.get("error"):
                    raw_code = data.get("code", data.get("error_code"))
                    api_code = int(raw_code) if isinstance(raw_code, (int, str)) and str(raw_code).lstrip("-").isdigit() else None
                    error = self._classify_error(
                        str(data.get("errmsg") or data.get("message") or response.text[:500]), response.status_code, api_code
                    )
                    error.api_code = api_code if api_code is not None else api_error_code(error.message)
                    if error.retryable and attempt < self.max_retries:
                        delay = self._retry_after_seconds(response.headers.get("Retry-After"), 0.5 * (2**attempt))
                        await asyncio.sleep(delay + random.uniform(0, max(0.05, delay * 0.2)))
                        last_error = error
                        continue
                    raise error
                if endpoint:
                    self._record_charge(data)
                return data
            except (httpx.TimeoutException, httpx.NetworkError) as exc:
                last_error = FofaError(FofaErrorCode.TRANSPORT_ERROR, str(exc), retryable=True)
                if attempt >= self.max_retries:
                    raise last_error from exc
                await asyncio.sleep(0.5 * (2**attempt) + random.uniform(0, 0.2))
        raise last_error or FofaError(FofaErrorCode.TRANSPORT_ERROR, "FOFA 请求失败")

    def _apply_membership_rate_limit(self) -> None:
        membership = membership_from_account(self.user_info)
        if membership is None:
            return
        capped = capped_requests_per_second(self._configured_rps, membership.vip_level)
        self._limiter = _RateLimiter(capped)

    def _record_charge(self, data: dict[str, Any]) -> None:
        for name in ("consumed_fpoint", "consumed", "cost"):
            value = data.get(name)
            if value is not None:
                self.reported_charge = (self.reported_charge or 0) + float(value)
                break

    async def _require_api(self, api: str) -> None:
        if self.user_info is None:
            await self.account()
        message = capability_error(self.user_info, api)
        if message:
            raise FofaError(
                FofaErrorCode.PERMISSION_DENIED,
                message,
                alternatives=["host", "ip", "port", "protocol", "title"],
            )

    async def account(self) -> dict[str, Any]:
        self.user_info = await self._request("/api/v1/info/my", {})
        self._apply_membership_rate_limit()
        return self.user_info

    async def check_login(self) -> dict[str, Any]:
        return await self.account()

    @staticmethod
    def _encode_query(query: str) -> str:
        return base64.b64encode(query.encode("utf-8")).decode("ascii")

    @classmethod
    def _retry_after_seconds(cls, value: str | None, fallback: float) -> float:
        if value:
            try:
                return min(cls.MAX_RETRY_DELAY, max(0.0, float(value.strip())))
            except ValueError:
                try:
                    retry_at = parsedate_to_datetime(value)
                    if retry_at.tzinfo is None:
                        retry_at = retry_at.replace(tzinfo=timezone.utc)
                    delay = (retry_at - datetime.now(timezone.utc)).total_seconds()
                    return min(cls.MAX_RETRY_DELAY, max(0.0, delay))
                except (TypeError, ValueError, OverflowError):
                    pass
        return min(cls.MAX_RETRY_DELAY, max(0.0, fallback))

    async def search_page(self, request: SearchRequest) -> SearchPage:
        fields = fofa_request_fields(request.fields) or list(request.fields)
        params: dict[str, Any] = {
            "qbase64": self._encode_query(request.query),
            "fields": ",".join(fields),
            "size": search_page_size(request.size, fields),
            "full": str(request.full).lower(),
        }
        if request.continuous or request.cursor:
            path = "/api/v1/search/next"
            if request.cursor:
                params["next"] = request.cursor
        else:
            path = "/api/v1/search/all"
            params["page"] = request.page
        data = await self._request(path, params)
        actual_fields_raw = data.get("fields") or fields
        actual_fields = [x.strip() for x in actual_fields_raw.split(",")] if isinstance(actual_fields_raw, str) else list(actual_fields_raw)
        raw_rows = data.get("results") or []
        self.fetched_records += len(raw_rows)
        records = [AssetRecord.from_row(actual_fields, row if isinstance(row, (list, tuple)) else [row]) for row in raw_rows]
        consumed = data.get("consumed_fpoint")
        if consumed is None:
            consumed = data.get("consumed", data.get("cost"))
        return SearchPage(
            records=records,
            fields=actual_fields,
            total=data.get("size") if isinstance(data.get("size"), int) else data.get("total"),
            next_cursor=data.get("next") or data.get("next_cursor"),
            page=None if request.continuous or request.cursor else request.page,
            consumed=consumed,
            query=request.query,
            metadata={k: v for k, v in data.items() if k not in {"results", "fields", "next", "next_cursor"}},
        )

    async def iter_search(self, request: SearchRequest) -> AsyncIterator[SearchPage]:
        request = request.model_copy(update={"size": search_page_size(request.size, request.fields)})
        cursor = request.cursor
        page_number = request.page
        # start_page > 1 uses FOFA's numbered /search/all window (2.0 semantics).
        # Page 1 keeps cursor pagination so large exports stay continuous.
        use_cursor = bool(request.cursor) or request.continuous or request.page <= 1
        seen: set[tuple[Any, ...]] = set()
        emitted = 0
        spent = 0.0
        fetched = 0
        for _ in range(request.max_pages):
            page_request = request.model_copy(
                update={"cursor": cursor if use_cursor else None, "page": page_number, "continuous": use_cursor}
            )
            try:
                page = await self.search_page(page_request)
            except FofaError as exc:
                if not self._expired_cursor(exc) or not use_cursor:
                    raise
                # A continuation token that dies before any row comes back cannot
                # be mapped onto a page number. Restarting at page 1 would look
                # like the next page.
                if fetched == 0 and request.cursor:
                    raise FofaError(
                        exc.code,
                        f"{exc.message}. The continuation cursor expired. Start a new search; page 1 is not the next page.",
                        api_code=exc.api_code,
                        status_code=exc.status_code,
                    ) from exc
                use_cursor = False
                cursor = None
                page_number = fetched + 1 if fetched else request.page
                logger.debug("FOFA 翻页游标已过期，改用页码继续")
                try:
                    page = await self.search_page(request.model_copy(update={"cursor": None, "page": page_number, "continuous": False}))
                except FofaError as again:
                    if fetched and self._expired_cursor(again):
                        self.cursor_page_fallback = "stopped"
                        return
                    raise
                self.cursor_page_fallback = "continued"
            raw_count = len(page.records)
            if request.dedupe_by:
                filtered: list[AssetRecord] = []
                for record in page.records:
                    key = tuple(record.values.get(field) for field in request.dedupe_by)
                    if key not in seen:
                        seen.add(key)
                        filtered.append(record)
                page.records = filtered
            if emitted + len(page.records) > request.max_records:
                page.records = page.records[: request.max_records - emitted]
            emitted += len(page.records)
            spent += float(page.consumed or 0)
            fetched += 1
            yield page
            if emitted >= request.max_records or raw_count == 0:
                break
            if request.cost_budget is not None and spent >= request.cost_budget:
                break
            if use_cursor:
                cursor = page.next_cursor
                if not cursor:
                    break
                page_number = 1
            else:
                if raw_count < request.size:
                    break
                page_number += 1

    async def host_profile(self, host: str, *, detail: bool = True) -> dict[str, Any]:
        target = host.strip().strip("'\"")
        if not target or any(ch in target for ch in ("/", "\\", "?", "#", "@")):
            raise FofaError(FofaErrorCode.INVALID_QUERY, "主机必须是 IP 地址或域名")
        await self._require_api("host")
        data = await self._request(
            f"/api/v1/host/{quote(target, safe=':.[]-')}",
            {"detail": str(detail).lower()},
        )
        self.fetched_records += 1
        return data

    async def host_search(self, host: str) -> dict[str, Any]:
        return await self.host_profile(host)

    async def stats(self, query: str, fields: list[str], size: int = 5) -> dict[str, Any]:
        await self._require_api("stats")
        return await self._request(
            "/api/v1/search/stats",
            {
                "qbase64": self._encode_query(query),
                "fields": ",".join(fields),
                "size": max(1, min(int(size), 1000)),
            },
        )

    async def stats_search(self, query_str: str, fields: str = "title") -> dict[str, Any]:
        return await self.stats(query_str, [field.strip() for field in fields.split(",") if field.strip()])

    async def search(self, query_str: str, page: int = 1, fields: str | None = None):
        """v2 migration adapter. New code should call :meth:`search_page`."""
        request = SearchRequest(
            query=query_str,
            fields=[field.strip() for field in (fields or settings.search.fields).split(",") if field.strip()],
            size=settings.search.size,
            full=settings.search.full,
            page=page,
        )
        result = await self.search_page(request)
        return [list(record.values.values()) for record in result.records], ",".join(result.fields)
