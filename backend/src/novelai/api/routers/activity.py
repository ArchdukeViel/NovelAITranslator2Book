from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from novelai.api.models import ActivityListResponse, ActivityRecordResponse
from novelai.activity.queue import ActivityQueueService
from novelai.activity.worker import ActivityWorkerService
from novelai.api.routers.dependencies import get_activity_log, get_activity_worker, verify_api_key

router = APIRouter()


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
    metadata: dict[str, Any] | None = None


class ActivityStatusUpdateRequest(BaseModel):
    status: str
    error: str | None = None
    metadata: dict[str, Any] | None = None


CrawlJobRequest = CrawlActivityRequest
TranslationJobRequest = TranslationActivityRequest
JobStatusUpdateRequest = ActivityStatusUpdateRequest


_PROGRESS_KEYS = (
    "current_stage",
    "current_label",
    "completed",
    "total",
    "paused_reason",
    "resume_after",
    "errors",
    "warnings",
    "model_states",
)


def _metadata_dict(item: dict[str, Any]) -> dict[str, Any]:
    metadata = item.get("metadata")
    return dict(metadata) if isinstance(metadata, dict) else {}


def _progress_dict(metadata: dict[str, Any]) -> dict[str, Any]:
    progress = metadata.get("progress")
    return dict(progress) if isinstance(progress, dict) else {}


def _normalize_activity_record(item: dict[str, Any]) -> ActivityRecordResponse:
    normalized = dict(item)
    metadata = _metadata_dict(normalized)
    progress = _progress_dict(metadata)
    activity_id = str(normalized.get("id") or normalized.get("activity_id") or normalized.get("job_id") or "")
    normalized["activity_id"] = str(normalized.get("activity_id") or activity_id)
    normalized["job_id"] = str(normalized.get("job_id") or activity_id)
    normalized["provider_key"] = normalized.get("provider_key") or metadata.get("provider_key") or normalized.get("provider")
    normalized["provider_model"] = normalized.get("provider_model") or metadata.get("provider_model") or normalized.get("model")
    normalized["metadata"] = metadata
    for key in _PROGRESS_KEYS:
        if key in normalized and normalized.get(key) is not None:
            continue
        if key in progress:
            normalized[key] = progress.get(key)
        elif key in metadata:
            normalized[key] = metadata.get(key)
    normalized.setdefault("errors", [])
    normalized.setdefault("warnings", [])
    normalized.setdefault("model_states", [])
    return ActivityRecordResponse.model_validate(normalized)


def _activity_response(items: list[dict[str, Any]]) -> ActivityListResponse:
    normalized = [_normalize_activity_record(item) for item in items]
    return ActivityListResponse(activity=normalized, jobs=normalized)


@router.get("/activity")
@router.get("/jobs", include_in_schema=False)
async def list_activity(
    status: str | None = None,
    activity_type: str | None = None,
    job_type: str | None = None,
    novel_id: str | None = None,
    limit: int | None = None,
    activity_log: ActivityQueueService = Depends(get_activity_log),
    _auth: None = Depends(verify_api_key),
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
    return _activity_response(items)


@router.get("/activity/source-health")
@router.get("/jobs/source-health", include_in_schema=False)
async def list_source_health(
    activity_log: ActivityQueueService = Depends(get_activity_log),
    _auth: None = Depends(verify_api_key),
) -> dict[str, Any]:
    return {"sources": activity_log.list_source_health()}


@router.get("/activity/source-health/{source_key}")
@router.get("/jobs/source-health/{source_key}", include_in_schema=False)
async def get_source_health(
    source_key: str,
    activity_log: ActivityQueueService = Depends(get_activity_log),
    _auth: None = Depends(verify_api_key),
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
    _auth: None = Depends(verify_api_key),
) -> ActivityRecordResponse:
    activity = activity_log.get_activity(activity_id)
    if activity is None:
        raise HTTPException(status_code=404, detail="Activity not found")
    return _normalize_activity_record(activity)


@router.delete("/activity/{activity_id}", status_code=204)
@router.delete("/jobs/{activity_id}", status_code=204, include_in_schema=False)
async def delete_activity(
    activity_id: str,
    activity_log: ActivityQueueService = Depends(get_activity_log),
    _auth: None = Depends(verify_api_key),
) -> None:
    if not activity_log.delete_activity(activity_id):
        raise HTTPException(status_code=404, detail="Activity not found")


@router.post("/activity/crawl")
@router.post("/jobs/crawl", include_in_schema=False)
async def create_crawl_activity(
    body: CrawlActivityRequest,
    activity_log: ActivityQueueService = Depends(get_activity_log),
    _auth: None = Depends(verify_api_key),
) -> ActivityRecordResponse:
    try:
        return _normalize_activity_record(activity_log.create_crawl_activity(
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
    _auth: None = Depends(verify_api_key),
) -> ActivityRecordResponse:
    try:
        return _normalize_activity_record(activity_log.create_translation_activity(
            novel_id=body.novel_id,
            source_key=body.source_key,
            kind=body.kind,
            chapters=body.chapters,
            provider=body.provider_key or body.provider,
            model=body.provider_model or body.model,
            metadata=body.metadata,
        ))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/activity/run-next")
@router.post("/jobs/run-next", include_in_schema=False)
async def run_next_activity(
    activity_type: str | None = None,
    job_type: str | None = None,
    worker: ActivityWorkerService = Depends(get_activity_worker),
    _auth: None = Depends(verify_api_key),
) -> ActivityRecordResponse:
    try:
        activity = await worker.run_next(activity_type=activity_type or job_type)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if activity is None:
        raise HTTPException(status_code=404, detail="No pending activity found")
    return _normalize_activity_record(activity)


@router.post("/activity/{activity_id}/run")
@router.post("/jobs/{activity_id}/run", include_in_schema=False)
async def run_activity(
    activity_id: str,
    worker: ActivityWorkerService = Depends(get_activity_worker),
    _auth: None = Depends(verify_api_key),
) -> ActivityRecordResponse:
    try:
        activity = await worker.run_activity(activity_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if activity is None:
        raise HTTPException(status_code=404, detail="Activity not found")
    stored_activity = worker.activity_log.get_activity(activity_id)
    return _normalize_activity_record(stored_activity or activity)


@router.patch("/activity/{activity_id}")
@router.patch("/jobs/{activity_id}", include_in_schema=False)
async def update_activity_status(
    activity_id: str,
    body: ActivityStatusUpdateRequest,
    activity_log: ActivityQueueService = Depends(get_activity_log),
    _auth: None = Depends(verify_api_key),
) -> ActivityRecordResponse:
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
    return _normalize_activity_record(activity)
