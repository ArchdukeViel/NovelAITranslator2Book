"""Tests for the notification service and event bus (DEBT-009)."""

from __future__ import annotations

from typing import Any

import pytest
from pydantic import SecretStr

from novelai.services import notification_service as svc_mod
from novelai.services.notification_service import (
    NoopNotificationBackend,
    NotificationEventBus,
    NotificationService,
    SmtpNotificationBackend,
    get_event_bus,
    reset_event_bus,
)


@pytest.fixture
def fresh_bus(monkeypatch) -> NotificationEventBus:
    """Reset the module singleton and install a deterministic service."""
    reset_event_bus()
    captured: list[tuple[str, str, str, str | None]] = []

    class _CapturingBackend:
        def send(self, subject: str, message: str, recipient: str | None = None) -> None:
            captured.append((subject, message, recipient or "", recipient))

    service = NotificationService(backend=_CapturingBackend())
    bus = NotificationEventBus(service)
    monkeypatch.setattr(svc_mod, "_default_bus", bus)
    bus._captured = captured  # type: ignore[attr-defined]
    return bus


def test_publish_calls_default_backend_with_args(fresh_bus: NotificationEventBus):
    bus = fresh_bus
    bus.publish(
        "backup.failed",
        subject="Backup failed",
        message="Snapshot A failed at 03:30 UTC",
        recipient="ops@example.com",
    )
    captured: Any = bus._captured  # type: ignore[attr-defined]
    assert captured[-1] == ("Backup failed", "Snapshot A failed at 03:30 UTC", "ops@example.com", "ops@example.com")


def test_publish_fans_out_to_subscribers(fresh_bus: NotificationEventBus):
    bus = fresh_bus
    received: list[tuple[str, str, str, str | None]] = []

    def subscriber(event_type, subject, message, recipient):
        received.append((event_type, subject, message, recipient))

    bus.subscribe("backup.failed", subscriber)
    bus.publish(
        "backup.failed",
        subject="Backup failed",
        message="see logs",
        recipient="ops@example.com",
    )
    assert received == [("backup.failed", "Backup failed", "see logs", "ops@example.com")]


def test_publish_swallows_subscriber_errors(fresh_bus: NotificationEventBus):
    bus = fresh_bus

    def bad_subscriber(*_args: Any, **_kwargs: Any) -> None:
        raise RuntimeError("subscriber failed")

    bus.subscribe("backup.failed", bad_subscriber)
    # The bus must not raise even though the subscriber explodes.
    bus.publish(
        "backup.failed",
        subject="Backup failed",
        message="ignored",
        recipient="ops@example.com",
    )


def test_publish_rejects_unknown_event(fresh_bus: NotificationEventBus):
    bus = fresh_bus
    bus.publish(
        "unknown.event",
        subject="x",
        message="y",
        recipient="ops@example.com",
    )
    captured: Any = bus._captured  # type: ignore[attr-defined]
    assert captured == []


def test_get_event_bus_returns_singleton():
    reset_event_bus()
    bus = get_event_bus()
    again = get_event_bus()
    assert bus is again


def test_noop_backend_does_not_raise():
    backend = NoopNotificationBackend()
    # Must not raise even with edge-case recipient and message.
    backend.send("subject", "message", None)
    backend.send("subject", "message", recipient="anyone@example.com")


def test_noop_backend_logs_no_sensitive_data(caplog: pytest.LogCaptureFixture) -> None:
    """NoopBackend must not log subject, body, or recipient — only static safe text."""
    import logging

    caplog.set_level(logging.INFO, logger="novelai.services.notification_service")
    backend = NoopNotificationBackend()

    SENSITIVE_BODY = "ULTRA_PRIVATE_TRANSLATION_CONTENT_789xyz"
    SENSITIVE_SUBJECT = "Top Secret Subject 456"
    SENSITIVE_EMAIL = "secret-agent@example.com"

    backend.send(SENSITIVE_SUBJECT, SENSITIVE_BODY, SENSITIVE_EMAIL)

    # Delivery behavior preserved — no exception
    # All sensitive values must be absent from captured logs
    for record in caplog.records:
        msg = record.getMessage()
        assert SENSITIVE_BODY not in msg, f"sensitive body leaked: {msg!r}"
        assert SENSITIVE_SUBJECT not in msg, f"sensitive subject leaked: {msg!r}"
        assert SENSITIVE_EMAIL not in msg, f"sensitive email leaked: {msg!r}"


