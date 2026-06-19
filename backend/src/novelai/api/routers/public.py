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

Architecture note: The base catalog listing prefers DB-backed published novel
pagination. Complex filters temporarily fall back to the legacy file-backed
scanner until their DB query contracts are introduced.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import and_, case
from sqlalchemy.orm import Session

from novelai.api.routers.dependencies import (
    get_db_session,
    get_storage,
    metadata_chapters,
    reader_title,
)
from novelai.db.models.genre import Genre
from novelai.db.models.novel import Novel
from novelai.db.models.tag import Tag
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
    title: str
    source_title: str | None = None
    author: str | None = None
    language: str | None = None
    synopsis: str | None = None
    status: str | None = None
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


class PublicCatalogResponse(BaseModel):
    novels: list[PublicNovelSummary]
    total: int
    page: int
    page_size: int


class PublicGenreResponse(BaseModel):
    slug: str
    name_ja: str
    name_en: str | None = None


class PublicTagSearchResult(BaseModel):
    name: str
    name_ja: str | None = None


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


def _datetime_to_public_string(value: datetime | None) -> str | None:
    return value.isoformat() if isinstance(value, datetime) else None


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
        translated = storage.load_translated_chapter(novel_id, chapter_id)
        if translated is None or not isinstance(translated.get("text"), str):
            continue
        latest = {
            "id": chapter_id,
            "number": chapter.get("num") or (index + 1),
            "title": _optional_str(chapter.get("translated_title")) or _optional_str(chapter.get("title")),
            "updated_at": _optional_str(translated.get("translated_at")) or _optional_str(translated.get("created_at")),
        }

    return latest


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

    # Determine display title and source (original) title.
    translated_title = _optional_str(meta.get("translated_title"))
    original_title = _optional_str(meta.get("title"))
    display_title = translated_title or original_title or novel_id
    source_title: str | None = None
    if translated_title and original_title and translated_title != original_title:
        source_title = original_title
    latest_chapter = _latest_translated_chapter(novel_id, meta, storage)

    return PublicNovelSummary(
        novel_id=novel_id,
        slug=novel_id,
        title=display_title,
        source_title=source_title,
        author=_optional_str(meta.get("translated_author")) or _optional_str(meta.get("author")),
        language=_optional_str(meta.get("language")),
        synopsis=_optional_str(meta.get("description")),
        status=_optional_str(meta.get("status")),
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
) -> PublicNovelSummary:
    genres, tags = _taxonomy_from_db_novel(novel, include_adult=include_adult)
    source_title = novel.original_title if novel.original_title and novel.original_title != novel.title else None
    return PublicNovelSummary(
        novel_id=novel.slug,
        slug=novel.slug,
        title=novel.title,
        source_title=source_title,
        author=novel.author,
        language=novel.language,
        synopsis=novel.synopsis,
        status=novel.status,
        chapter_count=novel.chapter_count,
        translated_count=novel.translated_count,
        added_at=_datetime_to_public_string(novel.updated_at),
        latest_chapter_id=novel.latest_chapter_id,
        latest_chapter_number=novel.latest_chapter_number,
        latest_chapter_title=novel.latest_chapter_title,
        latest_chapter_updated_at=_datetime_to_public_string(novel.latest_chapter_updated_at),
        genres=genres,
        tags=tags,
    )


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
    return (
        not genre_include_set
        and not genre_exclude_set
        and not tag_include_set
        and not tag_exclude_set
        and (sort_by is None or sort_by in VALID_SORT_FIELDS)
    )


def _published_db_catalog_query(db: Session, *, include_adult: bool):
    query = db.query(Novel).filter(Novel.is_published.is_(True))
    if not include_adult:
        query = query.filter(
            ~Novel.genres.any(
                and_(
                    Genre.is_active.is_(True),
                    Genre.is_adult.is_(True),
                )
            )
        )
    return query


def _catalog_from_db_page(
    db: Session,
    *,
    q: str | None,
    status: str | None,
    language: str | None,
    effective_sort_by: str,
    min_chapters: int | None,
    max_chapters: int | None,
    include_adult: bool,
    page: int,
    page_size: int,
    order: str,
) -> PublicCatalogResponse | None:
    query = _published_db_catalog_query(db, include_adult=include_adult)
    has_published_db_catalog = query.count() > 0
    if not has_published_db_catalog:
        return None

    search_text = _optional_str(q)
    if search_text:
        pattern = f"%{search_text}%"
        query = query.filter(
            Novel.title.ilike(pattern)
            | Novel.author.ilike(pattern)
        )
    if status:
        query = query.filter(Novel.publication_status == status)
    if language:
        query = query.filter(Novel.language == language)
    if min_chapters is not None:
        query = query.filter(Novel.chapter_count >= min_chapters)
    if max_chapters is not None:
        query = query.filter(Novel.chapter_count <= max_chapters)

    total = query.count()

    if effective_sort_by == "title":
        order_field = Novel.title
    elif effective_sort_by == "chapter_count":
        order_field = Novel.chapter_count
    else:
        order_field = Novel.updated_at
    order_columns = (order_field.asc(), Novel.id.asc()) if order == "asc" else (order_field.desc(), Novel.id.desc())
    offset = (page - 1) * page_size
    novels = query.order_by(*order_columns).offset(offset).limit(page_size).all()
    return PublicCatalogResponse(
        novels=[
            _db_novel_summary(novel, include_adult=include_adult)
            for novel in novels
        ],
        total=total,
        page=page,
        page_size=page_size,
    )


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
    # Stable order: display_order then slug
    genre_slugs.sort(key=lambda s: next(
        (g.display_order for g in novel.genres if g.slug == s), 999
    ))

    tag_names = sorted({
        t.name for t in novel.tags
        if include_adult or not t.is_adult
    })
    return genre_slugs, tag_names, has_adult_genre


