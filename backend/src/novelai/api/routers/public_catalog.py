"""Public catalog and genre endpoints.

Catalog browse, genre listing, and catalog-specific helpers.
Novel detail and chapter list are in ``public_novel.py``.
Chapter reader and tags search are in ``public_chapter.py``.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request, Response
from sqlalchemy.orm import Session

from novelai.api.auth.session import SessionUser, get_current_user
from novelai.api.routers.dependencies import (
    get_db_session,
    get_public_catalog_service,
)
from novelai.api.routers.public_contracts import (
    DEFAULT_ORDER,
    DEFAULT_SORT_BY,
    PUBLIC_CACHE_MAX_AGE_SECONDS,
    VALID_ORDER_VALUES,
    VALID_SORT_FIELDS,
    PublicCatalogResponse,
    PublicGenreResponse,
    PublicNovelSummary,
    PublicTagSearchResult,
    _optional_str,
    _parse_csv_filter,
)
from novelai.services.analytics_service import record_server_event
from novelai.services.public_catalog_service import PublicCatalogService
from novelai.services.public_projection_cache import public_projection_cache
from novelai.services.takedown_service import TakedownService

router = APIRouter(prefix="/api/public", tags=["public"])


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.get("/catalog", response_model=PublicCatalogResponse)
async def catalog(
    request: Request,
    response_headers: Response,
    q: str | None = Query(default=None, description="Search title or author"),
    publication_status: str | None = Query(default=None, description="Filter by publication status"),
    source_key: str | None = Query(default=None, description="Filter by canonical source identifier"),
    sort_by: str | None = Query(default=None, description="Sort field: added_at, updated_at, title, chapter_count"),
    order: str | None = Query(default=None, description="Sort order: asc or desc"),
    min_chapters: int | None = Query(default=None, ge=0, description="Minimum chapter count"),
    max_chapters: int | None = Query(default=None, ge=0, description="Maximum chapter count"),
    genre_include: str | None = Query(default=None, description="Comma-separated genre slugs — novel must have all"),
    genre_exclude: str | None = Query(default=None, description="Comma-separated genre slugs — novel must have none"),
    genre_op: str | None = Query(default="and", description="Genre include operator: and or or"),
    tag_include: str | None = Query(default=None, description="Comma-separated tag names — novel must have all"),
    tag_exclude: str | None = Query(default=None, description="Comma-separated tag names — novel must have none"),
    tag_op: str | None = Query(default="and", description="Tag include operator: and or or"),
    search_synopsis: bool = Query(
        default=False,
        description="Search novel synopsis in addition to title and author",
    ),
    include_adult: bool = Query(
        default=False,
        description="Include adult/R18 taxonomy terms in catalog metadata and filters",
    ),
    page: int = Query(default=1, ge=1, description="Page number (1-indexed)"),
    page_size: int = Query(default=24, ge=1, le=100, description="Items per page"),
    service: PublicCatalogService = Depends(get_public_catalog_service),
    user: SessionUser = Depends(get_current_user),
    db: Session = Depends(get_db_session),
) -> PublicCatalogResponse:
    """Paginated public novel catalog with optional search, filter, and sort."""
    from novelai.sources.status import normalize_publication_status

    publication_status_filter = (
        normalize_publication_status(publication_status)
        if isinstance(publication_status, str) and publication_status.strip()
        else None
    )

    sort_by_str = _optional_str(sort_by)
    order_str = _optional_str(order)
    effective_sort_by = sort_by_str if sort_by_str and sort_by_str in VALID_SORT_FIELDS else DEFAULT_SORT_BY
    effective_order = order_str if order_str and order_str in VALID_ORDER_VALUES else DEFAULT_ORDER
    raw_genre_op = _optional_str(genre_op)
    raw_tag_op = _optional_str(tag_op)
    effective_genre_op = raw_genre_op.lower() if raw_genre_op and raw_genre_op.lower() in ("and", "or") else "and"
    effective_tag_op = raw_tag_op.lower() if raw_tag_op and raw_tag_op.lower() in ("and", "or") else "and"
    genre_include_set = set(_parse_csv_filter(genre_include if isinstance(genre_include, str) else None))
    genre_exclude_set = set(_parse_csv_filter(genre_exclude if isinstance(genre_exclude, str) else None))
    tag_include_set = set(_parse_csv_filter(tag_include if isinstance(tag_include, str) else None))
    tag_exclude_set = set(_parse_csv_filter(tag_exclude if isinstance(tag_exclude, str) else None))
    min_chapters_val = min_chapters if isinstance(min_chapters, int) else None
    max_chapters_val = max_chapters if isinstance(max_chapters, int) else None
    is_include_adult = include_adult is True
    is_search_synopsis = search_synopsis is True
    page_val = page if isinstance(page, int) and page >= 1 else 1
    page_size_val = page_size if isinstance(page_size, int) and page_size >= 1 else 24

    response: PublicCatalogResponse
    source_key_filter = _optional_str(source_key)
    query_str = (q or "").strip() if isinstance(q, str) else ""
    cacheable = not any(
        (
            publication_status_filter,
            source_key_filter,
            min_chapters_val is not None,
            max_chapters_val is not None,
            genre_include_set,
            genre_exclude_set,
            tag_include_set,
            tag_exclude_set,
            is_include_adult,
            is_search_synopsis,
            effective_genre_op != "and",
            effective_tag_op != "and",
        )
    )
    base_cache_key = service.public_catalog_cache_key(
        sort_by=effective_sort_by,
        order=effective_order,
        page=page_val,
        page_size=page_size_val,
    )
    cache_key = (*base_cache_key, query_str) if query_str else base_cache_key
    cached = public_projection_cache.get(cache_key) if cacheable else None
    if isinstance(cached, dict):
        response = PublicCatalogResponse.model_validate(cached)
    else:
        novels, total, degraded = service.get_public_catalog_page(
            q=query_str or None,
            publication_status=publication_status_filter,
            source_key=source_key_filter,
            effective_sort_by=effective_sort_by,
            min_chapters=min_chapters_val,
            max_chapters=max_chapters_val,
            genre_include_set=genre_include_set,
            genre_exclude_set=genre_exclude_set,
            tag_include_set=tag_include_set,
            tag_exclude_set=tag_exclude_set,
            include_adult=is_include_adult,
            page=page_val,
            page_size=page_size_val,
            order=effective_order,
            search_synopsis=is_search_synopsis,
            genre_op=effective_genre_op,
            tag_op=effective_tag_op,
        )
        public_novels: list[PublicNovelSummary] = []
        for novel in novels:
            summary = service.build_public_novel_summary(novel, include_adult=is_include_adult)
            if summary is not None:
                public_novels.append(PublicNovelSummary(**summary))
        response = PublicCatalogResponse(
            novels=public_novels,
            total=total,
            page=page_val,
            page_size=page_size_val,
            degraded=degraded,
        )
        if cacheable and response.novels and not response.degraded:
            public_projection_cache.set(cache_key, response.model_dump(mode="json"))
    if query_str:
        record_server_event(
            "search.performed",
            user_id=user.user_id,
            metadata={
                "scope": "catalog",
                "result_count": response.total,
                "filter_count": len(genre_include_set)
                + len(genre_exclude_set)
                + len(tag_include_set)
                + len(tag_exclude_set),
            },
        )
    blocked_slugs = TakedownService(db).active_takedown_slugs(
        [novel.slug for novel in response.novels] + [novel.novel_id for novel in response.novels]
    )
    visible_novels = [
        novel
        for novel in response.novels
        if novel.slug.casefold() not in blocked_slugs and novel.novel_id.casefold() not in blocked_slugs
    ]
    if len(visible_novels) != len(response.novels):
        response = response.model_copy(
            update={
                "novels": visible_novels,
                "total": max(0, response.total - (len(response.novels) - len(visible_novels))),
            }
        )
    # DEBT-059 / REQ-9: short, public-safe edge cache for guest-visible catalog
    # page. Session user has not personalized the response (no per-user data is
    # embedded), so a short max-age is safe. Personal routes MUST NOT use this.
    response_headers.headers["Cache-Control"] = f"public, max-age={PUBLIC_CACHE_MAX_AGE_SECONDS}"
    return response


@router.get("/genres", response_model=list[PublicGenreResponse])
async def list_genres(
    include_adult: bool = Query(default=False, description="Include adult genres"),
    service: PublicCatalogService = Depends(get_public_catalog_service),
) -> list[PublicGenreResponse]:
    """Return active genres ordered by display_order then name."""
    return [PublicGenreResponse(**genre) for genre in service.list_public_genres(include_adult=include_adult)]


@router.get("/tags", response_model=list[PublicTagSearchResult])
async def list_tags(
    include_adult: bool = Query(default=False, description="Include adult tags"),
    limit: int = Query(default=200, ge=1, le=500, description="Max results"),
    service: PublicCatalogService = Depends(get_public_catalog_service),
) -> list[PublicTagSearchResult]:
    """Return available public tags ordered alphabetically."""
    return [PublicTagSearchResult(**tag) for tag in service.list_public_tags(include_adult=include_adult, limit=limit)]
