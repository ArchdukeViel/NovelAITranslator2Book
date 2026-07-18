"""Redacted operator alerts with process-local cooldown protection."""

from __future__ import annotations

import logging
import smtplib
import ssl
from datetime import UTC, datetime, timedelta
from email.message import EmailMessage
from email.utils import formataddr

from novelai.config.settings import settings
from novelai.core.security import redact_secret_text

logger = logging.getLogger(__name__)


class OperatorAlertService:
    def __init__(self) -> None:
        self._last_sent: dict[str, datetime] = {}
        self._failures: dict[str, int] = {}

    def send(self, *, code: str, message: str) -> bool:
        safe_message = redact_secret_text(message)
        logger.error("operator_alert code=%s message=%s", code, safe_message[:200])
        failures = self._failures.get(code, 0) + 1
        self._failures[code] = failures
        if failures < settings.OPERATOR_ALERT_FAILURE_THRESHOLD:
            return False
        if not settings.OPERATOR_ALERT_ENABLED or not settings.OPERATOR_ALERT_EMAIL:
            return False
        now = datetime.now(UTC)
        last_sent = self._last_sent.get(code)
        if last_sent and now - last_sent < timedelta(seconds=settings.OPERATOR_ALERT_COOLDOWN_SECONDS):
            return False
        if not settings.SMTP_HOST or not settings.SMTP_FROM_EMAIL:
            return False
        email = EmailMessage()
        email["Subject"] = f"[Dokushodo] {code}"
        email["From"] = formataddr((settings.SMTP_FROM_NAME, settings.SMTP_FROM_EMAIL))
        email["To"] = settings.OPERATOR_ALERT_EMAIL
        email.set_content(safe_message[:2000])
        factory = smtplib.SMTP_SSL if settings.SMTP_USE_SSL else smtplib.SMTP
        try:
            smtp = factory(settings.SMTP_HOST, settings.SMTP_PORT, timeout=settings.SMTP_TIMEOUT_SECONDS)
            try:
                if settings.SMTP_STARTTLS and not settings.SMTP_USE_SSL:
                    smtp.starttls(context=ssl.create_default_context())
                password = settings.SMTP_PASSWORD.get_secret_value() if settings.SMTP_PASSWORD else None
                if settings.SMTP_USERNAME and password:
                    smtp.login(settings.SMTP_USERNAME, password)
                smtp.send_message(email)
            finally:
                smtp.quit()
        except Exception as exc:
            logger.warning("operator_alert_delivery_failed code=%s type=%s", code, exc.__class__.__name__)
            return False
        self._last_sent[code] = now
        return True

    def clear(self, code: str) -> None:
        self._failures.pop(code, None)
