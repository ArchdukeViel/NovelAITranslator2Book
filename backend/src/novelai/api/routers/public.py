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
from sqlalchemy.orm import Session

from novelai.api.routers.dependencies import (
    get_db_session,
    get_storage,
    metadata_chapters,
    reader_title,
)
from novelai.db.models.genre import Genre
from novelai.db.models.novel import Novel
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
    genres: list[str] = []
    tags: list[str] = []


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


class PublicGenreResponse(BaseModel):
    slug: str
    name_ja: str
    name_en: str | None = None
    is_adult: bool = False


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _optional_str(value: Any) -> str | None:
    return value.strip() if isinstance(value, str) and value.strip() else None


def _parse_csv_filter(value: str | None) -> list[str]:
    """Parse comma-separated filter value, trim whitespace, drop empties."""
    if not value:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


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


def _novel_summary(
    novel_id: str,
    meta: dict[str, Any],
    storage: StorageService,
    *,
    genres: list[str] | None = None,
    tags: list[str] | None = None,
) -> PublicNovelSummary:
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
        genres=genres or [],
        tags=tags or [],
    )


def _load_taxonomy_for_novel(session: Session, slug: str) -> tuple[list[str], list[str]]:
    """Load assigned genres and tags for a novel from the DB.

    Returns (genre_slugs, tag_names) ordered stably.
    - genres: by Genre.display_order then Genre.slug
    - tags: alphabetical by Tag.name
    """
    novel = session.query(Novel).filter_by(slug=slug).one_or_none()
    if novel is None:
        return [], []

    genre_slugs = [
        g.slug
        for g in novel.genres
        if g.is_active
    ]
    # Stable order: display_order then slug
    genre_slugs.sort(key=lambda s: next(
        (g.display_order for g in novel.genres if g.slug == s), 999
    ))

    tag_names = sorted({t.name for t in novel.tags})
    return genre_slugs, tag_names


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
    genre_include: str | None = Query(default=None, description="Comma-separated genre slugs — novel must have all"),
    genre_exclude: str | None = Query(default=None, description="Comma-separated genre slugs — novel must have none"),
    tag_include: str | None = Query(default=None, description="Comma-separated tag names — novel must have all"),
    tag_exclude: str | None = Query(default=None, description="Comma-separated tag names — novel must have none"),
    page: int = Query(default=1, ge=1, description="Page number (1-indexed)"),
    page_size: int = Query(default=24, ge=1, le=100, description="Items per page"),
    storage: StorageService = Depends(get_storage),
    db: Session = Depends(get_db_session),
) -> PublicCatalogResponse:
    """Paginated public novel catalog with optional search, filter, and sort."""
    # Normalize sort parameters with safe fallbacks
    effective_sort_by = sort_by if sort_by and sort_by in VALID_SORT_FIELDS else DEFAULT_SORT_BY
    effective_order = order if order and order in VALID_ORDER_VALUES else DEFAULT_ORDER
    reverse = effective_order == "desc"

    # Pre-parse taxonomy filters outside the loop
    genre_include_set = set(_parse_csv_filter(genre_include))
    genre_exclude_set = set(_parse_csv_filter(genre_exclude))
    tag_include_set = set(_parse_csv_filter(tag_include))
    tag_exclude_set = set(_parse_csv_filter(tag_exclude))

    novels: list[PublicNovelSummary] = []
    for novel_id in storage.list_novels():
        meta = storage.load_metadata(novel_id) or {}
        if q and not _novel_matches_search(meta, q):
            continue
        if status and _optional_str(meta.get("status")) != status:
            continue
        if language and _optional_str(meta.get("language")) != language:
            continue
        genres, tags = _load_taxonomy_for_novel(db, novel_id)
        # Taxonomy include/exclude filters
        novel_genre_set = set(genres)
        novel_tag_set = set(tags)
        if genre_include_set and not genre_include_set.issubset(novel_genre_set):
            continue
        if genre_exclude_set and novel_genre_set.intersection(genre_exclude_set):
            continue
        if tag_include_set and not set(tag_include_set).issubset(novel_tag_set):
            continue
        if tag_exclude_set and novel_tag_set.intersection(tag_exclude_set):
            continue
        summary = _novel_summary(novel_id, meta, storage, genres=genres, tags=tags)
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
    db: Session = Depends(get_db_session),
) -> PublicNovelSummary:
    """Public novel detail."""
    meta = storage.load_metadata(slug)
    if meta is None:
        raise HTTPException(status_code=404, detail="Novel not found.")
    genres, tags = _load_taxonomy_for_novel(db, slug)
    return _novel_summary(slug, meta, storage, genres=genres, tags=tags)


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


# ---------------------------------------------------------------------------
# Genres
# ---------------------------------------------------------------------------

@router.get("/genres", response_model=list[PublicGenreResponse])
async def list_genres(
    include_adult: bool = Query(default=True, description="Include adult genres"),
    db: Session = Depends(get_db_session),
) -> list[PublicGenreResponse]:
    """Return active genres ordered by display_order then name."""
    query = db.query(Genre).filter(Genre.is_active.is_(True))
    if not include_adult:
        query = query.filter(Genre.is_adult.is_(False))
    query = query.order_by(Genre.display_order, Genre.name_ja)
    return [
        PublicGenreResponse(
            slug=g.slug,
            name_ja=g.name_ja,
            name_en=g.name_en,
            is_adult=g.is_adult,
        )
        for g in query.all()
    ]
