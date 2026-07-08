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
import re
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel
from sqlalchemy import and_, case, true
from sqlalchemy.orm import Session

from novelai.api.routers.dependencies import (
    get_db_session,
    get_storage,
    metadata_chapters,
    reader_title,
)
from novelai.config.settings import settings
from novelai.db.models.genre import Genre
from novelai.db.models.novel import Novel
from novelai.db.models.tag import Tag
from novelai.sources.status import normalize_publication_status
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
PUBLIC_SLUG_MAX_LENGTH = 160
PUBLIC_PROTOCOL_MARKER_RE = re.compile(
    r"^\s*(?:\[CHAPTER[^\]]*\]|\[P\s+p\d{4}\])\s*",
    re.IGNORECASE,
)
PUBLIC_PARAGRAPH_MARKER_RE = re.compile(
    r"^\s*\[P\s+p\d{4}\]\s*",
    re.IGNORECASE,
)

# Public reader availability policies (REQ-1.4)
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
# Internal helpers
# ---------------------------------------------------------------------------

def _optional_str(value: Any) -> str | None:
    return value.strip() if isinstance(value, str) and value.strip() else None


def _public_reader_text(text: str) -> str:
    """Remove internal translation protocol markers from public reader text."""
    cleaned_lines: list[str] = []
    for line in text.splitlines():
        current = line
        had_marker = False
        while True:
            current, replacements = PUBLIC_PROTOCOL_MARKER_RE.subn("", current, count=1)
            if replacements == 0:
                break
            had_marker = True
        if had_marker and not current.strip():
            continue
        cleaned_lines.append(current)
    return "\n".join(cleaned_lines).strip("\n")


def _reader_line_block(text: str) -> dict[str, str]:
    return {"type": "line", "text": text}


def _reader_break_block() -> dict[str, str]:
    return {"type": "break"}


def _append_reader_break(blocks: list[dict[str, str]]) -> None:
    if blocks and blocks[-1].get("type") != "break":
        blocks.append(_reader_break_block())


def _with_conservative_reader_breaks(blocks: list[dict[str, str]]) -> list[dict[str, str]]:
    """Add readable group breaks when old storage has line order but no group metadata."""
    if any(block.get("type") == "break" for block in blocks):
        return blocks

    line_blocks = [block for block in blocks if block.get("type") == "line"]
    if len(line_blocks) < 8:
        return blocks

    grouped: list[dict[str, str]] = []
    line_index = 0
    for block in blocks:
        grouped.append(block)
        if block.get("type") != "line":
            continue
        line_index += 1
        if line_index % 4 == 0 and line_index < len(line_blocks):
            grouped.append(_reader_break_block())
    return grouped


def _translated_paragraph_map(text: str) -> dict[str, str]:
    translations: dict[str, str] = {}
    current_id: str | None = None
    current_lines: list[str] = []

    def flush_current() -> None:
        nonlocal current_id
        if current_id is not None:
            translated = "\n".join(current_lines).strip("\n")
            if translated.strip():
                translations[current_id] = translated
        current_id = None
        current_lines.clear()

    for line in text.splitlines():
        if re.match(r"^\s*\[CHAPTER[^\]]*\]\s*$", line, flags=re.IGNORECASE):
            flush_current()
            continue
        marker_match = re.match(r"^\s*\[P\s+(p\d{4})\]\s*(.*)$", line, flags=re.IGNORECASE)
        if marker_match:
            flush_current()
            current_id = marker_match.group(1).lower()
            remainder = marker_match.group(2)
            if remainder.strip():
                current_lines.append(remainder)
            continue
        if current_id is not None:
            current_lines.append(line)

    flush_current()
    return translations


def _source_layout_reader_blocks(text: str, source_blocks: Any) -> list[dict[str, str]]:
    if not isinstance(source_blocks, list):
        return []

    translations = _translated_paragraph_map(text)
    if not translations:
        return []

    blocks: list[dict[str, str]] = []
    for source_block in source_blocks:
        if not isinstance(source_block, dict):
            continue
        block_type = source_block.get("type")
        if block_type == "break":
            _append_reader_break(blocks)
            continue
        if block_type != "line":
            continue
        paragraph_id = source_block.get("paragraph_id")
        if not isinstance(paragraph_id, str):
            continue
        translated = translations.get(paragraph_id.lower())
        if translated and translated.strip():
            blocks.append(_reader_line_block(_public_reader_text(translated)))

    if blocks:
        return _with_conservative_reader_breaks(blocks)
    return []


