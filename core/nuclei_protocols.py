"""Typed target conversion for Nuclei; target identity is kept separate from template protocol."""

from __future__ import annotations

import ipaddress
import re
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

NUCLEI_PROTOCOLS = {"http", "tcp", "dns", "ssl", "headless", "websocket", "whois", "javascript", "code", "file"}
_SERVICE_SCHEMES = {
    "tcp",
    "udp",
    "tls",
    "ssl",
    "ssh",
    "ftp",
    "smb",
    "rdp",
    "redis",
    "mongodb",
    "mysql",
    "postgres",
    "postgresql",
}


@dataclass(frozen=True)
class ScanEndpoint:
    original: str
    host: str
    port: int | None
    kind: str
    nuclei_input: str


def parse_scan_target(value: str) -> ScanEndpoint:
    text = value.strip()
    if not text or any(char.isspace() for char in text) or text.startswith("-"):
        raise ValueError("Scan target must be one URL, domain or explicit host:port without whitespace")
    explicit = "://" in text
    parsed = urlparse(text if explicit else "//" + text)
    scheme = parsed.scheme.lower() if explicit else ""
    if not parsed.hostname or parsed.username or parsed.password or parsed.fragment:
        raise ValueError("Scan targets cannot contain credentials or fragments")
    host = parsed.hostname
    try:
        port = parsed.port
    except ValueError as exc:
        raise ValueError("Invalid scan target port") from exc
    if port is not None and not 1 <= port <= 65535:
        raise ValueError("Invalid scan target port")
    try:
        ipaddress.ip_address(host)
    except ValueError:
        if not re.fullmatch(r"[A-Za-z0-9_.-]+", host) or host.startswith("."):
            raise ValueError("Invalid scan target hostname") from None
    if scheme in {"http", "https", "ws", "wss"}:
        return ScanEndpoint(text, host, port or (443 if scheme in {"https", "wss"} else 80), "web", text)
    if scheme == "dns":
        if port is not None or parsed.path not in {"", "/"} or parsed.query:
            raise ValueError("DNS templates take a domain, not a DNS resolver URL/port")
        return ScanEndpoint(text, host, None, "dns", host)
    if scheme and scheme not in _SERVICE_SCHEMES:
        raise ValueError(f"Unsupported target scheme: {scheme}")
    if parsed.path not in {"", "/"} or parsed.query:
        raise ValueError("Network targets cannot contain paths or queries")
    if scheme or port is not None:
        if port is None:
            raise ValueError("Non-Web service targets require an explicit port; no port is guessed")
        address = f"[{host}]:{port}" if ":" in host else f"{host}:{port}"
        return ScanEndpoint(text, host, port, "udp" if scheme == "udp" else "network", address)
    return ScanEndpoint(text, host, 443, "web", f"https://{host}")


def asset_scan_target(values: dict[str, Any]) -> str | None:
    from utils.helpers import asset_http_url

    web = asset_http_url(values)
    if web:
        return web
    host = str(values.get("ip") or values.get("host") or "").strip()
    port = str(values.get("port") or "").strip()
    if not host or not port.isdigit():
        return None
    transport = str(values.get("base_protocol") or "").lower()
    address = f"[{host}]" if ":" in host and not host.startswith("[") else host
    target = f"{'udp' if transport == 'udp' else 'tcp'}://{address}:{port}"
    try:
        parse_scan_target(target)
    except ValueError:
        return None
    return target
