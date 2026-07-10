from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse

from novelai.api.auth.roles import require_role
from novelai.api.auth.security import require_csrf_for_unsafe_methods
from novelai.api.routers.admin_schemas import (
    ProviderApiKeyRequest,
    ProviderApiKeyValidationRequest,
    ProviderCredentialCreateRequest,
    ProviderCredentialUpdateRequest,
    ProviderFallbackPolicyRequest,
    model_payload,
    provider_credential_response,
)
from novelai.api.routers.dependencies import (
    get_admin_db_service,
    get_admin_service,
    get_storage,
)
from novelai.services.admin_service import AdminService
from novelai.services.export_manifest_service import (
    compute_export_freshness,
    latest_export,
    list_manifests,
)
from novelai.storage.service import StorageService

router = APIRouter(dependencies=[Depends(require_csrf_for_unsafe_methods)])

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


@router.get("/admin/provider-api-key/{provider_key}")
async def get_provider_api_key_status(
    provider_key: str,
    service: AdminService = Depends(get_admin_service),
    _owner=Depends(require_role("owner")),
) -> dict[str, Any]:
    try:
        return service.provider_api_key_status(provider_key)
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
            provider=body.provider_key,
            api_key=body.api_key,
            label=body.label,
            model=body.provider_model,
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
            model=body.provider_model,
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
            model=body.provider_model if body else None,
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
        return service.set_provider_fallback_policy(model_payload(body))
    except (KeyError, ValueError) as exc:
        _raise_admin_error(exc)
        raise AssertionError("unreachable")


@router.get("/admin/providers/{provider_key}")
async def get_provider_credential(
    provider_key: str,
    service: AdminService = Depends(get_admin_service),
    _owner=Depends(require_role("owner")),
) -> dict[str, Any]:
    try:
        return provider_credential_response(service.provider_api_key_status(provider_key))
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
            provider=body.provider_key,
            api_key=body.api_key,
            model=body.provider_model,
            apply_globally=body.apply_globally,
        )
        if body.validate_connection:
            return await service.validate_provider_api_key(
                provider=body.provider_key,
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
            provider=body.provider_key,
            api_key=body.api_key,
            model=body.provider_model,
            apply_globally=body.apply_globally,
        )
        if body.validate_connection:
            status = await service.validate_provider_api_key(
                provider=body.provider_key,
                model=status.get("provider_model"),
            )
        return provider_credential_response(status)
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
            provider=body.provider_key,
            api_key=body.api_key,
            model=body.provider_model,
        )
    except (KeyError, ValueError) as exc:
        _raise_admin_error(exc)
        raise AssertionError("unreachable")


@router.post("/admin/providers/{provider_key}/validate")
async def validate_provider_credential(
    provider_key: str,
    body: ProviderApiKeyValidationRequest | None = None,
    service: AdminService = Depends(get_admin_service),
    _owner=Depends(require_role("owner")),
) -> dict[str, Any]:
    try:
        status = await service.validate_provider_api_key(
            provider=body.provider_key if body else provider_key,
            api_key=body.api_key if body else None,
            model=body.provider_model if body else None,
        )
        return provider_credential_response(status)
    except (KeyError, ValueError) as exc:
        _raise_admin_error(exc)
        raise AssertionError("unreachable")


@router.delete("/admin/provider-api-key/{provider_key}")
async def clear_provider_api_key(
    provider_key: str,
    service: AdminService = Depends(get_admin_service),
    _owner=Depends(require_role("owner")),
) -> dict[str, Any]:
    try:
        return service.clear_provider_api_key(provider_key)
    except (KeyError, ValueError) as exc:
        _raise_admin_error(exc)
        raise AssertionError("unreachable")


@router.delete("/admin/providers/{provider_key}")
async def clear_provider_credential(
    provider_key: str,
    service: AdminService = Depends(get_admin_service),
    _owner=Depends(require_role("owner")),
) -> dict[str, Any]:
    try:
        return provider_credential_response(service.clear_provider_api_key(provider_key))
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


@router.post("/admin/runtime-state/cleanup")
async def cleanup_runtime_state(
    service: AdminService = Depends(get_admin_service),
    _owner=Depends(require_role("owner")),
) -> dict[str, Any]:
    return {"purged": service.storage.cleanup_expired_runtime_data() if service.storage else 0}


@router.delete("/admin/runtime-state/{state_key}")
async def clear_runtime_state(
    state_key: str,
    service: AdminService = Depends(get_admin_service),
    _owner=Depends(require_role("owner")),
) -> dict[str, Any]:
    if state_key.strip().lower() == "backup_manifest":
        raise HTTPException(
            status_code=422,
            detail="backup_manifest cannot be cleared via this endpoint.",
        )
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


@router.post("/admin/novels/{novel_id}/cache/invalidate")
async def invalidate_novel_cache(
    novel_id: str,
    _owner=Depends(require_role("owner")),
) -> dict[str, Any]:
    from novelai.services.cache.translation_cache import TranslationCacheService
    try:
        service = TranslationCacheService()
        count = service.invalidate(novel_id)
        return {"status": "success", "invalidated": count}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to invalidate cache: {exc}") from exc


@router.get("/admin/translation/scheduler-health")
async def scheduler_health(
    service: AdminService = Depends(get_admin_db_service),
    _owner=Depends(require_role("owner")),
) -> dict[str, Any]:
    return service.scheduler_health()


@router.get("/admin/health/errors")
async def health_errors(
    _owner=Depends(require_role("owner")),
) -> dict[str, Any]:
    from novelai.api.errors import get_error_metrics
    return get_error_metrics()


@router.get("/admin/novels/{novel_id}/exports")
async def list_novel_exports(
    novel_id: str,
    storage: StorageService = Depends(get_storage),
    _owner=Depends(require_role("owner")),
) -> dict[str, Any]:
    if storage.load_metadata(novel_id) is None:
        raise HTTPException(status_code=404, detail="Novel not found")
    manifests = list_manifests(storage, novel_id)
    # Annotate with freshness
    for m in manifests:
        meta = storage.load_metadata(novel_id)
        current_rev = (meta or {}).get("glossary_revision")
        current_updated = (meta or {}).get("updated_at")
        m["freshness"] = compute_export_freshness(
            storage, novel_id, m,
            current_glossary_revision=current_rev,
            current_novel_updated_at=current_updated,
        )
    return {"novel_id": novel_id, "manifests": manifests}


@router.get("/admin/novels/{novel_id}/exports/latest/{export_format}")
async def latest_novel_export(
    novel_id: str,
    export_format: str,
    storage: StorageService = Depends(get_storage),
    _owner=Depends(require_role("owner")),
) -> dict[str, Any]:
    if storage.load_metadata(novel_id) is None:
        raise HTTPException(status_code=404, detail="Novel not found")
    latest = latest_export(storage, novel_id, export_format)
    if latest is None:
        raise HTTPException(status_code=404, detail="No export found for format")
    return latest
