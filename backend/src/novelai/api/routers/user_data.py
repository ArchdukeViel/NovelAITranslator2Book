"""User data router: authenticated public user features.

All endpoints require role ``user`` or higher and derive ownership from the
server-side session. Clients never submit or choose ``user_id``.
"""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Body, Depends, HTTPException, Query, Request
from pydantic import BaseModel, ConfigDict, Field, HttpUrl, model_validator
from sqlalchemy.orm import Session

from novelai.api.auth.security import require_csrf_token, require_public_rate_limit
from novelai.api.auth.roles import require_role
from novelai.api.auth.session import SessionUser
from novelai.api.routers.dependencies import get_db_session
from novelai.db.models.chapter import Chapter
from novelai.db.models.novel import Novel
from novelai.db.models.users import (
    LibraryItem,
    NovelRequest,
    ReadingHistory,
    ReadingProgress,
    Review,
)

router = APIRouter(prefix="/api/user", tags=["user"])


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _get_novel(slug: str, session: Session) -> Novel:
    novel = session.query(Novel).filter_by(slug=slug).one_or_none()
    if novel is None:
        raise HTTPException(status_code=404, detail="Novel not found.")
    return novel


def _get_chapter_for_novel(chapter_id: str | None, novel_id: int, session: Session) -> int | None:
    if chapter_id is None:
        return None
    try:
        chapter_db_id = int(chapter_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="Chapter not found.") from exc
    chapter = session.query(Chapter).filter_by(id=chapter_db_id, novel_id=novel_id).one_or_none()
    if chapter is None:
        raise HTTPException(status_code=404, detail="Chapter not found.")
    return chapter.id


def _novel_slug(novel_id: int | None, session: Session) -> str | None:
    if novel_id is None:
        return None
    novel = session.query(Novel).filter_by(id=novel_id).one_or_none()
    return novel.slug if novel else None


class LibraryItemResponse(BaseModel):
    slug: str
    status: str
    added_at: datetime


def _library_response(item: LibraryItem, slug: str) -> LibraryItemResponse:
    return LibraryItemResponse(slug=slug, status=item.status, added_at=item.added_at)


@router.get("/library", response_model=list[LibraryItemResponse])
def list_library(
    user: SessionUser = Depends(require_role("user")),
    session: Session = Depends(get_db_session),
) -> list[LibraryItemResponse]:
    items = session.query(LibraryItem).filter_by(user_id=user.user_id).all()
    result: list[LibraryItemResponse] = []
    for item in items:
        result.append(_library_response(item, _novel_slug(item.novel_id, session) or str(item.novel_id)))
    return result


@router.get("/library/{slug}", response_model=LibraryItemResponse)
def get_library_item(
    slug: str,
    user: SessionUser = Depends(require_role("user")),
    session: Session = Depends(get_db_session),
) -> LibraryItemResponse:
    novel = _get_novel(slug, session)
    item = session.query(LibraryItem).filter_by(user_id=user.user_id, novel_id=novel.id).one_or_none()
    if item is None:
        raise HTTPException(status_code=404, detail="Library item not found.")
    return _library_response(item, slug)


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
    session: Session = Depends(get_db_session),
) -> LibraryItemResponse:
    require_public_rate_limit(request, "library_mutation", user_id=user.user_id)
    novel = _get_novel(slug, session)
    existing = session.query(LibraryItem).filter_by(user_id=user.user_id, novel_id=novel.id).one_or_none()
    if existing:
        return _library_response(existing, slug)
    item = LibraryItem(user_id=user.user_id, novel_id=novel.id)
    session.add(item)
    session.flush()
    return _library_response(item, slug)


