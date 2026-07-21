from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from novelai.activity.queue import ActivityQueueService
from novelai.activity.worker import ActivityWorkerService
from novelai.api.auth.roles import require_role
from novelai.api.auth.security import require_csrf_for_unsafe_methods
from novelai.api.models import ActivityListResponse, ActivityRecordResponse
from novelai.api.response_helpers import activity_list_response, activity_record_response
from novelai.api.routers.dependencies import get_activity_log, get_activity_worker, get_db_session
from novelai.core.platform import JobStatus

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
    allow_cross_provider_fallback: bool = True
    skip_glossary_gate: bool = False
    metadata: dict[str, Any] | None = None


class ActivityStatusUpdateRequest(BaseModel):
    status: str
    error: str | None = None
    metadata: dict[str, Any] | None = None


@router.get("/activity")
async def list_activity(
    status: str | None = None,
    activity_type: str | None = None,
    novel_id: str | None = None,
    limit: int | None = None,
    activity_log: ActivityQueueService = Depends(get_activity_log),
    _owner=Depends(require_role("owner")),
) -> ActivityListResponse:
    try:
        items = activity_log.list_activity(
            status=status,
            activity_type=activity_type,
            novel_id=novel_id,
            limit=limit,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return activity_list_response(items)


@router.get("/activity/source-health")
async def list_source_health(
    activity_log: ActivityQueueService = Depends(get_activity_log),
    _owner=Depends(require_role("owner")),
) -> dict[str, Any]:
    return {"sources": activity_log.list_source_health()}


@router.get("/activity/source-health/{source_key}")
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
async def delete_activity(
    activity_id: str,
    activity_log: ActivityQueueService = Depends(get_activity_log),
    _owner=Depends(require_role("owner")),
) -> None:
    if not activity_log.delete_activity(activity_id):
        raise HTTPException(status_code=404, detail="Activity not found")


@router.post("/activity/crawl")
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
async def create_translation_activity(
    body: TranslationActivityRequest,
    activity_log: ActivityQueueService = Depends(get_activity_log),
    _owner=Depends(require_role("owner")),
    db: Session = Depends(get_db_session),
) -> ActivityRecordResponse:
    try:
        metadata = dict(body.metadata or {})
        if not body.allow_cross_provider_fallback:
            metadata["allow_cross_provider_fallback"] = False
        if body.skip_glossary_gate:
            metadata["skip_glossary_gate"] = True

        # Record current glossary revision at schedule time (REQ-10).
        # The worker may compare this with the current revision before
        # execution to detect stale scheduled jobs.
        if "scheduled_glossary_revision" not in metadata:
            from novelai.services.novel_query_service import get_glossary_revision
            try:
                revision = get_glossary_revision(db, body.novel_id)
                if revision is not None:
                    metadata["scheduled_glossary_revision"] = revision
            except Exception:
                pass

        return activity_record_response(activity_log.create_translation_activity(
            novel_id=body.novel_id,
            source_key=body.source_key,
            kind=body.kind,
            chapters=body.chapters,
            provider_key=body.provider_key,
            provider_model=body.provider_model,
            metadata=metadata,
        ))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/activity/run-next")
async def run_next_activity(
    activity_type: str | None = None,
    worker: ActivityWorkerService = Depends(get_activity_worker),
    _owner=Depends(require_role("owner")),
) -> ActivityRecordResponse:
    try:
        activity = await worker.run_next(activity_type=activity_type)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if activity is None:
        raise HTTPException(status_code=404, detail="No pending activity found")
    return activity_record_response(activity)


@router.post("/activity/{activity_id}/run")
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
