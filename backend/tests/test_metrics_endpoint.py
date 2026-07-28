"""Tests for the Prometheus /metrics endpoint (DEBT-040)."""

from __future__ import annotations

from typing import Any

import pytest

import novelai.api.routers.metrics as metrics_mod
from novelai.api.routers.metrics import get_metrics


class _StubActivityLog:
    """Minimal stand-in for ``container.activity_log`` used by the metrics handler."""

    def __init__(self, activities: list[dict]) -> None:
        self._activities = activities

    def list_activity(self) -> list[dict]:
        return list(self._activities)


def _stub_log(activities: list[dict]) -> _StubActivityLog:
    return _StubActivityLog(activities)


def _patch_log(monkeypatch: pytest.MonkeyPatch, activities: list[dict]) -> _StubActivityLog:
    stub = _stub_log(activities)
    monkeypatch.setattr(metrics_mod, "_load_container_activity_log", lambda: stub)
    return stub


def _parse_prometheus_metrics(body: str) -> dict[str, float]:
    """Parse a Prometheus text-format payload into a flat name -> value dict.

    Lines starting with ``#`` are metadata; metric lines are either
    ``name value`` or ``name{labels} value``. Used only by the focused
    tests in this module.
    """
    result: dict[str, float] = {}
    for line in body.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "{" in line:
            _, rest = line.split("{", 1)
            value = rest.split("}", 1)[1].strip()
        else:
            _, _, value = line.partition(" ")
        try:
            result[line.split(" ")[0] if "{" not in line else line.split("{")[0]] = float(value)
        except ValueError:
            continue
    return result


def test_metrics_handler_emits_process_gauges():
    response = get_metrics()
    assert response.media_type == "text/plain; version=0.0.4"
    body = response.body.decode("utf-8") if isinstance(response.body, bytes) else str(response.body)
    metrics = _parse_prometheus_metrics(body)

    assert "novelai_process_uptime_seconds" in metrics
    assert "novelai_cpu_count_total" in metrics
    assert "novelai_active_threads_count" in metrics
    assert "novelai_gc_tracked_objects_count" in metrics
    assert metrics["novelai_process_uptime_seconds"] >= 0.0
    assert metrics["novelai_cpu_count_total"] >= 0


def test_metrics_handler_emits_activity_counts(monkeypatch):
    _patch_log(
        monkeypatch,
        [
            {"activity_id": "a1", "status": "pending"},
            {"activity_id": "a2", "status": "queued"},
            {"activity_id": "a3", "status": "running"},
            {"activity_id": "a4", "status": "completed"},
            {"activity_id": "a5", "status": "failed"},
            {"activity_id": "a6", "status": "cancelled"},
        ],
    )

    response = get_metrics()
    body = response.body.decode("utf-8") if isinstance(response.body, bytes) else str(response.body)
    metrics = _parse_prometheus_metrics(body)

    assert metrics["novelai_activity_pending_count"] == 1.0
    assert metrics["novelai_activity_queued_count"] == 1.0
    assert metrics["novelai_activity_running_count"] == 1.0
    assert metrics["novelai_activity_completed_count"] == 1.0
    assert metrics["novelai_activity_failed_count"] == 1.0
    assert metrics["novelai_activity_cancelled_count"] == 1.0


def test_metrics_handler_emits_failures_per_source_label(monkeypatch):
    _patch_log(
        monkeypatch,
        [
            {"activity_id": "a1", "status": "failed", "metadata": {"source_key": "syosetu_ncode"}},
            {"activity_id": "a2", "status": "failed", "metadata": {"source_key": "syosetu_ncode"}},
            {"activity_id": "a3", "status": "failed", "metadata": {"source_key": "kakuyomu"}},
        ],
    )

    response = get_metrics()
    body = response.body.decode("utf-8") if isinstance(response.body, bytes) else str(response.body)

    assert 'novelai_activity_failures_per_source{source_key="syosetu_ncode"} 2' in body
    assert 'novelai_activity_failures_per_source{source_key="kakuyomu"} 1' in body


def test_metrics_handler_never_leaks_secrets(monkeypatch):
    _patch_log(
        monkeypatch,
        [
            {
                "activity_id": "a1",
                "status": "failed",
                "metadata": {
                    "source_key": "syosetu_ncode",
                    "api_key": "sk-secret-value-must-not-leak",
                    "email": "private@example.com",
                },
            },
        ],
    )

    response = get_metrics()
    body = response.body.decode("utf-8") if isinstance(response.body, bytes) else str(response.body)

    assert "sk-secret-value-must-not-leak" not in body
    assert "private@example.com" not in body
    assert "api_key" not in body


def test_metrics_handler_fails_closed_when_container_unavailable(monkeypatch):
    """If the runtime container raises, the endpoint must still return gauges."""
    monkeypatch.setattr(metrics_mod, "_load_container_activity_log", lambda: None)

    response = get_metrics()
    body = response.body.decode("utf-8") if isinstance(response.body, bytes) else str(response.body)

    # Process gauges still present; activity counts default to 0.
    assert "novelai_process_uptime_seconds" in body
    assert "novelai_activity_pending_count 0" in body
    assert "novelai_activity_failed_count 0" in body


def test_metrics_handler_fails_closed_when_activity_log_raises(monkeypatch):
    """An exception in the activity log must not break /metrics."""

    class _ExplodingLog:
        def list_activity(self) -> list[dict[str, Any]]:
            raise RuntimeError("storage unavailable")

    monkeypatch.setattr(metrics_mod, "_load_container_activity_log", lambda: _ExplodingLog())

    response = get_metrics()
    body = response.body.decode("utf-8") if isinstance(response.body, bytes) else str(response.body)

    # Process gauges still present; activity counts default to 0.
    assert "novelai_process_uptime_seconds" in body
    assert "novelai_activity_failed_count 0" in body