@router.delete(
    "/library/{slug}",
    status_code=204,
    dependencies=[Depends(require_csrf_token)],
)
def remove_from_library(
    slug: str,
    request: Request,
    user: SessionUser = Depends(require_role("user")),
    session: Session = Depends(get_db_session),
) -> None:
    require_public_rate_limit(request, "library_mutation", user_id=user.user_id)
    novel = _get_novel(slug, session)
    item = session.query(LibraryItem).filter_by(user_id=user.user_id, novel_id=novel.id).one_or_none()
    if item:
        session.delete(item)


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
    session: Session = Depends(get_db_session),
) -> ProgressResponse:
    novel = _get_novel(slug, session)
    rp = session.query(ReadingProgress).filter_by(user_id=user.user_id, novel_id=novel.id).one_or_none()
    if rp is None:
        return ProgressResponse(slug=slug, progress_percent=0.0, chapter_id=None, updated_at=_utcnow())
    chapter_number: int | None = None
    if rp.chapter_id is not None:
        ch = session.query(Chapter.chapter_number).filter_by(id=rp.chapter_id).one_or_none()
        if ch:
            chapter_number = ch[0]
    return ProgressResponse(
        slug=slug,
        progress_percent=rp.progress_percent,
        chapter_id=str(rp.chapter_id) if rp.chapter_id is not None else None,
        chapter_number=chapter_number,
        updated_at=rp.updated_at,
    )


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
    session: Session = Depends(get_db_session),
) -> ProgressResponse:
    require_public_rate_limit(request, "progress_write", user_id=user.user_id)
    novel = _get_novel(slug, session)
    chapter_db_id = _get_chapter_for_novel(payload.chapter_id, novel.id, session)
    rp = session.query(ReadingProgress).filter_by(user_id=user.user_id, novel_id=novel.id).one_or_none()
    if rp is None:
        rp = ReadingProgress(user_id=user.user_id, novel_id=novel.id)
        session.add(rp)
    rp.progress_percent = payload.progress_percent
    rp.chapter_id = chapter_db_id
    rp.updated_at = _utcnow()
    session.flush()
    chapter_number: int | None = None
    if rp.chapter_id is not None:
        ch = session.query(Chapter.chapter_number).filter_by(id=rp.chapter_id).one_or_none()
        if ch:
            chapter_number = ch[0]
    return ProgressResponse(
        slug=slug,
        progress_percent=rp.progress_percent,
        chapter_id=str(rp.chapter_id) if rp.chapter_id is not None else None,
        chapter_number=chapter_number,
        updated_at=rp.updated_at,
    )


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
    session: Session = Depends(get_db_session),
) -> HistoryEntryResponse:
    require_public_rate_limit(request, "history_record", user_id=user.user_id)
    effective_slug = payload.slug if payload else slug
    effective_chapter_id = payload.chapter_id if payload else chapter_id
    if effective_slug is None:
        raise HTTPException(status_code=400, detail="slug is required.")
    novel = _get_novel(effective_slug, session)
    chapter_db_id = _get_chapter_for_novel(effective_chapter_id, novel.id, session)
    entry = ReadingHistory(user_id=user.user_id, novel_id=novel.id, chapter_id=chapter_db_id)
    session.add(entry)
    session.flush()
    chapter_number: int | None = None
    if entry.chapter_id is not None:
        ch = session.query(Chapter.chapter_number).filter_by(id=entry.chapter_id).one_or_none()
        if ch:
            chapter_number = ch[0]
    return HistoryEntryResponse(
        id=entry.id,
        slug=effective_slug,
        chapter_id=str(entry.chapter_id) if entry.chapter_id is not None else None,
        chapter_number=chapter_number,
        read_at=entry.read_at,
    )


@router.get("/history", response_model=HistoryListResponse)
def list_history(
    limit: int = Query(default=50, ge=1, le=100),
    user: SessionUser = Depends(require_role("user")),
    session: Session = Depends(get_db_session),
) -> HistoryListResponse:
    results = (
        session.query(ReadingHistory, Chapter.chapter_number)
        .outerjoin(Chapter, ReadingHistory.chapter_id == Chapter.id)
        .filter(ReadingHistory.user_id == user.user_id)
        .order_by(ReadingHistory.read_at.desc())
        .limit(limit)
        .all()
    )
    return HistoryListResponse(
        items=[
            HistoryEntryResponse(
                id=entry.id,
                slug=_novel_slug(entry.novel_id, session) or str(entry.novel_id),
                chapter_id=str(entry.chapter_id) if entry.chapter_id is not None else None,
                chapter_number=chapter_number,
                read_at=entry.read_at,
            )
            for entry, chapter_number in results
        ]
    )


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