def _public_reader_blocks(text: str, source_blocks: Any = None) -> list[dict[str, str]]:
    """Return source-layout-aware blocks without internal protocol markers."""
    layout_blocks = _source_layout_reader_blocks(text, source_blocks)
    if layout_blocks:
        return layout_blocks

    blocks: list[dict[str, str]] = []
    current_lines: list[str] = []
    saw_paragraph_marker = False
    pending_blank_lines = 0

    def flush_current() -> None:
        block = "\n".join(line for line in current_lines).strip("\n")
        current_lines.clear()
        if block.strip():
            blocks.append(_reader_line_block(block))

    for line in text.splitlines():
        stripped_line = line.strip()
        if re.match(r"^\s*\[CHAPTER[^\]]*\]\s*$", line, flags=re.IGNORECASE):
            flush_current()
            continue

        is_paragraph_marker = PUBLIC_PARAGRAPH_MARKER_RE.match(line) is not None
        if is_paragraph_marker:
            flush_current()
            if saw_paragraph_marker and pending_blank_lines >= 2:
                _append_reader_break(blocks)
            saw_paragraph_marker = True
            pending_blank_lines = 0

        current = line
        had_marker = False
        while True:
            current, replacements = PUBLIC_PROTOCOL_MARKER_RE.subn("", current, count=1)
            if replacements == 0:
                break
            had_marker = True

        if had_marker and not current.strip():
            continue
        if not stripped_line:
            flush_current()
            pending_blank_lines += 1
            if not saw_paragraph_marker and pending_blank_lines >= 1:
                _append_reader_break(blocks)
            continue
        pending_blank_lines = 0
        current_lines.append(current)

    flush_current()
    if blocks:
        return _with_conservative_reader_breaks(blocks)

    clean_text = _public_reader_text(text)
    fallback_blocks: list[dict[str, str]] = []
    for index, block in enumerate(block.strip("\n") for block in re.split(r"\n{2,}", clean_text) if block.strip()):
        if index > 0:
            fallback_blocks.append(_reader_break_block())
        fallback_blocks.append(_reader_line_block(block))
    return fallback_blocks


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
    storage: StorageService,
    q: str | None,
    status: str | None,
    language: str | None,
    effective_sort_by: str,
    min_chapters: int | None,
    max_chapters: int | None,
    genre_include_set: set[str],
    genre_exclude_set: set[str],
    tag_include_set: set[str],
    tag_exclude_set: set[str],
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
    active_public_genre = (
        Genre.is_active.is_(True)
        if include_adult
        else and_(Genre.is_active.is_(True), Genre.is_adult.is_(False))
    )
    public_tag = true() if include_adult else Tag.is_adult.is_(False)
    for genre_slug in sorted(genre_include_set):
        query = query.filter(
            Novel.genres.any(
                and_(
                    Genre.slug == genre_slug,
                    active_public_genre,
                )
            )
        )
    if genre_exclude_set:
        query = query.filter(
            ~Novel.genres.any(
                and_(
                    Genre.slug.in_(genre_exclude_set),
                    active_public_genre,
                )
            )
        )
    for tag_name in sorted(tag_include_set):
        query = query.filter(
            Novel.tags.any(
                and_(
                    Tag.name == tag_name,
                    public_tag,
                )
            )
        )
    if tag_exclude_set:
        query = query.filter(
            ~Novel.tags.any(
                and_(
                    Tag.name.in_(tag_exclude_set),
                    public_tag,
                )
            )
        )

    total = query.count()

    if effective_sort_by == "title":
        order_field = Novel.title
    elif effective_sort_by == "chapter_count":
        order_field = Novel.chapter_count
    else:
        order_field = Novel.created_at
    order_columns = (order_field.asc(), Novel.id.asc()) if order == "asc" else (order_field.desc(), Novel.id.desc())
    offset = (page - 1) * page_size
    novels = query.order_by(*order_columns).offset(offset).limit(page_size).all()
    return PublicCatalogResponse(
        novels=[
            _db_novel_summary(novel, include_adult=include_adult, storage=storage)
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

    # DB slug lookup avoids scanning storage when the slug is a known novel.
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
        if status and _publication_status_from_metadata(meta) != status:
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
        degraded=True,
    )


# ---------------------------------------------------------------------------
# Public reader availability helpers (REQ-1, REQ-3, REQ-4, REQ-5)
# ---------------------------------------------------------------------------


def _resolve_unavailable_policy(meta: dict[str, Any]) -> str:
    """Resolve the unavailable-chapter policy for a novel.

    Per-novel ``public_reader_unavailable_policy`` in metadata takes
    precedence over the global ``PUBLIC_READER_UNAVAILABLE_POLICY``
    setting. Invalid values fall back to ``hard_404`` and log a warning.
    Missing values are not warned about.
    """
    per_novel = meta.get("public_reader_unavailable_policy")
    if isinstance(per_novel, str) and per_novel.strip():
        if per_novel in VALID_UNAVAILABLE_POLICIES:
            return per_novel
        logger.warning(
            "Invalid per-novel public_reader_unavailable_policy %r; using hard_404",
            per_novel,
        )
        return DEFAULT_UNAVAILABLE_POLICY

    global_policy = settings.PUBLIC_READER_UNAVAILABLE_POLICY
    if isinstance(global_policy, str) and global_policy in VALID_UNAVAILABLE_POLICIES:
        return global_policy
    if isinstance(global_policy, str) and global_policy.strip():
        logger.warning(
            "Invalid PUBLIC_READER_UNAVAILABLE_POLICY %r; using hard_404",
            global_policy,
        )
    return DEFAULT_UNAVAILABLE_POLICY


async def _try_get_owner(request: Request | None) -> Any | None:
    """Best-effort, non-raising owner check for optional public preview.

    Returns the owner session user when authenticated as owner, otherwise
    ``None``. Swallows expected auth failures so public ``?version_id=``
    requests continue normally.
    """
    if request is None:
        return None
    try:
        from novelai.api.auth.session import get_current_user

        # Honor FastAPI dependency overrides (used in tests) by checking
        # the app's override map before falling back to the default
        # ``get_current_user`` implementation.
        scope = getattr(request, "scope", None) or {}
        app = scope.get("app") if isinstance(scope, dict) else None
        override = None
        if app is not None:
            overrides = getattr(app, "dependency_overrides", None)
            if isinstance(overrides, dict):
                override = overrides.get(get_current_user)
        if override is not None:
            user = override()
        else:
            user = get_current_user(request)
        if getattr(user, "is_owner", False):
            return user
        return None
    except Exception:
        return None


def _has_reader_text(translated: dict[str, Any] | None) -> bool:
    return isinstance((translated or {}).get("text"), str)


def _latest_version_with_text(
    versions: list[dict[str, Any]],
) -> dict[str, Any] | None:
    """Return the newest version that has usable string text."""
    candidates = [
        version
        for version in versions
        if isinstance(version, dict) and isinstance(version.get("text"), str)
    ]
    if not candidates:
        return None
    return sorted(
        candidates,
        key=lambda version: (
            version.get("created_at") or version.get("translated_at") or ""
        ),
        reverse=True,
    )[0]


def _translated_from_version(
    chapter_id: str,
    version: dict[str, Any],
) -> dict[str, Any]:
    """Build a normalized translated-chapter dict from a raw version entry."""
    created_at = version.get("created_at") or version.get("translated_at")
    translated_at = version.get("translated_at") or version.get("created_at")
    return {
        "id": chapter_id,
        "version_id": version.get("id") or version.get("version_id"),
        "version_kind": version.get("version_kind") or version.get("kind"),
        "provider": version.get("provider"),
        "model": version.get("model"),
        "translated_at": translated_at,
        "created_at": created_at,
        "text": version.get("text"),
        "editor": version.get("editor"),
        "note": version.get("note"),
        "confidence_score": version.get("confidence_score"),
        "glossary_revision": version.get("glossary_revision", 0)
        if isinstance(version.get("glossary_revision"), int)
        else 0,
    }


def _chapter_shell_response(
    *,
    novel_id: str,
    meta: dict[str, Any],
    public_slug: str,
    chapter_id: str,
    chapter: dict[str, Any],
    chapters: list[dict[str, Any]],
    storage: StorageService,
) -> dict[str, Any]:
    """Build a reader-safe chapter shell response with no translated text."""
    chapter_ids = [str(ch.get("id", "")) for ch in chapters]
    if chapter_id in chapter_ids:
        index = chapter_ids.index(chapter_id)
    else:
        index = 0
    translated_ids = set(storage.list_translated_chapters(novel_id))

    prev_id = chapter_ids[index - 1] if index > 0 else None
    next_id = chapter_ids[index + 1] if index + 1 < len(chapter_ids) else None

    return {
        "novel_id": novel_id,
        "slug": public_slug,
        "chapter_id": chapter_id,
        "chapter_number": chapter.get("num") or (index + 1),
        "novel_title": reader_title(meta),
        "title": _optional_str(chapter.get("translated_title"))
        or _optional_str(chapter.get("title")),
        "text": None,
        "reader_blocks": [],
        "previous_chapter_id": prev_id if prev_id in translated_ids else None,
        "next_chapter_id": next_id if next_id in translated_ids else None,
        "previous_chapter_unavailable": prev_id is not None and prev_id not in translated_ids,
        "next_chapter_unavailable": next_id is not None and next_id not in translated_ids,
        "availability_status": "not_translated",
        "availability_message": "This chapter has not been translated yet.",
        "version_id": None,
        "version_kind": None,
        "is_active_version": False,
        "provider": None,
        "model": None,
        "translated_at": None,
    }


def _availability_fields(
    translated: dict[str, Any] | None,
    *,
    is_active_version: bool,
) -> dict[str, Any]:
    """Build additive availability/version fields for a translated response."""
    if not isinstance(translated, dict):
        return {
            "availability_status": "available",
            "availability_message": None,
            "version_id": None,
            "version_kind": None,
            "is_active_version": is_active_version,
            "provider": None,
            "model": None,
            "translated_at": None,
        }
    return {
        "availability_status": "available",
        "availability_message": None,
        "version_id": translated.get("version_id"),
        "version_kind": translated.get("version_kind"),
        "is_active_version": is_active_version,
        "provider": translated.get("provider"),
        "model": translated.get("model"),
        "translated_at": translated.get("translated_at"),
    }


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.get("/catalog", response_model=PublicCatalogResponse)
async def catalog(
    q: str | None = Query(default=None, description="Search title or author"),
    status: str | None = Query(default=None, description="Filter by status"),
    publication_status: str | None = Query(default=None, description="Filter by publication status"),
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
    effective_status = normalize_publication_status(status) if status else None
    effective_publication_status = (
        normalize_publication_status(publication_status)
        if publication_status
        else None
    )
    if effective_status and effective_publication_status and effective_status != effective_publication_status:
        raise HTTPException(
            status_code=400,
            detail="status and publication_status filters must match when both are provided.",
        )
    publication_status_filter = effective_publication_status or effective_status

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
        status=publication_status_filter,
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
            storage=storage,
            q=q,
            status=publication_status_filter,
            language=language,
            effective_sort_by=effective_sort_by,
            min_chapters=min_chapters,
            max_chapters=max_chapters,
            genre_include_set=genre_include_set,
            genre_exclude_set=genre_exclude_set,
            tag_include_set=tag_include_set,
            tag_exclude_set=tag_exclude_set,
            include_adult=include_adult,
            page=page,
            page_size=page_size,
            order=effective_order,
        )
        if db_response is not None:
            return db_response
        logger.warning("DB catalog fell back to storage scan — no DB projection found")

    return _catalog_from_storage(
        q=q,
        status=publication_status_filter,
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


@router.get("/novels/{slug}/chapters/{chapter_id}")
async def get_chapter(
    slug: str,
    chapter_id: str,
    version_id: str | None = Query(default=None),
    request: Request = None,  # type: ignore[assignment]
    storage: StorageService = Depends(get_storage),
    db: Session = Depends(get_db_session),
) -> dict[str, Any]:
    """Public translated chapter reader."""
    resolved = _resolve_public_novel(slug, storage, db=db)
    if resolved is None:
        raise HTTPException(status_code=404, detail="Novel not found.")
    novel_id, meta, public_slug = resolved

    chapters = metadata_chapters(meta)
    chapter_ids = [str(ch.get("id", "")) for ch in chapters]
    if chapter_id not in chapter_ids:
        raise HTTPException(status_code=404, detail="Chapter not found.")

    # Owner-only version preview (REQ-5). Public unauthenticated requests
    # silently ignore ``version_id``.
    effective_version_id: str | None = None
    if version_id is not None:
        owner = await _try_get_owner(request)
        if owner is not None:
            effective_version_id = version_id

    translated: dict[str, Any] | None = None
    is_active_version = True

    if effective_version_id is not None:
        translated = storage.load_translated_chapter_by_version_id(
            novel_id,
            chapter_id,
            effective_version_id,
        )
        if translated is None:
            raise HTTPException(status_code=404, detail="Version not found.")
        active = storage.load_translated_chapter(novel_id, chapter_id)
        active_version_id = active.get("version_id") if isinstance(active, dict) else None
        is_active_version = active_version_id == effective_version_id
    else:
        translated = storage.load_translated_chapter(novel_id, chapter_id)
        is_active_version = True

    # Unavailable-chapter policy handling (REQ-1, REQ-3, REQ-4).
    if not _has_reader_text(translated):
        policy = _resolve_unavailable_policy(meta)

        if policy == "latest_version":
            versions = storage.list_translated_chapter_versions(novel_id, chapter_id)
            latest = _latest_version_with_text(versions)
            if latest is not None:
                translated = _translated_from_version(chapter_id, latest)
                is_active_version = False
            else:
                policy = "chapter_shell"

        if policy == "chapter_shell":
            index = chapter_ids.index(chapter_id)
            chapter = chapters[index]
            return _chapter_shell_response(
                novel_id=novel_id,
                meta=meta,
                public_slug=public_slug,
                chapter_id=chapter_id,
                chapter=chapter,
                chapters=chapters,
                storage=storage,
            )

        if policy == "hard_404":
            raise HTTPException(
                status_code=404,
                detail="Translated chapter not available.",
            )

    # Active translation path (REQ-7).
    assert isinstance(translated, dict)
    translated_text = translated.get("text")  # type: ignore[no-untyped-call]
    if not isinstance(translated_text, str):
        raise HTTPException(
            status_code=404,
            detail="Translated chapter not available.",
        )
    paragraph_map = translated.get("paragraph_map")
    raw_chapter: dict[str, Any] = {}
    if not paragraph_map or not isinstance(paragraph_map, list) or not paragraph_map:
        raw_chapter = storage.load_chapter(novel_id, chapter_id) or {}

    index = chapter_ids.index(chapter_id)
    chapter = chapters[index]
    translated_ids = set(storage.list_translated_chapters(novel_id))
    previous_adjacent_id = chapter_ids[index - 1] if index > 0 else None
    next_adjacent_id = chapter_ids[index + 1] if index + 1 < len(chapter_ids) else None
    previous_chapter_id = previous_adjacent_id if previous_adjacent_id in translated_ids else None
    next_chapter_id = next_adjacent_id if next_adjacent_id in translated_ids else None
    response = {
        "novel_id": novel_id,
        "slug": public_slug,
        "chapter_id": chapter_id,
        "chapter_number": chapter.get("num") or (index + 1),
        "novel_title": reader_title(meta),
        "title": _optional_str(chapter.get("translated_title")) or _optional_str(chapter.get("title")),
        "text": _public_reader_text(translated_text),
        "reader_blocks": _public_reader_blocks(translated_text, raw_chapter.get("source_blocks")),
        "previous_chapter_id": previous_chapter_id,
        "next_chapter_id": next_chapter_id,
        "previous_chapter_unavailable": previous_adjacent_id is not None and previous_chapter_id is None,
        "next_chapter_unavailable": next_adjacent_id is not None and next_chapter_id is None,
    }
    response.update(_availability_fields(translated, is_active_version=is_active_version))
    return response


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
