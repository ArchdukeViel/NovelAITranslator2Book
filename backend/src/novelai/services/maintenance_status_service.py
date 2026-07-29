"""Owner-facing projection of durable maintenance task state."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from zoneinfo import ZoneInfo

from croniter import croniter

from novelai.config.settings import settings
from novelai.services.maintenance_service import MAINTENANCE_TASK_KEYS
from novelai.services.scheduler_runtime_state_service import SchedulerRuntimeStateService


class MaintenanceStatusService:
    """Combine registered task configuration with DB-backed runtime state."""

    def __init__(self, runtime_state: SchedulerRuntimeStateService) -> None:
        self._runtime_state = runtime_state

    def status(self) -> dict[str, Any]:
        states = {
            str(item["scope_key"]): item
            for item in self._runtime_state.list_runtime_states(
                scheduler_key="maintenance",
                scope_type="task",
            )
        }
        tasks = [self._task_status(task_key, states.get(task_key)) for task_key in MAINTENANCE_TASK_KEYS]
        return {
            "status": "degraded" if any(task["state"] == "failed" for task in tasks) else "healthy",
            "tasks": tasks,
        }

    @staticmethod
    def _task_status(task_key: str, state: dict[str, Any] | None) -> dict[str, Any]:
        timezone = ZoneInfo(settings.MAINTENANCE_TIMEZONE)
        base = _aware((state or {}).get("last_finished_at"), timezone) or datetime.now(timezone)
        enabled = settings.MAINTENANCE_ENABLED
        next_eligible = croniter(settings.MAINTENANCE_SCHEDULE_CRON, base).get_next(datetime) if enabled else None
        state_value = (str(state["state"]) if state else "never_run") if enabled else "disabled"
        if state_value == "idle":
            result = "succeeded"
        elif state_value == "failed":
            result = "failed"
        else:
            result = None
        return {
            "task_key": task_key,
            "schedule": settings.MAINTENANCE_SCHEDULE_CRON,
            "timezone": settings.MAINTENANCE_TIMEZONE,
            "enabled": enabled,
            "state": state_value,
            "last_started_at": _iso((state or {}).get("last_started_at")),
            "last_finished_at": _iso((state or {}).get("last_finished_at")),
            "result": result,
            "failure_summary": (
                "Maintenance task failed; inspect redacted operator logs." if state_value == "failed" else None
            ),
            "next_eligible_at": (
                next_eligible.astimezone(UTC).isoformat().replace("+00:00", "Z") if next_eligible else None
            ),
        }


def _aware(value: Any, timezone: ZoneInfo) -> datetime | None:
    if not isinstance(value, datetime):
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC).astimezone(timezone)
    return value.astimezone(timezone)


def _iso(value: Any) -> str | None:
    if not isinstance(value, datetime):
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")
