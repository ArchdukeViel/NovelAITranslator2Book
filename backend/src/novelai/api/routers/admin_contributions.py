"""Owner controls for the unified credential registry."""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from novelai.api.auth.roles import require_role
from novelai.api.auth.security import require_csrf_token
from novelai.api.routers.dependencies import get_db_session
from novelai.services.provider_credentials import ProviderCredentialService

router = APIRouter(prefix="/api/admin/contributions", tags=["admin-api"])


class AdminContributionStatusRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action: Literal["pause", "resume", "revoke", "share", "unshare"]


@router.get("", dependencies=[Depends(require_role("owner"))])
def list_provider_credentials(db: Session = Depends(get_db_session)) -> dict[str, object]:
    service = ProviderCredentialService(db)
    return {"credentials": [service.safe_response(row) for row in service.list_all()]}


@router.patch(
    "/{credential_id}",
    dependencies=[Depends(require_role("owner")), Depends(require_csrf_token)],
)
def update_provider_credential(
    credential_id: str,
    body: AdminContributionStatusRequest,
    db: Session = Depends(get_db_session),
) -> dict[str, object]:
    service = ProviderCredentialService(db)
    credential = service.get_any(credential_id)
    if credential is None:
        raise HTTPException(status_code=404, detail="Provider credential not found.")
    try:
        if body.action == "pause":
            updated = service.pause(credential)
        elif body.action == "resume":
            updated = service.resume(credential)
        elif body.action == "revoke":
            updated = service.revoke(credential)
        else:
            updated = service.set_pool_eligibility(credential, body.action == "share")
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return ProviderCredentialService.safe_response(updated)
