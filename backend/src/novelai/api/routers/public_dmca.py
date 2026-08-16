"""Public DMCA takedown intake endpoint.

Accepts DMCA notices from copyright holders and records them for
owner/admin review.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, EmailStr, Field, HttpUrl, field_validator
from sqlalchemy.orm import Session

from novelai.api.middleware.security import get_client_ip
from novelai.api.routers.dependencies import _rate_limit, get_db_session
from novelai.services.takedown_service import TakedownService

router = APIRouter(prefix="/api/public", tags=["public"])
logger = logging.getLogger(__name__)


class DmcaSubmission(BaseModel):
    complainant_name: str = Field(min_length=1, max_length=128)
    complainant_email: EmailStr
    complainant_phone: str | None = Field(default=None, max_length=64)
    infringing_url: HttpUrl
    description: str = Field(min_length=1, max_length=10_000)
    original_work_url: HttpUrl | None = None
    original_work_description: str | None = Field(default=None, max_length=10_000)
    signature: str = Field(min_length=1, max_length=256)

    @field_validator("complainant_name", "complainant_phone", "signature")
    @classmethod
    def _single_line_text(cls, v: str | None) -> str | None:
        if v is None:
            return None
        if not v.strip() or any(ord(char) < 32 for char in v):
            raise ValueError("Must not be empty")
        return v.strip()

    @field_validator("description", "original_work_description")
    @classmethod
    def _multiline_text(cls, v: str | None) -> str | None:
        if v is None:
            return None
        if not v.strip() or any(ord(char) < 32 and char not in "\n\t" for char in v):
            raise ValueError("Must not be empty")
        return v.strip()

    @field_validator("infringing_url", "original_work_url")
    @classmethod
    def _bounded_url(cls, value: HttpUrl | None) -> HttpUrl | None:
        if value is not None and len(str(value)) > 2_048:
            raise ValueError("URL must be at most 2048 characters")
        return value


def _dmca_rate_limit(request: Request) -> None:
    _rate_limit(request, "dmca")


@router.post("/dmca", status_code=201)
def submit_dmca(
    body: DmcaSubmission,
    request: Request,
    db: Session = Depends(get_db_session),
    rate_limit: None = Depends(_dmca_rate_limit),
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
        infringing_url=str(body.infringing_url),
        description=body.description,
        original_work_url=str(body.original_work_url) if body.original_work_url else None,
        original_work_description=body.original_work_description,
        signature=body.signature,
        ip_address=get_client_ip(request),
        user_agent=request.headers.get("user-agent"),
    )
    logger.info("Public DMCA notice accepted")
    return {"status": "accepted"}
