from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from novelai.activity.runner import BackgroundActivityRunner
from novelai.api.auth.roles import require_role
from novelai.api.auth.security import require_csrf_for_unsafe_methods
from novelai.api.routers.dependencies import (
    get_activity_runner,
    get_db_session,
    get_preferences,
    get_translation_cache,
    get_usage,
)
from novelai.services.admin_service import AdminService
from novelai.services.preferences_service import PreferencesService
from novelai.services.translation_cache import TranslationCache
from novelai.services.usage_service import UsageService
from sqlalchemy.orm import Session

router = APIRouter(dependencies=[Depends(require_csrf_for_unsafe_methods)])


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


class ProviderCredentialCreateRequest(BaseModel):
    provider: str
    api_key: str
    label: str | None = None
    model: str | None = None
    provider_model: str | None = None
    is_active: bool = True
    notes: str | None = None
    apply_globally: bool = False


class ProviderCredentialUpdateRequest(BaseModel):
    label: str | None = None
    model: str | None = None
    provider_model: str | None = None
    is_active: bool | None = None
    notes: str | None = None


class ProviderFallbackPolicyRequest(BaseModel):
    default_provider: str | None = None
    default_model: str | None = None
    default_credential_id: str | None = None
    allow_cross_provider_fallback: bool | None = None
    allow_run_overrides: bool | None = None
    fallback_on_qa_failure: bool | None = None
    candidates: list[dict[str, Any]] | None = None


def _provider_credential_response(status: dict[str, Any]) -> dict[str, Any]:
    provider = str(status.get("provider_key") or status.get("provider") or "gemini")
    validation_status = {
        "working": "Working",
        "failed": "Failed",
        "checking": "Checking",
        "unchecked": "Unchecked",
    }.get(str(status.get("validation_status") or "unchecked").lower(), "Unchecked")
    configured = bool(status.get("configured"))
    return {
        "id": provider,
        "provider": provider,
        "masked_token": "Configured" if configured else "",
        "configured": configured,
        "is_active": configured and status.get("preferred_provider_key", status.get("preferred_provider")) == provider,
        "validation_status": validation_status,
        "validation_message": status.get("validation_message"),
        "model": status.get("provider_model") or status.get("model"),
    }


def _model_payload(model: BaseModel) -> dict[str, Any]:
    dump = getattr(model, "model_dump", None)
    if callable(dump):
        return dump(exclude_none=True)
    return model.dict(exclude_none=True)


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


def get_admin_db_service(
    preferences: PreferencesService = Depends(get_preferences),
    translation_cache: TranslationCache = Depends(get_translation_cache),
    usage: UsageService = Depends(get_usage),
    activity_runner: BackgroundActivityRunner = Depends(get_activity_runner),
    db_session: Session = Depends(get_db_session),
) -> AdminService:
    return AdminService(
        preferences=preferences,
        translation_cache=translation_cache,
        usage=usage,
        activity_runner=activity_runner,
        db_session=db_session,
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
    _owner=Depends(require_role("owner")),
) -> HTMLResponse:
    return HTMLResponse(service.dashboard_html())


@router.get("/admin/provider-api-key/{provider}")
async def get_provider_api_key_status(
    provider: str,
    service: AdminService = Depends(get_admin_service),
    _owner=Depends(require_role("owner")),
) -> dict[str, Any]:
    try:
        return service.provider_api_key_status(provider)
    except (KeyError, ValueError) as exc:
        _raise_admin_error(exc)
        raise AssertionError("unreachable")


@router.get("/admin/providers")
async def list_providers(
    service: AdminService = Depends(get_admin_db_service),
    _owner=Depends(require_role("owner")),
) -> dict[str, Any]:
    return service.provider_inventory()


@router.get("/admin/providers/models")
async def list_provider_models(
    service: AdminService = Depends(get_admin_db_service),
    _owner=Depends(require_role("owner")),
) -> dict[str, Any]:
    return service.provider_models()


