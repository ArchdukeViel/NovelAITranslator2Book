"""Security headers, trusted proxy, and request-body enforcement middleware.

Adds baseline security headers to all responses, trusted proxy
forwarded-header validation, and pure-ASGI request-body enforcement
(size and Content-Type) for /api/ mutation endpoints.
Never logs or exposes secrets, raw IPs, or tokens.
"""

from __future__ import annotations

import ipaddress
import json
import logging
import uuid
from collections.abc import Awaitable, Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp, Message, Receive, Scope, Send

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
        request_id = request.headers.get("X-Request-ID") or uuid.uuid4().hex
        response.headers.setdefault("X-Request-ID", request_id)
        if settings.SECURITY_HEADERS_ENABLED:
            response.headers.setdefault("X-Content-Type-Options", "nosniff")
            response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
            response.headers.setdefault("X-Frame-Options", "DENY")
            response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=(), payment=()")
            response.headers.setdefault("Cross-Origin-Opener-Policy", "same-origin")
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
            try:
                return str(ipaddress.ip_address(first_ip))
            except ValueError:
                return direct_ip

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


# ── Request body enforcement ──────────────────────────────────────────

_MUTATION_METHODS = frozenset({"POST", "PUT", "PATCH"})
_413_BODY = json.dumps({"detail": "Request body too large"}).encode()
_415_BODY = json.dumps({"detail": "Unsupported media type"}).encode()


async def _send_error(send: Send, status: int, body: bytes) -> None:
    """Send a JSON error response without exposing body fragments."""
    await send(
        {
            "type": "http.response.start",
            "status": status,
            "headers": [
                (b"content-type", b"application/json"),
                (b"content-length", str(len(body)).encode()),
            ],
        }
    )
    await send({"type": "http.response.body", "body": body})


def _get_header(scope_headers: list[tuple[bytes, bytes]], key: bytes) -> str | None:
    values = [value.decode("latin-1") for name, value in scope_headers if name.lower() == key]
    return values[0] if len(values) == 1 else None


def _declared_body_size(scope_headers: list[tuple[bytes, bytes]]) -> int | None:
    value = _get_header(scope_headers, b"content-length")
    if value is None:
        return None
    try:
        size = int(value)
    except ValueError:
        return None
    return size if size >= 0 else None


def _content_type_valid(content_type: str | None) -> bool:
    """Check if Content-Type is application/json or application/*+json."""
    if content_type is None:
        return False
    media_type = content_type.split(";")[0].strip().lower()
    return media_type == "application/json" or (media_type.startswith("application/") and media_type.endswith("+json"))


class RequestBodyEnforcementMiddleware:
    """Pure-ASGI body-size and Content-Type enforcement for /api/ mutations.

    Reads the entire body before passing to the app so enforcement happens
    before any route handler runs. Returns JSON 413 or 415 without echoing
    body fragments.

    Limits are enforced on actual byte count, not Content-Length.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        method: str = scope.get("method", "GET")
        path: str = scope.get("path", "")

        # Bound every API request body; validate media type only for JSON mutations.
        if not path.startswith("/api/"):
            await self.app(scope, receive, send)
            return

        # Determine body size limit
        if path.startswith("/api/auth/"):
            max_body = settings.WEB_MAX_AUTH_BODY_BYTES
        elif path == "/api/public/analytics/events":
            max_body = settings.ANALYTICS_INGEST_MAX_BODY_BYTES
        else:
            max_body = settings.WEB_MAX_JSON_BODY_BYTES

        scope_headers: list[tuple[bytes, bytes]] = scope.get("headers", [])
        declared_size = _declared_body_size(scope_headers)
        if declared_size is not None and declared_size > max_body:
            await _send_error(send, 413, _413_BODY)
            return

        # Read a bounded body and count actual bytes so streamed requests cannot bypass the limit.
        chunks: list[bytes] = []
        more_body = True
        total = 0
        while more_body:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            if message["type"] == "http.request":
                chunk: bytes = message.get("body", b"")
                chunks.append(chunk)
                total += len(chunk)
                more_body = message.get("more_body", False)

                if total > max_body:
                    await _send_error(send, 413, _413_BODY)
                    return

        body = b"".join(chunks)
        has_body = len(body) > 0

        # Content-Type enforcement for non-empty bodies
        if has_body and method in _MUTATION_METHODS:
            content_type = _get_header(scope_headers, b"content-type")
            if not _content_type_valid(content_type):
                await _send_error(send, 415, _415_BODY)
                return

        # Reconstruct receive so downstream sees the full body
        body_sent = False

        async def _receive() -> Message:
            nonlocal body_sent
            if body_sent:
                return {"type": "http.request", "body": b"", "more_body": False}
            body_sent = True
            return {"type": "http.request", "body": body, "more_body": False}

        await self.app(scope, _receive, send)
