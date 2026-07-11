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

import hashlib
import logging
import re
import secrets
from datetime import UTC, datetime, timedelta
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.orm import Session
from starlette.responses import RedirectResponse

from novelai.api.auth.google_oauth import GoogleOAuthClient, GoogleOAuthProfile, get_google_oauth_client
from novelai.api.auth.passwords import hash_password, verify_password
from novelai.api.auth.roles import require_role
from novelai.api.auth.security import (
    clear_csrf_token,
    get_or_create_csrf_token,
    require_csrf_token,
    require_public_rate_limit,
)
from novelai.api.auth.session import SessionUser, get_current_user
from novelai.api.routers.dependencies import get_db_session
from novelai.config.settings import settings
from novelai.db.models.users import EmailVerificationToken, PasswordResetToken, User
from novelai.runtime.container import container
from novelai.services.email import AuthEmailService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/auth", tags=["auth"])

_OAUTH_STATE_KEY = "oauth_google_state"
_OAUTH_RETURN_TO_KEY = "oauth_google_return_to"
_DEFAULT_PUBLIC_RETURN_TO = "/"
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_MIN_PASSWORD_LENGTH = 10
_MAX_PASSWORD_LENGTH = 256
_PASSWORD_RESET_TOKEN_BYTES = 32
_PASSWORD_RESET_EXPIRES_MINUTES = 60
_EMAIL_VERIFICATION_TOKEN_BYTES = 32
_EMAIL_VERIFICATION_EXPIRES_HOURS = 24


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------

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
    base = settings.PUBLIC_FRONTEND_URL.rstrip("/")
    safe_path = _safe_return_path(path)
    return f"{base}{safe_path}"


def _normalize_email(email: str) -> str:
    return email.strip().lower()


def _validate_public_email(email: str) -> str:
    normalized = _normalize_email(email)
    if len(normalized) > 255 or not _EMAIL_RE.match(normalized):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid email address.")
    return normalized


def _validate_public_password(password: str) -> None:
    if len(password) < _MIN_PASSWORD_LENGTH:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Password must be at least {_MIN_PASSWORD_LENGTH} characters.",
        )
    if len(password) > _MAX_PASSWORD_LENGTH:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Password must be at most {_MAX_PASSWORD_LENGTH} characters.",
        )


def _new_password_reset_token() -> str:
    return secrets.token_urlsafe(_PASSWORD_RESET_TOKEN_BYTES)


def _hash_password_reset_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _new_email_verification_token() -> str:
    return secrets.token_urlsafe(_EMAIL_VERIFICATION_TOKEN_BYTES)


def _hash_email_verification_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _is_expired(expires_at: datetime) -> bool:
    now = datetime.now(UTC)
    if expires_at.tzinfo is None:
        return expires_at <= now.replace(tzinfo=None)
    return expires_at <= now


def _client_ip(request: Request) -> str | None:
    try:
        return request.client.host if request.client else None
    except Exception:
        return None


def _truncate_header(value: str | None, max_length: int = 255) -> str | None:
    if not isinstance(value, str) or not value.strip():
        return None
    return value.strip()[:max_length]


def get_auth_email_service() -> AuthEmailService:
    return container.auth_email


def _deliver_password_reset_email(
    mailer: AuthEmailService,
    *,
    email: str,
    token: str,
    user_id: int,
) -> None:
    try:
        result = mailer.send_password_reset_email(email=email, token=token)
    except Exception as exc:
        logger.warning(
            "Password reset email delivery failed for user_id=%s error=%s.",
            user_id,
            exc.__class__.__name__,
        )
        return
    if not result.delivered:
        logger.info(
            "Password reset email not delivered for user_id=%s provider=%s.",
            user_id,
            result.provider,
        )