@router.get("/admin/providers/credentials")
async def list_provider_credentials(
    service: AdminService = Depends(get_admin_db_service),
    _owner=Depends(require_role("owner")),
) -> dict[str, Any]:
    return service.list_provider_credentials()


@router.post("/admin/providers/credentials")
async def create_provider_credential(
    body: ProviderCredentialCreateRequest,
    service: AdminService = Depends(get_admin_db_service),
    _owner=Depends(require_role("owner")),
) -> dict[str, Any]:
    try:
        return service.create_provider_credential(
            provider=body.provider,
            api_key=body.api_key,
            label=body.label,
            model=body.provider_model or body.model,
            is_active=body.is_active,
            notes=body.notes,
            apply_globally=body.apply_globally,
        )
    except (KeyError, ValueError) as exc:
        _raise_admin_error(exc)
        raise AssertionError("unreachable")


@router.patch("/admin/providers/credentials/{credential_id}")
async def update_provider_credential(
    credential_id: str,
    body: ProviderCredentialUpdateRequest,
    service: AdminService = Depends(get_admin_db_service),
    _owner=Depends(require_role("owner")),
) -> dict[str, Any]:
    try:
        return service.update_provider_credential(
            credential_id,
            label=body.label,
            model=body.provider_model or body.model,
            is_active=body.is_active,
            notes=body.notes,
        )
    except (KeyError, ValueError) as exc:
        _raise_admin_error(exc)
        raise AssertionError("unreachable")


@router.delete("/admin/providers/credentials/{credential_id}")
async def delete_provider_credential(
    credential_id: str,
    service: AdminService = Depends(get_admin_db_service),
    _owner=Depends(require_role("owner")),
) -> dict[str, Any]:
    try:
        return service.delete_provider_credential(credential_id)
    except (KeyError, ValueError) as exc:
        _raise_admin_error(exc)
        raise AssertionError("unreachable")


@router.post("/admin/providers/credentials/{credential_id}/test")
async def test_provider_credential(
    credential_id: str,
    body: ProviderApiKeyValidationRequest | None = None,
    service: AdminService = Depends(get_admin_db_service),
    _owner=Depends(require_role("owner")),
) -> dict[str, Any]:
    try:
        return await service.validate_provider_api_key(
            provider=credential_id,
            api_key=body.api_key if body else None,
            model=(body.provider_model or body.model) if body else None,
        )
    except (KeyError, ValueError) as exc:
        _raise_admin_error(exc)
        raise AssertionError("unreachable")


@router.get("/admin/providers/fallback-policy")
async def get_provider_fallback_policy(
    service: AdminService = Depends(get_admin_db_service),
    _owner=Depends(require_role("owner")),
) -> dict[str, Any]:
    return service.get_provider_fallback_policy()


@router.put("/admin/providers/fallback-policy")
async def set_provider_fallback_policy(
    body: ProviderFallbackPolicyRequest,
    service: AdminService = Depends(get_admin_db_service),
    _owner=Depends(require_role("owner")),
) -> dict[str, Any]:
    try:
        return service.set_provider_fallback_policy(_model_payload(body))
    except (KeyError, ValueError) as exc:
        _raise_admin_error(exc)
        raise AssertionError("unreachable")


@router.get("/admin/providers/{provider}")
async def get_provider_credential(
    provider: str,
    service: AdminService = Depends(get_admin_service),
    _owner=Depends(require_role("owner")),
) -> dict[str, Any]:
    try:
        return _provider_credential_response(service.provider_api_key_status(provider))
    except (KeyError, ValueError) as exc:
        _raise_admin_error(exc)
        raise AssertionError("unreachable")


