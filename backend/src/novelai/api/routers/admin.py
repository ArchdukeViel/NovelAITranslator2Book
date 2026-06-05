from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from novelai.activity.runner import BackgroundActivityRunner
from novelai.api.routers.dependencies import (
    get_activity_runner,
    get_preferences,
    get_translation_cache,
    get_usage,
    verify_api_key,
)
from novelai.services.admin_service import AdminService
from novelai.services.preferences_service import PreferencesService
from novelai.services.translation_cache import TranslationCache
from novelai.services.usage_service import UsageService

router = APIRouter()


class ProviderApiKeyRequest(BaseModel):
    provider: str = "gemini"
    provider_key: str | None = None
    api_key: str
    model: str | None = None
    provider_model: str | None = None
    apply_globally: bool = True
    validate_connection: bool = True


class ProviderApiKeyValidationRequest(BaseModel):
    provider: str = "gemini"
    provider_key: str | None = None
    api_key: str | None = None
    model: str | None = None
    provider_model: str | None = None


def get_admin_service(
    preferences: PreferencesService = Depends(get_preferences),
    translation_cache: TranslationCache = Depends(get_translation_cache),
    usage: UsageService = Depends(get_usage),
    activity_runner: BackgroundActivityRunner = Depends(get_activity_runner),
) -> AdminService:
    return AdminService(
        preferences=preferences,
        translation_cache=translation_cache,
        usage=usage,
        activity_runner=activity_runner,
    )


def _raise_admin_error(exc: Exception) -> None:
    if isinstance(exc, ValueError):
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if isinstance(exc, KeyError):
        message = exc.args[0] if exc.args else "Unknown runtime state file"
        raise HTTPException(status_code=404, detail=str(message)) from exc
    raise exc


@router.get("/admin", response_class=HTMLResponse)
async def admin_dashboard(
    service: AdminService = Depends(get_admin_service),
    _auth: None = Depends(verify_api_key),
) -> HTMLResponse:
    return HTMLResponse(service.dashboard_html())


@router.get("/admin/provider-api-key/{provider}")
async def get_provider_api_key_status(
    provider: str,
    service: AdminService = Depends(get_admin_service),
    _auth: None = Depends(verify_api_key),
) -> dict[str, Any]:
    try:
        return service.provider_api_key_status(provider)
    except (KeyError, ValueError) as exc:
        _raise_admin_error(exc)
        raise AssertionError("unreachable")


@router.post("/admin/provider-api-key")
async def set_provider_api_key(
    body: ProviderApiKeyRequest,
    service: AdminService = Depends(get_admin_service),
    _auth: None = Depends(verify_api_key),
) -> dict[str, Any]:
    try:
        status = service.set_provider_api_key(
            provider=body.provider_key or body.provider,
            api_key=body.api_key,
            model=body.provider_model or body.model,
            apply_globally=body.apply_globally,
        )
        if body.validate_connection:
            return await service.validate_provider_api_key(
                provider=body.provider_key or body.provider,
                model=status.get("provider_model"),
            )
        return status
    except (KeyError, ValueError) as exc:
        _raise_admin_error(exc)
        raise AssertionError("unreachable")


@router.post("/admin/provider-api-key/validate")
async def validate_provider_api_key(
    body: ProviderApiKeyValidationRequest,
    service: AdminService = Depends(get_admin_service),
    _auth: None = Depends(verify_api_key),
) -> dict[str, Any]:
    try:
        return await service.validate_provider_api_key(
            provider=body.provider_key or body.provider,
            api_key=body.api_key,
            model=body.provider_model or body.model,
        )
    except (KeyError, ValueError) as exc:
        _raise_admin_error(exc)
        raise AssertionError("unreachable")


@router.delete("/admin/provider-api-key/{provider}")
async def clear_provider_api_key(
    provider: str,
    service: AdminService = Depends(get_admin_service),
    _auth: None = Depends(verify_api_key),
) -> dict[str, Any]:
    try:
        return service.clear_provider_api_key(provider)
    except (KeyError, ValueError) as exc:
        _raise_admin_error(exc)
        raise AssertionError("unreachable")


@router.get("/admin/runtime-state")
async def list_runtime_state(
    service: AdminService = Depends(get_admin_service),
    _auth: None = Depends(verify_api_key),
) -> dict[str, Any]:
    return service.list_runtime_state()


@router.post("/admin/runtime-state/{state_key}/refresh")
async def refresh_runtime_state(
    state_key: str,
    service: AdminService = Depends(get_admin_service),
    _auth: None = Depends(verify_api_key),
) -> dict[str, Any]:
    try:
        return service.refresh_runtime_state(state_key)
    except KeyError as exc:
        _raise_admin_error(exc)
        raise AssertionError("unreachable")


@router.delete("/admin/runtime-state/{state_key}")
async def clear_runtime_state(
    state_key: str,
    service: AdminService = Depends(get_admin_service),
    _auth: None = Depends(verify_api_key),
) -> dict[str, Any]:
    try:
        return service.clear_runtime_state(state_key)
    except KeyError as exc:
        _raise_admin_error(exc)
        raise AssertionError("unreachable")


@router.get("/admin/worker")
async def get_worker_status(
    service: AdminService = Depends(get_admin_service),
    _auth: None = Depends(verify_api_key),
) -> dict[str, Any]:
    return service.worker_status()


@router.post("/admin/worker/start")
async def start_worker(
    service: AdminService = Depends(get_admin_service),
    _auth: None = Depends(verify_api_key),
) -> dict[str, Any]:
    return await service.start_worker()


@router.post("/admin/worker/stop")
async def stop_worker(
    service: AdminService = Depends(get_admin_service),
    _auth: None = Depends(verify_api_key),
) -> dict[str, Any]:
    return await service.stop_worker()


@router.post("/admin/worker/run-once")
async def run_worker_once(
    service: AdminService = Depends(get_admin_service),
    _auth: None = Depends(verify_api_key),
) -> dict[str, Any]:
    return await service.run_worker_once()
