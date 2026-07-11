"""Admin library CRT endpoints: thin HTTP adapter delegating to LibraryService."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel

from novelai.api.auth.roles import require_role
from novelai.api.auth.security import require_csrf_for_unsafe_methods
from novelai.api.routers.dependencies import (
    _rate_limit,
    get_library_service,
)
from novelai.services.library_service import LibraryService

router = APIRouter(dependencies=[Depends(require_csrf_for_unsafe_methods)])


class ChapterCheckpointFile(BaseModel):
    name: str
    timestamp: str | None = None


class ChapterCheckpoints(BaseModel):
    chapter_id: str
    checkpoints: list[ChapterCheckpointFile]


class NovelCheckpointsResponse(BaseModel):
    novel_id: str
    chapters: list[ChapterCheckpoints]


class NovelSummary(BaseModel):
    novel_id: str
    title: str | None = None
    source_title: str | None = None
    author: str | None = None
    source_key: str | None = None
    source_url: str | None = None
    publication_status: str = "unknown"
    chapter_count: int = 0
    scraped_count: int = 0
    translated_count: int = 0
    is_published: bool = False
    latest_chapter_id: str | None = None
    latest_chapter_number: int | None = None
    latest_chapter_title: str | None = None
    glossary_status: str = "glossary_pending"
    glossary_revision: int = 0
    glossary_pending_count: int = 0
    onboarding_status: str | None = None
    onboarding_updated_at: str | None = None
    onboarding_error_code: str | None = None
    onboarding_error_message: str | None = None
    body_scrape_required: bool | None = None


class NovelCreateRequest(BaseModel):
    novel_id: str
    title: str
    source_url: str | None = None
    source_key: str | None = None
    language: str = "ja"


class NovelCreateResponse(BaseModel):
    novel_id: str
    title: str
    source_url: str | None = None
    source_key: str | None = None
    language: str
    created_at: str
    db_id: int


@router.get("/", response_model=list[NovelSummary])
async def list_novels(
    limit: int | None = Query(default=None, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    service: LibraryService = Depends(get_library_service),
    _owner=Depends(require_role("owner")),
) -> list[dict[str, Any]]:
    return service.list_novels(limit=limit, offset=offset)


@router.post("/", response_model=NovelCreateResponse, status_code=201)
async def create_novel(
    body: NovelCreateRequest,
    service: LibraryService = Depends(get_library_service),
    _owner=Depends(require_role("owner")),
) -> dict[str, Any]:
    try:
        return service.create_novel(
            novel_id=body.novel_id,
            title=body.title,
            source_url=body.source_url,
            source_key=body.source_key,
            language=body.language,
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/{novel_id}")
async def get_novel(
    novel_id: str,
    service: LibraryService = Depends(get_library_service),
    _owner=Depends(require_role("owner")),
) -> dict[str, Any]:
    payload = service.get_novel(novel_id)
    if payload is None:
        raise HTTPException(status_code=404, detail="Novel not found")
    return payload


@router.delete("/{novel_id}", status_code=204)
async def delete_novel(
    novel_id: str,
    request: Request,
    service: LibraryService = Depends(get_library_service),
    _owner=Depends(require_role("owner")),
) -> None:
    _rate_limit(request, "delete")
    try:
        service.delete_novel(novel_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
