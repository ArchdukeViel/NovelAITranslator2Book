"""Owner emergency controls for contributor credentials."""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from novelai.api.auth.roles import require_role
from novelai.api.auth.security import require_csrf_token
from novelai.api.routers.dependencies import get_db_session
from novelai.services.contributor_credentials import ContributorCredentialService

router = APIRouter(prefix="/api/admin/contributions", tags=["admin-api"])


class AdminContributionStatusRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action: Literal["pause", "resume", "revoke"]


@router.get("", dependencies=[Depends(require_role("owner"))])
def list_contributor_credentials(db: Session = Depends(get_db_session)) -> dict[str, object]:
    service = ContributorCredentialService(db)
    return {"credentials": [service.safe_response(row) for row in service.list_all()]}


@router.patch(
    "/{credential_id}",
    dependencies=[Depends(require_role("owner")), Depends(require_csrf_token)],
)
def update_contributor_credential(
    credential_id: str,
    body: AdminContributionStatusRequest,
    db: Session = Depends(get_db_session),
) -> dict[str, object]:
    service = ContributorCredentialService(db)
    credential = service.get_any(credential_id)
    if credential is None:
        raise HTTPException(status_code=404, detail="Contributor credential not found.")
    try:
        if body.action == "pause":
            updated = service.pause(credential)
        elif body.action == "resume":
            updated = service.resume(credential)
        else:
            updated = service.revoke(credential)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return ContributorCredentialService.safe_response(updated)
