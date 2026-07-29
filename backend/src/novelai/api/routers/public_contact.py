"""Public contact / support intake endpoint.

Accepts visitor messages and hands them to the notification service.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, EmailStr

from novelai.api.routers.dependencies import _rate_limit
from novelai.services.notification_service import NotificationService

router = APIRouter(prefix="/api/public", tags=["public"])
logger = logging.getLogger(__name__)


class ContactSubmission(BaseModel):
    name: str
    email: EmailStr
    subject: str
    message: str


def _contact_rate_limit(request: Request) -> None:
    _rate_limit(request, "contact")


@router.post("/contact", status_code=201)
def submit_contact(
    body: ContactSubmission,
    rate_limit: None = Depends(_contact_rate_limit),
) -> dict[str, str]:
    """Receive a contact-message from a public visitor.

    The message is dispatched through the configured notification backend.
    At rest (no SMTP) it logs at INFO; with SMTP env vars it sends email.
    """
    svc = NotificationService()
    svc.notify(
        subject=f"[Contact] {body.subject}",
        message=f"From: {body.name} <{body.email}>\n\n{body.message}",
    )
    logger.info("Public contact message accepted")
    return {"status": "accepted"}
