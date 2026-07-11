"""Public catalog router — guest-accessible, no auth required.

Provides the public reader surface (architecture.md §20):
- GET /api/public/catalog        — paginated novel list with search/filter
- GET /api/public/novels/{slug}  — novel detail
- GET /api/public/novels/{slug}/chapters — chapter list
- GET /api/public/novels/{slug}/chapters/{chapter_id} — translated chapter reader

Endpoints are split across three router files:
- ``public_catalog.py`` — catalog browse + genres
- ``public_novel.py`` — novel detail + chapter list
- ``public_chapter.py`` — chapter reader + tags search

This file holds shared Pydantic models, constants, and cross-router helpers.
"""

from __future__ import annotations

import logging
import re
from datetime import datetime
from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel
from sqlalchemy.orm import Session

from novelai.api.routers.dependencies import (
    metadata_chapters,
)
from novelai.db.models.novel import Novel
from novelai.sources.status import normalize_publication_status
from novelai.storage.service import StorageService

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

VALID_SORT_FIELDS = {"added_at", "title", "chapter_count"}
VALID_ORDER_VALUES = {"asc", "desc"}
DEFAULT_SORT_BY = "added_at"
DEFAULT_ORDER = "desc"
PUBLIC_SLUG_MAX_LENGTH = 160
PUBLIC_PROTOCOL_MARKER_RE = re.compile(
    r"^\s*(?:\[CHAPTER[^\]]*\]|\[P\s+p\d{4}\])\s*",
    re.IGNORECASE,
)
PUBLIC_PARAGRAPH_MARKER_RE = re.compile(
    r"^\s*\[P\s+p\d{4}\]\s*",
    re.IGNORECASE,
)

VALID_UNAVAILABLE_POLICIES = {"hard_404", "chapter_shell", "latest_version"}
DEFAULT_UNAVAILABLE_POLICY = "hard_404"


# ---------------------------------------------------------------------------
# Response models
# ---------------------------------------------------------------------------

class PublicNovelSummary(BaseModel):
    novel_id: str
    slug: str
    title: str
    source_title: str | None = None
    author: str | None = None
    language: str | None = None
    synopsis: str | None = None
    status: str | None = None
    publication_status: str = "unknown"
    chapter_count: int = 0
    translated_count: int = 0
    added_at: str | None = None
    latest_chapter_id: str | None = None
    latest_chapter_number: int | None = None
    latest_chapter_title: str | None = None
    latest_chapter_updated_at: str | None = None
    genres: list[str] = []
    tags: list[str] = []


class PublicChapterSummary(BaseModel):
    chapter_id: str
    title: str | None = None
    chapter_number: int | None = None
    translated: bool = False
    availability_status: str = "not_translated"


class PublicCatalogResponse(BaseModel):
    novels: list[PublicNovelSummary]
    total: int
    page: int
    page_size: int
    degraded: bool = False


class PublicGenreResponse(BaseModel):
    slug: str
    name_ja: str
    name_en: str | None = None


class PublicTagSearchResult(BaseModel):
    name: str
    name_ja: str | None = None


# ---------------------------------------------------------------------------
# Cross-router helpers
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


def _datetime_to_public_string(value: datetime | None) -> str | None:
    return value.isoformat() if isinstance(value, datetime) else None


def _publication_status_from_metadata(meta: dict[str, Any]) -> str:
    return normalize_publication_status(meta.get("publication_status") or meta.get("status"))


