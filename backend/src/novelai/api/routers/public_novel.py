"""Public novel detail and chapter-list endpoints.

Novel detail, chapter list, and novel-specific helpers.
Catalog browse and genres are in ``public_catalog.py``.
Chapter reader and tags search are in ``public_chapter.py``.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.orm import Session

from novelai.api.auth.session import SessionUser, get_current_user
from novelai.api.routers.dependencies import (
    get_db_session,
    get_public_catalog_service,
    metadata_chapters,
)
from novelai.api.routers.public_contracts import (
    PublicChapterSummary,
    PublicNovelSummary,
    _optional_str,
)
from novelai.services.analytics_service import record_server_event
from novelai.services.public_catalog_service import PublicCatalogService
from novelai.services.takedown_service import TakedownService

router = APIRouter(prefix="/api/public", tags=["public"])


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.get("/novels/{slug}", response_model=PublicNovelSummary)
async def get_novel(
    slug: str,
    include_adult: bool = Query(default=False, description="Include adult/R18 taxonomy terms"),
    service: PublicCatalogService = Depends(get_public_catalog_service),
    user: SessionUser = Depends(get_current_user),
    db: Session = Depends(get_db_session),
    response: Response = None,  # type: ignore[assignment]
) -> dict[str, Any]:
    """Public novel detail."""
    resolved = service._resolve_public_novel(slug)
    if resolved is None:
        raise HTTPException(status_code=404, detail="Novel not found.")
    # HTTP 451 — Unavailable For Legal Reasons
    if isinstance(db, Session) and TakedownService(db).has_active_takedown_for_slug(slug):
        raise HTTPException(
            status_code=451,
            detail="Unavailable For Legal Reasons",
            headers={"Cache-Control": "no-store"},
        )
    novel_id, meta, _public_slug = resolved
    genres, tags, _ = service._load_taxonomy_for_novel(novel_id, include_adult=include_adult)
    # Best-effort analytics: record public_novel.view
    record_server_event("public_novel.view", user_id=user.user_id, novel_id=novel_id)
    if response is not None:
        response.headers["Cache-Control"] = "public, max-age=60"
    return service._novel_summary(novel_id, meta, genres=genres, tags=tags)


@router.get("/novels/{slug}/chapters", response_model=list[PublicChapterSummary])
async def list_chapters(
    slug: str,
    response: Response,
    service: PublicCatalogService = Depends(get_public_catalog_service),
    db: Session = Depends(get_db_session),
) -> list[PublicChapterSummary]:
    """Public chapter list for a novel."""
    resolved = service._resolve_public_novel(slug)
    if resolved is None:
        raise HTTPException(status_code=404, detail="Novel not found.")
    if TakedownService(db).has_active_takedown_for_slug(slug):
        raise HTTPException(
            status_code=451,
            detail="Unavailable For Legal Reasons",
            headers={"Cache-Control": "no-store"},
        )
    novel_id, meta, _public_slug = resolved
    translated_ids = set(service.storage.list_translated_chapters(novel_id))
    result = []
    for idx, ch in enumerate(metadata_chapters(meta)):
        chapter_id = str(ch.get("id", ""))
        is_translated = chapter_id in translated_ids
        result.append(
            PublicChapterSummary(
                chapter_id=chapter_id,
                title=_optional_str(ch.get("translated_title")) or _optional_str(ch.get("title")),
                chapter_number=ch.get("num") or (idx + 1),
                translated=is_translated,
                availability_status="available" if is_translated else "not_translated",
                part=_optional_str(ch.get("part")) or _optional_str(ch.get("volume")),
            )
        )
    response.headers["Cache-Control"] = "public, max-age=60"
    return result
