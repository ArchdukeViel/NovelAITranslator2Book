"""Regression: activity worker must read crawl counts from the nested
``metadata.crawl_result`` envelope, not the top-level ``result_metadata``.

Before this fix the worker computed ``has_errors = result_metadata.get("failed", 0) > 0
or result_metadata.get("terminal_status") in (...)`` while ``_run_crawl_activity``
returns ``{"chapters": [...], "crawl_result": {...}}``; the path silently produced
``has_errors == False`` for every crawl so partial-failure crawls were never
recorded as source-health failures.
"""

from __future__ import annotations

import json
import shutil
from typing import Any
from uuid import uuid4

import pytest

from novelai.activity.queue import ActivityQueueService
from novelai.activity.worker import ActivityWorkerService
from novelai.config.settings import settings
from novelai.core.platform import CrawlJobKind, JobStatus
from tests.conftest import TESTS_TMP_ROOT


class _StubOrchestrator:
    def __init__(self) -> None:
        self.scrape_calls: list[dict[str, Any]] = []

    async def scrape_chapters(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
        self.scrape_calls.append({"args": args, "kwargs": kwargs})
        return {}


@pytest.fixture
def activity_env(monkeypatch):
    TESTS_TMP_ROOT.mkdir(parents=True, exist_ok=True)
    data_dir = TESTS_TMP_ROOT / f"activity_crawl_{uuid4().hex}"
    data_dir.mkdir(parents=True, exist_ok=False)

    monkeypatch.setattr(settings, "WEB_CORS_ORIGINS", ["http://localhost"])
    log_store = ActivityQueueService(data_dir)
    orchestrator = _StubOrchestrator()
    worker = ActivityWorkerService(activity_log=log_store, orchestrator=orchestrator)  # type: ignore[arg-type]

    try:
        yield {
            "data_dir": data_dir,
            "log_store": log_store,
            "orchestrator": orchestrator,
            "worker": worker,
        }
    finally:
        shutil.rmtree(data_dir, ignore_errors=True)


def _create_crawl_activity(log_store: ActivityQueueService) -> dict[str, Any]:
    return log_store.create_crawl_activity(
        novel_id=f"novel-{uuid4().hex}",
        source_key="stub",
        source_url="https://example.com/stub",
        chapters="1",
        kind=CrawlJobKind.CHAPTERS,
        metadata={"activity_subtype": "metadata"},
    )


def _read_source_health(log_store: ActivityQueueService, source_key: str) -> dict[str, Any] | None:
    """Read the persisted source-health record if any; ``None`` otherwise.

    Matches the JSON shape ``ActivityQueueService._load_source_health`` emits.
    """

    path = log_store.source_health_file
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    return data.get(source_key) if isinstance(data, dict) else None


@pytest.mark.asyncio
async def test_partial_failure_crawl_records_source_health_failure(activity_env) -> None:
    """A crawl that failed 3 of 10 chapters must produce a source-health
    failure record with the actual failed count surfaced in the error
    message (Blocker E: nested crawl_result is the source of truth).
    """

    worker = activity_env["worker"]
    log_store = activity_env["log_store"]

    activity = _create_crawl_activity(log_store)
    activity_id = activity["activity_id"]
    source_key = activity["source_key"]

    async def _stub_run_crawl_activity(self, activity: dict[str, Any]) -> dict[str, Any]:
        return {
            "chapters": activity.get("chapters"),
            "crawl_result": {
                "succeeded": 7,
                "skipped": 0,
                "failed": 3,
                "failures": [],
                "image_download_failures": 0,
                "terminal_status": "completed_with_errors",
            },
        }

    # Patch the unbound method on the class so ``self`` binds correctly.
    _original_method = ActivityWorkerService._run_crawl_activity
    ActivityWorkerService._run_crawl_activity = _stub_run_crawl_activity  # type: ignore[method-assign]
    try:
        # Drive the worker; the activity must complete.
        result = await worker.run_activity(activity_id)
        assert result is not None
        assert result["status"] == JobStatus.COMPLETED.value
    finally:
        # Restore the original method to avoid leaking across tests.
        ActivityWorkerService._run_crawl_activity = _original_method  # type: ignore[method-assign]

    health = _read_source_health(log_store, source_key)
    assert health is not None, "source_health must be recorded after a crawl activity"
    assert health.get("failure_count", 0) == 1
    assert health.get("success_count", 0) == 0
    last_error = health.get("last_error")
    assert isinstance(last_error, str) and "3 failed chapters" in last_error


@pytest.mark.asyncio
async def test_clean_crawl_records_source_health_success(activity_env) -> None:
    """A crawl with zero failed chapters must record a success, even though
    the previous (broken) implementation also recorded success here — the
    success path is preserved while the failure path is fixed."""

    worker = activity_env["worker"]
    log_store = activity_env["log_store"]

    activity = _create_crawl_activity(log_store)
    activity_id = activity["activity_id"]
    source_key = activity["source_key"]

    async def _stub_run_crawl_activity(self, activity: dict[str, Any]) -> dict[str, Any]:
        return {
            "chapters": activity.get("chapters"),
            "crawl_result": {
                "succeeded": 10,
                "skipped": 0,
                "failed": 0,
                "failures": [],
                "image_download_failures": 0,
                "terminal_status": "completed",
            },
        }

    _original_method = ActivityWorkerService._run_crawl_activity
    ActivityWorkerService._run_crawl_activity = _stub_run_crawl_activity  # type: ignore[method-assign]
    try:
        result = await worker.run_activity(activity_id)
        assert result is not None
        assert result["status"] == JobStatus.COMPLETED.value
    finally:
        ActivityWorkerService._run_crawl_activity = _original_method  # type: ignore[method-assign]

    health = _read_source_health(log_store, source_key)
    assert health is not None
    assert health.get("success_count", 0) == 1
    assert health.get("failure_count", 0) == 0
