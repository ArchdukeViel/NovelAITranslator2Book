"""Auth router — login, logout, me, OAuth.

Owner bootstrap login, session management, and OAuth flow stay in the
adapter. All DB-backed auth operations delegate to AuthService.
"""

from __future__ import annotations

import logging
import secrets
from typing import Any
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, Field
from starlette.responses import RedirectResponse

from novelai.api.auth.google_oauth import get_google_oauth_client
from novelai.api.auth.roles import require_role
from novelai.api.auth.security import (
    clear_csrf_token,
    get_or_create_csrf_token,
    require_csrf_token,
    require_public_rate_limit,
)
from novelai.api.auth.session import SessionUser, get_current_user
from novelai.api.routers.dependencies import get_auth_service
from novelai.config.settings import settings
from novelai.runtime.container import container
from novelai.services.auth_service import AuthService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/auth", tags=["auth"])

# Compatibility re-exports for tests that patch these via monkeypatch.setattr.
# The canonical implementations live on AuthService.
_hash_password_reset_token = AuthService.hash_password_reset_token
_hash_email_verification_token = AuthService.hash_email_verification_token
_new_password_reset_token = AuthService.new_password_reset_token
_new_email_verification_token = AuthService.new_email_verification_token


def get_auth_email_service() -> Any:
    """Compatibility shim — returns the container's auth email service."""
    return container.auth_email

_OAUTH_STATE_KEY = "oauth_google_state"
_OAUTH_RETURN_TO_KEY = "oauth_google_return_to"
_DEFAULT_PUBLIC_RETURN_TO = "/"

_MAX_PASSWORD_LENGTH = 256


class LoginRequest(BaseModel):
    """Owner bootstrap login payload."""
    secret: str


class RegisterRequest(BaseModel):
    """Public email/password signup payload."""
    email: str
    password: str = Field(min_length=1, max_length=_MAX_PASSWORD_LENGTH)
    display_name: str | None = Field(default=None, max_length=128)


class PasswordLoginRequest(BaseModel):
    """Public email/password login payload."""
    email: str
    password: str = Field(min_length=1, max_length=_MAX_PASSWORD_LENGTH)


class PasswordResetRequest(BaseModel):
    """Public password reset request payload."""
    email: str


class PasswordResetConfirmRequest(BaseModel):
    """Public password reset confirmation payload."""
    token: str = Field(min_length=1, max_length=512)
    new_password: str = Field(min_length=1, max_length=_MAX_PASSWORD_LENGTH)


class PasswordResetResponse(BaseModel):
    status: str


class EmailVerificationRequest(BaseModel):
    """Public email verification request/resend payload."""
    email: str


class EmailVerificationConfirmRequest(BaseModel):
    """Public email verification confirmation payload."""
    token: str = Field(min_length=1, max_length=512)


class EmailVerificationResponse(BaseModel):
    status: str


class UserResponse(BaseModel):
    """Safe public representation of the session user."""
    user_id: int | None
    email: str | None
    role: str
    is_authenticated: bool
    is_owner: bool


class CsrfResponse(BaseModel):
    csrf_token: str


def _user_response(user: SessionUser) -> UserResponse:
    return UserResponse(
        user_id=user.user_id,
        email=user.email,
        role=user.role,
        is_authenticated=user.is_authenticated,
        is_owner=user.is_owner,
    )


def _oauth_configured() -> bool:
    return bool(
        settings.GOOGLE_OAUTH_CLIENT_ID
        and settings.GOOGLE_OAUTH_CLIENT_SECRET
        and settings.GOOGLE_OAUTH_REDIRECT_URI
    )


def _safe_return_path(value: str | None) -> str:
    if not value:
        return _DEFAULT_PUBLIC_RETURN_TO
    parsed = urlparse(value)
    if parsed.scheme or parsed.netloc or not value.startswith("/") or value.startswith("//"):
        return _DEFAULT_PUBLIC_RETURN_TO
    return value


def _frontend_redirect(path: str) -> str:
    public_frontend_url = settings.PUBLIC_FRONTEND_URL
    if not public_frontend_url:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Public frontend URL is not configured.",
        )
    base = public_frontend_url.rstrip("/")
    safe_path = _safe_return_path(path)
    return f"{base}{safe_path}"


