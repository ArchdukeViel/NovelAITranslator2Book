from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from novelai.api.auth.roles import require_role
from novelai.api.routers.dependencies import get_db_session
from novelai.core.platform import NovelRequestStatus
from novelai.db.models.novel import Novel
from novelai.db.models.users import NovelRequest

router = APIRouter()

_VALID_STATUSES = {item.value for item in NovelRequestStatus}
_RESOLVED_STATUSES = {
    NovelRequestStatus.APPROVED.value,
    NovelRequestStatus.REJECTED.value,
    NovelRequestStatus.RELEASED.value,
}


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


class SourceCandidateCreateRequest(BaseModel):
    source_key: str | None = None
    source_url: str | None = None
    submitted_by: str | None = None
    notes: str | None = None


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _normalize_status(status: str | None) -> str | None:
    if status is None:
        return None
    normalized = status.strip().lower()
    if normalized not in _VALID_STATUSES:
        raise HTTPException(status_code=400, detail="Invalid request status")
    return normalized


def _request_pk(request_id: str) -> int:
    try:
        return int(request_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="Novel request not found") from exc


def _novel_slug(novel_id: int | None, session: Session) -> str | None:
    if novel_id is None:
        return None
    novel = session.query(Novel).filter_by(id=novel_id).one_or_none()
    return novel.slug if novel else None


def _request_response(item: NovelRequest, session: Session) -> dict[str, Any]:
    request_id = str(item.id)
    return {
        "id": request_id,
        "request_id": request_id,
        "db_id": item.id,
        "user_id": item.user_id,
        "request_type": item.request_type,
        "status": item.status,
        "source_url": item.source_url,
        "slug": _novel_slug(item.novel_id, session),
        "chapter_id": None,
        "created_at": item.created_at,
        "resolved_at": item.resolved_at,
    }


def _get_request(request_id: str, session: Session) -> NovelRequest:
    item = session.get(NovelRequest, _request_pk(request_id))
    if item is None:
        raise HTTPException(status_code=404, detail="Novel request not found")
    return item


@router.get("/requests")
async def list_novel_requests(
    status: str | None = None,
    limit: int = Query(default=50, ge=1, le=100),
    session: Session = Depends(get_db_session),
    _owner=Depends(require_role("owner")),
) -> dict[str, Any]:
    normalized_status = _normalize_status(status)
    query = session.query(NovelRequest)
    if normalized_status is not None:
        query = query.filter(NovelRequest.status == normalized_status)
    items = query.order_by(NovelRequest.created_at.desc()).limit(limit).all()
    return {"requests": [_request_response(item, session) for item in items]}


@router.post("/requests")
async def create_novel_request(
    _body: NovelRequestCreateRequest,
    _session: Session = Depends(get_db_session),
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
    session: Session = Depends(get_db_session),
    _owner=Depends(require_role("owner")),
) -> dict[str, Any]:
    return _request_response(_get_request(request_id, session), session)


@router.post("/requests/{request_id}/vote")
async def vote_novel_request(
    request_id: str,
    _body: NovelRequestVoteRequest,
    _session: Session = Depends(get_db_session),
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
    session: Session = Depends(get_db_session),
    _owner=Depends(require_role("owner")),
) -> dict[str, Any]:
    status = _normalize_status(body.status)
    assert status is not None
    item = _get_request(request_id, session)
    item.status = status
    if status == NovelRequestStatus.PENDING.value:
        item.resolved_at = None
    elif status in _RESOLVED_STATUSES:
        item.resolved_at = item.resolved_at or _utcnow()
    session.flush()
    return _request_response(item, session)


@router.post("/requests/{request_id}/source-candidates")
async def add_source_candidate(
    request_id: str,
    _body: SourceCandidateCreateRequest,
    _session: Session = Depends(get_db_session),
    _owner=Depends(require_role("owner")),
) -> dict[str, Any]:
    # Source candidates are still legacy file-backed data. A future phase should
    # add DB-backed candidate/link fields before re-enabling this route.
    raise HTTPException(
        status_code=410,
        detail="Source candidates are not supported on the DB-backed request moderation route.",
    )
