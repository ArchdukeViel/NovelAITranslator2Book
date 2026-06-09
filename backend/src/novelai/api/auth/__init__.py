"""Authentication and session boundary for Novel AI.

Provides:
- Session middleware setup (HTTP-only, same-site, signed cookies)
- get_current_user: FastAPI dependency — returns session user or None
- require_role: FastAPI dependency factory — rejects by role
- Auth router: /api/auth/login, /api/auth/logout, /api/auth/me

Architecture (architecture.md §19):
- v1 uses HTTP-only server sessions (NOT JWT).
- Exactly one owner; owner is seeded via OWNER_BOOTSTRAP_SECRET, never a public signup.
- Authorization is enforced in the backend — never by hiding frontend routes.
- Ownership is established only by the backend session layer, never by
  client-supplied IDs, localStorage, or frontend flags.
"""

from __future__ import annotations

from novelai.api.auth.roles import require_role
from novelai.api.auth.session import SessionUser, get_current_user

__all__ = ["require_role", "get_current_user", "SessionUser"]
