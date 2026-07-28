"""Session helpers: SessionUser model and get_current_user dependency.

Session data is stored server-side in a signed HTTP-only cookie via
Starlette's SessionMiddleware.  The session dict holds:
  {
    "user_id": int,
    "email": str,
    "role": "guest" | "user" | "owner",
    "issued_at": str (ISO-8601 UTC, optional)
  }

``get_current_user`` validates the session against the DB on every
authenticated request — rejecting disabled accounts and sessions issued
before ``session_revoked_at``.  A missing or empty session is treated
as a guest (not an error).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from novelai.api.routers.dependencies import get_db_session
from novelai.db.models.users import User


@dataclass(frozen=True)
class SessionUser:
    """Immutable snapshot of the authenticated session user.

    Attributes:
        user_id: DB primary key (None for anonymous/guest requests).
        email: User email address.
        role: guest | user | owner (from architecture.md §19).
    """

    user_id: int | None
    email: str | None
    role: str  # "guest" | "user" | "owner"

    @property
    def is_authenticated(self) -> bool:
        return self.user_id is not None

    @property
    def is_owner(self) -> bool:
        return self.role == "owner"

    @property
    def is_user(self) -> bool:
        return self.role in ("user", "owner")


# Sentinel representing an unauthenticated (guest) request.
GUEST = SessionUser(user_id=None, email=None, role="guest")


def get_current_user(
    request: Request,
    db_session: Session = Depends(get_db_session),
) -> SessionUser:
    """FastAPI dependency: return the session user or GUEST.

    Validates session against database on every authenticated request:
    - Rejects disabled accounts (``is_active=False`` or ``disabled_at`` set).
    - Rejects sessions issued before the user's ``session_revoked_at``.

    Never raises — invalid/expired session returns GUEST.
    Use require_role() to enforce access control.
    """
    session = request.session
    user_id = session.get("user_id")
    if not isinstance(user_id, int):
        return GUEST

    user = db_session.get(User, user_id)
    if user is None:
        return GUEST
    if not user.is_active or user.disabled_at is not None:
        return GUEST

    issued_raw = session.get("issued_at")
    if isinstance(issued_raw, str) and user.session_revoked_at is not None:
        try:
            issued_at = datetime.fromisoformat(issued_raw)
            if issued_at.tzinfo is None:
                issued_at = issued_at.replace(tzinfo=UTC)
            revoked_at = user.session_revoked_at
            if revoked_at.tzinfo is None:
                revoked_at = revoked_at.replace(tzinfo=UTC)
            if issued_at < revoked_at:
                return GUEST
        except (ValueError, TypeError):
            pass

    email = session.get("email")
    role = session.get("role", "user")
    return SessionUser(
        user_id=user_id,
        email=email if isinstance(email, str) else None,
        role=role if role in ("guest", "user", "owner") else "user",
    )
