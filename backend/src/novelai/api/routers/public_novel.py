"""Public novel detail + chapter list endpoints — extracted from public.py.

Novel detail, chapter list, and novel-specific helpers.
Catalog browse and genres are in ``public_catalog.py``.
Chapter reader and tags search are in ``public_chapter.py``.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query

from novelai.api.routers.dependencies import (
    get_public_catalog_service,
    metadata_chapters,
)
from novelai.api.routers.public import (
    PublicChapterSummary,
    PublicNovelSummary,
    _optional_str,
)
from novelai.services.public_catalog_service import PublicCatalogService

router = APIRouter(prefix="/api/public", tags=["public"])
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.get("/novels/{slug}", response_model=PublicNovelSummary)
async def get_novel(
    slug: str,
    include_adult: bool = Query(default=False, description="Include adult/R18 taxonomy terms"),
    service: PublicCatalogService = Depends(get_public_catalog_service),
) -> dict[str, Any]:
    """Public novel detail."""
    resolved = service._resolve_public_novel(slug)
    if resolved is None:
        raise HTTPException(status_code=404, detail="Novel not found.")
    novel_id, meta, _public_slug = resolved
    genres, tags, _ = service._load_taxonomy_for_novel(novel_id, include_adult=include_adult)
    return service._novel_summary(novel_id, meta, genres=genres, tags=tags)


@router.get("/novels/{slug}/chapters", response_model=list[PublicChapterSummary])
async def list_chapters(
    slug: str,
    service: PublicCatalogService = Depends(get_public_catalog_service),
) -> list[PublicChapterSummary]:
    """Public chapter list for a novel."""
    resolved = service._resolve_public_novel(slug)
    if resolved is None:
        raise HTTPException(status_code=404, detail="Novel not found.")
    novel_id, meta, _public_slug = resolved
    translated_ids = set(service.storage.list_translated_chapters(novel_id))
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
            part=_optional_str(ch.get("part")) or _optional_str(ch.get("volume")),
        ))
    return result
