from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import Any

from novelai.services.job_worker_service import JobWorkerService


def _utc_now_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


class BackgroundJobRunner:
    """Continuously executes pending queued jobs in the active event loop."""

    def __init__(
        self,
        worker: JobWorkerService,
        *,
        poll_seconds: float = 2.0,
        job_type: str | None = None,
    ) -> None:
        self.worker = worker
        self.poll_seconds = max(0.05, float(poll_seconds))
        self.job_type = job_type
        self._task: asyncio.Task[None] | None = None
        self._stop_event: asyncio.Event | None = None
        self._started_at: str | None = None
        self._stopped_at: str | None = None
        self._last_tick_at: str | None = None
        self._last_job_id: str | None = None
        self._last_error: str | None = None
        self._jobs_processed = 0
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
        self._task = asyncio.create_task(self._run_loop(), name="novelai-job-runner")
        return self.status()

    async def stop(self) -> dict[str, Any]:
        if self._stop_event is not None:
            self._stop_event.set()

        task = self._task
        if task is not None and not task.done():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

        self._task = None
        self._stop_event = None
        self._stopped_at = _utc_now_iso()
        return self.status()

    async def run_once(self) -> dict[str, Any] | None:
        job = await self.worker.run_next(job_type=self.job_type)
        self._last_tick_at = _utc_now_iso()
        if job is None:
            self._idle_ticks += 1
            return None
        self._jobs_processed += 1
        self._last_job_id = str(job.get("id")) if job.get("id") is not None else None
        self._last_error = str(job.get("error")) if job.get("error") else None
        return job

    async def _run_loop(self) -> None:
        assert self._stop_event is not None
        while not self._stop_event.is_set():
            try:
                job = await self.run_once()
                if job is None:
                    await asyncio.wait_for(self._stop_event.wait(), timeout=self.poll_seconds)
            except TimeoutError:
                continue
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # noqa: BLE001 - runner must survive job-layer failures.
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
            "job_type": self.job_type,
            "started_at": self._started_at,
            "stopped_at": self._stopped_at,
            "last_tick_at": self._last_tick_at,
            "last_job_id": self._last_job_id,
            "last_error": self._last_error,
            "jobs_processed": self._jobs_processed,
            "idle_ticks": self._idle_ticks,
            "error_count": self._error_count,
        }
