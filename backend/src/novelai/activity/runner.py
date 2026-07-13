from __future__ import annotations

import asyncio
from contextlib import suppress
from datetime import UTC, datetime
from typing import Any

from novelai.activity.worker import ActivityWorkerService


def _utc_now_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


class BackgroundActivityRunner:
    """Continuously executes pending queued activity in the active event loop."""

    def __init__(
        self,
        worker: ActivityWorkerService,
        *,
        poll_seconds: float = 2.0,
        activity_type: str | None = None,
        job_type: str | None = None,
    ) -> None:
        self.worker = worker
        self.poll_seconds = max(0.05, float(poll_seconds))
        self.activity_type = activity_type or job_type
        self.job_type = self.activity_type
        self._task: asyncio.Task[None] | None = None
        self._stop_event: asyncio.Event | None = None
        self._started_at: str | None = None
        self._stopped_at: str | None = None
        self._last_tick_at: str | None = None
        self._last_activity_id: str | None = None
        self._last_error: str | None = None
        self._activity_processed = 0
        self._idle_ticks = 0
        self._error_count = 0

    def is_running(self) -> bool:
        return self._task is not None and not self._task.done()

    async def start(self) -> dict[str, Any]:
        if self.is_running():
            return self.status()

        self._stop_event = asyncio.Event()
        self._started_at = _utc_now_iso()
        self._stopped_at = None
        self._last_error = None
        self._task = asyncio.create_task(self._run_loop(), name="novelai-activity-runner")
        return self.status()

    async def stop(self) -> dict[str, Any]:
        if self._stop_event is not None:
            self._stop_event.set()

        task = self._task
        if task is not None and not task.done():
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task

        self._task = None
        self._stop_event = None
        self._stopped_at = _utc_now_iso()
        return self.status()

    async def run_once(self) -> dict[str, Any] | None:
        activity = await self.worker.run_next(activity_type=self.activity_type)
        self._last_tick_at = _utc_now_iso()
        if activity is None:
            self._idle_ticks += 1
            return None
        self._activity_processed += 1
        self._last_activity_id = str(activity.get("id")) if activity.get("id") is not None else None
        self._last_error = str(activity.get("error")) if activity.get("error") else None
        return activity

    async def _run_loop(self) -> None:
        assert self._stop_event is not None
        while not self._stop_event.is_set():
            try:
                activity = await self.run_once()
                if activity is None:
                    await asyncio.wait_for(self._stop_event.wait(), timeout=self.poll_seconds)
            except TimeoutError:
                continue
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                self._error_count += 1
                self._last_error = str(exc)
                try:
                    await asyncio.wait_for(self._stop_event.wait(), timeout=self.poll_seconds)
                except TimeoutError:
                    continue

    def status(self) -> dict[str, Any]:
        return {
            "running": self.is_running(),
            "poll_seconds": self.poll_seconds,
            "activity_type": self.activity_type,
            "job_type": self.activity_type,
            "started_at": self._started_at,
            "stopped_at": self._stopped_at,
            "last_tick_at": self._last_tick_at,
            "last_activity_id": self._last_activity_id,
            "last_job_id": self._last_activity_id,
            "last_error": self._last_error,
            "activity_processed": self._activity_processed,
            "jobs_processed": self._activity_processed,
            "idle_ticks": self._idle_ticks,
            "error_count": self._error_count,
        }


BackgroundJobRunner = BackgroundActivityRunner
