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


class NovelRequestCreateRequest(BaseModel):
    title: str
    source_key: str | None = None
    source_url: str | None = None
    requested_by: str | None = None
    notes: str | None = None


class NovelRequestVoteRequest(BaseModel):
    voter: str | None = None


class NovelRequestStatusRequest(BaseModel):
    status: str
    reviewed_by: str | None = None
    notes: str | None = None
    rejection_reason: str | None = None
    approved_novel_id: int | None = None


class SourceCandidateCreateRequest(BaseModel):
    source_key: str | None = None
    source_url: str | None = None
    submitted_by: str | None = None
    notes: str | None = None


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


@router.post("/requests")
async def create_novel_request(
    _body: NovelRequestCreateRequest,
    _owner=Depends(require_role("owner")),
) -> dict[str, Any]:
    # Admin request creation used to write to the legacy file-backed queue. The
    # canonical request path is now public user creation plus owner moderation.
    raise HTTPException(
        status_code=410,
        detail="Admin request creation is not supported on the DB-backed request moderation route.",
    )


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


@router.post("/requests/{request_id}/vote")
async def vote_novel_request(
    request_id: str,
    _body: NovelRequestVoteRequest,
    _owner=Depends(require_role("owner")),
) -> dict[str, Any]:
    # Voting belongs to the legacy file-backed request queue and has no DB
    # schema yet. Keep the endpoint explicit so callers do not mutate old state.
    raise HTTPException(
        status_code=410,
        detail="Request voting is not supported on the DB-backed request moderation route.",
    )


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


@router.post("/requests/{request_id}/source-candidates")
async def add_source_candidate(
    request_id: str,
    _body: SourceCandidateCreateRequest,
    _owner=Depends(require_role("owner")),
) -> dict[str, Any]:
    # Source candidates are still legacy file-backed data. A future phase should
    # add DB-backed candidate/link fields before re-enabling this route.
    raise HTTPException(
        status_code=410,
        detail="Source candidates are not supported on the DB-backed request moderation route.",
    )