def _deliver_email_verification_email(
    mailer: AuthEmailService,
    *,
    email: str,
    token: str,
    user_id: int,
) -> None:
    try:
        result = mailer.send_email_verification_email(email=email, token=token)
    except Exception as exc:
        logger.warning(
            "Email verification delivery failed for user_id=%s error=%s.",
            user_id,
            exc.__class__.__name__,
        )
        return
    if not result.delivered:
        logger.info(
            "Email verification not delivered for user_id=%s provider=%s.",
            user_id,
            result.provider,
        )


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
        if user.email_verified_at is None:
            user.email_verified_at = datetime.now(UTC)
        user.last_login_at = datetime.now(UTC)
        session.flush()
        return user

    user = User(
        email=email,
        display_name=profile.display_name,
        role="user",
        auth_provider="google",
        auth_provider_subject=profile.subject,
        email_verified_at=datetime.now(UTC),
        is_active=True,
        last_login_at=datetime.now(UTC),
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

    # Seed a minimal owner session — no DB row required for bootstrap login.
    request.session["user_id"] = 1  # Bootstrap owner is always ID 1
    request.session["email"] = "owner@local"
    request.session["role"] = "owner"
    logger.info("Owner bootstrap login succeeded.")
    return _user_response(SessionUser(user_id=1, email="owner@local", role="owner"))


@router.post("/register")
async def register(
    payload: RegisterRequest,
    request: Request,
    session: Session = Depends(get_db_session),
    mailer: AuthEmailService = Depends(get_auth_email_service),
) -> UserResponse:
    """Create a public email/password user account and session."""
    require_public_rate_limit(request, "auth_register")
    email = _validate_public_email(payload.email)
    _validate_public_password(payload.password)
    display_name = payload.display_name.strip() if payload.display_name else None
    if display_name == "":
        display_name = None

    existing = session.query(User).filter(func.lower(User.email) == email).one_or_none()
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account already exists for this email.",
        )

    now = datetime.now(UTC)
    user = User(
        email=email,
        display_name=display_name,
        role="user",
        auth_provider="password",
        auth_provider_subject=None,
        password_hash=hash_password(payload.password),
        is_active=True,
        last_login_at=now,
    )
    session.add(user)
    session.flush()
    raw_token = _new_email_verification_token()
    session.add(
        EmailVerificationToken(
            user_id=user.id,
            token_hash=_hash_email_verification_token(raw_token),
            created_at=now,
            expires_at=now + timedelta(hours=_EMAIL_VERIFICATION_EXPIRES_HOURS),
            request_ip=_client_ip(request),
            user_agent=_truncate_header(request.headers.get("user-agent")),
        )
    )
    session.flush()
    _deliver_email_verification_email(mailer, email=user.email, token=raw_token, user_id=user.id)
    _set_session_user(request, user)
    logger.info("Public password registration succeeded for user_id=%s.", user.id)
    return _user_response(SessionUser(user_id=user.id, email=user.email, role=user.role))


@router.post("/password/login")
async def password_login(
    payload: PasswordLoginRequest,
    request: Request,
    session: Session = Depends(get_db_session),
) -> UserResponse:
    """Authenticate a public email/password user."""
    require_public_rate_limit(request, "auth_password_login")
    email = _normalize_email(payload.email)
    generic_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid email or password.",
    )
    if not email or len(email) > 255:
        raise generic_error

    user = session.query(User).filter(func.lower(User.email) == email).one_or_none()
    if (
        user is None
        or not user.is_active
        or user.role == "owner"
        or not user.password_hash
        or not verify_password(payload.password, user.password_hash)
    ):
        logger.warning("Failed public password login attempt.")
        raise generic_error

    user.last_login_at = datetime.now(UTC)
    session.flush()
    _set_session_user(request, user)
    logger.info("Public password login succeeded for user_id=%s.", user.id)
    return _user_response(SessionUser(user_id=user.id, email=user.email, role=user.role))


@router.post("/password/reset/request")
async def password_reset_request(
    payload: PasswordResetRequest,
    request: Request,
    session: Session = Depends(get_db_session),
    mailer: AuthEmailService = Depends(get_auth_email_service),
) -> PasswordResetResponse:
    """Create a reset token for a public email/password user, if eligible.

    The response is intentionally generic and never exposes whether an account
    exists. Raw reset tokens are not returned or logged; delivery is a future
    email-provider integration.
    """
    require_public_rate_limit(request, "auth_password_reset_request")
    try:
        email = _validate_public_email(payload.email)
    except HTTPException:
        return PasswordResetResponse(status="ok")

    user = session.query(User).filter(func.lower(User.email) == email).one_or_none()
    if (
        user is None
        or not user.is_active
        or user.role != "user"
        or user.auth_provider != "password"
        or not user.password_hash
    ):
        return PasswordResetResponse(status="ok")

    now = datetime.now(UTC)
    session.query(PasswordResetToken).filter(
        PasswordResetToken.user_id == user.id,
        PasswordResetToken.used_at.is_(None),
    ).update({"used_at": now}, synchronize_session=False)
    raw_token = _new_password_reset_token()
    session.add(
        PasswordResetToken(
            user_id=user.id,
            token_hash=_hash_password_reset_token(raw_token),
            created_at=now,
            expires_at=now + timedelta(minutes=_PASSWORD_RESET_EXPIRES_MINUTES),
            request_ip=_client_ip(request),
            user_agent=_truncate_header(request.headers.get("user-agent")),
        )
    )
    session.flush()
    _deliver_password_reset_email(mailer, email=user.email, token=raw_token, user_id=user.id)
    logger.info("Password reset requested for user_id=%s.", user.id)
    return PasswordResetResponse(status="ok")


