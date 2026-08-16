"""Public contact / support intake endpoint.

Accepts visitor messages and hands them to the notification service.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, BackgroundTasks, Depends, Request
from pydantic import BaseModel, EmailStr, Field, field_validator

from novelai.api.routers.dependencies import _rate_limit
from novelai.services.notification_service import NotificationService

router = APIRouter(prefix="/api/public", tags=["public"])
logger = logging.getLogger(__name__)


class ContactSubmission(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    email: EmailStr
    subject: str = Field(min_length=1, max_length=200)
    message: str = Field(min_length=1, max_length=10_000)

    @field_validator("name", "subject")
    @classmethod
    def _single_line_text(cls, value: str) -> str:
        value = value.strip()
        if not value or any(ord(char) < 32 for char in value):
            raise ValueError("Must contain printable single-line text")
        return value

    @field_validator("message")
    @classmethod
    def _message_text(cls, value: str) -> str:
        value = value.strip()
        if not value or any(ord(char) < 32 and char not in "\n\t" for char in value):
            raise ValueError("Must contain printable text")
        return value


def _contact_rate_limit(request: Request) -> None:
    _rate_limit(request, "contact")


def _dispatch_contact(subject: str, message: str) -> None:
    try:
        NotificationService().notify(subject=subject, message=message)
    except Exception:
        logger.warning("Public contact notification delivery failed")


@router.post("/contact", status_code=201)
def submit_contact(
    body: ContactSubmission,
    background_tasks: BackgroundTasks,
    rate_limit: None = Depends(_contact_rate_limit),
) -> dict[str, str]:
    """Receive a contact-message from a public visitor.

    The message is dispatched through the configured notification backend.
    At rest (no SMTP) it logs at INFO; with SMTP env vars it sends email.
    """
    background_tasks.add_task(
        _dispatch_contact,
        f"[Contact] {body.subject}",
        f"From: {body.name} <{body.email}>\n\n{body.message}",
    )
    logger.info("Public contact message accepted")
    return {"status": "accepted"}
