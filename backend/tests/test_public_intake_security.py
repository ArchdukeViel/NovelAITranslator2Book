from __future__ import annotations

import logging

import pytest
from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from novelai.api.routers.public_contact import ContactSubmission, _dispatch_contact
from novelai.api.routers.public_dmca import DmcaSubmission
from novelai.db.base import Base
from novelai.services.notification_service import NotificationService
from novelai.services.takedown_service import TakedownService


def test_contact_submission_is_bounded_and_rejects_control_characters() -> None:
    with pytest.raises(ValidationError):
        ContactSubmission(
            name="visitor\nname",
            email="visitor@example.com",
            subject="Question",
            message="A valid message",
        )

    with pytest.raises(ValidationError):
        ContactSubmission(
            name="visitor",
            email="visitor@example.com",
            subject="Question",
            message="x" * 10_001,
        )


def test_dmca_submission_requires_http_url_and_bounds_url_length() -> None:
    with pytest.raises(ValidationError):
        DmcaSubmission.model_validate(
            {
                "complainant_name": "Rights Holder",
                "complainant_email": "rights@example.com",
                "infringing_url": "ftp://example.com/work",
                "description": "Copyrighted work",
                "signature": "Rights Holder",
            }
        )

    with pytest.raises(ValidationError):
        DmcaSubmission.model_validate(
            {
                "complainant_name": "Rights Holder",
                "complainant_email": "rights@example.com",
                "infringing_url": f"https://example.com/{'x' * 2_050}",
                "description": "Copyrighted work",
                "signature": "Rights Holder",
            }
        )


def test_contact_delivery_failure_is_isolated_from_request_processing(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    def fail(*_args: object, **_kwargs: object) -> None:
        raise RuntimeError("smtp unavailable")

    monkeypatch.setattr(NotificationService, "notify", fail)
    with caplog.at_level(logging.WARNING):
        _dispatch_contact("[Contact] Question", "message")

    assert "Public contact notification delivery failed" in caplog.text


def test_takedown_submission_does_not_log_untrusted_url(caplog: pytest.LogCaptureFixture) -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    try:
        with Session(engine) as session:
            untrusted_url = "https://attacker.example/notice?id=raw-secret"
            TakedownService(session).submit(
                complainant_name="Rights Holder",
                complainant_email="rights@example.com",
                infringing_url=untrusted_url,
                description="Copyrighted work",
                signature="Rights Holder",
            )
            session.commit()

        assert untrusted_url not in caplog.text
    finally:
        Base.metadata.drop_all(engine)