def test_smtp_backend_logs_no_sensitive_data(caplog: pytest.LogCaptureFixture, monkeypatch) -> None:
    """SmtpBackend must not log recipient address or subject — only static safe text."""
    import logging

    caplog.set_level(logging.INFO, logger="novelai.services.notification_service")

    monkeypatch.setattr(svc_mod.settings, "SMTP_HOST", "smtp.example.com")
    monkeypatch.setattr(svc_mod.settings, "SMTP_PORT", 587)
    monkeypatch.setattr(svc_mod.settings, "SMTP_USERNAME", None)
    monkeypatch.setattr(svc_mod.settings, "SMTP_PASSWORD", None)
    monkeypatch.setattr(svc_mod.settings, "SMTP_USE_SSL", False)
    monkeypatch.setattr(svc_mod.settings, "SMTP_STARTTLS", False)
    monkeypatch.setattr(svc_mod.settings, "SMTP_TIMEOUT_SECONDS", 5.0)

    class DummySMTP:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return None

        def send_message(self, m):
            pass

    monkeypatch.setattr("smtplib.SMTP", lambda *a, **kw: DummySMTP())

    backend = SmtpNotificationBackend()
    SENSITIVE_BODY = "ULTRA_PRIVATE_SMTP_CONTENT_789xyz"
    SENSITIVE_SUBJECT = "Top Secret SMTP Subject 456"
    SENSITIVE_EMAIL = "secret-smtp@example.com"

    backend.send(SENSITIVE_SUBJECT, SENSITIVE_BODY, SENSITIVE_EMAIL)

    for record in caplog.records:
        msg = record.getMessage()
        assert SENSITIVE_BODY not in msg, f"sensitive body leaked via SMTP: {msg!r}"
        assert SENSITIVE_SUBJECT not in msg, f"sensitive subject leaked via SMTP: {msg!r}"
        assert SENSITIVE_EMAIL not in msg, f"sensitive email leaked via SMTP: {msg!r}"
    assert any("SMTP notification sent" in r.getMessage() for r in caplog.records), "safe static log expected"


def test_smtp_backend_uses_starttls_when_configured(monkeypatch):
    calls: list[str] = []

    class StubSMTP:
        def __init__(self, host, port, *, timeout):
            calls.append(f"connect:{host}:{port}:{timeout}")

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def starttls(self):
            calls.append("starttls")

        def login(self, username, password):
            calls.append(f"login:{username}:{password}")

        def send_message(self, _message):
            calls.append("send")

    monkeypatch.setattr("smtplib.SMTP", StubSMTP)
    monkeypatch.setattr(svc_mod.settings, "SMTP_HOST", "smtp.example.com")
    monkeypatch.setattr(svc_mod.settings, "SMTP_PORT", 587)
    monkeypatch.setattr(svc_mod.settings, "SMTP_USERNAME", "user")
    monkeypatch.setattr(svc_mod.settings, "SMTP_PASSWORD", SecretStr("password"))
    monkeypatch.setattr(svc_mod.settings, "SMTP_USE_SSL", False)
    monkeypatch.setattr(svc_mod.settings, "SMTP_STARTTLS", True)
    monkeypatch.setattr(svc_mod.settings, "SMTP_TIMEOUT_SECONDS", 5.0)

    SmtpNotificationBackend().send("subject", "message", "ops@example.com")

    assert calls == [
        "connect:smtp.example.com:587:5.0",
        "starttls",
        "login:user:password",
        "send",
    ]


def test_smtp_backend_uses_ssl_without_starttls(monkeypatch):
    calls: list[str] = []

    class StubSMTPSSL:
        def __init__(self, host, port, *, timeout):
            calls.append(f"ssl:{host}:{port}:{timeout}")

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def login(self, *_args):
            return None

        def send_message(self, _message):
            calls.append("send")

    monkeypatch.setattr("smtplib.SMTP_SSL", StubSMTPSSL)
    monkeypatch.setattr(svc_mod.settings, "SMTP_HOST", "smtp.example.com")
    monkeypatch.setattr(svc_mod.settings, "SMTP_PORT", 465)
    monkeypatch.setattr(svc_mod.settings, "SMTP_USERNAME", None)
    monkeypatch.setattr(svc_mod.settings, "SMTP_PASSWORD", None)
    monkeypatch.setattr(svc_mod.settings, "SMTP_USE_SSL", True)
    monkeypatch.setattr(svc_mod.settings, "SMTP_STARTTLS", True)
    monkeypatch.setattr(svc_mod.settings, "SMTP_TIMEOUT_SECONDS", 5.0)

    SmtpNotificationBackend().send("subject", "message", "ops@example.com")

    assert calls == ["ssl:smtp.example.com:465:5.0", "send"]
