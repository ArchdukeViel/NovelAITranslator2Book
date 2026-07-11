"""Public novel detail + chapter list endpoints — extracted from public.py.

Novel detail, chapter list, and novel-specific helpers.
Catalog browse and genres are in ``public_catalog.py``.
Chapter reader and tags search are in ``public_chapter.py``.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from novelai.api.routers.dependencies import (
    get_db_session,
    get_storage,
    metadata_chapters,
)
from novelai.api.routers.public import (
    PublicChapterSummary,
    PublicNovelSummary,
    _load_taxonomy_for_novel,
    _novel_summary,
    _optional_str,
    _resolve_public_novel,
)
from novelai.storage.service import StorageService

router = APIRouter(prefix="/api/public", tags=["public"])
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.get("/novels/{slug}", response_model=PublicNovelSummary)
async def get_novel(
    slug: str,
    include_adult: bool = Query(default=False, description="Include adult/R18 taxonomy terms"),
    storage: StorageService = Depends(get_storage),
    db: Session = Depends(get_db_session),
) -> PublicNovelSummary:
    """Public novel detail."""
    resolved = _resolve_public_novel(slug, storage)
    if resolved is None:
        raise HTTPException(status_code=404, detail="Novel not found.")
    novel_id, meta, _public_slug = resolved
    genres, tags, _ = _load_taxonomy_for_novel(db, novel_id, include_adult=include_adult)
    return _novel_summary(novel_id, meta, storage, genres=genres, tags=tags)


@router.get("/novels/{slug}/chapters", response_model=list[PublicChapterSummary])
async def list_chapters(
    slug: str,
    storage: StorageService = Depends(get_storage),
) -> list[PublicChapterSummary]:
    """Public chapter list for a novel."""
    resolved = _resolve_public_novel(slug, storage)
    if resolved is None:
        raise HTTPException(status_code=404, detail="Novel not found.")
    novel_id, meta, _public_slug = resolved
    translated_ids = set(storage.list_translated_chapters(novel_id))
    result = []
    for idx, ch in enumerate(metadata_chapters(meta)):
        chapter_id = str(ch.get("id", ""))
        is_translated = chapter_id in translated_ids
        result.append(PublicChapterSummary(
            chapter_id=chapter_id,
            title=_optional_str(ch.get("translated_title")) or _optional_str(ch.get("title")),
            chapter_number=ch.get("num") or (idx + 1),
            translated=is_translated,
            availability_status="available" if is_translated else "not_translated",
        ))
    return result
