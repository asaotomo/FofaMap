"""Optional HTTP helpers with DNS rebinding-aware private-network blocking."""

from __future__ import annotations

import asyncio
import codecs
import contextvars
import ipaddress
import os
import socket
import ssl
import time
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin, urlparse

import httpx
import mmh3

from config import settings
from core.version import VERSION
from utils.logger import logger

# Clash / Surge / Quantumult X fake-ip (RFC 2544 benchmarking range). Python marks
# these as non-global, but the actual HTTP fetch still egresses via the local proxy.
_FAKE_IP_NETWORKS = (ipaddress.ip_network("198.18.0.0/15"),)
_METADATA_NETWORKS = (
    ipaddress.ip_network("169.254.169.254/32"),
    ipaddress.ip_network("100.100.100.200/32"),
    ipaddress.ip_network("fd00:ec2::254/128"),
)


def is_cloud_metadata_address(address: str) -> bool:
    ip = ipaddress.ip_address(address)
    return any(ip in network for network in _METADATA_NETWORKS)


def is_blocked_ssrf_address(address: str, *, allow_private: bool = False) -> bool:
    if is_cloud_metadata_address(address):
        return True
    if allow_private:
        return False
    ip = ipaddress.ip_address(address)
    if any(ip in network for network in _FAKE_IP_NETWORKS):
        return False
    return not ip.is_global


def assert_public_http_url(url: str, *, allow_private: bool | None = None) -> str:
    if not url.startswith(("http://", "https://")):
        url = f"http://{url}"
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError("仅支持不带账号密码的 HTTP(S) URL")
    if allow_private is None:
        allow_private = settings.system.allow_private_network
    try:
        addresses = {
            item[4][0]
            for item in socket.getaddrinfo(
                parsed.hostname, parsed.port or (443 if parsed.scheme == "https" else 80), type=socket.SOCK_STREAM
            )
        }
    except socket.gaierror as exc:
        raise ValueError(f"无法解析 {parsed.hostname}") from exc
    blocked = [address for address in addresses if is_blocked_ssrf_address(address, allow_private=allow_private)]
    if blocked:
        if any(is_cloud_metadata_address(address) for address in blocked):
            raise ValueError("已拦截云元数据目标")
        raise ValueError("已拦截私网、回环、链路本地、保留地址目标")
    return url


_REDIRECT_STATUS = {301, 302, 303, 307, 308}
_MAX_ICON_REDIRECTS = 5


async def _get_with_safe_redirects(
    client: httpx.AsyncClient, url: str, *, max_bytes: int = 4 * 1024 * 1024,
) -> httpx.Response:
    current = assert_public_http_url(url)
    for _ in range(_MAX_ICON_REDIRECTS + 1):
        async with client.stream("GET", current) as response:
            if response.status_code in _REDIRECT_STATUS:
                location = (response.headers.get("location") or "").strip()
                if not location:
                    response.raise_for_status()
                current = assert_public_http_url(urljoin(current, location))
                continue
            response.raise_for_status()
            content = bytearray()
            async for chunk in response.aiter_bytes():
                content.extend(chunk)
                if len(content) > max_bytes:
                    raise ValueError("图标或页面超过读取上限")
            # aiter_bytes has already decompressed the body; do not decode gzip a second time.
            headers = {key: value for key, value in response.headers.items() if key not in {"content-encoding", "content-length"}}
            return httpx.Response(response.status_code, headers=headers, content=bytes(content), request=response.request)
    raise ValueError("图标地址跳转次数过多")


class _PageIcons(HTMLParser):
    """Read only declared icons; never execute page scripts or load other resources."""

    def __init__(self) -> None:
        super().__init__()
        self.base: str | None = None
        self.icons: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        href = (values.get("href") or "").strip()
        if tag == "base" and self.base is None and href:
            self.base = href
        if tag == "link" and "icon" in (values.get("rel") or "").lower().split() and href:
            if href not in self.icons and len(self.icons) < 3:
                self.icons.append(href)


