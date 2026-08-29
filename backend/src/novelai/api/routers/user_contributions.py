"""Authenticated user-owned contributor credential endpoints."""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict, SecretStr
from sqlalchemy.orm import Session

from novelai.api.auth.roles import require_role
from novelai.api.auth.security import require_csrf_token, require_public_rate_limit
from novelai.api.auth.session import SessionUser
from novelai.api.routers.dependencies import get_db_session
from novelai.config.settings import settings
from novelai.services.provider_credentials import ProviderCredentialService

router = APIRouter(prefix="/api/user/contributions", tags=["contributions"])


class ContributionCredentialResponse(BaseModel):
    credential_id: str
    provider: str
    provider_model: str
    last4: str
    fingerprint: str
    status: str
    validation_status: str
    validation_message: str | None
    consent_version: str
    created_at: str | None
    updated_at: str | None
    last_validated_at: str | None
    last_used_at: str | None
    failure_count: int


class ContributionLimitsResponse(BaseModel):
    requests_per_minute: int
    tokens_per_minute: int
    requests_per_day: int


class ContributionListResponse(BaseModel):
    enabled: bool
    encryption_ready: bool
    consent_version: str
    limits: ContributionLimitsResponse
    credentials: list[ContributionCredentialResponse]


class ContributionWriteResponse(BaseModel):
    credential: ContributionCredentialResponse
    validation_ok: bool


class ContributionUpsertRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider_key: Literal["gemini"] = "gemini"
    api_key: SecretStr
    consent_version: str


class ContributionStatusRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["active", "paused"]


class UsageEntryResponse(BaseModel):
    id: int
    status: str
    provider: str
    provider_model: str
    request_id: str | None
    job_id: str | None
    activity_id: str | None
    input_tokens: int | None
    output_tokens: int | None
    total_tokens: int | None
    estimated_cost_usd: float | None
    error_code: str | None
    created_at: str | None
    completed_at: str | None


class UsageResponse(BaseModel):
    credential_id: str
    limits: ContributionLimitsResponse
    current_minute: dict[str, int]
    today: dict[str, int]
    recent: list[UsageEntryResponse]


def _user_id(user: SessionUser) -> int:
    assert user.user_id is not None, "Authenticated route requires user_id"
    return user.user_id


def _limits() -> ContributionLimitsResponse:
    return ContributionLimitsResponse(
        requests_per_minute=settings.CONTRIBUTOR_RPM_LIMIT,
        tokens_per_minute=settings.CONTRIBUTOR_TPM_LIMIT,
        requests_per_day=settings.CONTRIBUTOR_RPD_LIMIT,
    )


@router.get("", response_model=ContributionListResponse)
def list_contributions(
    user: SessionUser = Depends(require_role("user")),
    db: Session = Depends(get_db_session),
) -> ContributionListResponse:
    service = ProviderCredentialService(db)
    return ContributionListResponse(
        enabled=service.enabled(),
        encryption_ready=service.encryption_available(),
        consent_version=settings.CONTRIBUTOR_CONSENT_VERSION,
        limits=_limits(),
        credentials=[
            ContributionCredentialResponse.model_validate(service.safe_response(item))
            for item in service.list_for_user(_user_id(user))
        ],
    )


@router.put("", response_model=ContributionWriteResponse, dependencies=[Depends(require_csrf_token)])
async def replace_contribution(
    body: ContributionUpsertRequest,
    request: Request,
    user: SessionUser = Depends(require_role("user")),
    db: Session = Depends(get_db_session),
) -> ContributionWriteResponse:
    require_public_rate_limit(request, "contributor_validation", user_id=_user_id(user))
    service = ProviderCredentialService(db)
    if not service.enabled():
        raise HTTPException(status_code=503, detail="Contributor credentials are temporarily unavailable.")
    if not service.encryption_available():
        raise HTTPException(status_code=503, detail="Contributor credential encryption is not configured.")
    try:
        credential, api_key = service.replace_unvalidated(
            owner_user_id=_user_id(user),
            provider_key=body.provider_key,
            api_key=body.api_key.get_secret_value(),
            consent_version=body.consent_version,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    ok, _message = await service.validate_and_activate(credential, api_key)
    return ContributionWriteResponse(
        credential=ContributionCredentialResponse.model_validate(service.safe_response(credential)),
        validation_ok=ok,
    )


@router.patch(
    "/{credential_id}",
    response_model=ContributionCredentialResponse,
    dependencies=[Depends(require_csrf_token)],
)
def update_contribution_status(
    credential_id: str,
    body: ContributionStatusRequest,
    user: SessionUser = Depends(require_role("user")),
    db: Session = Depends(get_db_session),
) -> ContributionCredentialResponse:
    service = ProviderCredentialService(db)
    credential = service.get_owned(_user_id(user), credential_id)
    if credential is None:
        raise HTTPException(status_code=404, detail="Contributor credential not found.")
    try:
        updated = service.resume(credential) if body.status == "active" else service.pause(credential)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return ContributionCredentialResponse.model_validate(service.safe_response(updated))


@router.delete("/{credential_id}", status_code=204, dependencies=[Depends(require_csrf_token)])
def delete_contribution(
    credential_id: str,
    user: SessionUser = Depends(require_role("user")),
    db: Session = Depends(get_db_session),
) -> None:
    service = ProviderCredentialService(db)
    credential = service.get_owned(_user_id(user), credential_id)
    if credential is None:
        raise HTTPException(status_code=404, detail="Contributor credential not found.")
    service.delete(credential)


@router.get("/{credential_id}/usage", response_model=UsageResponse)
def contribution_usage(
    credential_id: str,
    user: SessionUser = Depends(require_role("user")),
    db: Session = Depends(get_db_session),
) -> UsageResponse:
    service = ProviderCredentialService(db)
    if service.get_owned(_user_id(user), credential_id) is None:
        raise HTTPException(status_code=404, detail="Contributor credential not found.")
    return UsageResponse.model_validate(service.usage_summary(credential_id))
