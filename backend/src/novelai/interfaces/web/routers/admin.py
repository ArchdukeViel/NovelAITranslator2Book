from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from fastapi.responses import HTMLResponse

from novelai.interfaces.web.routers._legacy_novels import _ADMIN_HTML
from novelai.interfaces.web.routers.dependencies import get_job_runner, verify_api_key
from novelai.services.job_runner_service import BackgroundJobRunner

router = APIRouter()


@router.get("/admin", response_class=HTMLResponse)
async def admin_dashboard(_auth: None = Depends(verify_api_key)) -> HTMLResponse:
    return HTMLResponse(_ADMIN_HTML)


@router.get("/admin/worker")
async def get_worker_status(
    runner: BackgroundJobRunner = Depends(get_job_runner),
    _auth: None = Depends(verify_api_key),
) -> dict[str, Any]:
    return runner.status()


@router.post("/admin/worker/start")
async def start_worker(
    runner: BackgroundJobRunner = Depends(get_job_runner),
    _auth: None = Depends(verify_api_key),
) -> dict[str, Any]:
    return await runner.start()


@router.post("/admin/worker/stop")
async def stop_worker(
    runner: BackgroundJobRunner = Depends(get_job_runner),
    _auth: None = Depends(verify_api_key),
) -> dict[str, Any]:
    return await runner.stop()


@router.post("/admin/worker/run-once")
async def run_worker_once(
    runner: BackgroundJobRunner = Depends(get_job_runner),
    _auth: None = Depends(verify_api_key),
) -> dict[str, Any]:
    job = await runner.run_once()
    return {
        "job": job,
        "worker": runner.status(),
    }
