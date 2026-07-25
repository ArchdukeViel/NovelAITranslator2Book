"""Public DMCA takedown intake endpoint.

Accepts DMCA notices from copyright holders and records them for
owner/admin review.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, EmailStr, field_validator
from sqlalchemy.orm import Session

from novelai.api.routers.dependencies import _rate_limit, get_db_session
from novelai.services.takedown_service import TakedownService

router = APIRouter(prefix="/api/public", tags=["public"])
logger = logging.getLogger(__name__)


class DmcaSubmission(BaseModel):
    complainant_name: str
    complainant_email: EmailStr
    complainant_phone: str | None = None
    infringing_url: str
    description: str
    original_work_url: str | None = None
    original_work_description: str | None = None
    signature: str

    @field_validator("infringing_url", "signature")
    @classmethod
    def _not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Must not be empty")
        return v.strip()


@router.post("/dmca", status_code=201)
def submit_dmca(
    body: DmcaSubmission,
    request: Request,
    db: Session = Depends(get_db_session),
    rate_limit: None = Depends(_rate_limit),
) -> dict[str, str]:
    """Submit a DMCA takedown notice.

    Records the notice for admin review.  The owner is notified through
    the notification backend.
    """
    svc = TakedownService(db)
    svc.submit(
        complainant_name=body.complainant_name,
        complainant_email=body.complainant_email,
        complainant_phone=body.complainant_phone,
        infringing_url=body.infringing_url,
        description=body.description,
        original_work_url=body.original_work_url,
        original_work_description=body.original_work_description,
        signature=body.signature,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    logger.info("DMCA notice submitted for %s by %s", body.infringing_url, body.complainant_name)
    return {"status": "accepted"}
