from __future__ import annotations

import shutil
from uuid import uuid4

import pytest

from novelai.core.platform import JobStatus
from novelai.jobs.queue import JobQueueService
from tests.conftest import TESTS_TMP_ROOT


@pytest.fixture
def jobs() -> JobQueueService:
    TESTS_TMP_ROOT.mkdir(parents=True, exist_ok=True)
    data_dir = TESTS_TMP_ROOT / f"jobs_{uuid4().hex}"
    data_dir.mkdir(parents=True, exist_ok=False)
    service = JobQueueService(data_dir)
    yield service
    shutil.rmtree(data_dir, ignore_errors=True)


def test_create_and_load_crawl_job(jobs: JobQueueService) -> None:
    job = jobs.create_crawl_job(
        novel_id="novel-1",
        source_key="syosetu_ncode",
        kind="metadata",
        chapters=None,
        source_url="https://ncode.syosetu.com/n1234ab/",
    )

    loaded = jobs.get_job(job["id"])

    assert loaded is not None
    assert loaded["type"] == "crawl"
    assert loaded["kind"] == "metadata"
    assert loaded["status"] == "pending"
    assert loaded["source_key"] == "syosetu_ncode"


def test_create_translation_job_and_filter(jobs: JobQueueService) -> None:
    jobs.create_crawl_job(novel_id="novel-1", source_key="kakuyomu", kind="chapters")
    translation = jobs.create_translation_job(
        novel_id="novel-1",
        kind="translate",
        chapters="1-3",
        provider="openai",
        model="gpt-5.4",
    )

    filtered = jobs.list_jobs(job_type="translation", status=JobStatus.PENDING)

    assert filtered == [translation]


def test_update_job_status_records_lifecycle_fields(jobs: JobQueueService) -> None:
    job = jobs.create_translation_job(novel_id="novel-1")

    running = jobs.update_job_status(job["id"], "running")
    failed = jobs.update_job_status(job["id"], "failed", error="source timeout", metadata={"attempt": 1})

    assert running is not None
    assert running["started_at"] is not None
    assert failed is not None
    assert failed["status"] == "failed"
    assert failed["finished_at"] is not None
    assert failed["retry_count"] == 1
    assert failed["error"] == "source timeout"
    assert failed["metadata"]["attempt"] == 1


def test_next_pending_job_returns_oldest_pending_by_type(jobs: JobQueueService) -> None:
    first = jobs.create_crawl_job(novel_id="novel-1", source_key="syosetu_ncode")
    jobs.create_translation_job(novel_id="novel-1")

    pending = jobs.next_pending_job(job_type="crawl")

    assert pending is not None
    assert pending["id"] == first["id"]


def test_record_source_health_tracks_success_and_failure(jobs: JobQueueService) -> None:
    jobs.record_source_health("syosetu_ncode", success=True)
    failed = jobs.record_source_health("syosetu_ncode", success=False, error="timeout")

    loaded = jobs.get_source_health("syosetu_ncode")
    all_sources = jobs.list_source_health()

    assert loaded is not None
    assert loaded["success_count"] == 1
    assert loaded["failure_count"] == 1
    assert loaded["last_error"] == "timeout"
    assert failed == loaded
    assert all_sources == [loaded]
