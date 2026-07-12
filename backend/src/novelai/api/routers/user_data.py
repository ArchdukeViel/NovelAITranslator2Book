"""User data router: authenticated public user features.

All endpoints require role ``user`` or higher and derive ownership from the
server-side session. Clients never submit or choose ``user_id``.
"""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Body, Depends, HTTPException, Query, Request
from pydantic import BaseModel, ConfigDict, Field, model_validator

from novelai.api.auth.roles import require_role
from novelai.api.auth.security import require_csrf_token, require_public_rate_limit
from novelai.api.auth.session import SessionUser
from novelai.api.routers.dependencies import (
    get_novel_request_service,
    get_reading_service,
    get_review_service,
    get_user_library_service,
)
from novelai.services.novel_request_service import NovelRequestService
from novelai.services.reading_service import ReadingService
from novelai.services.review_service import ReviewService
from novelai.services.user_library_service import UserLibraryService

router = APIRouter(prefix="/api/user", tags=["user"])


def _uid(user: SessionUser) -> int:
    assert _uid(user) is not None, "Authenticated route requires user_id"
    return _uid(user)


def _utcnow() -> datetime:
    return datetime.now(UTC)


class LibraryItemResponse(BaseModel):
    slug: str
    status: str
    added_at: datetime


@router.get("/library", response_model=list[LibraryItemResponse])
def list_library(
    user: SessionUser = Depends(require_role("user")),
    service: UserLibraryService = Depends(get_user_library_service),
) -> list[LibraryItemResponse]:
    items = service.list_library(_uid(user))
    return [LibraryItemResponse(**item) for item in items]


@router.get("/library/{slug}", response_model=LibraryItemResponse)
def get_library_item(
    slug: str,
    user: SessionUser = Depends(require_role("user")),
    service: UserLibraryService = Depends(get_user_library_service),
) -> LibraryItemResponse:
    try:
        item = service.get_library_item(_uid(user), slug)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return LibraryItemResponse(**item)


@router.post(
    "/library/{slug}",
    status_code=201,
    response_model=LibraryItemResponse,
    dependencies=[Depends(require_csrf_token)],
)
def add_to_library(
    slug: str,
    request: Request,
    user: SessionUser = Depends(require_role("user")),
    service: UserLibraryService = Depends(get_user_library_service),
) -> LibraryItemResponse:
    require_public_rate_limit(request, "library_mutation", user_id=_uid(user))
    try:
        item = service.add_to_library(_uid(user), slug)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return LibraryItemResponse(**item)


@router.delete(
    "/library/{slug}",
    status_code=204,
    dependencies=[Depends(require_csrf_token)],
)
def remove_from_library(
    slug: str,
    request: Request,
    user: SessionUser = Depends(require_role("user")),
    service: UserLibraryService = Depends(get_user_library_service),
) -> None:
    require_public_rate_limit(request, "library_mutation", user_id=_uid(user))
    try:
        service.remove_from_library(_uid(user), slug)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


class ProgressUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    chapter_id: str | None = None
    progress_percent: float = Field(default=0.0, ge=0.0, le=1.0)


class ProgressResponse(BaseModel):
    slug: str
    chapter_id: str | None
    chapter_number: int | None = None
    progress_percent: float
    updated_at: datetime


@router.get("/progress/{slug}", response_model=ProgressResponse)
def get_progress(
    slug: str,
    user: SessionUser = Depends(require_role("user")),
    service: ReadingService = Depends(get_reading_service),
) -> ProgressResponse:
    try:
        progress = service.get_progress(_uid(user), slug)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return ProgressResponse(**progress)


@router.put(
    "/progress/{slug}",
    response_model=ProgressResponse,
    dependencies=[Depends(require_csrf_token)],
)
def update_progress(
    slug: str,
    payload: ProgressUpdate,
    request: Request,
    user: SessionUser = Depends(require_role("user")),
    service: ReadingService = Depends(get_reading_service),
) -> ProgressResponse:
    require_public_rate_limit(request, "progress_write", user_id=_uid(user))
    try:
        progress = service.update_progress(
            _uid(user), slug, payload.chapter_id, payload.progress_percent
        )
    except ValueError as exc:
        detail = str(exc)
        status = 404 if "not found" in detail.lower() else 400
        raise HTTPException(status_code=status, detail=detail) from exc
    return ProgressResponse(**progress)


class HistoryRecordRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    slug: str
    chapter_id: str | None = None


class HistoryEntryResponse(BaseModel):
    id: int
    slug: str
    chapter_id: str | None
    chapter_number: int | None = None
    read_at: datetime


class HistoryListResponse(BaseModel):
    items: list[HistoryEntryResponse]
    next_cursor: str | None = None


