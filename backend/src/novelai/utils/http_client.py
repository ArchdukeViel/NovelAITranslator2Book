from __future__ import annotations

from typing import Any

import httpx


def create_async_client(
    *,
    timeout: float = 30.0,
    headers: dict[str, str] | None = None,
    cookies: Any = None,
    follow_redirects: bool = True,
) -> httpx.AsyncClient:
    """Create a configured httpx.AsyncClient used across sources.

    Centralizing client creation ensures consistent headers, timeouts,
    and makes future instrumentation (tracing, proxies) easy to add.
    """
    default_headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    if headers:
        default_headers.update(headers)

    return httpx.AsyncClient(
        timeout=timeout,
        headers=default_headers,
        cookies=cookies,
        follow_redirects=follow_redirects,
    )
