from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from novelai.api.auth.roles import require_role
from novelai.api.auth.security import require_csrf_for_unsafe_methods
from novelai.api.response_helpers import activity_list_response, activity_record_response
from novelai.api.models import ActivityListResponse, ActivityRecordResponse
from novelai.activity.queue import ActivityQueueService
from novelai.activity.worker import ActivityWorkerService
from novelai.core.platform import JobStatus
from novelai.api.routers.dependencies import get_activity_log, get_activity_worker

router = APIRouter(dependencies=[Depends(require_csrf_for_unsafe_methods)])


class CrawlActivityRequest(BaseModel):
    novel_id: str
    source_key: str
    kind: str = "chapters"
    chapters: str | None = "all"
    source_url: str | None = None
    metadata: dict[str, Any] | None = None


class TranslationActivityRequest(BaseModel):
    novel_id: str
    source_key: str | None = None
    kind: str = "translate"
    chapters: str = "all"
    provider_key: str | None = None
    provider_model: str | None = None
    provider: str | None = None
    model: str | None = None
    allow_cross_provider_fallback: bool = True
    skip_glossary_gate: bool = False
    metadata: dict[str, Any] | None = None


class ActivityStatusUpdateRequest(BaseModel):
    status: str
    error: str | None = None
    metadata: dict[str, Any] | None = None


CrawlJobRequest = CrawlActivityRequest
TranslationJobRequest = TranslationActivityRequest
JobStatusUpdateRequest = ActivityStatusUpdateRequest


@router.get("/activity")
@router.get("/jobs", include_in_schema=False)
async def list_activity(
    status: str | None = None,
    activity_type: str | None = None,
    job_type: str | None = None,
    novel_id: str | None = None,
    limit: int | None = None,
    activity_log: ActivityQueueService = Depends(get_activity_log),
    _owner=Depends(require_role("owner")),
) -> ActivityListResponse:
    try:
        items = activity_log.list_activity(
            status=status,
            activity_type=activity_type or job_type,
            novel_id=novel_id,
            limit=limit,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return activity_list_response(items)


@router.get("/activity/source-health")
@router.get("/jobs/source-health", include_in_schema=False)
async def list_source_health(
    activity_log: ActivityQueueService = Depends(get_activity_log),
    _owner=Depends(require_role("owner")),
) -> dict[str, Any]:
    return {"sources": activity_log.list_source_health()}


@router.get("/activity/source-health/{source_key}")
@router.get("/jobs/source-health/{source_key}", include_in_schema=False)
async def get_source_health(
    source_key: str,
    activity_log: ActivityQueueService = Depends(get_activity_log),
    _owner=Depends(require_role("owner")),
) -> dict[str, Any]:
    source = activity_log.get_source_health(source_key)
    if source is None:
        raise HTTPException(status_code=404, detail="Source health not found")
    return source


@router.get("/activity/{activity_id}")
@router.get("/jobs/{activity_id}", include_in_schema=False)
async def get_activity(
    activity_id: str,
    activity_log: ActivityQueueService = Depends(get_activity_log),
    _owner=Depends(require_role("owner")),
) -> ActivityRecordResponse:
    activity = activity_log.get_activity(activity_id)
    if activity is None:
        raise HTTPException(status_code=404, detail="Activity not found")
    return activity_record_response(activity)


@router.delete("/activity/{activity_id}", status_code=204)
@router.delete("/jobs/{activity_id}", status_code=204, include_in_schema=False)
async def delete_activity(
    activity_id: str,
    activity_log: ActivityQueueService = Depends(get_activity_log),
    _owner=Depends(require_role("owner")),
) -> None:
    if not activity_log.delete_activity(activity_id):
        raise HTTPException(status_code=404, detail="Activity not found")


@router.post("/activity/crawl")
@router.post("/jobs/crawl", include_in_schema=False)
async def create_crawl_activity(
    body: CrawlActivityRequest,
    activity_log: ActivityQueueService = Depends(get_activity_log),
    _owner=Depends(require_role("owner")),
) -> ActivityRecordResponse:
    try:
        return activity_record_response(activity_log.create_crawl_activity(
            novel_id=body.novel_id,
            source_key=body.source_key,
            kind=body.kind,
            chapters=body.chapters,
            source_url=body.source_url,
            metadata=body.metadata,
        ))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/activity/translation")
@router.post("/jobs/translation", include_in_schema=False)
async def create_translation_activity(
    body: TranslationActivityRequest,
    activity_log: ActivityQueueService = Depends(get_activity_log),
    _owner=Depends(require_role("owner")),
) -> ActivityRecordResponse:
    try:
        metadata = dict(body.metadata or {})
        if not body.allow_cross_provider_fallback:
            metadata["allow_cross_provider_fallback"] = False
        if body.skip_glossary_gate:
            metadata["skip_glossary_gate"] = True
        return activity_record_response(activity_log.create_translation_activity(
            novel_id=body.novel_id,
            source_key=body.source_key,
            kind=body.kind,
            chapters=body.chapters,
            provider=body.provider_key or body.provider,
            model=body.provider_model or body.model,
            metadata=metadata,
        ))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/activity/run-next")
@router.post("/jobs/run-next", include_in_schema=False)
async def run_next_activity(
    activity_type: str | None = None,
    job_type: str | None = None,
    worker: ActivityWorkerService = Depends(get_activity_worker),
    _owner=Depends(require_role("owner")),
) -> ActivityRecordResponse:
    try:
        activity = await worker.run_next(activity_type=activity_type or job_type)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if activity is None:
        raise HTTPException(status_code=404, detail="No pending activity found")
    return activity_record_response(activity)


@router.post("/activity/{activity_id}/run")
@router.post("/jobs/{activity_id}/run", include_in_schema=False)
async def run_activity(
    activity_id: str,
    worker: ActivityWorkerService = Depends(get_activity_worker),
    _owner=Depends(require_role("owner")),
) -> ActivityRecordResponse:
    try:
        activity = await worker.run_activity(activity_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if activity is None:
        raise HTTPException(status_code=404, detail="Activity not found")
    stored_activity = worker.activity_log.get_activity(activity_id)
    return activity_record_response(stored_activity or activity)


@router.post("/activity/{activity_id}/retry")
@router.post("/jobs/{activity_id}/retry", include_in_schema=False)
async def retry_activity(
    activity_id: str,
    worker: ActivityWorkerService = Depends(get_activity_worker),
    _owner=Depends(require_role("owner")),
) -> ActivityRecordResponse:
    try:
        activity = await worker.retry_activity(activity_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if activity is None:
        raise HTTPException(status_code=404, detail="Activity not found")
    return activity_record_response(activity)


@router.patch("/activity/{activity_id}")
@router.patch("/jobs/{activity_id}", include_in_schema=False)
async def update_activity_status(
    activity_id: str,
    body: ActivityStatusUpdateRequest,
    activity_log: ActivityQueueService = Depends(get_activity_log),
    _owner=Depends(require_role("owner")),
) -> ActivityRecordResponse:
    if body.status == JobStatus.RUNNING.value:
        raise HTTPException(status_code=400, detail="Use the activity run endpoint to start pending activity.")
    try:
        activity = activity_log.update_activity_status(
            activity_id,
            body.status,
            error=body.error,
            metadata=body.metadata,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if activity is None:
        raise HTTPException(status_code=404, detail="Activity not found")
    return activity_record_response(activity)
