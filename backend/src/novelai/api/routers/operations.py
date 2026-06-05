from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel

from novelai.activity.queue import ActivityQueueService
from novelai.api.routers.dependencies import _rate_limit, get_activity_log, get_orchestrator, get_storage, verify_api_key
from novelai.runtime.container import container
from novelai.services.novel_orchestration_service import NovelOrchestrationService
from novelai.services.orchestration.operations import OperationError, OperationsService
from novelai.storage.service import StorageService

router = APIRouter()


class ScrapeRequest(BaseModel):
    source_key: str | None = None
    url: str
    chapters: str = "all"
    mode: str = "update"
    max_chapter: int | None = None


class PreliminaryCrawlRequest(BaseModel):
    source_key: str | None = None
    identifier: str
    mode: str = "update"
    max_chapter: int | None = None


class TranslateRequest(BaseModel):
    source_key: str
    chapters: str = "all"
    provider_key: str | None = None
    provider_model: str | None = None
    force: bool = False
    source_language: str | None = None
    target_language: str | None = "English"


class ExportRequest(BaseModel):
    format: str = "epub"
    chapters: str | None = None


class ImportRequest(BaseModel):
    adapter_key: str
    source: str
    max_units: int | None = None


def get_operations_service(
    orchestrator: NovelOrchestrationService = Depends(get_orchestrator),
    activity_log: ActivityQueueService = Depends(get_activity_log),
    storage: StorageService = Depends(get_storage),
) -> OperationsService:
    return OperationsService(
        orchestrator=orchestrator,
        activity_log=activity_log,
        storage=storage,
        export_service=container.export,
    )


def _raise_operation_error(exc: OperationError) -> None:
    raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc


@router.post("/{novel_id}/scrape")
async def scrape_novel(
    novel_id: str,
    body: ScrapeRequest,
    request: Request,
    service: OperationsService = Depends(get_operations_service),
    _auth: None = Depends(verify_api_key),
) -> dict[str, Any]:
    _rate_limit(request, "scrape")
    try:
        return await service.scrape_novel(
            novel_id=novel_id,
            source_key=body.source_key,
            url=body.url,
            chapters=body.chapters,
            mode=body.mode,
            max_chapter=body.max_chapter,
        )
    except OperationError as exc:
        _raise_operation_error(exc)
        raise AssertionError("unreachable")


@router.post("/{novel_id}/preliminary-crawl")
async def preliminary_crawl_novel(
    novel_id: str,
    body: PreliminaryCrawlRequest,
    request: Request,
    service: OperationsService = Depends(get_operations_service),
    _auth: None = Depends(verify_api_key),
) -> dict[str, Any]:
    _rate_limit(request, "scrape")
    try:
        return await service.preliminary_crawl_novel(
            novel_id=novel_id,
            identifier=body.identifier,
            requested_source_key=body.source_key,
            mode=body.mode,
            max_chapter=body.max_chapter,
        )
    except OperationError as exc:
        _raise_operation_error(exc)
        raise AssertionError("unreachable")


@router.post("/{novel_id}/import")
async def import_document(
    novel_id: str,
    body: ImportRequest,
    request: Request,
    service: OperationsService = Depends(get_operations_service),
    _auth: None = Depends(verify_api_key),
) -> dict[str, Any]:
    _rate_limit(request, "scrape")
    try:
        return await service.import_document(
            novel_id=novel_id,
            adapter_key=body.adapter_key,
            source=body.source,
            max_units=body.max_units,
        )
    except OperationError as exc:
        _raise_operation_error(exc)
        raise AssertionError("unreachable")


@router.post("/{novel_id}/translate")
async def translate_novel(
    novel_id: str,
    body: TranslateRequest,
    request: Request,
    service: OperationsService = Depends(get_operations_service),
    _auth: None = Depends(verify_api_key),
) -> dict[str, str]:
    _rate_limit(request, "translate")
    try:
        return await service.translate_novel(
            novel_id=novel_id,
            source_key=body.source_key,
            chapters=body.chapters,
            provider_key=body.provider_key,
            provider_model=body.provider_model,
            force=body.force,
            source_language=body.source_language,
            target_language=body.target_language,
        )
    except OperationError as exc:
        _raise_operation_error(exc)
        raise AssertionError("unreachable")


@router.post("/{novel_id}/export")
async def export_novel(
    novel_id: str,
    body: ExportRequest,
    request: Request,
    service: OperationsService = Depends(get_operations_service),
    _auth: None = Depends(verify_api_key),
) -> FileResponse:
    _rate_limit(request, "export")
    try:
        result = service.export_novel(novel_id=novel_id, export_format=body.format)
    except OperationError as exc:
        _raise_operation_error(exc)
        raise AssertionError("unreachable")
    return FileResponse(result.path, media_type=result.media_type, filename=result.filename)
