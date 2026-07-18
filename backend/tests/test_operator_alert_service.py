from __future__ import annotations

import logging

from novelai.config.settings import settings
from novelai.services.operator_alert_service import OperatorAlertService


class FakeSMTP:
    instances: list[FakeSMTP] = []

    def __init__(self, host: str, port: int, timeout: int) -> None:
        self.host = host
        self.port = port
        self.timeout = timeout
        self.messages = []
        self.logged_in = None
        self.starttls_called = False
        FakeSMTP.instances.append(self)

    def starttls(self, *, context) -> None:
        self.starttls_called = True

    def login(self, username: str, password: str) -> None:
        self.logged_in = (username, password)

    def send_message(self, message) -> None:
        self.messages.append(message)

    def quit(self) -> None:
        return None


def test_alert_requires_configured_failure_threshold(monkeypatch) -> None:
    monkeypatch.setattr(settings, "OPERATOR_ALERT_FAILURE_THRESHOLD", 3)
    monkeypatch.setattr(settings, "OPERATOR_ALERT_ENABLED", False)
    service = OperatorAlertService()
    assert service.send(code="database_unavailable", message="Database unavailable") is False
    assert service.send(code="database_unavailable", message="Database unavailable") is False
    assert service._failures["database_unavailable"] == 2
    service.clear("database_unavailable")
    assert "database_unavailable" not in service._failures


def test_alert_delivery_redacts_secrets_and_honors_cooldown(monkeypatch, caplog) -> None:
    FakeSMTP.instances.clear()
    monkeypatch.setattr(settings, "OPERATOR_ALERT_FAILURE_THRESHOLD", 1)
    monkeypatch.setattr(settings, "OPERATOR_ALERT_ENABLED", True)
    monkeypatch.setattr(settings, "OPERATOR_ALERT_EMAIL", "operator@example.test")
    monkeypatch.setattr(settings, "OPERATOR_ALERT_COOLDOWN_SECONDS", 3600)
    monkeypatch.setattr(settings, "SMTP_HOST", "smtp.example.test")
    monkeypatch.setattr(settings, "SMTP_PORT", 587)
    monkeypatch.setattr(settings, "SMTP_FROM_EMAIL", "alerts@example.test")
    monkeypatch.setattr(settings, "SMTP_FROM_NAME", "Dokushodo")
    monkeypatch.setattr(settings, "SMTP_STARTTLS", False)
    monkeypatch.setattr(settings, "SMTP_USE_SSL", False)
    monkeypatch.setattr(settings, "SMTP_USERNAME", None)
    monkeypatch.setattr(settings, "SMTP_PASSWORD", None)
    monkeypatch.setattr(
        "novelai.services.operator_alert_service.smtplib.SMTP",
        FakeSMTP,
    )
    caplog.set_level(logging.ERROR)
    service = OperatorAlertService()
    unsafe = "Backup failed Authorization: Bearer top-secret-token password=hunter2"

    assert service.send(code="database_backup_stale", message=unsafe) is True
    assert service.send(code="database_backup_stale", message=unsafe) is False

    assert len(FakeSMTP.instances) == 1
    assert len(FakeSMTP.instances[0].messages) == 1
    delivered = FakeSMTP.instances[0].messages[0].get_content()
    assert "top-secret-token" not in delivered
    assert "hunter2" not in delivered
    assert "[REDACTED]" in delivered
    assert "top-secret-token" not in caplog.text
    assert "hunter2" not in caplog.text
