from __future__ import annotations

import ipaddress
import socket
from typing import Any
from urllib.parse import urlparse

import httpx

from novelai.core.errors import SourceError

DEFAULT_USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) NovelAI/1.0"
_BLOCKED_HOSTNAMES = {
    "localhost",
    "localhost.localdomain",
    "metadata.google.internal",
}


def _is_blocked_address(address: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    return any(
        (
            address.is_private,
            address.is_loopback,
            address.is_link_local,
            address.is_reserved,
            address.is_multicast,
            address.is_unspecified,
        )
    )


def validate_safe_url(url: str) -> str:
    """Validate fetch URLs and reject private/internal targets."""

    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise SourceError(f"Unsupported URL scheme: {parsed.scheme!r}. Only http/https are allowed.")
    if parsed.username or parsed.password:
        raise SourceError("URLs with embedded credentials are not allowed.")
    hostname = parsed.hostname
    if not hostname:
        raise SourceError(f"Invalid URL (missing hostname): {url}")
    normalized_hostname = hostname.rstrip(".").lower()
    if normalized_hostname in _BLOCKED_HOSTNAMES or normalized_hostname.endswith(".localhost"):
        raise SourceError(f"URL hostname is not allowed: {hostname}")

    try:
        literal_address = ipaddress.ip_address(normalized_hostname.strip("[]"))
    except ValueError:
        literal_address = None
    if literal_address is not None and _is_blocked_address(literal_address):
        raise SourceError(f"URL resolves to a private/reserved address: {hostname}")

    try:
        resolved = socket.getaddrinfo(hostname, None, proto=socket.IPPROTO_TCP)
    except socket.gaierror:
        return url

    for _family, _type, _proto, _canonname, sockaddr in resolved:
        addr = ipaddress.ip_address(sockaddr[0])
        if _is_blocked_address(addr):
            raise SourceError(f"URL resolves to a private/reserved address: {hostname}")
    return url


def create_async_client(
    *,
    headers: dict[str, str] | None = None,
    cookies: Any = None,
    follow_redirects: bool = True,
    transport: httpx.AsyncBaseTransport | None = None,
) -> httpx.AsyncClient:
    """Create the shared async HTTP client used by source fetching."""

    default_headers = {"User-Agent": DEFAULT_USER_AGENT}
    if headers:
        default_headers.update(headers)

    return httpx.AsyncClient(
        headers=default_headers,
        cookies=cookies,
        follow_redirects=follow_redirects,
        limits=httpx.Limits(max_connections=20, max_keepalive_connections=10, keepalive_expiry=30.0),
        timeout=httpx.Timeout(connect=10.0, read=30.0, write=10.0, pool=10.0),
        transport=transport,
    )
