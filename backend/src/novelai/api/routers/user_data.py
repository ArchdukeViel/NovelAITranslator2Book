"""User data router — authenticated user features.

Requires minimum role "user" (architecture.md §20).
All endpoints use the DB session; ownership is enforced server-side.

Endpoints:
  GET/POST/DELETE /api/user/library/         — saved novels
  GET/PUT         /api/user/progress/{slug}  — reading progress
  GET/POST        /api/user/history          — reading history
  GET/POST        /api/user/reviews/{slug}   — ratings/reviews
  GET/POST        /api/user/requests         — novel/chapter requests
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from novelai.api.auth.roles import require_role
from novelai.api.auth.session import SessionUser
from novelai.api.routers.dependencies import get_db_session
from novelai.db.models.users import (
    LibraryItem, NovelRequest, ReadingHistory, ReadingProgress, Review,
)
from novelai.db.models.novel import Novel

router = APIRouter(prefix="/api/user", tags=["user"])
logger = logging.getLogger(__name__)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _get_novel_db_id(slug: str, session: Session) -> int:
    novel = session.query(Novel).filter_by(slug=slug).one_or_none()
    if novel is None:
        raise HTTPException(status_code=404, detail="Novel not found.")
    return novel.id


# ---------------------------------------------------------------------------
# Library
# ---------------------------------------------------------------------------

class LibraryItemResponse(BaseModel):
    slug: str
    status: str
    added_at: datetime


@router.get("/library", response_model=list[LibraryItemResponse])
def list_library(
    user: SessionUser = Depends(require_role("user")),
    session: Session = Depends(get_db_session),
) -> list[LibraryItemResponse]:
    items = session.query(LibraryItem).filter_by(user_id=user.user_id).all()
    result = []
    for item in items:
        novel = session.query(Novel).filter_by(id=item.novel_id).one_or_none()
        slug = novel.slug if novel else str(item.novel_id)
        result.append(LibraryItemResponse(slug=slug, status=item.status, added_at=item.added_at))
    return result


@router.post("/library/{slug}", status_code=201)
def add_to_library(
    slug: str,
    user: SessionUser = Depends(require_role("user")),
    session: Session = Depends(get_db_session),
) -> dict[str, Any]:
    novel_id = _get_novel_db_id(slug, session)
    existing = session.query(LibraryItem).filter_by(
        user_id=user.user_id, novel_id=novel_id
    ).one_or_none()
    if existing:
        return {"slug": slug, "status": existing.status, "message": "already_in_library"}
    item = LibraryItem(user_id=user.user_id, novel_id=novel_id)
    session.add(item)
    return {"slug": slug, "status": "reading", "message": "added"}


@router.delete("/library/{slug}", status_code=204)
def remove_from_library(
    slug: str,
    user: SessionUser = Depends(require_role("user")),
    session: Session = Depends(get_db_session),
) -> None:
    novel_id = _get_novel_db_id(slug, session)
    item = session.query(LibraryItem).filter_by(
        user_id=user.user_id, novel_id=novel_id
    ).one_or_none()
    if item:
        session.delete(item)


# ---------------------------------------------------------------------------
# Reading progress
# ---------------------------------------------------------------------------

class ProgressUpdate(BaseModel):
    chapter_id: str | None = None
    progress_percent: float = 0.0


@router.get("/progress/{slug}")
def get_progress(
    slug: str,
    user: SessionUser = Depends(require_role("user")),
    session: Session = Depends(get_db_session),
) -> dict[str, Any]:
    novel_id = _get_novel_db_id(slug, session)
    rp = session.query(ReadingProgress).filter_by(
        user_id=user.user_id, novel_id=novel_id
    ).one_or_none()
    if rp is None:
        return {"slug": slug, "progress_percent": 0.0, "chapter_id": None}
    return {"slug": slug, "progress_percent": rp.progress_percent, "chapter_id": rp.chapter_id}


@router.put("/progress/{slug}", status_code=200)
def update_progress(
    slug: str,
    payload: ProgressUpdate,
    user: SessionUser = Depends(require_role("user")),
    session: Session = Depends(get_db_session),
) -> dict[str, Any]:
    novel_id = _get_novel_db_id(slug, session)
    rp = session.query(ReadingProgress).filter_by(
        user_id=user.user_id, novel_id=novel_id
    ).one_or_none()
    if rp is None:
        rp = ReadingProgress(user_id=user.user_id, novel_id=novel_id)
        session.add(rp)
    rp.progress_percent = payload.progress_percent
    return {"slug": slug, "progress_percent": rp.progress_percent}


# ---------------------------------------------------------------------------
# Reading history
# ---------------------------------------------------------------------------

@router.post("/history", status_code=201)
def record_history(
    slug: str,
    chapter_id: str | None = None,
    user: SessionUser = Depends(require_role("user")),
    session: Session = Depends(get_db_session),
) -> dict[str, Any]:
    novel_id = _get_novel_db_id(slug, session)
    entry = ReadingHistory(user_id=user.user_id, novel_id=novel_id)
    session.add(entry)
    return {"slug": slug, "recorded": True}


@router.get("/history")
def list_history(
    user: SessionUser = Depends(require_role("user")),
    session: Session = Depends(get_db_session),
) -> list[dict[str, Any]]:
    entries = (
        session.query(ReadingHistory)
        .filter_by(user_id=user.user_id)
        .order_by(ReadingHistory.read_at.desc())
        .limit(100)
        .all()
    )
    result = []
    for e in entries:
        novel = session.query(Novel).filter_by(id=e.novel_id).one_or_none()
        result.append({"slug": novel.slug if novel else str(e.novel_id), "read_at": e.read_at})
    return result


# ---------------------------------------------------------------------------
# Reviews / ratings
# ---------------------------------------------------------------------------

class ReviewCreate(BaseModel):
    rating: int | None = None
    body: str | None = None


@router.post("/reviews/{slug}", status_code=201)
def post_review(
    slug: str,
    payload: ReviewCreate,
    user: SessionUser = Depends(require_role("user")),
    session: Session = Depends(get_db_session),
) -> dict[str, Any]:
    novel_id = _get_novel_db_id(slug, session)
    review = Review(
        user_id=user.user_id,
        novel_id=novel_id,
        rating=payload.rating,
        body=payload.body,
    )
    session.add(review)
    return {"slug": slug, "rating": payload.rating, "message": "review_submitted"}


# ---------------------------------------------------------------------------
# Novel/chapter requests
# ---------------------------------------------------------------------------

class RequestCreate(BaseModel):
    request_type: str
    source_url: str | None = None
    novel_id: int | None = None


@router.post("/requests", status_code=201)
def create_request(
    payload: RequestCreate,
    user: SessionUser = Depends(require_role("user")),
    session: Session = Depends(get_db_session),
) -> dict[str, Any]:
    req = NovelRequest(
        user_id=user.user_id,
        request_type=payload.request_type,
        novel_id=payload.novel_id,
        source_url=payload.source_url,
        status="pending",
    )
    session.add(req)
    return {"request_type": payload.request_type, "status": "pending", "message": "request_submitted"}


@router.get("/requests")
def list_requests(
    user: SessionUser = Depends(require_role("user")),
    session: Session = Depends(get_db_session),
) -> list[dict[str, Any]]:
    reqs = session.query(NovelRequest).filter_by(user_id=user.user_id).all()
    return [
        {"id": r.id, "request_type": r.request_type, "status": r.status, "source_url": r.source_url}
        for r in reqs
    ]