def _set_session_user(request: Request, user_data: dict) -> None:
    request.session["user_id"] = user_data["user_id"]
    request.session["email"] = user_data["email"]
    request.session["role"] = user_data["role"]


def _clear_google_oauth_session(request: Request) -> None:
    request.session.pop(_OAUTH_STATE_KEY, None)
    request.session.pop(_OAUTH_RETURN_TO_KEY, None)


@router.post("/login")
async def login(payload: LoginRequest, request: Request) -> UserResponse:
    """Owner bootstrap login using OWNER_BOOTSTRAP_SECRET."""
    require_public_rate_limit(request, "auth_login")
    bootstrap_secret = settings.OWNER_BOOTSTRAP_SECRET
    if not bootstrap_secret:
        logger.warning("Owner login attempted but OWNER_BOOTSTRAP_SECRET is not configured.")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Owner login is not configured on this server.",
        )
    if not secrets.compare_digest(payload.secret, bootstrap_secret):
        logger.warning("Failed owner login attempt.")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials.",
        )
    request.session["user_id"] = 1
    request.session["email"] = "owner@local"
    request.session["role"] = "owner"
    logger.info("Owner bootstrap login succeeded.")
    return _user_response(SessionUser(user_id=1, email="owner@local", role="owner"))


@router.post("/register")
async def register(
    payload: RegisterRequest,
    request: Request,
    svc: AuthService = Depends(get_auth_service),
) -> UserResponse:
    """Create a public email/password user account and session."""
    require_public_rate_limit(request, "auth_register")
    ip = request.client.host if request.client else None
    user_agent = (request.headers.get("user-agent") or "")[:255] if request.headers.get("user-agent") else None
    try:
        result = svc.register(
            payload.email,
            payload.password,
            payload.display_name,
            ip=ip,
            user_agent=user_agent,
        )
    except ValueError as exc:
        msg = str(exc)
        if "Invalid email" in msg or "Password" in msg:
            raise HTTPException(status_code=400, detail=msg) from exc
        raise HTTPException(status_code=409, detail=msg) from exc

    _set_session_user(request, result)
    return _user_response(SessionUser(user_id=result["user_id"], email=result["email"], role=result["role"]))


@router.post("/password/login")
async def password_login(
    payload: PasswordLoginRequest,
    request: Request,
    svc: AuthService = Depends(get_auth_service),
) -> UserResponse:
    """Authenticate a public email/password user."""
    require_public_rate_limit(request, "auth_password_login")
    try:
        result = svc.password_login(payload.email, payload.password)
    except ValueError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc

    _set_session_user(request, result)
    return _user_response(SessionUser(user_id=result["user_id"], email=result["email"], role=result["role"]))


@router.post("/password/reset/request")
async def password_reset_request(
    payload: PasswordResetRequest,
    request: Request,
    svc: AuthService = Depends(get_auth_service),
) -> PasswordResetResponse:
    """Create a reset token for a public email/password user, if eligible."""
    require_public_rate_limit(request, "auth_password_reset_request")
    ip = request.client.host if request.client else None
    user_agent = (request.headers.get("user-agent") or "")[:255] if request.headers.get("user-agent") else None
    svc.request_password_reset(payload.email, ip=ip, user_agent=user_agent)
    return PasswordResetResponse(status="ok")


@router.post("/password/reset/confirm")
async def password_reset_confirm(
    payload: PasswordResetConfirmRequest,
    request: Request,
    svc: AuthService = Depends(get_auth_service),
) -> PasswordResetResponse:
    """Reset a public email/password user's password with a one-time token."""
    require_public_rate_limit(request, "auth_password_reset_confirm")
    try:
        svc.confirm_password_reset(payload.token, payload.new_password)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return PasswordResetResponse(status="ok")


@router.post("/email/verification/request")
async def email_verification_request(
    payload: EmailVerificationRequest,
    request: Request,
    svc: AuthService = Depends(get_auth_service),
) -> EmailVerificationResponse:
    """Create or resend a verification token for an eligible public account."""
    require_public_rate_limit(request, "auth_email_verification_request")
    ip = request.client.host if request.client else None
    user_agent = (request.headers.get("user-agent") or "")[:255] if request.headers.get("user-agent") else None
    svc.request_email_verification(payload.email, ip=ip, user_agent=user_agent)
    return EmailVerificationResponse(status="ok")