def _slugify_public_title(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug[:PUBLIC_SLUG_MAX_LENGTH].strip("-") or "novel"


def _public_slug_from_metadata(novel_id: str, meta: dict[str, Any]) -> str:
    storage_slug = _optional_str(meta.get("storage_slug"))
    if storage_slug:
        return storage_slug
    translated_title = _optional_str(meta.get("translated_title"))
    if translated_title:
        return _slugify_public_title(translated_title)
    return novel_id


def _public_synopsis_from_metadata(meta: dict[str, Any]) -> str | None:
    for key in ("translated_synopsis", "translated_description", "synopsis", "description"):
        value = _optional_str(meta.get(key))
        if value:
            return value
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

    translated_title = _optional_str(meta.get("translated_title"))
    original_title = _optional_str(meta.get("title"))
    display_title = translated_title or original_title or novel_id
    source_title: str | None = None
    if translated_title and original_title and translated_title != original_title:
        source_title = original_title
    latest_chapter = _latest_translated_chapter(novel_id, meta, storage)
    publication_status = _publication_status_from_metadata(meta)

    return PublicNovelSummary(
        novel_id=novel_id,
        slug=_public_slug_from_metadata(novel_id, meta),
        title=display_title,
        source_title=source_title,
        author=_optional_str(meta.get("translated_author")) or _optional_str(meta.get("author")),
        language=_optional_str(meta.get("language")),
        synopsis=_public_synopsis_from_metadata(meta),
        status=publication_status,
        publication_status=publication_status,
        chapter_count=chapter_count,
        translated_count=translated_count,
        added_at=_novel_added_at(meta),
        latest_chapter_id=latest_chapter.get("id") if latest_chapter else None,
        latest_chapter_number=latest_chapter.get("number") if latest_chapter else None,
        latest_chapter_title=latest_chapter.get("title") if latest_chapter else None,
        latest_chapter_updated_at=latest_chapter.get("updated_at") if latest_chapter else None,
        genres=genres or [],
        tags=tags or [],
    )


def _taxonomy_from_db_novel(
    novel: Novel,
    *,
    include_adult: bool = True,
) -> tuple[list[str], list[str]]:
    genre_slugs = [
        genre.slug
        for genre in sorted(novel.genres, key=lambda item: (item.display_order, item.slug))
        if genre.is_active and (include_adult or not genre.is_adult)
    ]
    tag_names = sorted({
        tag.name
        for tag in novel.tags
        if include_adult or not tag.is_adult
    })
    return genre_slugs, tag_names


def _db_novel_summary(
    novel: Novel,
    *,
    include_adult: bool,
    storage: StorageService | None = None,
) -> PublicNovelSummary:
    genres, tags = _taxonomy_from_db_novel(novel, include_adult=include_adult)
    source_title = novel.original_title if novel.original_title and novel.original_title != novel.title else None
    publication_status = normalize_publication_status(
        novel.publication_status or novel.status
    )
    storage_summary: PublicNovelSummary | None = None
    if storage is not None:
        resolved = _resolve_storage_metadata_for_db_novel(
            novel.slug,
            storage,
            allow_title_slug_scan=_db_title_is_placeholder(novel),
        )
        if resolved is not None:
            storage_novel_id, metadata, _public_slug = resolved
            storage_summary = _novel_summary(
                storage_novel_id,
                metadata,
                storage,
                genres=genres,
                tags=tags,
            )

    if storage_summary is not None and _db_summary_needs_storage_hydration(novel, storage_summary):
        storage_summary.added_at = _datetime_to_public_string(novel.created_at)
        return storage_summary

    public_slug = storage_summary.slug if storage_summary is not None else novel.slug
    return PublicNovelSummary(
        novel_id=novel.slug,
        slug=public_slug,
        title=novel.title,
        source_title=source_title,
        author=novel.author,
        language=novel.language,
        synopsis=novel.synopsis,
        status=publication_status,
        publication_status=publication_status,
        chapter_count=novel.chapter_count,
        translated_count=novel.translated_count,
        added_at=_datetime_to_public_string(novel.created_at),
        latest_chapter_id=novel.latest_chapter_id,
        latest_chapter_number=novel.latest_chapter_number,
        latest_chapter_title=novel.latest_chapter_title,
        latest_chapter_updated_at=_datetime_to_public_string(novel.latest_chapter_updated_at),
        genres=genres,
        tags=tags,
    )


def _resolve_storage_metadata_for_db_novel(
    novel_slug: str,
    storage: StorageService,
    *,
    allow_title_slug_scan: bool = False,
) -> tuple[str, dict[str, Any], str] | None:
    """Load storage metadata for a DB novel, including title-slug layout fallbacks."""
    meta = storage.load_metadata(novel_slug)
    if meta is not None:
        source_id = _optional_str(meta.get("novel_id")) or novel_slug
        return source_id, meta, _public_slug_from_metadata(source_id, meta)

    if not allow_title_slug_scan:
        return None

    title_slug_root = getattr(storage, "base_dir", None)
    if title_slug_root is not None:
        title_slug_root = title_slug_root / "novel"
    if title_slug_root is not None and title_slug_root.exists():
        return _resolve_public_novel(novel_slug, storage)
    return None


def _db_summary_needs_storage_hydration(
    novel: Novel,
    storage_summary: PublicNovelSummary,
) -> bool:
    """Detect stale/underfed DB projections without abandoning DB pagination."""
    title_is_placeholder = _db_title_is_placeholder(novel)
    count_is_underfed = title_is_placeholder and (novel.chapter_count or 0) <= 0 and storage_summary.chapter_count > 0
    translated_is_underfed = (novel.translated_count or 0) <= 0 and storage_summary.translated_count > 0
    latest_is_underfed = not novel.latest_chapter_id and storage_summary.latest_chapter_id is not None
    return title_is_placeholder or count_is_underfed or translated_is_underfed or latest_is_underfed


def _db_title_is_placeholder(novel: Novel) -> bool:
    title = (novel.title or "").strip()
    return not title or title == novel.slug


def _is_db_catalog_base_request(
    *,
    q: str | None,
    status: str | None,
    language: str | None,
    sort_by: str | None,
    min_chapters: int | None,
    max_chapters: int | None,
    genre_include_set: set[str],
    genre_exclude_set: set[str],
    tag_include_set: set[str],
    tag_exclude_set: set[str],
) -> bool:
    return sort_by is None or sort_by in VALID_SORT_FIELDS


def _db_row_allows_storage_catalog_entry(db: Session, novel_id: str) -> bool:
    novel = db.query(Novel).filter_by(slug=novel_id).one_or_none()
    return novel is None or novel.is_published is True


def _load_taxonomy_for_novel(
    session: Session,
    slug: str,
    *,
    include_adult: bool = True,
) -> tuple[list[str], list[str], bool]:
    """Load assigned genres and tags for a novel from the DB.

    Returns (genre_slugs, tag_names, has_adult_genre) ordered stably.
    - genres: by Genre.display_order then Genre.slug
    - tags: alphabetical by Tag.name
    - has_adult_genre: True if the novel has any genre with is_adult=True
    """
    novel = session.query(Novel).filter_by(slug=slug).one_or_none()
    if novel is None:
        return [], [], False

    genre_slugs = []
    has_adult_genre = False
    for g in novel.genres:
        if not g.is_active:
            continue
        if not include_adult and g.is_adult:
            has_adult_genre = True
            continue
        genre_slugs.append(g.slug)
    genre_slugs.sort(key=lambda s: next(
        (g.display_order for g in novel.genres if g.slug == s), 999
    ))

    tag_names = sorted({
        t.name for t in novel.tags
        if include_adult or not t.is_adult
    })
    return genre_slugs, tag_names, has_adult_genre


def _latest_translated_chapter(
    novel_id: str,
    meta: dict[str, Any],
    storage: StorageService,
) -> dict[str, Any] | None:
    """Return latest chapter metadata that the public reader can actually load."""
    translated_ids = set(storage.list_translated_chapters(novel_id))
    if not translated_ids:
        return None

    latest: dict[str, Any] | None = None
    for index, chapter in enumerate(metadata_chapters(meta)):
        chapter_id = str(chapter.get("id", "")).strip()
        if not chapter_id or chapter_id not in translated_ids:
            continue
        latest = {
            "id": chapter_id,
            "number": chapter.get("num") or (index + 1),
            "title": _optional_str(chapter.get("translated_title")) or _optional_str(chapter.get("title")),
            "updated_at": (
                _optional_str(chapter.get("translated_at"))
                or _optional_str(chapter.get("updated_at"))
                or _optional_str(chapter.get("scraped_at"))
            ),
        }

    return latest


def _resolve_public_novel(
    slug: str,
    storage: StorageService,
    db: Session | None = None,
) -> tuple[str, dict[str, Any], str] | None:
    """Resolve a public slug or legacy source id to canonical storage metadata.

    Checks direct storage key first, then optional DB slug lookup, then falls
    back to scanning all storage metadata.
    """
    meta = storage.load_metadata(slug)
    if meta is not None:
        source_id = _optional_str(meta.get("novel_id")) or slug
        return source_id, meta, _public_slug_from_metadata(source_id, meta)

    if db is not None:
        novel = db.query(Novel).filter_by(slug=slug).one_or_none()
        if novel is not None:
            meta = storage.load_metadata(novel.slug) or {}
            source_id = _optional_str(meta.get("novel_id")) or novel.slug
            return source_id, meta, _public_slug_from_metadata(source_id, meta)

    for novel_id in storage.list_novels():
        candidate_meta = storage.load_metadata(novel_id) or {}
        public_slug = _public_slug_from_metadata(novel_id, candidate_meta)
        source_id = _optional_str(candidate_meta.get("novel_id")) or novel_id
        aliases = {
            novel_id,
            source_id,
            public_slug,
            _optional_str(candidate_meta.get("source_novel_id")) or "",
        }
        if slug in aliases:
            return source_id, candidate_meta, public_slug
    return None


# ---------------------------------------------------------------------------
# Re-exports — unified router for backward compatibility
# ---------------------------------------------------------------------------

from novelai.api.routers.public_catalog import router as _catalog_router  # noqa: E402
from novelai.api.routers.public_chapter import router as _chapter_router  # noqa: E402
from novelai.api.routers.public_novel import router as _novel_router  # noqa: E402

router = APIRouter(prefix="/api/public", tags=["public"])
router.routes.extend(_catalog_router.routes)
router.routes.extend(_novel_router.routes)
router.routes.extend(_chapter_router.routes)
