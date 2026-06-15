from __future__ import annotations

import secrets
import time
from collections import defaultdict

from fastapi import HTTPException, Request, status

CSRF_HEADER_NAME = "X-CSRF-Token"
_CSRF_SESSION_KEY = "csrf_token"
_PUBLIC_RATE_WINDOW_SECONDS = 60
_PUBLIC_RATE_LIMITS = {
    "auth_login": 10,
    "auth_logout": 20,
    "oauth_start": 10,
    "oauth_callback": 20,
    "library_mutation": 60,
    "progress_write": 120,
    "history_record": 120,
    "review_mutation": 20,
    "request_create": 10,
}
_rate_hits: dict[str, list[float]] = defaultdict(list)


def get_or_create_csrf_token(request: Request) -> str:
    token = request.session.get(_CSRF_SESSION_KEY)
    if not isinstance(token, str) or not token:
        token = secrets.token_urlsafe(32)
        request.session[_CSRF_SESSION_KEY] = token
    return token


def clear_csrf_token(request: Request) -> None:
    request.session.pop(_CSRF_SESSION_KEY, None)


def require_csrf_token(request: Request) -> None:
    expected = request.session.get(_CSRF_SESSION_KEY)
    supplied = request.headers.get(CSRF_HEADER_NAME)
    if (
        not isinstance(expected, str)
        or not supplied
        or not secrets.compare_digest(supplied, expected)
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid CSRF token.",
        )


def _client_ip(request: Request) -> str:
    try:
        return request.client.host if request.client else "unknown"
    except Exception:
        return "unknown"


def public_rate_limit_key(request: Request, *, user_id: int | None = None) -> str:
    if user_id is not None:
        return f"user:{user_id}"
    session_user_id = request.session.get("user_id")
    if isinstance(session_user_id, int):
        return f"user:{session_user_id}"
    if isinstance(session_user_id, str) and session_user_id.isdigit():
        return f"user:{session_user_id}"
    return f"ip:{_client_ip(request)}"


def require_public_rate_limit(request: Request, action: str, *, user_id: int | None = None) -> None:
    limit = _PUBLIC_RATE_LIMITS.get(action, 0)
    if limit <= 0:
        return
    key = f"{public_rate_limit_key(request, user_id=user_id)}:{action}"
    now = time.monotonic()
    window_start = now - _PUBLIC_RATE_WINDOW_SECONDS
    hits = [hit for hit in _rate_hits.get(key, []) if hit > window_start]
    if len(hits) >= limit:
        _rate_hits[key] = hits
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded.",
        )
    hits.append(now)
    _rate_hits[key] = hits


def reset_public_rate_limits() -> None:
    _rate_hits.clear()
