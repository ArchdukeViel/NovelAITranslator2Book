from __future__ import annotations

from novelai.config.settings import settings
from novelai.services.operator_alert_service import OperatorAlertService


def test_alert_requires_configured_failure_threshold(monkeypatch) -> None:
    monkeypatch.setattr(settings, "OPERATOR_ALERT_FAILURE_THRESHOLD", 3)
    monkeypatch.setattr(settings, "OPERATOR_ALERT_ENABLED", False)
    service = OperatorAlertService()
    assert service.send(code="database_unavailable", message="Database unavailable") is False
    assert service.send(code="database_unavailable", message="Database unavailable") is False
    assert service._failures["database_unavailable"] == 2
    service.clear("database_unavailable")
    assert "database_unavailable" not in service._failures
