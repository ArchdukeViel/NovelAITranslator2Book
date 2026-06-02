from __future__ import annotations

from fastapi import APIRouter

from novelai.api.routers import admin, editor, jobs, library, operations, requests, sources
from novelai.api.routers.dependencies import (
    _hits,
    _rate_limit,
    get_job_runner,
    get_job_worker,
    get_jobs,
    get_orchestrator,
    get_requests,
    get_storage,
    verify_api_key,
)

router = APIRouter()

router.include_router(sources.router)
router.include_router(jobs.router)
router.include_router(requests.router)
router.include_router(admin.router)
router.include_router(editor.router)
router.include_router(operations.router)
router.include_router(library.router)

__all__ = [
    "_hits",
    "_rate_limit",
    "get_job_runner",
    "get_job_worker",
    "get_jobs",
    "get_orchestrator",
    "get_requests",
    "get_storage",
    "router",
    "verify_api_key",
]