@router.post("/email/verification/confirm")
async def email_verification_confirm(
    payload: EmailVerificationConfirmRequest,
    request: Request,
    svc: AuthService = Depends(get_auth_service),
) -> EmailVerificationResponse:
    """Verify a public email/password user's email with a one-time token."""
    require_public_rate_limit(request, "auth_email_verification_confirm")
    try:
        svc.confirm_email_verification(payload.token)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return EmailVerificationResponse(status="ok")


@router.get("/google/start")
async def google_start(
    request: Request,
    next: str | None = Query(default=None),
    oauth_client=Depends(get_google_oauth_client),
) -> RedirectResponse:
    """Start public Google OAuth login."""
    require_public_rate_limit(request, "oauth_start")
    if not _oauth_configured():
        raise HTTPException(status_code=503, detail="Google OAuth is not configured on this server.")
    state = secrets.token_urlsafe(32)
    request.session[_OAUTH_STATE_KEY] = state
    request.session[_OAUTH_RETURN_TO_KEY] = _safe_return_path(next)
    return RedirectResponse(
        oauth_client.authorization_url(
            state=state,
            redirect_uri=settings.GOOGLE_OAUTH_REDIRECT_URI or "",
        ),
        status_code=status.HTTP_302_FOUND,
    )


@router.get("/google/callback")
async def google_callback(
    request: Request,
    state: str | None = Query(default=None),
    code: str | None = Query(default=None),
    oauth_client=Depends(get_google_oauth_client),
    svc: AuthService = Depends(get_auth_service),
) -> RedirectResponse:
    """Complete public Google OAuth login and create/resume a user session."""
    require_public_rate_limit(request, "oauth_callback")
    expected_state = request.session.get(_OAUTH_STATE_KEY)
    return_to = _safe_return_path(request.session.get(_OAUTH_RETURN_TO_KEY))
    try:
        if not _oauth_configured():
            raise HTTPException(status_code=503, detail="Google OAuth is not configured on this server.")
        if not isinstance(expected_state, str) or not state or not secrets.compare_digest(state, expected_state):
            raise HTTPException(status_code=400, detail="Invalid OAuth state.")
        if not code:
            raise HTTPException(status_code=400, detail="Missing OAuth code.")
        profile = await oauth_client.exchange_code(
            code=code,
            redirect_uri=settings.GOOGLE_OAUTH_REDIRECT_URI or "",
        )
        user = svc.upsert_google_user(profile)
        _set_session_user(request, {"user_id": user.id, "email": user.email, "role": user.role})
        return RedirectResponse(_frontend_redirect(return_to), status_code=status.HTTP_302_FOUND)
    except HTTPException:
        raise
    except ValueError as exc:
        logger.warning("Google OAuth callback failed: %s", exc.__class__.__name__)
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except Exception as exc:
        logger.warning("Google OAuth callback failed: %s", exc.__class__.__name__)
        raise HTTPException(status_code=400, detail="Google OAuth login failed.") from exc
    finally:
        _clear_google_oauth_session(request)


@router.get("/csrf")
async def csrf(request: Request) -> CsrfResponse:
    """Return a session-bound CSRF token for browser state-changing requests."""
    return CsrfResponse(csrf_token=get_or_create_csrf_token(request))


@router.post("/logout", dependencies=[Depends(require_csrf_token)])
async def logout(request: Request) -> dict[str, str]:
    """Clear the current session (log out any role)."""
    require_public_rate_limit(request, "auth_logout")
    clear_csrf_token(request)
    request.session.clear()
    return {"status": "logged_out"}


@router.get("/me")
async def me(user: SessionUser = Depends(get_current_user)) -> UserResponse:
    """Return the current session user (or guest if unauthenticated)."""
    return _user_response(user)


@router.get("/me/owner-only", include_in_schema=False)
async def me_owner_only(user: SessionUser = Depends(require_role("owner"))) -> UserResponse:
    """Test endpoint — proves require_role('owner') works end-to-end."""
    return _user_response(user)