class IconHashCalculator:
    MAX_ICON_BYTES = 4 * 1024 * 1024

    @staticmethod
    def from_bytes(content: bytes) -> str:
        if not content:
            raise ValueError("图标内容为空")
        if len(content) > IconHashCalculator.MAX_ICON_BYTES:
            raise ValueError("图标文件超过 4 MiB 安全上限")
        icon_hash = mmh3.hash(codecs.lookup("base64").encode(content)[0])
        return f'icon_hash="{icon_hash}"'

    @staticmethod
    def from_file(path_value: str) -> str:
        path = Path(path_value).expanduser()
        if not path.is_file():
            raise ValueError(f"图标文件不存在：{path}")
        if path.stat().st_size > IconHashCalculator.MAX_ICON_BYTES:
            raise ValueError("图标文件超过 4 MiB 安全上限")
        return IconHashCalculator.from_bytes(path.read_bytes())

    @staticmethod
    async def get_hash(url: str) -> str | None:
        safe_url = assert_public_http_url(url)
        parsed = urlparse(safe_url)
        explicit_icon = Path(parsed.path).suffix.lower() in {".ico", ".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp"}
        favicon_url = safe_url if explicit_icon else f"{parsed.scheme}://{parsed.netloc}/favicon.ico"

        def is_html(response: httpx.Response) -> bool:
            return "text/html" in response.headers.get("content-type", "").lower()

        async with httpx.AsyncClient(verify=True, timeout=10, follow_redirects=False) as client:
            try:
                try:
                    response = await _get_with_safe_redirects(client, favicon_url, max_bytes=IconHashCalculator.MAX_ICON_BYTES)
                    if not is_html(response):
                        return IconHashCalculator.from_bytes(response.content)
                    if explicit_icon:
                        return None
                except httpx.HTTPStatusError as exc:
                    if explicit_icon or exc.response.status_code not in {404, 410}:
                        raise
                # Preserve the fast root-favicon path. Inspect one page only when it has no usable icon.
                page = await _get_with_safe_redirects(client, safe_url, max_bytes=256 * 1024)
                parser = _PageIcons()
                parser.feed(page.text)
                base = urljoin(str(page.url), parser.base) if parser.base else str(page.url)
                for href in parser.icons:
                    target = urljoin(base, href)
                    if urlparse(target).scheme not in {"http", "https"}:
                        continue
                    try:
                        response = await _get_with_safe_redirects(client, target, max_bytes=IconHashCalculator.MAX_ICON_BYTES)
                        if not is_html(response):
                            return IconHashCalculator.from_bytes(response.content)
                    except (httpx.HTTPError, ValueError):
                        continue
                return None
            except (httpx.HTTPError, ValueError) as exc:
                logger.warning(f"图标计算失败: {exc}")
                return None


_HTTP_PROTOCOLS = frozenset({"http", "https", "http/https", "https/http", "tls", "ssl", "ws", "wss"})
_PROXY_ENV = ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy", "all_proxy")
_alive_pin: contextvars.ContextVar[str | None] = contextvars.ContextVar("fofamap_alive_pin", default=None)


@dataclass(frozen=True)
class AssetEndpoint:
    kind: str
    url: str
    hostname: str
    port: int


def _split_host_port(value: str) -> tuple[str, str]:
    if value.startswith("[") and "]" in value:
        name, _, rest = value.partition("]")
        port = rest[1:] if rest.startswith(":") and rest[1:].isdigit() else ""
        return name[1:], port
    if value.count(":") > 1:
        return value, ""
    if value.count(":") == 1:
        name, maybe_port = value.rsplit(":", 1)
        if maybe_port.isdigit():
            return name, maybe_port
    return value, ""


def _bracket_host(hostname: str) -> str:
    if hostname.startswith("[") and hostname.endswith("]"):
        return hostname
    try:
        if ipaddress.ip_address(hostname).version == 6:
            return f"[{hostname}]"
    except ValueError:
        return hostname
    return hostname


def _wants_https(scheme: str, protocol: str, port_text: str) -> bool:
    if scheme in {"https", "wss"}:
        return True
    if scheme in {"http", "ws"}:
        return False
    if protocol in {"https", "wss", "tls", "ssl"} or "https" in protocol:
        return True
    return port_text in {"443", "8443"}


