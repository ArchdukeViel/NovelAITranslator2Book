"""require_role FastAPI dependency factory.

Usage:
    from novelai.api.auth.roles import require_role

    @router.post("/dangerous-action")
    async def dangerous(user: SessionUser = Depends(require_role("owner"))):
        ...

Architecture rules (architecture.md §19):
- Every dangerous router MUST use Depends(require_role("owner")).
- Non-owner calls MUST return 401/403 — never 200.
- Frontend route hiding is NOT authorization.
"""

from __future__ import annotations

from fastapi import Depends, HTTPException, status

from novelai.api.auth.session import SessionUser, get_current_user


def require_role(minimum_role: str):
    """Return a FastAPI dependency that enforces a minimum role.

    Role hierarchy: guest < user < owner.

    Args:
        minimum_role: One of "guest", "user", "owner".
            - "guest": any request passes (no-op).
            - "user": authenticated users and owner pass; guests get 401.
            - "owner": only the owner passes; others get 401 or 403.

    Returns:
        A FastAPI dependency callable that returns SessionUser on success
        or raises HTTPException on failure.

    Raises:
        HTTPException 401: unauthenticated request to a user/owner route.
        HTTPException 403: authenticated non-owner request to an owner route.
    """
    _ROLE_RANK = {"guest": 0, "user": 1, "owner": 2}
    required_rank = _ROLE_RANK.get(minimum_role, 99)

    def _check(user: SessionUser = Depends(get_current_user)) -> SessionUser:
        user_rank = _ROLE_RANK.get(user.role, 0)
        if user_rank >= required_rank:
            return user
        if not user.is_authenticated:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication required.",
            )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions.",
        )

    return _check
