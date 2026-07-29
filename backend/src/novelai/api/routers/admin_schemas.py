"""Pydantic request/response schemas for admin endpoints."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict


class ProviderApiKeyRequest(BaseModel):
    provider_key: str = "gemini"
    api_key: str
    provider_model: str | None = None
    apply_globally: bool = True
    validate_connection: bool = True


class ProviderApiKeyValidationRequest(BaseModel):
    provider_key: str = "gemini"
    api_key: str | None = None
    provider_model: str | None = None


class ProviderCredentialCreateRequest(BaseModel):
    provider_key: str
    api_key: str
    label: str | None = None
    provider_model: str | None = None
    is_active: bool = True
    notes: str | None = None
    apply_globally: bool = False


class ProviderCredentialUpdateRequest(BaseModel):
    label: str | None = None
    provider_model: str | None = None
    is_active: bool | None = None
    notes: str | None = None


class ProviderFallbackPolicyRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    default_provider_key: str | None = None
    default_provider_model: str | None = None
    default_credential_id: str | None = None
    allow_cross_provider_fallback: bool | None = None
    allow_run_overrides: bool | None = None
    fallback_on_qa_failure: bool | None = None
    candidates: list[dict[str, Any]] | None = None


class MaintenanceTaskStatusResponse(BaseModel):
    task_key: str
    schedule: str
    timezone: str
    enabled: bool
    state: str
    last_started_at: datetime | None
    last_finished_at: datetime | None
    result: str | None
    failure_summary: str | None
    next_eligible_at: datetime | None


class MaintenanceStatusResponse(BaseModel):
    status: Literal["healthy", "degraded"]
    tasks: list[MaintenanceTaskStatusResponse]


def provider_credential_response(status: dict[str, Any]) -> dict[str, Any]:
    provider_key = str(status.get("provider_key") or "gemini")
    validation_status = {
        "working": "Working",
        "failed": "Failed",
        "checking": "Checking",
        "unchecked": "Unchecked",
    }.get(str(status.get("validation_status") or "unchecked").lower(), "Unchecked")
    configured = bool(status.get("configured"))
    return {
        "provider_key": provider_key,
        "masked_token": "Configured" if configured else "",
        "configured": configured,
        "is_active": configured and status.get("preferred_provider_key") == provider_key,
        "validation_status": validation_status,
        "validation_message": status.get("validation_message"),
        "provider_model": status.get("provider_model"),
    }


def model_payload(model: BaseModel) -> dict[str, Any]:
    dump = getattr(model, "model_dump", None)
    if callable(dump):
        result = dump(exclude_none=True)
        assert isinstance(result, dict)
        return result
    return model.dict(exclude_none=True)
