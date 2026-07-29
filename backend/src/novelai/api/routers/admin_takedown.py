"""Admin DMCA takedown-review endpoints."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from novelai.api.auth.roles import require_role
from novelai.api.auth.security import require_csrf_for_unsafe_methods
from novelai.api.auth.session import SessionUser
from novelai.api.routers.dependencies import get_db_session
from novelai.services.audit_service import AuditService
from novelai.services.takedown_service import TakedownService

router = APIRouter(
    prefix="/api/admin",
    tags=["admin-api"],
    dependencies=[Depends(require_csrf_for_unsafe_methods)],
)
logger = logging.getLogger(__name__)


class ReviewRequest(BaseModel):
    status: str
    reviewer_notes: str | None = None


def _get_takedown_service(db: Session = Depends(get_db_session)) -> TakedownService:
    return TakedownService(db)


@router.get("/takedowns", dependencies=[Depends(require_role("owner"))])
def list_takedowns(
    status: str | None = Query(None, description="Filter by status"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    sort_by: str = Query("created_at"),
    order: str = Query("desc", regex="^(asc|desc)$"),
    svc: TakedownService = Depends(_get_takedown_service),
) -> dict[str, Any]:
    """List DMCA takedown requests (owner only)."""
    rows, total = svc.list_requests(status=status, page=page, page_size=page_size, sort_by=sort_by, order=order)

    def _to_dict(r: Any) -> dict[str, Any]:
        return {
            "id": r.id,
            "created_at": str(r.created_at) if r.created_at else None,
            "complainant_name": r.complainant_name,
            "complainant_email": r.complainant_email,
            "infringing_url": r.infringing_url,
            "description": r.description,
            "status": r.status,
            "reviewer_notes": r.reviewer_notes,
            "reviewed_at": str(r.reviewed_at) if r.reviewed_at else None,
        }

    return {
        "items": [_to_dict(r) for r in rows],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.get("/takedowns/{request_id}", dependencies=[Depends(require_role("owner"))])
def get_takedown(
    request_id: int,
    svc: TakedownService = Depends(_get_takedown_service),
) -> dict[str, Any]:
    """Get a single DMCA takedown request detail."""
    req = svc.get_request(request_id)
    if not req:
        raise HTTPException(404, "Takedown request not found")
    return {
        "id": req.id,
        "created_at": str(req.created_at) if req.created_at else None,
        "updated_at": str(req.updated_at) if req.updated_at else None,
        "complainant_name": req.complainant_name,
        "complainant_email": req.complainant_email,
        "complainant_phone": req.complainant_phone,
        "infringing_url": req.infringing_url,
        "description": req.description,
        "original_work_url": req.original_work_url,
        "original_work_description": req.original_work_description,
        "status": req.status,
        "reviewer_notes": req.reviewer_notes,
        "reviewed_at": str(req.reviewed_at) if req.reviewed_at else None,
        "signature": req.signature,
        "ip_address": req.ip_address,
    }


@router.post("/takedowns/{request_id}/review")
def review_takedown(
    request_id: int,
    body: ReviewRequest,
    actor: SessionUser = Depends(require_role("owner")),
    db: Session = Depends(get_db_session),
    svc: TakedownService = Depends(_get_takedown_service),
) -> dict[str, str]:
    """Review a DMCA takedown request — approve, reject, etc."""
    try:
        req = svc.review(
            request_id=request_id,
            status=body.status,
            reviewer_notes=body.reviewer_notes,
            reviewed_by_user_id=actor.user_id,
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    if not req:
        raise HTTPException(404, "Takedown request not found")

    # DEBT-054: Audit log entry for every takedown review outcome.
    audit = AuditService(db)
    audit.log(
        action="takedown.reviewed",
        actor_user_id=actor.user_id,
        target_type="takedown_request",
        target_id=str(request_id),
        metadata={
            "decision": req.status,
            "infringing_url": getattr(req, "infringing_url", None),
        },
    )
    db.commit()
    return {"status": req.status}
