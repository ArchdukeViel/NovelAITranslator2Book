from __future__ import annotations

import asyncio

import pytest

from novelai.activity.runner import BackgroundActivityRunner


class StubWorker:
    def __init__(self, activity: list[dict[str, object]] | None = None) -> None:
        self.activity = list(activity or [])
        self.calls = 0
        self.processed = asyncio.Event()
        self.shutdown_calls = 0

    async def run_next(self, *, activity_type: str | None = None) -> dict[str, object] | None:
        self.calls += 1
        if not self.activity:
            return None
        activity = self.activity.pop(0)
        if activity_type is not None:
            activity["activity_type"] = activity_type
        self.processed.set()
        return activity

    async def shutdown(self, timeout_seconds: float = 30.0) -> bool:
        self.shutdown_calls += 1
        return timeout_seconds >= 0


@pytest.mark.asyncio
async def test_runner_start_stop_status() -> None:
    worker = StubWorker()
    runner = BackgroundActivityRunner(worker, poll_seconds=0.05)  # type: ignore[arg-type]

    started = await runner.start()
    stopped = await runner.stop()

    assert started["running"] is True
    assert stopped["running"] is False
    assert stopped["started_at"] is not None
    assert stopped["stopped_at"] is not None
    assert worker.shutdown_calls == 1


@pytest.mark.asyncio
async def test_runner_processes_pending_activity_in_background() -> None:
    worker = StubWorker([{"activity_id": "activity-1"}])
    runner = BackgroundActivityRunner(worker, poll_seconds=0.05, activity_type="crawl")  # type: ignore[arg-type]

    await runner.start()
    await asyncio.wait_for(worker.processed.wait(), timeout=1.0)
    status = runner.status()
    await runner.stop()

    assert status["activity_processed"] == 1
    assert status["last_activity_id"] == "activity-1"
    assert worker.calls >= 1


@pytest.mark.asyncio
async def test_runner_run_once_reports_idle() -> None:
    worker = StubWorker()
    runner = BackgroundActivityRunner(worker, poll_seconds=0.05)  # type: ignore[arg-type]

    activity = await runner.run_once()
    status = runner.status()

    assert activity is None
    assert status["idle_ticks"] == 1
    assert status["last_tick_at"] is not None


def test_runner_idle_poll_backoff_is_bounded_and_resets() -> None:
    runner = BackgroundActivityRunner(StubWorker(), poll_seconds=2.0)  # type: ignore[arg-type]

    assert [runner.next_idle_poll_seconds() for _ in range(5)] == [5.0, 10.0, 20.0, 30.0, 30.0]

    runner._reset_idle_backoff()
    assert runner.next_idle_poll_seconds() == 5.0
