"""Auth router: login, logout, me.

Endpoints:
  POST /api/auth/login   - owner bootstrap login (OWNER_BOOTSTRAP_SECRET)
  GET  /api/auth/google/start    - start public Google OAuth login
  GET  /api/auth/google/callback - complete public Google OAuth login
  POST /api/auth/logout  - clear session
  GET  /api/auth/me      - return current session user

Architecture rules (architecture.md §19):
- v1 uses HTTP-only server sessions (not JWT).
- Exactly one owner; seeded via OWNER_BOOTSTRAP_SECRET, never public signup.
- Frontend must not receive raw session secrets or user passwords.
- Google OAuth is the planned next login method; schema is OAuth-ready.
"""

from __future__ import annotations

import logging
import secrets
from datetime import datetime, timezone
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session
from starlette.responses import RedirectResponse

from novelai.api.auth.google_oauth import GoogleOAuthClient, GoogleOAuthProfile, get_google_oauth_client
from novelai.api.auth.roles import require_role
from novelai.api.auth.session import SessionUser, get_current_user
from novelai.api.routers.dependencies import get_db_session
from novelai.config.settings import settings
from novelai.db.models.users import User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/auth", tags=["auth"])

_OAUTH_STATE_KEY = "oauth_google_state"
_OAUTH_RETURN_TO_KEY = "oauth_google_return_to"
_DEFAULT_PUBLIC_RETURN_TO = "/"


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------

class LoginRequest(BaseModel):
    """Owner bootstrap login payload."""
    secret: str


class UserResponse(BaseModel):
    """Safe public representation of the session user."""
    user_id: int | None
    email: str | None
    role: str
    is_authenticated: bool
    is_owner: bool


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
    base = settings.PUBLIC_FRONTEND_URL.rstrip("/")
    safe_path = _safe_return_path(path)
    return f"{base}{safe_path}"


def _normalize_email(email: str) -> str:
    return email.strip().lower()


def _clear_google_oauth_session(request: Request) -> None:
    request.session.pop(_OAUTH_STATE_KEY, None)
    request.session.pop(_OAUTH_RETURN_TO_KEY, None)


def _set_session_user(request: Request, user: User) -> None:
    request.session["user_id"] = user.id
    request.session["email"] = user.email
    request.session["role"] = user.role


def _upsert_google_user(profile: GoogleOAuthProfile, session: Session) -> User:
    if not profile.email_verified:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Google account email must be verified.",
        )

    email = _normalize_email(profile.email)
    if not email:
        raise HTTPException(status_code=400, detail="Google account email is missing.")

    user = (
        session.query(User)
        .filter_by(auth_provider="google", auth_provider_subject=profile.subject)
        .one_or_none()
    )
    email_user = (
        session.query(User)
        .filter(func.lower(User.email) == email)
        .one_or_none()
    )

    if user is None and email_user is not None:
        if email_user.role == "owner":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Public OAuth cannot link to the owner account.",
            )
        if email_user.auth_provider and (
            email_user.auth_provider != "google"
            or email_user.auth_provider_subject != profile.subject
        ):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="An account already exists for this email.",
            )
        user = email_user
        user.auth_provider = "google"
        user.auth_provider_subject = profile.subject

    if user is not None:
        if user.role == "owner":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Public OAuth cannot authenticate the owner account.",
            )
        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="This account is inactive.",
            )
        user.email = email
        if profile.display_name:
            user.display_name = profile.display_name
        user.last_login_at = datetime.now(timezone.utc)
        session.flush()
        return user

    user = User(
        email=email,
        display_name=profile.display_name,
        role="user",
        auth_provider="google",
        auth_provider_subject=profile.subject,
        is_active=True,
        last_login_at=datetime.now(timezone.utc),
    )
    session.add(user)
    session.flush()
    return user


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.post("/login")
async def login(payload: LoginRequest, request: Request) -> UserResponse:
    """Owner bootstrap login using OWNER_BOOTSTRAP_SECRET.

    Compares the supplied secret against OWNER_BOOTSTRAP_SECRET using a
    constant-time comparison to prevent timing attacks.

    Returns the session user on success. Sets an HTTP-only session cookie
    (managed by SessionMiddleware in app.py).

    This is the v1 entry point until Google OAuth is implemented.
    """
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

    # Seed a minimal owner session — no DB row required for bootstrap login.
    request.session["user_id"] = 1  # Bootstrap owner is always ID 1
    request.session["email"] = "owner@local"
    request.session["role"] = "owner"
    logger.info("Owner bootstrap login succeeded.")
    return _user_response(SessionUser(user_id=1, email="owner@local", role="owner"))


@router.get("/google/start")
async def google_start(
    request: Request,
    next: str | None = Query(default=None),
    oauth_client: GoogleOAuthClient = Depends(get_google_oauth_client),
) -> RedirectResponse:
    """Start public Google OAuth login.

    This endpoint only creates state and redirects to Google. It never creates a
    local user and never touches owner bootstrap auth.
    """
    if not _oauth_configured():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Google OAuth is not configured on this server.",
        )

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
    oauth_client: GoogleOAuthClient = Depends(get_google_oauth_client),
    session: Session = Depends(get_db_session),
) -> RedirectResponse:
    """Complete public Google OAuth login and create/resume a user session."""
    expected_state = request.session.get(_OAUTH_STATE_KEY)
    return_to = _safe_return_path(request.session.get(_OAUTH_RETURN_TO_KEY))

    try:
        if not _oauth_configured():
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Google OAuth is not configured on this server.",
            )
        if not isinstance(expected_state, str) or not state or not secrets.compare_digest(state, expected_state):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid OAuth state.")
        if not code:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing OAuth code.")

        profile = await oauth_client.exchange_code(
            code=code,
            redirect_uri=settings.GOOGLE_OAUTH_REDIRECT_URI or "",
        )
        user = _upsert_google_user(profile, session)
        _set_session_user(request, user)
        return RedirectResponse(_frontend_redirect(return_to), status_code=status.HTTP_302_FOUND)
    except HTTPException:
        raise
    except Exception as exc:
        logger.warning("Google OAuth callback failed: %s", exc.__class__.__name__)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Google OAuth login failed.",
        ) from exc
    finally:
        _clear_google_oauth_session(request)


@router.post("/logout")
async def logout(request: Request) -> dict[str, str]:
    """Clear the current session (log out any role)."""
    request.session.clear()
    return {"status": "logged_out"}


@router.get("/me")
async def me(user: SessionUser = Depends(get_current_user)) -> UserResponse:
    """Return the current session user (or guest if unauthenticated)."""
    return _user_response(user)


@router.get("/me/owner-only", include_in_schema=False)
async def me_owner_only(
    user: SessionUser = Depends(require_role("owner")),
) -> UserResponse:
    """Test endpoint — proves require_role('owner') works end-to-end."""
    return _user_response(user)