def describe_asset_endpoint(values: dict[str, object]) -> AssetEndpoint | None:
    """Build the real service address, including a separate FOFA port and IPv6 brackets."""
    raw = str(values.get("host") or "").strip()
    field_port = str(values.get("port") or "").strip()
    protocol = str(values.get("protocol") or "").strip().lower()
    scheme = ""
    path = ""
    hostname = ""
    embedded = ""
    if "://" in raw:
        parsed = urlparse(raw)
        if parsed.username or parsed.password or parsed.scheme.lower() not in {"http", "https", "ws", "wss"}:
            return None
        scheme = parsed.scheme.lower()
        hostname = parsed.hostname or ""
        embedded = str(parsed.port or "")
        if parsed.path not in {"", "/"}:
            path = parsed.path
        if parsed.query:
            path = f"{path}?{parsed.query}"
    elif raw:
        hostname, embedded = _split_host_port(raw)
    else:
        hostname, embedded = _split_host_port(str(values.get("ip") or "").strip())
    if not hostname:
        return None
    port_text = embedded if embedded.isdigit() else field_port
    web = scheme in {"http", "https", "ws", "wss"} or not scheme and (not protocol or protocol in _HTTP_PROTOCOLS)
    if web:
        http_scheme = "https" if _wants_https(scheme, protocol, port_text) else "http"
        port = int(port_text) if port_text.isdigit() else (443 if http_scheme == "https" else 80)
        if not 1 <= port <= 65535:
            return None
        default = 443 if http_scheme == "https" else 80
        authority = _bracket_host(hostname) if port == default else f"{_bracket_host(hostname)}:{port}"
        return AssetEndpoint("http", f"{http_scheme}://{authority}{path}", hostname, port)
    if not port_text.isdigit():
        return None
    port = int(port_text)
    if not 1 <= port <= 65535:
        return None
    return AssetEndpoint("tcp", f"tcp://{_bracket_host(hostname)}:{port}", hostname, port)


def asset_http_url(values: dict[str, object]) -> str | None:
    endpoint = describe_asset_endpoint(values)
    if endpoint is None or endpoint.kind != "http":
        return None
    return endpoint.url


def asset_probe_target(values: dict[str, object]) -> str | None:
    endpoint = describe_asset_endpoint(values)
    return None if endpoint is None else endpoint.url


def insert_alive_status_field(fields: list[str]) -> list[str]:
    """Keep the alive column near host/port so it stays visible in compact tables."""
    if "alive_status" in fields:
        return fields
    for anchor in ("protocol", "port", "ip", "host"):
        if anchor in fields:
            index = fields.index(anchor) + 1
            return [*fields[:index], "alive_status", *fields[index:]]
    return ["alive_status", *fields]


class _PinningBackend:
    """Connect to the IP already checked for this task, without a second DNS lookup."""

    def __init__(self) -> None:
        import httpcore

        self._inner = httpcore.AnyIOBackend()

    async def connect_tcp(
        self,
        host: str,
        port: int,
        timeout: float | None = None,
        local_address: str | None = None,
        socket_options: object = None,
    ):
        return await self._inner.connect_tcp(
            _alive_pin.get() or host,
            port,
            timeout=timeout,
            local_address=local_address,
            socket_options=socket_options,
        )

    async def connect_unix_socket(self, path: str, timeout: float | None = None, socket_options: object = None):
        return await self._inner.connect_unix_socket(path, timeout=timeout, socket_options=socket_options)

    async def sleep(self, seconds: float) -> None:
        await self._inner.sleep(seconds)


def _uses_proxy() -> bool:
    return any(os.environ.get(name) for name in _PROXY_ENV)


def _is_fake_ip(address: str) -> bool:
    try:
        ip = ipaddress.ip_address(address)
    except ValueError:
        return False
    return any(ip in network for network in _FAKE_IP_NETWORKS)


def _screen_addresses(addresses: list[str]) -> str | None:
    allow_private = settings.system.allow_private_network
    blocked = [address for address in addresses if is_blocked_ssrf_address(address, allow_private=allow_private)]
    if not blocked:
        return None
    if any(is_cloud_metadata_address(address) for address in blocked):
        return "Blocked: 已拦截云元数据目标"
    return "Blocked: 已拦截私网、回环、链路本地、保留地址目标"


def _is_tls_error(exc: BaseException) -> bool:
    current: BaseException | None = exc
    seen: set[int] = set()
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        if isinstance(current, ssl.SSLError):
            return True
        message = str(current).lower()
        if "certificate" in message or "tls" in message or "ssl" in message:
            return True
        current = current.__cause__ or current.__context__
    return False


_TIMEOUTS = (TimeoutError, asyncio.TimeoutError) if asyncio.TimeoutError is not TimeoutError else (TimeoutError,)


async def _resolve_addresses(hostname: str, port: int, timeout: float) -> list[str]:
    try:
        infos = await asyncio.wait_for(
            asyncio.get_running_loop().getaddrinfo(hostname, port, type=socket.SOCK_STREAM),
            timeout,
        )
    except _TIMEOUTS as exc:
        raise ValueError("DNS 超时") from exc
    except socket.gaierror as exc:
        raise ValueError(f"无法解析 {hostname}") from exc
    addresses: list[str] = []
    for item in infos:
        address = str(item[4][0])
        if address not in addresses:
            addresses.append(address)
    if not addresses:
        raise ValueError(f"无法解析 {hostname}")
    return addresses


