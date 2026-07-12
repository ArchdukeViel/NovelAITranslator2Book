"""Library detail endpoints: catalog projection, publish/unpublish, health.

Extracted from library.py to keep the core router focused on novel CRUD,
chapter listing, reader, and progress.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from novelai.api.auth.roles import require_role
from novelai.api.auth.security import require_csrf_for_unsafe_methods
from novelai.api.routers.dependencies import get_db_session, get_storage
from novelai.services.catalog_service import CatalogService, get_projection_refresh_failures

router = APIRouter(dependencies=[Depends(require_csrf_for_unsafe_methods)])
logger = logging.getLogger(__name__)

_last_bulk_reconciliation_at: str | None = None


class CatalogPublicationResponse(BaseModel):
    novel_id: str
    title: str
    source_title: str | None = None
    is_published: bool
    chapter_count: int
    translated_count: int
    latest_chapter_id: str | None = None
    latest_chapter_number: int | None = None
    latest_chapter_title: str | None = None
    publication_status: str
    visibility_warnings: list[str] = []


def _optional_string(value: Any) -> str | None:
    return value.strip() if isinstance(value, str) and value.strip() else None


def _catalog_publication_response(
    novel: Any,
    *,
    visibility_warnings: list[str] | None = None,
    normalize_publication_status: Any = None,
) -> CatalogPublicationResponse:
    from novelai.sources.status import normalize_publication_status as _norm_status

    source_title = novel.original_title if novel.original_title and novel.original_title != novel.title else None
    publication_status = _norm_status(novel.publication_status or novel.status)
    return CatalogPublicationResponse(
        novel_id=novel.slug,
        title=_optional_string(novel.title) or novel.slug,
        source_title=source_title,
        is_published=novel.is_published,
        chapter_count=novel.chapter_count,
        translated_count=novel.translated_count,
        latest_chapter_id=novel.latest_chapter_id,
        latest_chapter_number=novel.latest_chapter_number,
        latest_chapter_title=novel.latest_chapter_title,
        publication_status=publication_status,
        visibility_warnings=visibility_warnings or [],
    )


class CatalogProjectionRefreshResponse(BaseModel):
    novel_id: str
    created: bool
    changed_fields: list[str]
    before: dict[str, Any] | None = None
    after: dict[str, Any]


class CatalogProjectionFailureResponse(BaseModel):
    novel_id: str
    error: str


class CatalogProjectionBulkChangedResponse(BaseModel):
    novel_id: str
    created: bool
    changed_fields: list[str]
    before: dict[str, Any] | None = None
    after: dict[str, Any]


class CatalogProjectionBulkRefreshResponse(BaseModel):
    dry_run: bool
    scanned: int
    created: int
    updated: int
    unchanged: int
    failed: int
    changed: list[CatalogProjectionBulkChangedResponse]
    failures: list[CatalogProjectionFailureResponse]
    details_truncated: bool = False


class CatalogHealthResponse(BaseModel):
    total_novels: int
    projection_stale_count: int
    missing_projection_count: int
    last_bulk_reconciliation_at: str | None = None
    recommendations: list[str]
    projection_refresh_errors: list[dict]


class NovelProjectionHealthResponse(BaseModel):
    novel_id: str
    db_has_row: bool
    db_chapter_count: int
    storage_translated_count: int
    in_sync: bool
    recommended_action: str


@router.post(
    "/refresh-catalog-projections",
    response_model=CatalogProjectionBulkRefreshResponse,
)
async def refresh_catalog_projections(
    dry_run: bool = Query(default=True),
    limit: int | None = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    storage: Any = Depends(get_storage),
    _owner=Depends(require_role("owner")),
    db: Session = Depends(get_db_session),
) -> CatalogProjectionBulkRefreshResponse:
    result = CatalogService(storage=storage, session=db).reconcile_all_catalog_projections(
        dry_run=dry_run,
        limit=limit,
        offset=offset,
    )
    if not dry_run:
        global _last_bulk_reconciliation_at
        _last_bulk_reconciliation_at = datetime.utcnow().isoformat()
    return CatalogProjectionBulkRefreshResponse(
        dry_run=result.dry_run,
        scanned=result.scanned,
        created=result.created,
        updated=result.updated,
        unchanged=result.unchanged,
        failed=result.failed,
        changed=[
            CatalogProjectionBulkChangedResponse(
                novel_id=item.novel_id,
                created=item.created,
                changed_fields=item.changed_fields,
                before=item.before,
                after=item.after,
            )
            for item in result.changed
        ],
        failures=[
            CatalogProjectionFailureResponse(
                novel_id=item.novel_id,
                error=item.error,
            )
            for item in result.failures
        ],
        details_truncated=result.details_truncated,
    )


@router.post(
    "/{novel_id}/refresh-catalog-projection",
    response_model=CatalogProjectionRefreshResponse,
)
async def refresh_catalog_projection(
    novel_id: str,
    storage: Any = Depends(get_storage),
    _owner=Depends(require_role("owner")),
    db: Session = Depends(get_db_session),
) -> CatalogProjectionRefreshResponse:
    result = CatalogService(storage=storage, session=db).reconcile_catalog_projection(novel_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Novel not found")
    return CatalogProjectionRefreshResponse(
        novel_id=result.novel_id,
        created=result.created,
        changed_fields=result.changed_fields,
        before=result.before,
        after=result.after,
    )


@router.post("/{novel_id}/publish", response_model=CatalogPublicationResponse)
async def publish_novel(
    novel_id: str,
    storage: Any = Depends(get_storage),
    _owner=Depends(require_role("owner")),
    db: Session = Depends(get_db_session),
) -> CatalogPublicationResponse:
    try:
        result = CatalogService(storage=storage, session=db).set_publication_state(
            novel_id,
            is_published=True,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from None
    if result is None:
        raise HTTPException(status_code=404, detail="Novel not found")
    return _catalog_publication_response(
        result.novel,
        visibility_warnings=result.visibility_warnings,
    )


@router.post("/{novel_id}/unpublish", response_model=CatalogPublicationResponse)
async def unpublish_novel(
    novel_id: str,
    storage: Any = Depends(get_storage),
    _owner=Depends(require_role("owner")),
    db: Session = Depends(get_db_session),
) -> CatalogPublicationResponse:
    result = CatalogService(storage=storage, session=db).set_publication_state(
        novel_id,
        is_published=False,
    )
    if result is None:
        raise HTTPException(status_code=404, detail="Novel not found")
    return _catalog_publication_response(
        result.novel,
        visibility_warnings=result.visibility_warnings,
    )


@router.get("/catalog-health", response_model=CatalogHealthResponse)
async def catalog_health(
    storage: Any = Depends(get_storage),
    _owner=Depends(require_role("owner")),
    db: Session = Depends(get_db_session),
) -> CatalogHealthResponse:
    from novelai.db.models.novel import Novel

    total_novels = db.query(func.count(Novel.id)).scalar() or 0
    stale_threshold = datetime.utcnow() - timedelta(hours=24)
    stale_count = db.query(func.count(Novel.id)).filter(
        Novel.updated_at < stale_threshold
    ).scalar() or 0

    storage_ids = set(storage.list_novels())
    db_slugs = {row[0] for row in db.query(Novel.slug).all()}
    missing_projection_count = len(storage_ids - db_slugs)

    recommendations: list[str] = []
    if missing_projection_count > 0:
        recommendations.append(
            f"POST /refresh-catalog-projections?dry_run=false "
            f"to create projections for {missing_projection_count} novel(s)"
        )
    if stale_count > 0:
        recommendations.append(
            f"{stale_count} stale projection(s) — run bulk reconciliation"
        )
    if not recommendations:
        recommendations.append("All catalog projections healthy")

    errors = get_projection_refresh_failures()

    return CatalogHealthResponse(
        total_novels=total_novels,
        projection_stale_count=stale_count,
        missing_projection_count=missing_projection_count,
        last_bulk_reconciliation_at=_last_bulk_reconciliation_at,
        recommendations=recommendations,
        projection_refresh_errors=errors,
    )


@router.get("/{novel_id}/catalog-projection-health", response_model=NovelProjectionHealthResponse)
async def novel_projection_health(
    novel_id: str,
    storage: Any = Depends(get_storage),
    _owner=Depends(require_role("owner")),
    db: Session = Depends(get_db_session),
) -> NovelProjectionHealthResponse:
    from novelai.db.models.novel import Novel

    novel = db.query(Novel).filter_by(slug=novel_id).one_or_none()
    if novel is None:
        raise HTTPException(status_code=404, detail="Novel not found in DB")

    storage_count = storage.count_translated_chapters(novel_id)
    db_count = novel.translated_count or 0
    in_sync = storage_count == db_count

    if in_sync:
        recommended_action = "None — in sync"
    elif storage_count > db_count:
        recommended_action = (
            f"Refresh projection: storage has {storage_count} translated, "
            f"DB shows {db_count}"
        )
    else:
        recommended_action = (
            f"Investigate: DB has {db_count} translated but storage has "
            f"{storage_count} — possible orphaned DB records"
        )

    return NovelProjectionHealthResponse(
        novel_id=novel_id,
        db_has_row=True,
        db_chapter_count=db_count,
        storage_translated_count=storage_count,
        in_sync=in_sync,
        recommended_action=recommended_action,
    )