def _catalog_from_storage(
    *,
    q: str | None,
    status: str | None,
    language: str | None,
    effective_sort_by: str,
    reverse: bool,
    min_chapters: int | None,
    max_chapters: int | None,
    genre_include_set: set[str],
    genre_exclude_set: set[str],
    tag_include_set: set[str],
    tag_exclude_set: set[str],
    include_adult: bool,
    page: int,
    page_size: int,
    storage: StorageService,
    db: Session,
) -> PublicCatalogResponse:
    novels: list[PublicNovelSummary] = []
    for novel_id in storage.list_novels():
        if not _db_row_allows_storage_catalog_entry(db, novel_id):
            continue
        meta = storage.load_metadata(novel_id) or {}
        if q and not _novel_matches_search(meta, q):
            continue
        if status and _optional_str(meta.get("status")) != status:
            continue
        if language and _optional_str(meta.get("language")) != language:
            continue
        genres, tags, is_adult = _load_taxonomy_for_novel(db, novel_id, include_adult=include_adult)
        # Exclude adult novels from public discovery unless explicitly requested
        if not include_adult and is_adult:
            continue
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
    include_adult: bool = Query(default=False, description="Include novels with adult/R18 genres"),
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

    if _is_db_catalog_base_request(
        q=q,
        status=status,
        language=language,
        sort_by=sort_by,
        min_chapters=min_chapters,
        max_chapters=max_chapters,
        genre_include_set=genre_include_set,
        genre_exclude_set=genre_exclude_set,
        tag_include_set=tag_include_set,
        tag_exclude_set=tag_exclude_set,
    ):
        db_response = _catalog_from_db_page(
            db,
            q=q,
            status=status,
            language=language,
            effective_sort_by=effective_sort_by,
            min_chapters=min_chapters,
            max_chapters=max_chapters,
            include_adult=include_adult,
            page=page,
            page_size=page_size,
            order=effective_order,
        )
        if db_response is not None:
            return db_response

    return _catalog_from_storage(
        q=q,
        status=status,
        language=language,
        effective_sort_by=effective_sort_by,
        reverse=reverse,
        min_chapters=min_chapters,
        max_chapters=max_chapters,
        genre_include_set=genre_include_set,
        genre_exclude_set=genre_exclude_set,
        tag_include_set=tag_include_set,
        tag_exclude_set=tag_exclude_set,
        include_adult=include_adult,
        page=page,
        page_size=page_size,
        storage=storage,
        db=db,
    )


@router.get("/novels/{slug}", response_model=PublicNovelSummary)
async def get_novel(
    slug: str,
    include_adult: bool = Query(default=False, description="Include adult/R18 taxonomy terms"),
    storage: StorageService = Depends(get_storage),
    db: Session = Depends(get_db_session),
) -> PublicNovelSummary:
    """Public novel detail."""
    meta = storage.load_metadata(slug)
    if meta is None:
        raise HTTPException(status_code=404, detail="Novel not found.")
    genres, tags, _ = _load_taxonomy_for_novel(db, slug, include_adult=include_adult)
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
        "chapter_number": chapter.get("num") or (index + 1),
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
    include_adult: bool = Query(default=False, description="Include adult genres"),
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
        )
        for g in query.all()
    ]


# ---------------------------------------------------------------------------
# Tags
# ---------------------------------------------------------------------------


@router.get("/tags/search", response_model=list[PublicTagSearchResult])
async def search_tags(
    q: str = Query(min_length=1, description="Search query — at least 2 non-whitespace characters"),
    include_adult: bool = Query(default=False, description="Include adult tags"),
    limit: int = Query(default=10, ge=1, le=50, description="Max results"),
    db: Session = Depends(get_db_session),
) -> list[PublicTagSearchResult]:
    """Search tags by name (case-insensitive). No tags are created."""
    query_str = q.strip()
    if len(query_str) < 2:
        return []

    pattern = f"%{query_str}%"
    base = db.query(Tag).filter(
        Tag.name.ilike(pattern) | Tag.name_ja.ilike(pattern)
    )
    if not include_adult:
        base = base.filter(Tag.is_adult.is_(False))

    # Prefix matches first (on name or name_ja), then alphabetical by name
    prefix_case = case(
        (Tag.name.ilike(f"{query_str}%"), 0),
        (Tag.name_ja.ilike(f"{query_str}%"), 0),
        else_=1,
    )
    results = base.order_by(prefix_case, Tag.name).limit(limit).all()

    return [
        PublicTagSearchResult(
            name=t.name,
            name_ja=t.name_ja,
        )
        for t in results
    ]