@router.post("/admin/provider-api-key")
async def set_provider_api_key(
    body: ProviderApiKeyRequest,
    service: AdminService = Depends(get_admin_service),
    _owner=Depends(require_role("owner")),
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


@router.post("/admin/providers")
async def set_provider_credential(
    body: ProviderApiKeyRequest,
    service: AdminService = Depends(get_admin_service),
    _owner=Depends(require_role("owner")),
) -> dict[str, Any]:
    try:
        status = service.set_provider_api_key(
            provider=body.provider_key or body.provider,
            api_key=body.api_key,
            model=body.provider_model or body.model,
            apply_globally=body.apply_globally,
        )
        if body.validate_connection:
            status = await service.validate_provider_api_key(
                provider=body.provider_key or body.provider,
                model=status.get("provider_model"),
            )
        return _provider_credential_response(status)
    except (KeyError, ValueError) as exc:
        _raise_admin_error(exc)
        raise AssertionError("unreachable")


@router.post("/admin/provider-api-key/validate")
async def validate_provider_api_key(
    body: ProviderApiKeyValidationRequest,
    service: AdminService = Depends(get_admin_service),
    _owner=Depends(require_role("owner")),
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


@router.post("/admin/providers/{provider}/validate")
async def validate_provider_credential(
    provider: str,
    body: ProviderApiKeyValidationRequest | None = None,
    service: AdminService = Depends(get_admin_service),
    _owner=Depends(require_role("owner")),
) -> dict[str, Any]:
    try:
        status = await service.validate_provider_api_key(
            provider=body.provider_key if body and body.provider_key else provider,
            api_key=body.api_key if body else None,
            model=(body.provider_model or body.model) if body else None,
        )
        return _provider_credential_response(status)
    except (KeyError, ValueError) as exc:
        _raise_admin_error(exc)
        raise AssertionError("unreachable")


@router.delete("/admin/provider-api-key/{provider}")
async def clear_provider_api_key(
    provider: str,
    service: AdminService = Depends(get_admin_service),
    _owner=Depends(require_role("owner")),
) -> dict[str, Any]:
    try:
        return service.clear_provider_api_key(provider)
    except (KeyError, ValueError) as exc:
        _raise_admin_error(exc)
        raise AssertionError("unreachable")


@router.delete("/admin/providers/{provider}")
async def clear_provider_credential(
    provider: str,
    service: AdminService = Depends(get_admin_service),
    _owner=Depends(require_role("owner")),
) -> dict[str, Any]:
    try:
        return _provider_credential_response(service.clear_provider_api_key(provider))
    except (KeyError, ValueError) as exc:
        _raise_admin_error(exc)
        raise AssertionError("unreachable")


@router.get("/admin/runtime-state")
async def list_runtime_state(
    service: AdminService = Depends(get_admin_service),
    _owner=Depends(require_role("owner")),
) -> dict[str, Any]:
    return service.list_runtime_state()


@router.post("/admin/runtime-state/{state_key}/refresh")
async def refresh_runtime_state(
    state_key: str,
    service: AdminService = Depends(get_admin_service),
    _owner=Depends(require_role("owner")),
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
    _owner=Depends(require_role("owner")),
) -> dict[str, Any]:
    try:
        return service.clear_runtime_state(state_key)
    except KeyError as exc:
        _raise_admin_error(exc)
        raise AssertionError("unreachable")


@router.get("/admin/worker")
async def get_worker_status(
    service: AdminService = Depends(get_admin_service),
    _owner=Depends(require_role("owner")),
) -> dict[str, Any]:
    return service.worker_status()


@router.post("/admin/worker/start")
async def start_worker(
    service: AdminService = Depends(get_admin_service),
    _owner=Depends(require_role("owner")),
) -> dict[str, Any]:
    return await service.start_worker()


@router.post("/admin/worker/stop")
async def stop_worker(
    service: AdminService = Depends(get_admin_service),
    _owner=Depends(require_role("owner")),
) -> dict[str, Any]:
    return await service.stop_worker()


@router.post("/admin/worker/run-once")
async def run_worker_once(
    service: AdminService = Depends(get_admin_service),
    _owner=Depends(require_role("owner")),
) -> dict[str, Any]:
    return await service.run_worker_once()
