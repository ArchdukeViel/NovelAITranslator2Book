from __future__ import annotations

from datetime import UTC, datetime

import pytest

from novelai.config.settings import settings
from novelai.services.maintenance_service import MAINTENANCE_TASK_KEYS
from novelai.services.maintenance_status_service import MaintenanceStatusService


class StubRuntimeState:
    def __init__(self, states: list[dict] | None = None) -> None:
        self.states = states or []

    def list_runtime_states(self, **filters):
        assert filters == {"scheduler_key": "maintenance", "scope_type": "task"}
        return self.states


@pytest.fixture(autouse=True)
def enable_maintenance(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "MAINTENANCE_ENABLED", True)


def test_status_lists_every_registered_task_as_never_run() -> None:
    result = MaintenanceStatusService(StubRuntimeState()).status()  # type: ignore[arg-type]

    assert result["status"] == "healthy"
    assert [task["task_key"] for task in result["tasks"]] == list(MAINTENANCE_TASK_KEYS)
    assert all(task["state"] == "never_run" for task in result["tasks"])
    assert all(task["next_eligible_at"] for task in result["tasks"])


def test_status_uses_db_state_and_redacts_failure() -> None:
    state = {
        "scope_key": MAINTENANCE_TASK_KEYS[0],
        "state": "failed",
        "last_started_at": datetime(2026, 7, 29, 1, tzinfo=UTC),
        "last_finished_at": datetime(2026, 7, 29, 2, tzinfo=UTC),
        "error_message": "C:/private/path secret=value",
        "locked_by": "private-host",
    }

    result = MaintenanceStatusService(StubRuntimeState([state])).status()  # type: ignore[arg-type]
    failed = result["tasks"][0]

    assert result["status"] == "degraded"
    assert failed["result"] == "failed"
    assert failed["failure_summary"] == "Maintenance task failed; inspect redacted operator logs."
    assert "private" not in str(result)
    assert "secret" not in str(result)
