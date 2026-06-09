"""Auth router: login, logout, me.

Endpoints:
  POST /api/auth/login   - owner bootstrap login (OWNER_BOOTSTRAP_SECRET)
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

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel

from novelai.api.auth.roles import require_role
from novelai.api.auth.session import SessionUser, get_current_user
from novelai.config.settings import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/auth", tags=["auth"])


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