def _upsert_review(slug: str, payload: ReviewCreate, user: SessionUser, session: Session) -> ReviewResponse:
    novel = _get_novel(slug, session)
    review = session.query(Review).filter_by(user_id=user.user_id, novel_id=novel.id).one_or_none()
    if review is None:
        review = Review(user_id=user.user_id, novel_id=novel.id)
        session.add(review)
    review.rating = payload.rating
    review.body = payload.body
    session.flush()
    return ReviewResponse(
        slug=slug,
        rating=review.rating,
        body=review.body,
        status="pending",
        updated_at=review.created_at,
    )


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
    session: Session = Depends(get_db_session),
) -> ReviewResponse:
    require_public_rate_limit(request, "review_mutation", user_id=user.user_id)
    return _upsert_review(slug, payload, user, session)


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
    session: Session = Depends(get_db_session),
) -> ReviewResponse:
    require_public_rate_limit(request, "review_mutation", user_id=user.user_id)
    return _upsert_review(slug, payload, user, session)


@router.delete(
    "/reviews/{slug}",
    status_code=204,
    dependencies=[Depends(require_csrf_token)],
)
def delete_review(
    slug: str,
    request: Request,
    user: SessionUser = Depends(require_role("user")),
    session: Session = Depends(get_db_session),
) -> None:
    require_public_rate_limit(request, "review_mutation", user_id=user.user_id)
    novel = _get_novel(slug, session)
    review = session.query(Review).filter_by(user_id=user.user_id, novel_id=novel.id).one_or_none()
    if review is not None:
        session.delete(review)


class RequestCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request_type: str
    source_url: HttpUrl | None = None
    slug: str | None = None
    chapter_id: str | None = None
    details: str | None = Field(default=None, max_length=2000)

    @model_validator(mode="after")
    def validate_request_type(self) -> "RequestCreate":
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
    source_url: str | None
    slug: str | None
    chapter_id: str | None
    created_at: datetime


class RequestListResponse(BaseModel):
    items: list[RequestResponse]
    next_cursor: str | None = None


def _request_response(req: NovelRequest, session: Session) -> RequestResponse:
    return RequestResponse(
        id=req.id,
        request_type=req.request_type,
        status=req.status,
        source_url=req.source_url,
        slug=_novel_slug(req.novel_id, session),
        chapter_id=None,
        created_at=req.created_at,
    )


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
    session: Session = Depends(get_db_session),
) -> RequestResponse:
    require_public_rate_limit(request, "request_create", user_id=user.user_id)
    novel_id = None
    if payload.slug is not None:
        novel = _get_novel(payload.slug, session)
        novel_id = novel.id
        _get_chapter_for_novel(payload.chapter_id, novel_id, session)
    source_url = str(payload.source_url) if payload.source_url is not None else None
    existing = session.query(NovelRequest).filter_by(
        user_id=user.user_id,
        request_type=payload.request_type,
        novel_id=novel_id,
        source_url=source_url,
        status="pending",
    ).one_or_none()
    if existing is not None:
        return _request_response(existing, session)
    req = NovelRequest(
        user_id=user.user_id,
        request_type=payload.request_type,
        novel_id=novel_id,
        source_url=source_url,
        status="pending",
    )
    session.add(req)
    session.flush()
    return _request_response(req, session)


@router.get("/requests", response_model=RequestListResponse)
def list_requests(
    limit: int = Query(default=50, ge=1, le=100),
    user: SessionUser = Depends(require_role("user")),
    session: Session = Depends(get_db_session),
) -> RequestListResponse:
    reqs = (
        session.query(NovelRequest)
        .filter_by(user_id=user.user_id)
        .order_by(NovelRequest.created_at.desc())
        .limit(limit)
        .all()
    )
    return RequestListResponse(items=[_request_response(req, session) for req in reqs])
