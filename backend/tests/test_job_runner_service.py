from __future__ import annotations

import asyncio

import pytest

from novelai.services.job_runner_service import BackgroundJobRunner


class StubWorker:
    def __init__(self, jobs: list[dict[str, object]] | None = None) -> None:
        self.jobs = list(jobs or [])
        self.calls = 0
        self.processed = asyncio.Event()

    async def run_next(self, *, job_type: str | None = None) -> dict[str, object] | None:
        self.calls += 1
        if not self.jobs:
            return None
        job = self.jobs.pop(0)
        if job_type is not None:
            job["job_type"] = job_type
        self.processed.set()
        return job


@pytest.mark.asyncio
async def test_runner_start_stop_status() -> None:
    worker = StubWorker()
    runner = BackgroundJobRunner(worker, poll_seconds=0.05)

    started = await runner.start()
    stopped = await runner.stop()

    assert started["running"] is True
    assert stopped["running"] is False
    assert stopped["started_at"] is not None
    assert stopped["stopped_at"] is not None


@pytest.mark.asyncio
async def test_runner_processes_pending_jobs_in_background() -> None:
    worker = StubWorker([{"id": "job-1"}])
    runner = BackgroundJobRunner(worker, poll_seconds=0.05, job_type="crawl")

    await runner.start()
    await asyncio.wait_for(worker.processed.wait(), timeout=1.0)
    status = runner.status()
    await runner.stop()

    assert status["jobs_processed"] == 1
    assert status["last_job_id"] == "job-1"
    assert worker.calls >= 1


@pytest.mark.asyncio
async def test_runner_run_once_reports_idle() -> None:
    worker = StubWorker()
    runner = BackgroundJobRunner(worker, poll_seconds=0.05)

    job = await runner.run_once()
    status = runner.status()

    assert job is None
    assert status["idle_ticks"] == 1
    assert status["last_tick_at"] is not None
