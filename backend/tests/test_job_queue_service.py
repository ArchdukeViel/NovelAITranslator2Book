from __future__ import annotations

import json
import shutil
from uuid import uuid4

import pytest

from novelai.core.platform import JobStatus
from novelai.activity.queue import ActivityQueueService
from tests.conftest import TESTS_TMP_ROOT


@pytest.fixture
def activity_log() -> ActivityQueueService:
    TESTS_TMP_ROOT.mkdir(parents=True, exist_ok=True)
    data_dir = TESTS_TMP_ROOT / f"jobs_{uuid4().hex}"
    data_dir.mkdir(parents=True, exist_ok=False)
    service = ActivityQueueService(data_dir)
    yield service
    shutil.rmtree(data_dir, ignore_errors=True)


def test_create_and_load_crawl_activity(activity_log: ActivityQueueService) -> None:
    activity = activity_log.create_crawl_activity(
        novel_id="novel-1",
        source_key="syosetu_ncode",
        kind="metadata",
        chapters=None,
        source_url="https://ncode.syosetu.com/n1234ab/",
    )

    loaded = activity_log.get_activity(activity["id"])

    assert loaded is not None
    assert loaded["type"] == "crawl"
    assert loaded["kind"] == "metadata"
    assert loaded["status"] == "pending"
    assert loaded["source_key"] == "syosetu_ncode"


def test_uses_activity_log_folder_and_migrates_legacy_jobs() -> None:
    TESTS_TMP_ROOT.mkdir(parents=True, exist_ok=True)
    data_dir = TESTS_TMP_ROOT / f"activity_log_{uuid4().hex}"
    legacy_dir = data_dir / "jobs"
    legacy_dir.mkdir(parents=True, exist_ok=False)
    legacy_job = {
        "id": "crawl_legacy",
        "type": "crawl",
        "kind": "metadata",
        "novel_id": "n0813kx",
        "source_key": "novel18_syosetu",
        "chapters": None,
        "status": "completed",
        "created_at": "2026-06-03T00:00:00Z",
        "started_at": None,
        "finished_at": "2026-06-03T00:01:00Z",
        "retry_count": 0,
        "error": None,
        "metadata": {},
    }
    (legacy_dir / "queue.json").write_text(json.dumps([legacy_job]), encoding="utf-8")
    (legacy_dir / "source_health.json").write_text(
        json.dumps({"novel18_syosetu": {"source_key": "novel18_syosetu", "success_count": 1}}),
        encoding="utf-8",
    )

    try:
        service = ActivityQueueService(data_dir)

        assert service.jobs_dir.name == "activity_log"
        assert (data_dir / "activity_log" / "queue.json").exists()
        assert (data_dir / "activity_log" / "source_health.json").exists()
        assert not (legacy_dir / "queue.json").exists()
        assert service.get_activity("crawl_legacy") == legacy_job
        assert service.get_source_health("novel18_syosetu") is not None
    finally:
        shutil.rmtree(data_dir, ignore_errors=True)


def test_create_translation_activity_and_filter(activity_log: ActivityQueueService) -> None:
    activity_log.create_crawl_activity(novel_id="novel-1", source_key="kakuyomu", kind="chapters")
    translation = activity_log.create_translation_activity(
        novel_id="novel-1",
        kind="translate",
        chapters="1-3",
        provider="openai",
        model="gpt-5.4",
    )

    filtered = activity_log.list_activity(activity_type="translation", status=JobStatus.PENDING)

    assert filtered == [translation]


def test_update_activity_status_records_lifecycle_fields(activity_log: ActivityQueueService) -> None:
    activity = activity_log.create_translation_activity(novel_id="novel-1")

    running = activity_log.update_activity_status(activity["id"], "running")
    failed = activity_log.update_activity_status(activity["id"], "failed", error="source timeout", metadata={"attempt": 1})

    assert running is not None
    assert running["started_at"] is not None
    assert failed is not None
    assert failed["status"] == "failed"
    assert failed["finished_at"] is not None
    assert failed["retry_count"] == 1
    assert failed["error"] == "source timeout"
    assert failed["metadata"]["attempt"] == 1


def test_retry_activity_resets_failed_activity_and_preserves_previous_error(activity_log: ActivityQueueService) -> None:
    activity = activity_log.create_translation_activity(novel_id="novel-1", metadata={"current_stage": "TranslateStage"})
    failed = activity_log.update_activity_status(
        activity["id"],
        "failed",
        error="provider timeout",
        metadata={"failure_code": "TRANSLATION_ACTIVITY_FAILED"},
    )

    retried = activity_log.retry_activity(activity["id"])

    assert failed is not None
    assert retried is not None
    assert retried["status"] == "pending"
    assert retried["started_at"] is None
    assert retried["finished_at"] is None
    assert retried["error"] is None
    assert retried["retry_count"] == 2
    assert retried["metadata"]["current_stage"] == "queued"
    assert retried["metadata"]["retry_history"][0]["status"] == "failed"
    assert retried["metadata"]["retry_history"][0]["error"] == "provider timeout"
    assert retried["metadata"]["retry_history"][0]["metadata"]["failure_code"] == "TRANSLATION_ACTIVITY_FAILED"


def test_retry_activity_accepts_cancelled_activity(activity_log: ActivityQueueService) -> None:
    activity = activity_log.create_translation_activity(novel_id="novel-1")
    cancelled = activity_log.update_activity_status(activity["id"], "cancelled", error="cancelled by owner")

    retried = activity_log.retry_activity(activity["id"])

    assert cancelled is not None
    assert retried is not None
    assert retried["status"] == "pending"
    assert retried["error"] is None
    assert retried["retry_count"] == 1


def test_next_pending_activity_returns_oldest_pending_by_type(activity_log: ActivityQueueService) -> None:
    first = activity_log.create_crawl_activity(novel_id="novel-1", source_key="syosetu_ncode")
    activity_log.create_translation_activity(novel_id="novel-1")

    pending = activity_log.next_pending_activity(activity_type="crawl")

    assert pending is not None
    assert pending["id"] == first["id"]


def test_record_source_health_tracks_success_and_failure(activity_log: ActivityQueueService) -> None:
    activity_log.record_source_health("syosetu_ncode", success=True)
    failed = activity_log.record_source_health("syosetu_ncode", success=False, error="timeout")

    loaded = activity_log.get_source_health("syosetu_ncode")
    all_sources = activity_log.list_source_health()

    assert loaded is not None
    assert loaded["success_count"] == 1
    assert loaded["failure_count"] == 1
    assert loaded["last_error"] == "timeout"
    assert failed == loaded
    assert all_sources == [loaded]
