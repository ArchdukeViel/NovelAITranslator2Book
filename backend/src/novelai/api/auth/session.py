"""Session helpers: SessionUser model and get_current_user dependency.

Session data is stored server-side in a signed HTTP-only cookie via
Starlette's SessionMiddleware.  The session dict holds:
  {
    "user_id": int,
    "email": str,
    "role": "guest" | "user" | "owner"
  }

A missing or empty session is treated as a guest (not an error).
"""

from __future__ import annotations

from dataclasses import dataclass

from fastapi import Request


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


def get_current_user(request: Request) -> SessionUser:
    """FastAPI dependency: return the session user or GUEST.

    Never raises — missing/invalid session returns GUEST.
    Use require_role() to enforce access control.
    """
    session = request.session
    user_id = session.get("user_id")
    if not isinstance(user_id, int):
        return GUEST
    email = session.get("email")
    role = session.get("role", "user")
    return SessionUser(
        user_id=user_id,
        email=email if isinstance(email, str) else None,
        role=role if role in ("guest", "user", "owner") else "user",
    )
