"""Admin audit log viewer endpoints (DEBT-054)."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from novelai.api.auth.roles import require_role
from novelai.api.auth.security import require_csrf_for_unsafe_methods
from novelai.api.routers.dependencies import get_db_session
from novelai.services.audit_service import AuditService

router = APIRouter(
    prefix="/api/admin/audit",
    tags=["admin-api"],
    dependencies=[Depends(require_csrf_for_unsafe_methods)],
)


def _get_audit_service(db: Session = Depends(get_db_session)) -> AuditService:
    return AuditService(db)


def _parse_iso_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        # Accept both ``...Z`` and offset-aware forms.
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"Invalid datetime: {value}") from exc


@router.get("", dependencies=[Depends(require_role("owner"))])
def list_audit_events(
    action: str | None = Query(None, description="Filter by action label"),
    actor_user_id: int | None = Query(None, ge=1, description="Filter by actor user id"),
    target_type: str | None = Query(None, description="Filter by target type"),
    target_id: str | None = Query(None, description="Filter by target id"),
    status: str | None = Query(
        None,
        description="Filter by status (succeeded, failed, denied, partial, unknown)",
    ),
    severity: str | None = Query(
        None,
        description="Filter by severity (info, warning, critical, unknown)",
    ),
    request_id: str | None = Query(None, max_length=128, description="Filter by request id"),
    correlation_id: str | None = Query(None, max_length=128, description="Filter by correlation id"),
    date_from: str | None = Query(None, description="ISO-8601 lower bound on created_at"),
    date_to: str | None = Query(None, description="ISO-8601 upper bound on created_at"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    svc: AuditService = Depends(_get_audit_service),
) -> dict[str, Any]:
    """List audit log events for the owner viewer (newest first)."""
    parsed_from = _parse_iso_datetime(date_from)
    parsed_to = _parse_iso_datetime(date_to)
    if parsed_from is not None and parsed_to is not None and parsed_from > parsed_to:
        raise HTTPException(
            status_code=400,
            detail="date_from must be earlier than or equal to date_to",
        )
    offset = (page - 1) * page_size
    rows, total = svc.list_logs(
        action=action,
        actor_user_id=actor_user_id,
        target_type=target_type,
        target_id=target_id,
        status=status,
        severity=severity,
        request_id=request_id,
        correlation_id=correlation_id,
        date_from=parsed_from,
        date_to=parsed_to,
        limit=page_size,
        offset=offset,
    )
    return {
        "items": [svc.to_summary(row) for row in rows],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.get("/{audit_id}", dependencies=[Depends(require_role("owner"))])
def get_audit_event(
    audit_id: int,
    svc: AuditService = Depends(_get_audit_service),
) -> dict[str, Any]:
    """Return the redacted detail for a single audit event."""
    log = svc.get_log(audit_id)
    if log is None:
        raise HTTPException(status_code=404, detail="Audit event not found")
    return svc.to_detail(log)
