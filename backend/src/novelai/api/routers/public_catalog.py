"""Public catalog + genres endpoints — extracted from public.py.

Catalog browse, genre listing, and catalog-specific helpers.
Novel detail and chapter list are in ``public_novel.py``.
Chapter reader and tags search are in ``public_chapter.py``.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import and_, true
from sqlalchemy.orm import Session

from novelai.api.routers.dependencies import (
    get_db_session,
    get_storage,
)
from novelai.api.routers.public import (
    DEFAULT_ORDER,
    DEFAULT_SORT_BY,
    VALID_ORDER_VALUES,
    VALID_SORT_FIELDS,
    PublicCatalogResponse,
    PublicGenreResponse,
    PublicNovelSummary,
    _db_novel_summary,
    _db_row_allows_storage_catalog_entry,
    _is_db_catalog_base_request,
    _load_taxonomy_for_novel,
    _novel_matches_search,
    _novel_summary,
    _optional_str,
    _parse_csv_filter,
    _publication_status_from_metadata,
)
from novelai.db.models.genre import Genre
from novelai.db.models.novel import Novel
from novelai.db.models.tag import Tag
from novelai.sources.status import normalize_publication_status
from novelai.storage.service import StorageService

router = APIRouter(prefix="/api/public", tags=["public"])
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Catalog-specific helpers
# ---------------------------------------------------------------------------


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
        if not include_adult and is_adult:
            continue
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
        if min_chapters is not None and summary.chapter_count < min_chapters:
            continue
        if max_chapters is not None and summary.chapter_count > max_chapters:
            continue
        novels.append(summary)

    def _sort_key(novel: PublicNovelSummary) -> str | int:
        if effective_sort_by == "title":
            return (novel.title or "").lower()
        if effective_sort_by == "chapter_count":
            return novel.chapter_count
        if novel.added_at:
            return novel.added_at
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

    effective_sort_by = sort_by if sort_by and sort_by in VALID_SORT_FIELDS else DEFAULT_SORT_BY
    effective_order = order if order and order in VALID_ORDER_VALUES else DEFAULT_ORDER
    reverse = effective_order == "desc"

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