@router.post("/password/reset/confirm")
async def password_reset_confirm(
    payload: PasswordResetConfirmRequest,
    request: Request,
    session: Session = Depends(get_db_session),
) -> PasswordResetResponse:
    """Reset a public email/password user's password with a one-time token."""
    require_public_rate_limit(request, "auth_password_reset_confirm")
    _validate_public_password(payload.new_password)
    generic_error = HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="Invalid or expired reset token.",
    )
    token = payload.token.strip()
    if not token:
        raise generic_error

    token_hash = _hash_password_reset_token(token)
    reset_token = session.query(PasswordResetToken).filter_by(token_hash=token_hash).one_or_none()
    if reset_token is None or reset_token.used_at is not None or _is_expired(reset_token.expires_at):
        raise generic_error

    user = session.get(User, reset_token.user_id)
    if (
        user is None
        or not user.is_active
        or user.role != "user"
        or user.auth_provider != "password"
        or not user.password_hash
    ):
        raise generic_error

    now = datetime.now(UTC)
    user.password_hash = hash_password(payload.new_password)
    reset_token.used_at = now
    session.query(PasswordResetToken).filter(
        PasswordResetToken.user_id == user.id,
        PasswordResetToken.used_at.is_(None),
        PasswordResetToken.id != reset_token.id,
    ).update({"used_at": now}, synchronize_session=False)
    session.flush()
    logger.info("Password reset confirmed for user_id=%s.", user.id)
    return PasswordResetResponse(status="ok")


@router.post("/email/verification/request")
async def email_verification_request(
    payload: EmailVerificationRequest,
    request: Request,
    session: Session = Depends(get_db_session),
    mailer: AuthEmailService = Depends(get_auth_email_service),
) -> EmailVerificationResponse:
    """Create or resend a verification token for an eligible public account.

    The response is intentionally generic and never exposes whether an account
    exists. Raw verification tokens are not returned or logged; delivery is a
    future email-provider integration.
    """
    require_public_rate_limit(request, "auth_email_verification_request")
    try:
        email = _validate_public_email(payload.email)
    except HTTPException:
        return EmailVerificationResponse(status="ok")

    user = session.query(User).filter(func.lower(User.email) == email).one_or_none()
    if (
        user is None
        or not user.is_active
        or user.role != "user"
        or user.auth_provider != "password"
        or not user.password_hash
        or user.email_verified_at is not None
    ):
        return EmailVerificationResponse(status="ok")

    now = datetime.now(UTC)
    session.query(EmailVerificationToken).filter(
        EmailVerificationToken.user_id == user.id,
        EmailVerificationToken.used_at.is_(None),
    ).update({"used_at": now}, synchronize_session=False)
    raw_token = _new_email_verification_token()
    session.add(
        EmailVerificationToken(
            user_id=user.id,
            token_hash=_hash_email_verification_token(raw_token),
            created_at=now,
            expires_at=now + timedelta(hours=_EMAIL_VERIFICATION_EXPIRES_HOURS),
            request_ip=_client_ip(request),
            user_agent=_truncate_header(request.headers.get("user-agent")),
        )
    )
    session.flush()
    _deliver_email_verification_email(mailer, email=user.email, token=raw_token, user_id=user.id)
    logger.info("Email verification requested for user_id=%s.", user.id)
    return EmailVerificationResponse(status="ok")


@router.post("/email/verification/confirm")
async def email_verification_confirm(
    payload: EmailVerificationConfirmRequest,
    request: Request,
    session: Session = Depends(get_db_session),
) -> EmailVerificationResponse:
    """Verify a public email/password user's email with a one-time token."""
    require_public_rate_limit(request, "auth_email_verification_confirm")
    generic_error = HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="Invalid or expired verification token.",
    )
    token = payload.token.strip()
    if not token:
        raise generic_error

    token_hash = _hash_email_verification_token(token)
    verification_token = (
        session.query(EmailVerificationToken)
        .filter_by(token_hash=token_hash)
        .one_or_none()
    )
    if (
        verification_token is None
        or verification_token.used_at is not None
        or _is_expired(verification_token.expires_at)
    ):
        raise generic_error

    user = session.get(User, verification_token.user_id)
    if (
        user is None
        or not user.is_active
        or user.role != "user"
        or user.auth_provider != "password"
        or not user.password_hash
    ):
        raise generic_error

    now = datetime.now(UTC)
    if user.email_verified_at is None:
        user.email_verified_at = now
    verification_token.used_at = now
    session.query(EmailVerificationToken).filter(
        EmailVerificationToken.user_id == user.id,
        EmailVerificationToken.used_at.is_(None),
        EmailVerificationToken.id != verification_token.id,
    ).update({"used_at": now}, synchronize_session=False)
    session.flush()
    logger.info("Email verification confirmed for user_id=%s.", user.id)
    return EmailVerificationResponse(status="ok")


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
    require_public_rate_limit(request, "oauth_start")
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
    require_public_rate_limit(request, "oauth_callback")
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
async def me_owner_only(
    user: SessionUser = Depends(require_role("owner")),
) -> UserResponse:
    """Test endpoint — proves require_role('owner') works end-to-end."""
    return _user_response(user)
