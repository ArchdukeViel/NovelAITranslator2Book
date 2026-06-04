from __future__ import annotations

import ipaddress
import socket
from typing import Any
from urllib.parse import urlparse

import httpx

from novelai.core.errors import SourceError

DEFAULT_USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) NovelAI/1.0"


def validate_safe_url(url: str) -> str:
    """Validate fetch URLs and reject private/internal targets."""

    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise SourceError(f"Unsupported URL scheme: {parsed.scheme!r}. Only http/https are allowed.")
    hostname = parsed.hostname
    if not hostname:
        raise SourceError(f"Invalid URL (missing hostname): {url}")

    try:
        resolved = socket.getaddrinfo(hostname, None, proto=socket.IPPROTO_TCP)
    except socket.gaierror:
        return url

    for _family, _type, _proto, _canonname, sockaddr in resolved:
        addr = ipaddress.ip_address(sockaddr[0])
        if addr.is_private or addr.is_loopback or addr.is_reserved or addr.is_link_local:
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
