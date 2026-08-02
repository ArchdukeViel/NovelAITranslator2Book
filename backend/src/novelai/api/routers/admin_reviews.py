"""Admin review-moderation endpoints."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from novelai.api.auth.roles import require_role
from novelai.api.auth.security import require_csrf_for_unsafe_methods
from novelai.api.auth.session import SessionUser
from novelai.api.routers.dependencies import get_db_session, get_review_service
from novelai.services.audit_service import AuditService
from novelai.services.review_service import ReviewService

router = APIRouter(
    prefix="/api/admin",
    tags=["admin-api"],
    dependencies=[Depends(require_csrf_for_unsafe_methods)],
)
logger = logging.getLogger(__name__)


class ModerationRequest(BaseModel):
    status: str
    reviewer_notes: str | None = None


@router.get("/reviews", dependencies=[Depends(require_role("owner"))])
def list_reviews(
    status: str | None = Query(None, description="Filter by status"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    sort_by: str = Query("created_at"),
    order: str = Query("desc", pattern="^(asc|desc)$"),
    svc: ReviewService = Depends(get_review_service),
) -> dict[str, Any]:
    """List all reviews for admin moderation (owner only)."""
    rows, total = svc.list_all_reviews(status=status, page=page, page_size=page_size, sort_by=sort_by, order=order)

    def _to_dict(r: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": r["id"],
            "user_id": r["user_id"],
            "slug": r["slug"],
            "title": r["title"],
            "rating": r["rating"],
            "body": r["body"],
            "status": r["status"],
            "created_at": str(r["created_at"]) if r["created_at"] else None,
            "updated_at": str(r["updated_at"]) if r["updated_at"] else None,
            "moderated_at": str(r["moderated_at"]) if r["moderated_at"] else None,
            "reviewer_notes": r["reviewer_notes"],
            "reviewed_by_user_id": r["reviewed_by_user_id"],
        }

    return {
        "items": [_to_dict(r) for r in rows],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.post("/reviews/{review_id}/review")
def review_moderation(
    review_id: int,
    body: ModerationRequest,
    actor: SessionUser = Depends(require_role("owner")),
    db: Session = Depends(get_db_session),
    svc: ReviewService = Depends(get_review_service),
) -> dict[str, str]:
    """Moderate a review — publish or reject."""
    try:
        review = svc.moderate_review(
            review_id=review_id,
            status=body.status,
            reviewer_notes=body.reviewer_notes,
            reviewed_by_user_id=actor.user_id,
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    if not review:
        raise HTTPException(404, "Review not found")

    AuditService(db).log(
        action="review.moderated",
        actor_user_id=actor.user_id,
        target_type="review",
        target_id=str(review_id),
        metadata={
            "decision": review.status,
            "novel_id": review.novel_id,
        },
    )
    db.commit()
    return {"status": review.status}
