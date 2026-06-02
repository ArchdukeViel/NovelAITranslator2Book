from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from novelai.interfaces.web.routers.dependencies import get_job_worker, get_jobs, verify_api_key
from novelai.services.job_queue_service import JobQueueService
from novelai.services.job_worker_service import JobWorkerService

router = APIRouter()


class CrawlJobRequest(BaseModel):
    novel_id: str
    source_key: str
    kind: str = "chapters"
    chapters: str | None = "all"
    source_url: str | None = None
    metadata: dict[str, Any] | None = None


class TranslationJobRequest(BaseModel):
    novel_id: str
    source_key: str | None = None
    kind: str = "translate"
    chapters: str = "all"
    provider: str | None = None
    model: str | None = None
    metadata: dict[str, Any] | None = None


class JobStatusUpdateRequest(BaseModel):
    status: str
    error: str | None = None
    metadata: dict[str, Any] | None = None


@router.get("/jobs")
async def list_jobs(
    status: str | None = None,
    job_type: str | None = None,
    novel_id: str | None = None,
    limit: int | None = None,
    jobs: JobQueueService = Depends(get_jobs),
    _auth: None = Depends(verify_api_key),
) -> dict[str, Any]:
    try:
        items = jobs.list_jobs(status=status, job_type=job_type, novel_id=novel_id, limit=limit)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"jobs": items}


@router.get("/jobs/source-health")
async def list_source_health(
    jobs: JobQueueService = Depends(get_jobs),
    _auth: None = Depends(verify_api_key),
) -> dict[str, Any]:
    return {"sources": jobs.list_source_health()}


@router.get("/jobs/source-health/{source_key}")
async def get_source_health(
    source_key: str,
    jobs: JobQueueService = Depends(get_jobs),
    _auth: None = Depends(verify_api_key),
) -> dict[str, Any]:
    source = jobs.get_source_health(source_key)
    if source is None:
        raise HTTPException(status_code=404, detail="Source health not found")
    return source


@router.get("/jobs/{job_id}")
async def get_job(
    job_id: str,
    jobs: JobQueueService = Depends(get_jobs),
    _auth: None = Depends(verify_api_key),
) -> dict[str, Any]:
    job = jobs.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@router.post("/jobs/crawl")
async def create_crawl_job(
    body: CrawlJobRequest,
    jobs: JobQueueService = Depends(get_jobs),
    _auth: None = Depends(verify_api_key),
) -> dict[str, Any]:
    try:
        return jobs.create_crawl_job(
            novel_id=body.novel_id,
            source_key=body.source_key,
            kind=body.kind,
            chapters=body.chapters,
            source_url=body.source_url,
            metadata=body.metadata,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/jobs/translation")
async def create_translation_job(
    body: TranslationJobRequest,
    jobs: JobQueueService = Depends(get_jobs),
    _auth: None = Depends(verify_api_key),
) -> dict[str, Any]:
    try:
        return jobs.create_translation_job(
            novel_id=body.novel_id,
            source_key=body.source_key,
            kind=body.kind,
            chapters=body.chapters,
            provider=body.provider,
            model=body.model,
            metadata=body.metadata,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/jobs/run-next")
async def run_next_job(
    job_type: str | None = None,
    worker: JobWorkerService = Depends(get_job_worker),
    _auth: None = Depends(verify_api_key),
) -> dict[str, Any]:
    try:
        job = await worker.run_next(job_type=job_type)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if job is None:
        raise HTTPException(status_code=404, detail="No pending job found")
    return job


@router.post("/jobs/{job_id}/run")
async def run_job(
    job_id: str,
    worker: JobWorkerService = Depends(get_job_worker),
    _auth: None = Depends(verify_api_key),
) -> dict[str, Any]:
    try:
        job = await worker.run_job(job_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@router.patch("/jobs/{job_id}")
async def update_job_status(
    job_id: str,
    body: JobStatusUpdateRequest,
    jobs: JobQueueService = Depends(get_jobs),
    _auth: None = Depends(verify_api_key),
) -> dict[str, Any]:
    try:
        job = jobs.update_job_status(job_id, body.status, error=body.error, metadata=body.metadata)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return job
