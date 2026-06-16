"""Public catalog router — guest-accessible, no auth required.

Provides the public reader surface (architecture.md §20):
- GET /api/public/catalog        — paginated novel list with search/filter
- GET /api/public/novels/{slug}  — novel detail
- GET /api/public/novels/{slug}/chapters — chapter list
- GET /api/public/novels/{slug}/chapters/{chapter_id} — translated chapter reader

These endpoints are intentionally open to guests. They must never expose:
- Admin/operational data (job logs, provider keys, usage, settings)
- Raw filesystem paths
- Unpublished chapters

Architecture note: In v1 the catalog is read from file-backed StorageService
(parallel-run). Once DB is fully populated, these will query the Novel/Chapter
DB models directly. The API contract does not change.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from novelai.api.routers.dependencies import (
    get_storage,
    metadata_chapters,
    reader_title,
)
from novelai.storage.service import StorageService

router = APIRouter(prefix="/api/public", tags=["public"])
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

VALID_SORT_FIELDS = {"added_at", "title", "chapter_count"}
VALID_ORDER_VALUES = {"asc", "desc"}
DEFAULT_SORT_BY = "added_at"
DEFAULT_ORDER = "desc"


# ---------------------------------------------------------------------------
# Response models
# ---------------------------------------------------------------------------

class PublicNovelSummary(BaseModel):
    novel_id: str
    slug: str
    title: str | None = None
    author: str | None = None
    language: str | None = None
    status: str | None = None
    chapter_count: int = 0
    translated_count: int = 0
    added_at: str | None = None


class PublicChapterSummary(BaseModel):
    chapter_id: str
    title: str | None = None
    chapter_number: int | None = None
    translated: bool = False


class PublicCatalogResponse(BaseModel):
    novels: list[PublicNovelSummary]
    total: int
    page: int
    page_size: int


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _optional_str(value: Any) -> str | None:
    return value.strip() if isinstance(value, str) and value.strip() else None


def _novel_matches_search(meta: dict[str, Any], query: str) -> bool:
    """Simple case-insensitive substring search across title and author."""
    q = query.lower()
    title = (_optional_str(meta.get("translated_title")) or _optional_str(meta.get("title")) or "").lower()
    author = (_optional_str(meta.get("translated_author")) or _optional_str(meta.get("author")) or "").lower()
    return q in title or q in author


def _novel_added_at(meta: dict[str, Any]) -> str | None:
    """Return the addition date from metadata, preferring scraped_at over updated_at."""
    for key in ("scraped_at", "updated_at"):
        value = meta.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _novel_summary(novel_id: str, meta: dict[str, Any], storage: StorageService) -> PublicNovelSummary:
    translated_count = storage.count_translated_chapters(novel_id)
    chapter_count = len(meta.get("chapters", [])) or max(
        storage.count_stored_chapters(novel_id), translated_count
    )
    return PublicNovelSummary(
        novel_id=novel_id,
        slug=novel_id,
        title=_optional_str(meta.get("translated_title")) or _optional_str(meta.get("title")) or novel_id,
        author=_optional_str(meta.get("translated_author")) or _optional_str(meta.get("author")),
        language=_optional_str(meta.get("language")),
        status=_optional_str(meta.get("status")),
        chapter_count=chapter_count,
        translated_count=translated_count,
        added_at=_novel_added_at(meta),
    )


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.get("/catalog", response_model=PublicCatalogResponse)
async def catalog(
    q: str | None = Query(default=None, description="Search title or author"),
    status: str | None = Query(default=None, description="Filter by status"),
    language: str | None = Query(default=None, description="Filter by language (deprecated for public Browse)"),
    sort_by: str | None = Query(default=None, description="Sort field: added_at, title, chapter_count"),
    order: str | None = Query(default=None, description="Sort order: asc or desc"),
    min_chapters: int | None = Query(default=None, ge=0, description="Minimum chapter count"),
    max_chapters: int | None = Query(default=None, ge=0, description="Maximum chapter count"),
    page: int = Query(default=1, ge=1, description="Page number (1-indexed)"),
    page_size: int = Query(default=24, ge=1, le=100, description="Items per page"),
    storage: StorageService = Depends(get_storage),
) -> PublicCatalogResponse:
    """Paginated public novel catalog with optional search, filter, and sort."""
    # Normalize sort parameters with safe fallbacks
    effective_sort_by = sort_by if sort_by and sort_by in VALID_SORT_FIELDS else DEFAULT_SORT_BY
    effective_order = order if order and order in VALID_ORDER_VALUES else DEFAULT_ORDER
    reverse = effective_order == "desc"

    novels: list[PublicNovelSummary] = []
    for novel_id in storage.list_novels():
        meta = storage.load_metadata(novel_id) or {}
        if q and not _novel_matches_search(meta, q):
            continue
        if status and _optional_str(meta.get("status")) != status:
            continue
        if language and _optional_str(meta.get("language")) != language:
            continue
        summary = _novel_summary(novel_id, meta, storage)
        # Filter by chapter count range
        if min_chapters is not None and summary.chapter_count < min_chapters:
            continue
        if max_chapters is not None and summary.chapter_count > max_chapters:
            continue
        novels.append(summary)

    # Sort the full filtered catalog before pagination
    def _sort_key(novel: PublicNovelSummary) -> str | int:
        """Return a sort value for the current sort field."""
        if effective_sort_by == "title":
            return (novel.title or "").lower()
        if effective_sort_by == "chapter_count":
            return novel.chapter_count
        # added_at (default) — use sentinel to push missing dates to end
        if novel.added_at:
            return novel.added_at
        # desc: "" sorts before all dates, so reversed it ends up last
        # asc:  max sentinel sorts after all dates, so it ends up last
        return "" if reverse else "9999-12-31T23:59:59"

    novels.sort(key=_sort_key, reverse=reverse)

    total = len(novels)
    start = (page - 1) * page_size
    return PublicCatalogResponse(
        novels=novels[start : start + page_size],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/novels/{slug}", response_model=PublicNovelSummary)
async def get_novel(
    slug: str,
    storage: StorageService = Depends(get_storage),
) -> PublicNovelSummary:
    """Public novel detail."""
    meta = storage.load_metadata(slug)
    if meta is None:
        raise HTTPException(status_code=404, detail="Novel not found.")
    return _novel_summary(slug, meta, storage)


@router.get("/novels/{slug}/chapters", response_model=list[PublicChapterSummary])
async def list_chapters(
    slug: str,
    storage: StorageService = Depends(get_storage),
) -> list[PublicChapterSummary]:
    """Public chapter list for a novel."""
    meta = storage.load_metadata(slug)
    if meta is None:
        raise HTTPException(status_code=404, detail="Novel not found.")
    translated_ids = set(storage.list_translated_chapters(slug))
    result = []
    for idx, ch in enumerate(metadata_chapters(meta)):
        chapter_id = str(ch.get("id", ""))
        result.append(PublicChapterSummary(
            chapter_id=chapter_id,
            title=_optional_str(ch.get("translated_title")) or _optional_str(ch.get("title")),
            chapter_number=ch.get("num") or (idx + 1),
            translated=chapter_id in translated_ids,
        ))
    return result


@router.get("/novels/{slug}/chapters/{chapter_id}")
async def get_chapter(
    slug: str,
    chapter_id: str,
    storage: StorageService = Depends(get_storage),
) -> dict[str, Any]:
    """Public translated chapter reader."""
    meta = storage.load_metadata(slug)
    if meta is None:
        raise HTTPException(status_code=404, detail="Novel not found.")

    chapters = metadata_chapters(meta)
    chapter_ids = [str(ch.get("id", "")) for ch in chapters]
    if chapter_id not in chapter_ids:
        raise HTTPException(status_code=404, detail="Chapter not found.")

    translated = storage.load_translated_chapter(slug, chapter_id)
    if translated is None or not isinstance(translated.get("text"), str):
        raise HTTPException(status_code=404, detail="Translated chapter not available.")

    index = chapter_ids.index(chapter_id)
    chapter = chapters[index]
    return {
        "novel_id": slug,
        "chapter_id": chapter_id,
        "novel_title": reader_title(meta),
        "title": _optional_str(ch.get("translated_title") if (ch := chapter) else None) or _optional_str(chapter.get("title")),
        "text": translated.get("text"),
        "previous_chapter_id": chapter_ids[index - 1] if index > 0 else None,
        "next_chapter_id": chapter_ids[index + 1] if index + 1 < len(chapter_ids) else None,
    }
