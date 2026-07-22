"""Novel request moderation endpoints — thin HTTP adapter."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from novelai.api.auth.roles import require_role
from novelai.api.auth.security import require_csrf_for_unsafe_methods
from novelai.api.routers.dependencies import get_novel_request_service
from novelai.core.platform import NovelRequestStatus
from novelai.services.novel_request_service import NovelRequestService

router = APIRouter(dependencies=[Depends(require_csrf_for_unsafe_methods)])


class NovelRequestStatusRequest(BaseModel):
    status: str
    reviewed_by: str | None = None
    notes: str | None = None
    rejection_reason: str | None = None
    approved_novel_id: int | None = None


@router.get("/requests")
async def list_novel_requests(
    status: str | None = None,
    limit: int = Query(default=50, ge=1, le=100),
    service: NovelRequestService = Depends(get_novel_request_service),
    _owner=Depends(require_role("owner")),
) -> dict[str, Any]:
    # Validate status first (returns 400 for invalid status)
    if status is not None:
        normalized = status.strip().lower()
        if normalized not in {item.value for item in NovelRequestStatus}:
            raise HTTPException(status_code=400, detail="Invalid request status")
    return {"requests": service.list_requests(status=status, limit=limit)}


@router.get("/requests/{request_id}")
async def get_novel_request(
    request_id: str,
    service: NovelRequestService = Depends(get_novel_request_service),
    _owner=Depends(require_role("owner")),
) -> dict[str, Any]:
    try:
        return service.get_request(request_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.patch("/requests/{request_id}")
async def update_novel_request_status(
    request_id: str,
    body: NovelRequestStatusRequest,
    service: NovelRequestService = Depends(get_novel_request_service),
    _owner=Depends(require_role("owner")),
) -> dict[str, Any]:
    # Validate status first (returns 400 for invalid status, 404 for not found)
    normalized = body.status.strip().lower() if body.status else None
    if normalized not in {item.value for item in NovelRequestStatus}:
        raise HTTPException(status_code=400, detail="Invalid request status")
    try:
        return service.update_request_status(
            request_id,
            body.status,
            rejection_reason=body.rejection_reason,
            approved_novel_id=body.approved_novel_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
