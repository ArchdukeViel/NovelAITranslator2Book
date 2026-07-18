from __future__ import annotations

import secrets
import time
from collections import defaultdict

from fastapi import Depends, HTTPException, Request, status

from novelai.api.auth.session import SessionUser, get_current_user
from novelai.config.settings import settings

CSRF_HEADER_NAME = "X-CSRF-Token"
_CSRF_SESSION_KEY = "csrf_token"
_SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}
_PUBLIC_RATE_WINDOW_SECONDS = 60
_PUBLIC_RATE_LIMITS = {
    "auth_login": 10,
    "auth_logout": 20,
    "auth_register": 10,
    "auth_password_login": 10,
    "auth_password_reset_request": 5,
    "auth_password_reset_confirm": 10,
    "auth_email_verification_request": 5,
    "auth_email_verification_confirm": 10,
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
    origin = request.headers.get("origin")
    if settings.CSRF_TRUSTED_ORIGINS and origin:
        trusted_origins = {item.rstrip("/") for item in settings.CSRF_TRUSTED_ORIGINS}
        if origin.rstrip("/") not in trusted_origins:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Untrusted request origin.",
            )
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


def require_csrf_for_unsafe_methods(
    request: Request,
    user: SessionUser = Depends(get_current_user),
) -> None:
    """Require CSRF for owner-authenticated unsafe browser requests.

    Non-owner requests are left for require_role("owner") to reject so auth
    failures keep their existing 401/403 behavior.
    """
    if request.method.upper() in _SAFE_METHODS:
        return
    if not user.is_owner:
        return
    require_csrf_token(request)


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
