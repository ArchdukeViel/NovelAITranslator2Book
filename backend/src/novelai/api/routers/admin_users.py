"""Admin user management endpoints (DEBT-008).

Owner-only CRUD for user accounts. The single-owner architecture means
no endpoint here can create, promote, or transfer the owner role — that
is reserved for ``OWNER_BOOTSTRAP_SECRET``. Roles ``user`` and ``guest``
can be assigned; active flag flips persistence only.

Every mutation requires a reason (1-500 chars, trimmed) and is audited
after a successful DB write. If audit persistence fails the transaction
is rolled back, keeping mutation and audit atomic.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, NoReturn

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from novelai.api.auth.roles import require_role
from novelai.api.auth.security import require_csrf_for_unsafe_methods
from novelai.api.auth.session import SessionUser
from novelai.api.routers.dependencies import get_db_session
from novelai.services.audit_service import AuditService
from novelai.services.auth_service import AuthService

router = APIRouter(
    prefix="/api/admin/users",
    tags=["admin-api"],
    dependencies=[Depends(require_csrf_for_unsafe_methods)],
)

_SAFE_ROLES = frozenset({"user", "guest"})


# ── request / response helpers ──────────────────────────────────────────────────


class ReasonMixin(BaseModel):
    reason: str = Field(
        ...,
        min_length=1,
        max_length=500,
        description="Reason for the action (1-500 chars, trimmed).",
    )


class ActiveUpdateRequest(ReasonMixin):
    is_active: bool


class RoleUpdateRequest(ReasonMixin):
    role: str = Field(..., description="Target role: 'user' or 'guest'")


class RevokeSessionsRequest(ReasonMixin):
    pass


def _iso(value: object) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.isoformat().replace("+00:00", "Z")
    return str(value)


def _to_user_dict(user: Any) -> dict[str, Any]:
    """Safe summary for list responses."""
    return {
        "id": user.id,
        "email": user.email,
        "display_name": user.display_name,
        "role": user.role,
        "is_active": user.is_active,
        "auth_provider": user.auth_provider,
        "has_password": bool(user.password_hash),
        "email_verified": getattr(user, "email_verified_at", None) is not None,
        "created_at": _iso(user.created_at),
        "last_login_at": _iso(user.last_login_at),
    }


def _to_user_detail(user: Any) -> dict[str, Any]:
    """Full detail including admin-management fields."""
    d = _to_user_dict(user)
    d.update(
        {
            "auth_provider_subject": user.auth_provider_subject,
            "disabled_at": _iso(user.disabled_at),
            "disabled_reason": user.disabled_reason,
            "disabled_by_user_id": user.disabled_by_user_id,
            "session_revoked_at": _iso(user.session_revoked_at),
        }
    )
    return d


def _svc(session: Session) -> AuthService:
    return AuthService(db_session=session)


def _get_user_or_404(svc: AuthService, user_id: int) -> Any:
    user = svc.get_user(user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return user


def _actor_user_id(actor: SessionUser) -> int:
    """Guaranteed non-None because require_role('owner') enforces auth."""
    assert actor.user_id is not None  # nosec
    return actor.user_id


# ── list / detail ───────────────────────────────────────────────────────────────


@router.get("", dependencies=[Depends(require_role("owner"))])
def list_users(
    role: str | None = Query(None, description="Filter by role"),
    is_active: bool | None = Query(None, description="Filter by active flag"),
    search: str | None = Query(None, description="Substring match on email or display_name"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    session: Session = Depends(get_db_session),
) -> dict[str, Any]:
    svc = _svc(session)
    rows, total = svc.list_users(
        role=role,
        is_active=is_active,
        search=search,
        page=page,
        page_size=page_size,
    )
    return {
        "items": [_to_user_dict(row) for row in rows],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.get("/{user_id}", dependencies=[Depends(require_role("owner"))])
def get_user(
    user_id: int,
    session: Session = Depends(get_db_session),
) -> dict[str, Any]:
    svc = _svc(session)
    user = _get_user_or_404(svc, user_id)
    return _to_user_detail(user)


# ── mutations ───────────────────────────────────────────────────────────────────


def _mutate_with_audit(
    *,
    session: Session,
    actor: SessionUser,
    action: str,
    target_id: str,
    before: dict[str, Any],
    mutation_fn: Any,
) -> dict[str, Any]:
    """Execute mutation, persist audit, commit atomically."""
    user = mutation_fn()
    after = _to_user_detail(user)
    AuditService(session).log(
        action=action,
        actor_user_id=actor.user_id,
        target_type="user",
        target_id=target_id,
        metadata={"before": before, "after": after},
    )
    session.commit()
    return after


def _handle_service_error(exc: Exception) -> NoReturn:
    if isinstance(exc, LookupError):
        raise HTTPException(status_code=404, detail="User not found") from exc
    if isinstance(exc, PermissionError):
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if isinstance(exc, ValueError):
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    raise HTTPException(status_code=500, detail="Unexpected error.") from exc


@router.patch("/{user_id}/active")
def update_active(
    user_id: int,
    body: ActiveUpdateRequest,
    actor: SessionUser = Depends(require_role("owner")),
    session: Session = Depends(get_db_session),
) -> dict[str, Any]:
    svc = _svc(session)
    try:
        reason = AuthService.validate_reason(body.reason)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    user = _get_user_or_404(svc, user_id)
    before = _to_user_detail(user)

    if body.is_active:
        try:
            return _mutate_with_audit(
                session=session,
                actor=actor,
                action="user.enabled",
                target_id=str(user_id),
                before=before,
                mutation_fn=lambda: svc.enable_user(user_id),
            )
        except Exception as exc:
            _handle_service_error(exc)
    else:
        try:
            return _mutate_with_audit(
                session=session,
                actor=actor,
                action="user.disabled",
                target_id=str(user_id),
                before=before,
                mutation_fn=lambda: svc.disable_user(user_id, reason=reason, by_user_id=_actor_user_id(actor)),
            )
        except Exception as exc:
            _handle_service_error(exc)


@router.patch("/{user_id}/role")
def update_role(
    user_id: int,
    body: RoleUpdateRequest,
    actor: SessionUser = Depends(require_role("owner")),
    session: Session = Depends(get_db_session),
) -> dict[str, Any]:
    target = body.role.strip().lower()
    if target not in _SAFE_ROLES:
        raise HTTPException(status_code=400, detail=f"role must be one of {sorted(_SAFE_ROLES)}")
    try:
        AuthService.validate_reason(body.reason)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    svc = _svc(session)
    user = _get_user_or_404(svc, user_id)
    before = _to_user_detail(user)
    try:
        return _mutate_with_audit(
            session=session,
            actor=actor,
            action="user.role_changed",
            target_id=str(user_id),
            before=before,
            mutation_fn=lambda: svc.set_role(user_id, target),
        )
    except Exception as exc:
        _handle_service_error(exc)


@router.post("/{user_id}/revoke-sessions")
def revoke_sessions(
    user_id: int,
    body: RevokeSessionsRequest,
    actor: SessionUser = Depends(require_role("owner")),
    session: Session = Depends(get_db_session),
) -> dict[str, Any]:
    try:
        AuthService.validate_reason(body.reason)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    svc = _svc(session)
    user = _get_user_or_404(svc, user_id)
    before = _to_user_detail(user)
    try:
        return _mutate_with_audit(
            session=session,
            actor=actor,
            action="user.sessions_revoked",
            target_id=str(user_id),
            before=before,
            mutation_fn=lambda: svc.revoke_sessions(user_id),
        )
    except Exception as exc:
        _handle_service_error(exc)
