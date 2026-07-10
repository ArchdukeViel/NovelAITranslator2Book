"""Admin taxonomy endpoints for per-novel genre/tag management.

Only accessible to owner role. Operates on the DB taxonomy tables
(novel_genres, novel_tags), NOT file-backed storage metadata.

Admin save replaces admin-managed assignments and promotes any
selected scraper rows to admin ownership. This ensures selections
survive re-scrape.

The composite PK (novel_id, genre_id) / (novel_id, tag_id) prevents
dual rows for the same assignment. When a genre/tag is already assigned
by the scraper and the admin selects it, the row is promoted to
assigned_by="admin". Admin cannot remove scraper-only assignments
through this endpoint — only admin-owned rows are deleted during save.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from novelai.api.auth.roles import require_role
from novelai.api.auth.security import require_csrf_for_unsafe_methods
from novelai.api.routers.dependencies import get_db_session
from novelai.services.taxonomy_service import TaxonomyService

router = APIRouter(dependencies=[Depends(require_csrf_for_unsafe_methods)])


class TaxonomyRequest(BaseModel):
    genre_slugs: list[str] = []
    tags: list[str] = []


class TaxonomyResponse(BaseModel):
    novel_id: str
    genres: list[str]
    tags: list[str]


class TaxonomyErrorDetail(BaseModel):
    """Match existing admin error response style."""

    detail: str


@router.get("/{novel_id}/taxonomy", response_model=TaxonomyResponse)
async def get_novel_taxonomy(
    novel_id: str,
    db_session=Depends(get_db_session),
    _owner=Depends(require_role("owner")),
) -> dict[str, Any]:
    """Return current taxonomy (genres + tags) for one novel.

    Returns combined scraper + admin assignments.
    """
    service = TaxonomyService(db_session)
    result = service.get_taxonomy(novel_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Novel not found")
    genres, tags = result
    return {"novel_id": novel_id, "genres": genres, "tags": tags}


@router.put("/{novel_id}/taxonomy", response_model=TaxonomyResponse)
async def set_novel_taxonomy(
    novel_id: str,
    body: TaxonomyRequest,
    db_session=Depends(get_db_session),
    _owner=Depends(require_role("owner")),
) -> dict[str, Any]:
    """Replace admin-managed taxonomy assignments for one novel.

    Semantics:
    - Validate novel exists in DB.
    - Validate genre slugs exist and are active.
    - Normalize tags: trim, deduplicate, drop empty.
    - Upsert tags by name if they do not exist.
    - Delete existing admin rows, then insert or promote scraper rows.
    - Scraper-only rows not selected by admin remain untouched.
    - Idempotent: repeat calls with same body produce same result.
    - Returns combined scraper + admin assignments after the change.
    """
    service = TaxonomyService(db_session)
    try:
        result = service.set_taxonomy(novel_id, body.genre_slugs, body.tags)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if result is None:
        raise HTTPException(status_code=404, detail="Novel not found")
    genres, tags = result
    return {"novel_id": novel_id, "genres": genres, "tags": tags}
