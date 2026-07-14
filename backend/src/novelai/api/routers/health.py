"""Health probe router (M2a, DEBT-001).

Provides:
- ``GET /health/live`` — process-only liveness, unauthenticated, fast.
- ``GET /health/ready`` — public-safe readiness, probes DB/storage/worker/disk.
- ``GET /admin/health`` — owner-only detailed diagnostics, still redacted.

Public responses never expose credentials, hostnames, paths, stack traces,
raw exceptions, bucket names, or signed URLs.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, status
from starlette.responses import JSONResponse

from novelai.api.auth.roles import require_role
from novelai.api.auth.security import require_csrf_for_unsafe_methods
from novelai.api.routers.dependencies import get_health_service

router = APIRouter()


@router.get("/health/live", tags=["health"])
async def health_live(
    service: Any = Depends(get_health_service),
) -> dict[str, Any]:
    """Process-only liveness check. No DB/storage/worker calls."""
    return service.liveness()


@router.get("/health/ready", tags=["health"])
async def health_ready(
    service: Any = Depends(get_health_service),
) -> JSONResponse:
    """Public-safe readiness check. Probes DB, storage, worker, disk.

    Returns 200 if healthy or degraded. Returns 503 if any probe is unhealthy.
    """
    result = await service.readiness()
    if result["status"] == "unhealthy":
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content=result,
        )
    return JSONResponse(status_code=status.HTTP_200_OK, content=result)


admin_router = APIRouter(dependencies=[Depends(require_csrf_for_unsafe_methods)])


@admin_router.get("/admin/health", tags=["health"])
async def admin_health(
    service: Any = Depends(get_health_service),
    _owner=Depends(require_role("owner")),
) -> dict[str, Any]:
    """Owner-only detailed health diagnostics. Still redacted."""
    return await service.admin_health()
