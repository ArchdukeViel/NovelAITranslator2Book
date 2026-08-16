from __future__ import annotations

import asyncio
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
            not address.is_global,
            address.is_private,
            address.is_loopback,
            address.is_link_local,
            address.is_reserved,
            address.is_multicast,
            address.is_unspecified,
        )
    )


def _resolve_public_addresses(hostname: str) -> tuple[str, ...]:
    """Resolve *hostname* once for the connection and reject non-public IPs."""

    try:
        resolved = socket.getaddrinfo(hostname, None, proto=socket.IPPROTO_TCP)
    except socket.gaierror as exc:
        raise SourceError(f"URL hostname could not be resolved: {hostname}") from exc

    addresses: list[str] = []
    for _family, _type, _proto, _canonname, sockaddr in resolved:
        try:
            address = ipaddress.ip_address(sockaddr[0])
        except ValueError as exc:
            raise SourceError(f"URL hostname resolved to an invalid address: {hostname}") from exc
        if _is_blocked_address(address):
            raise SourceError(f"URL resolves to a private/reserved address: {hostname}")
        normalized = str(address)
        if normalized not in addresses:
            addresses.append(normalized)

    if not addresses:
        raise SourceError(f"URL hostname did not resolve to a public address: {hostname}")
    return tuple(addresses)


class _PinnedAsyncNetworkBackend:
    """Resolve and validate immediately before dialing the destination.

    httpcore keeps the original hostname as the connection origin, so TLS SNI
    remains correct while the underlying socket is opened against the exact IP
    selected by this wrapper. This closes the validation/connect DNS race.
    """

    def __init__(self, delegate: Any) -> None:
        self._delegate = delegate

    async def connect_tcp(
        self,
        host: str,
        port: int,
        *,
        timeout: float | None = None,
        local_address: str | None = None,
        socket_options: Any = None,
    ) -> Any:
        addresses = await asyncio.to_thread(_resolve_public_addresses, host)
        last_error: Exception | None = None
        for address in addresses:
            try:
                return await self._delegate.connect_tcp(
                    address,
                    port,
                    timeout=timeout,
                    local_address=local_address,
                    socket_options=socket_options,
                )
            except Exception as exc:
                last_error = exc
        if last_error is not None:
            raise last_error
        raise SourceError(f"Unable to connect to public URL host: {host}")

    async def connect_unix_socket(self, *args: Any, **kwargs: Any) -> Any:
        return await self._delegate.connect_unix_socket(*args, **kwargs)

    async def sleep(self, seconds: float) -> None:
        await self._delegate.sleep(seconds)


def _create_pinned_transport() -> httpx.AsyncHTTPTransport:
    transport = httpx.AsyncHTTPTransport(
        limits=httpx.Limits(max_connections=20, max_keepalive_connections=10, keepalive_expiry=30.0)
    )
    pool = getattr(transport, "_pool", None)
    backend = getattr(pool, "_network_backend", None)
    if pool is None or backend is None:
        raise RuntimeError("httpx transport does not expose the required network backend")
    pool._network_backend = _PinnedAsyncNetworkBackend(backend)
    return transport


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

    # Hostname resolution is deliberately performed by the pinned transport at
    # connection time. Resolving here would create a TOCTOU window before the
    # HTTP client opens its socket.
    return url


def create_async_client(
    *,
    headers: dict[str, str] | None = None,
    cookies: Any = None,
    follow_redirects: bool = False,
    transport: httpx.AsyncBaseTransport | None = None,
) -> httpx.AsyncClient:
    """Create the shared async HTTP client used by source fetching.

    Redirects are handled manually by :class:`FetchService` so every hop is
    validated against SSRF rules before it is requested; automatic following
    is disabled on purpose.
    """

    default_headers = {"User-Agent": DEFAULT_USER_AGENT}
    if headers:
        default_headers.update(headers)

    if transport is None:
        transport = _create_pinned_transport()

    return httpx.AsyncClient(
        headers=default_headers,
        cookies=cookies,
        follow_redirects=follow_redirects,
        limits=httpx.Limits(max_connections=20, max_keepalive_connections=10, keepalive_expiry=30.0),
        timeout=httpx.Timeout(connect=10.0, read=30.0, write=10.0, pool=10.0),
        transport=transport,
    )