def _parse_probe_target(target: str) -> AssetEndpoint | None:
    if target.startswith("tcp://"):
        hostname, port_text = _split_host_port(target.removeprefix("tcp://"))
        if hostname and port_text.isdigit() and 1 <= int(port_text) <= 65535:
            return AssetEndpoint("tcp", target, hostname, int(port_text))
        return None
    parsed = urlparse(target if "://" in target else f"http://{target}")
    if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password:
        return None
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    return AssetEndpoint("http", target if "://" in target else f"http://{target}", parsed.hostname, port)


class FastChecker:
    @staticmethod
    async def check_alive(targets: list[str], timeout: int = 5) -> dict[str, int | str]:
        unique = list(dict.fromkeys(targets))
        if not unique:
            return {}
        concurrency = settings.fast_check.concurrency
        semaphore = asyncio.Semaphore(concurrency)
        limits = httpx.Limits(max_connections=concurrency, max_keepalive_connections=concurrency)
        timeouts = httpx.Timeout(timeout)
        headers = {"User-Agent": f"FofaMap/{VERSION}"}
        if _uses_proxy():
            client_manager = httpx.AsyncClient(
                verify=True,
                timeout=timeouts,
                follow_redirects=False,
                limits=limits,
                headers=headers,
            )
        else:
            transport = httpx.AsyncHTTPTransport(verify=True, retries=0, limits=limits)
            transport._pool._network_backend = _PinningBackend()  # type: ignore[attr-defined]
            client_manager = httpx.AsyncClient(
                transport=transport,
                timeout=timeouts,
                follow_redirects=False,
                headers=headers,
            )
        async with client_manager as client:
            responses = await asyncio.gather(
                *(FastChecker._guarded(client, target, timeout, semaphore) for target in unique),
            )
        return dict(responses)

    @staticmethod
    async def _guarded(
        client: httpx.AsyncClient,
        target: str,
        timeout: float,
        semaphore: asyncio.Semaphore,
    ) -> tuple[str, int | str]:
        async with semaphore:
            try:
                return target, await FastChecker._probe(client, target, timeout)
            except (asyncio.CancelledError, KeyboardInterrupt):
                raise
            except Exception as exc:
                logger.debug(f"存活探测失败 {target}: {exc}")
                return target, "Timeout" if isinstance(exc, _TIMEOUTS) else "Error"

    @staticmethod
    async def _probe(client: httpx.AsyncClient, target: str, timeout: float) -> int | str:
        endpoint = _parse_probe_target(target)
        if endpoint is None:
            return "Error"
        deadline = time.monotonic() + timeout

        def remaining() -> float:
            return max(0.001, deadline - time.monotonic())

        try:
            addresses = await _resolve_addresses(endpoint.hostname, endpoint.port, remaining())
        except ValueError as exc:
            return "Timeout" if "超时" in str(exc) else "DNS"
        blocked = _screen_addresses(addresses)
        if blocked:
            return blocked
        if endpoint.kind == "tcp":
            return await FastChecker._probe_tcp(addresses[0], endpoint.port, remaining())
        pin = None if _uses_proxy() or any(_is_fake_ip(address) for address in addresses) else addresses[0]
        return await FastChecker._probe_http(client, endpoint.url, endpoint.hostname, pin, remaining())

    @staticmethod
    async def _probe_tcp(address: str, port: int, timeout: float) -> str:
        try:
            _reader, writer = await asyncio.wait_for(asyncio.open_connection(address, port), timeout)
        except _TIMEOUTS:
            return "Timeout"
        except OSError:
            return "ConnErr"
        writer.close()
        try:
            await writer.wait_closed()
        except OSError:
            return "Open"
        return "Open"

    @staticmethod
    async def _probe_http(
        client: httpx.AsyncClient,
        url: str,
        hostname: str,
        pin: str | None,
        timeout: float,
    ) -> int | str:
        token = _alive_pin.set(pin)
        try:
            async with client.stream(
                "GET",
                url,
                timeout=httpx.Timeout(timeout),
                extensions={"sni_hostname": hostname},
            ) as response:
                return response.status_code
        except httpx.TimeoutException:
            return "Timeout"
        except httpx.ConnectError as exc:
            return "TLS" if _is_tls_error(exc) else "ConnErr"
        except (httpx.HTTPError, OSError):
            return "Error"
        finally:
            _alive_pin.reset(token)