@router.post(
    "/history",
    status_code=201,
    response_model=HistoryEntryResponse,
    dependencies=[Depends(require_csrf_token)],
)
def record_history(
    request: Request,
    payload: HistoryRecordRequest | None = Body(default=None),
    slug: str | None = Query(default=None),
    chapter_id: str | None = Query(default=None),
    user: SessionUser = Depends(require_role("user")),
    service: ReadingService = Depends(get_reading_service),
) -> HistoryEntryResponse:
    require_public_rate_limit(request, "history_record", user_id=_uid(user))
    effective_slug = payload.slug if payload else slug
    effective_chapter_id = payload.chapter_id if payload else chapter_id
    if effective_slug is None:
        raise HTTPException(status_code=400, detail="slug is required.")
    try:
        entry = service.record_history(_uid(user), effective_slug, effective_chapter_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return HistoryEntryResponse(**entry)


@router.get("/history", response_model=HistoryListResponse)
def list_history(
    limit: int = Query(default=50, ge=1, le=100),
    user: SessionUser = Depends(require_role("user")),
    service: ReadingService = Depends(get_reading_service),
) -> HistoryListResponse:
    items = service.list_history(_uid(user), limit=limit)
    return HistoryListResponse(items=[HistoryEntryResponse(**item) for item in items])


class ReviewCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    rating: int | None = Field(default=None, ge=1, le=5)
    body: str | None = Field(default=None, max_length=5000)


class ReviewResponse(BaseModel):
    slug: str
    rating: int | None
    body: str | None
    status: str
    updated_at: datetime


@router.put(
    "/reviews/{slug}",
    response_model=ReviewResponse,
    dependencies=[Depends(require_csrf_token)],
)
def put_review(
    slug: str,
    payload: ReviewCreate,
    request: Request,
    user: SessionUser = Depends(require_role("user")),
    service: ReviewService = Depends(get_review_service),
) -> ReviewResponse:
    require_public_rate_limit(request, "review_mutation", user_id=_uid(user))
    try:
        review = service.upsert_review(_uid(user), slug, payload.rating or 0, payload.body)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return ReviewResponse(**review)


@router.post(
    "/reviews/{slug}",
    status_code=201,
    response_model=ReviewResponse,
    dependencies=[Depends(require_csrf_token)],
)
def post_review(
    slug: str,
    payload: ReviewCreate,
    request: Request,
    user: SessionUser = Depends(require_role("user")),
    service: ReviewService = Depends(get_review_service),
) -> ReviewResponse:
    require_public_rate_limit(request, "review_mutation", user_id=_uid(user))
    try:
        review = service.upsert_review(_uid(user), slug, payload.rating or 0, payload.body)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return ReviewResponse(**review)


@router.delete(
    "/reviews/{slug}",
    status_code=204,
    dependencies=[Depends(require_csrf_token)],
)
def delete_review(
    slug: str,
    request: Request,
    user: SessionUser = Depends(require_role("user")),
    service: ReviewService = Depends(get_review_service),
) -> None:
    require_public_rate_limit(request, "review_mutation", user_id=_uid(user))
    try:
        service.delete_review(_uid(user), slug)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


# -- Requests -----------------------------------------------------------------


class RequestCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request_type: str
    source_url: str | None = None
    slug: str | None = None
    chapter_id: str | None = None
    details: str | None = None

    @model_validator(mode="after")
    def validate_type(self) -> RequestCreate:
        if self.request_type not in {"novel", "chapter"}:
            raise ValueError("request_type must be 'novel' or 'chapter'")
        if self.request_type == "novel" and self.source_url is None:
            raise ValueError("source_url is required for novel requests")
        if self.request_type == "chapter" and self.slug is None:
            raise ValueError("slug is required for chapter requests")
        return self


class RequestResponse(BaseModel):
    id: int
    request_type: str
    status: str
    source_url: str | None = None
    slug: str | None = None
    chapter_id: str | None = None
    created_at: datetime
    updated_at: datetime
    rejection_reason: str | None = None
    approved_novel_id: int | None = None
    approved_slug: str | None = None


class RequestListResponse(BaseModel):
    items: list[RequestResponse]
    next_cursor: str | None = None


@router.post(
    "/requests",
    status_code=201,
    response_model=RequestResponse,
    dependencies=[Depends(require_csrf_token)],
)
def create_request(
    payload: RequestCreate,
    request: Request,
    user: SessionUser = Depends(require_role("user")),
    service: NovelRequestService = Depends(get_novel_request_service),
) -> RequestResponse:
    require_public_rate_limit(request, "request_create", user_id=_uid(user))
    try:
        result = service.create_user_request(
            _uid(user), payload.request_type,
            source_url=payload.source_url,
            slug=payload.slug,
            chapter_id=payload.chapter_id,
        )
    except ValueError as exc:
        detail = str(exc)
        if "not found" in detail.lower():
            raise HTTPException(status_code=404, detail=detail) from exc
        raise HTTPException(status_code=400, detail=detail) from exc
    return RequestResponse(**result)


@router.get("/requests", response_model=RequestListResponse)
def list_requests(
    limit: int = Query(default=50, ge=1, le=100),
    user: SessionUser = Depends(require_role("user")),
    service: NovelRequestService = Depends(get_novel_request_service),
) -> RequestListResponse:
    items = service.list_user_requests(_uid(user), limit=limit)
    return RequestListResponse(items=[RequestResponse(**item) for item in items])
