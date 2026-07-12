from __future__ import annotations

import json
import shutil
from collections.abc import Generator
from uuid import uuid4

import pytest

from novelai.activity.queue import ActivityQueueService
from novelai.core.platform import JobStatus
from tests.conftest import TESTS_TMP_ROOT


@pytest.fixture
def activity_log() -> Generator[ActivityQueueService]:
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
        provider="gemini",
        model="gemini-2.0-flash",
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


def test_prune_activity_log_handles_missing_queue_file(activity_log: ActivityQueueService) -> None:
    result = activity_log.prune_activity_log(dry_run=False)

    assert result == {"dry_run": False, "deleted": 0, "candidates": [], "kept": 0}


def test_prune_activity_log_dry_run_reports_candidates_without_deleting(activity_log: ActivityQueueService) -> None:
    activity_log._persist_activity(
        [
            {
                "id": "completed_old",
                "status": "completed",
                "created_at": "2026-06-01T00:00:00Z",
                "finished_at": "2026-06-01T00:01:00Z",
            },
            {
                "id": "completed_new",
                "status": "completed",
                "created_at": "2026-06-02T00:00:00Z",
                "finished_at": "2026-06-02T00:01:00Z",
            },
            {
                "id": "pending_active",
                "status": "pending",
                "created_at": "2026-06-03T00:00:00Z",
            },
        ]
    )

    result = activity_log.prune_activity_log(keep_completed=1, keep_failed=1, dry_run=True)

    assert [item["id"] for item in result["candidates"]] == ["completed_old"]
    assert result["deleted"] == 0
    assert activity_log.get_activity("completed_old") is not None
    assert activity_log.get_activity("pending_active") is not None


def test_prune_activity_log_preserves_active_and_recent_failed_retry_metadata(
    activity_log: ActivityQueueService,
) -> None:
    activity_log._persist_activity(
        [
            {
                "id": "failed_old",
                "status": "failed",
                "created_at": "2026-06-01T00:00:00Z",
                "finished_at": "2026-06-01T00:01:00Z",
                "metadata": {"retry_history": [{"error": "old"}]},
            },
            {
                "id": "failed_recent",
                "status": "failed",
                "created_at": "2026-06-02T00:00:00Z",
                "finished_at": "2026-06-02T00:01:00Z",
                "metadata": {"retry_history": [{"error": "recent"}]},
            },
            {
                "id": "cancelled_recent",
                "status": "cancelled",
                "created_at": "2026-06-03T00:00:00Z",
                "finished_at": "2026-06-03T00:01:00Z",
                "metadata": {"retry_history": [{"error": "cancelled"}]},
            },
            {
                "id": "running_active",
                "status": "running",
                "created_at": "2026-06-04T00:00:00Z",
            },
        ]
    )

    result = activity_log.prune_activity_log(keep_completed=0, keep_failed=2, dry_run=False)

    assert [item["id"] for item in result["candidates"]] == ["failed_old"]
    assert result["deleted"] == 1
    assert activity_log.get_activity("failed_old") is None
    assert activity_log.get_activity("running_active") is not None
    recent_failed = activity_log.get_activity("failed_recent")
    cancelled_recent = activity_log.get_activity("cancelled_recent")
    assert recent_failed is not None
    assert recent_failed["metadata"]["retry_history"] == [{"error": "recent"}]
    assert cancelled_recent is not None
    assert cancelled_recent["metadata"]["retry_history"] == [{"error": "cancelled"}]
