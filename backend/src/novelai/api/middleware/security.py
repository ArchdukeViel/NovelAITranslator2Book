"""Security headers and trusted proxy middleware.

Adds baseline security headers to all responses and handles trusted proxy
forwarded-header validation. Never logs or exposes secrets, raw IPs, or tokens.
"""

from __future__ import annotations

import ipaddress
import logging
from collections.abc import Awaitable, Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from novelai.config.settings import settings

logger = logging.getLogger(__name__)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Adds baseline security headers to every response.

    Headers:
      - X-Content-Type-Options: nosniff
      - Referrer-Policy: strict-origin-when-cross-origin
      - X-Frame-Options: DENY
      - Strict-Transport-Security (only when HSTS_MAX_AGE_SECONDS > 0)
    """

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        response = await call_next(request)
        if settings.SECURITY_HEADERS_ENABLED:
            response.headers.setdefault("X-Content-Type-Options", "nosniff")
            response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
            response.headers.setdefault("X-Frame-Options", "DENY")
            if settings.HSTS_MAX_AGE_SECONDS > 0:
                hsts_value = f"max-age={settings.HSTS_MAX_AGE_SECONDS}; includeSubDomains"
                response.headers.setdefault("Strict-Transport-Security", hsts_value)
        return response


def _is_trusted_proxy(client_ip: str) -> bool:
    """Check if the client IP is within a trusted proxy CIDR range."""
    if not settings.TRUSTED_PROXY_CIDRS:
        return False
    try:
        ip = ipaddress.ip_address(client_ip)
    except ValueError:
        return False
    for cidr_str in settings.TRUSTED_PROXY_CIDRS:
        try:
            network = ipaddress.ip_network(cidr_str, strict=False)
            if ip in network:
                return True
        except ValueError:
            continue
    return False


def get_client_ip(request: Request) -> str:
    """Resolve the real client IP, respecting trusted proxy forwarded headers.

    If the request comes from a trusted proxy, X-Forwarded-For is used.
    Otherwise, the direct connection IP is used and forwarded headers are ignored.
    """
    direct_ip = request.client.host if request.client else "unknown"

    if not settings.TRUSTED_PROXY_CIDRS:
        return direct_ip

    if not _is_trusted_proxy(direct_ip):
        return direct_ip

    forwarded_for = request.headers.get("X-Forwarded-For", "")
    if forwarded_for:
        first_ip = forwarded_for.split(",")[0].strip()
        if first_ip:
            return first_ip

    return direct_ip


def is_allowed_host(host: str | None) -> bool:
    """Check if the Host header is in the allowed hosts list.

    Returns True if ALLOWED_HOSTS is empty (development mode).
    """
    if not settings.ALLOWED_HOSTS:
        return True
    if not host:
        return False
    host_lower = host.split(":")[0].lower()
    return host_lower in {h.lower() for h in settings.ALLOWED_HOSTS}
