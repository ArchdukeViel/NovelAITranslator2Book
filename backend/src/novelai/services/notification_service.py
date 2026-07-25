"""Pluggable notification service with a configurable backend.

Default: ``NoopNotificationBackend`` logs at INFO level.
In production, swap to an SMTP backend by providing ``SMTP_*`` settings.
"""

from __future__ import annotations

import logging
from typing import Protocol

from novelai.config.settings import settings

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Backend protocol
# ---------------------------------------------------------------------------


class NotificationBackend(Protocol):
    """Minimal notification contract.

    Implementations must handle their own batching, rate-limiting, and
    credential management.
    """

    def send(self, subject: str, message: str, recipient: str | None = None) -> None:
        """Deliver a notification."""


# ---------------------------------------------------------------------------
# Noop backend  (default)
# ---------------------------------------------------------------------------


class NoopNotificationBackend:
    """Default backend: log at INFO.

    Records the notification to the application log.  Replace with a
    real SMTP/HTTP backend when production credentials are configured.
    """

    def send(self, subject: str, message: str, recipient: str | None = None) -> None:
        logger.info(
            "NOTIFICATION [%s] to=%s\n%s",
            subject,
            recipient or "(default)",
            message,
        )


# ---------------------------------------------------------------------------
# SMTP backend   (used only when SMTP_HOST is set)
# ---------------------------------------------------------------------------


class SmtpNotificationBackend:
    """SMTP-based delivery backend.

    Reads SMTP_* settings at send-time so environment changes take effect
    without a restart.

    ponytail: No TLS upgrade, queue, or retry.  Add smtplib retry wrapper
    when production use requires reliability.
    """

    def __init__(self) -> None:
        host = settings.SMTP_HOST
        if not host:
            raise ValueError("SMTP_HOST is not configured")
        self._host: str = host
        self._port = settings.SMTP_PORT
        self._username = settings.SMTP_USERNAME
        pwd_secret = settings.SMTP_PASSWORD
        self._password: str | None = pwd_secret.get_secret_value() if pwd_secret else None  # type: ignore[reportConstantRedefinition]
        self._from_addr = settings.SMTP_FROM_ADDRESS

    def send(self, subject: str, message: str, recipient: str | None = None) -> None:
        import smtplib
        from email.message import EmailMessage

        to = recipient or self._from_addr
        msg = EmailMessage()
        msg.set_content(message)
        msg["Subject"] = subject
        msg["From"] = self._from_addr
        msg["To"] = to

        with smtplib.SMTP(self._host, self._port) as smtp:
            if self._username and self._password:
                smtp.login(self._username, self._password)
            smtp.send_message(msg)

        logger.info("SMTP notification sent to %s: %s", to, subject)


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------


def _detect_backend() -> NotificationBackend:
    """Return ``SmtpNotificationBackend`` if SMTP is configured, else noop."""
    if settings.SMTP_HOST and settings.SMTP_PORT:
        return SmtpNotificationBackend()
    return NoopNotificationBackend()


class NotificationService:
    """High-level notification dispatcher.

    Usage::

        svc = NotificationService()
        svc.notify("Backup failed", "…", recipient="admin@…")
    """

    def __init__(self, backend: NotificationBackend | None = None) -> None:
        self._backend = backend if backend is not None else _detect_backend()

    def notify(self, subject: str, message: str, recipient: str | None = None) -> None:
        """Send a notification through the configured back-end."""
        self._backend.send(subject, message, recipient)
