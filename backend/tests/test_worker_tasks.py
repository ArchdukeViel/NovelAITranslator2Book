"""Tests for RQ task enqueue helpers (worker/tasks.py).

Tests the enqueue_crawl_job / enqueue_translation_job helpers using
fakeredis — no real Redis, no real worker process, no real bootstrap.
The run_*_activity functions are not tested here because they require
a full bootstrap; those are covered by integration tests.
"""

from __future__ import annotations

import pytest
import fakeredis
from rq import Queue

from novelai.worker.queue import QUEUE_CRAWL, QUEUE_TRANSLATION
from novelai.worker.tasks import (
    enqueue_crawl_job,
    enqueue_translation_job,
    run_crawl_activity,
    run_translation_activity,
)


@pytest.fixture()
def fake_redis():
    return fakeredis.FakeRedis()


@pytest.fixture(autouse=True)
def patch_redis_connection(monkeypatch: pytest.MonkeyPatch, fake_redis):
    """Route all get_redis_connection calls to fakeredis."""
    monkeypatch.setattr(
        "novelai.worker.queue.get_redis_connection",
        lambda url=None: fake_redis,
    )


class TestEnqueueCrawlJob:
    def test_returns_rq_job_id(self, fake_redis) -> None:
        job_id = enqueue_crawl_job("crawl_abc123")
        assert isinstance(job_id, str)
        assert len(job_id) > 0

    def test_job_lands_on_crawl_queue(self, fake_redis) -> None:
        enqueue_crawl_job("crawl_abc123")
        q = Queue(QUEUE_CRAWL, connection=fake_redis)
        assert q.count == 1

    def test_job_not_on_translation_queue(self, fake_redis) -> None:
        enqueue_crawl_job("crawl_abc123")
        q = Queue(QUEUE_TRANSLATION, connection=fake_redis)
        assert q.count == 0

    def test_multiple_enqueues(self, fake_redis) -> None:
        enqueue_crawl_job("crawl_001")
        enqueue_crawl_job("crawl_002")
        q = Queue(QUEUE_CRAWL, connection=fake_redis)
        assert q.count == 2

    def test_job_has_correct_function(self, fake_redis) -> None:
        job_id = enqueue_crawl_job("crawl_abc123")
        q = Queue(QUEUE_CRAWL, connection=fake_redis)
        job = q.fetch_job(job_id)
        assert job is not None
        assert job.func_name is not None
        assert job.func_name.endswith("run_crawl_activity")

    def test_job_args_contain_activity_id(self, fake_redis) -> None:
        job_id = enqueue_crawl_job("crawl_abc123")
        q = Queue(QUEUE_CRAWL, connection=fake_redis)
        job = q.fetch_job(job_id)
        assert job is not None
        assert "crawl_abc123" in job.args


class TestEnqueueTranslationJob:
    def test_returns_rq_job_id(self, fake_redis) -> None:
        job_id = enqueue_translation_job("translation_xyz789")
        assert isinstance(job_id, str)
        assert len(job_id) > 0

    def test_job_lands_on_translation_queue(self, fake_redis) -> None:
        enqueue_translation_job("translation_xyz789")
        q = Queue(QUEUE_TRANSLATION, connection=fake_redis)
        assert q.count == 1

    def test_job_not_on_crawl_queue(self, fake_redis) -> None:
        enqueue_translation_job("translation_xyz789")
        q = Queue(QUEUE_CRAWL, connection=fake_redis)
        assert q.count == 0

    def test_job_has_correct_function(self, fake_redis) -> None:
        job_id = enqueue_translation_job("translation_xyz789")
        q = Queue(QUEUE_TRANSLATION, connection=fake_redis)
        job = q.fetch_job(job_id)
        assert job is not None
        assert job.func_name is not None
        assert job.func_name.endswith("run_translation_activity")

    def test_job_args_contain_activity_id(self, fake_redis) -> None:
        job_id = enqueue_translation_job("translation_xyz789")
        q = Queue(QUEUE_TRANSLATION, connection=fake_redis)
        job = q.fetch_job(job_id)
        assert job is not None
        assert "translation_xyz789" in job.args


class TestTaskFunctionsAreCallable:
    def test_run_crawl_activity_is_importable(self) -> None:
        assert callable(run_crawl_activity)

    def test_run_translation_activity_is_importable(self) -> None:
        assert callable(run_translation_activity)

    def test_run_crawl_activity_returns_empty_for_unknown_id(self) -> None:
        """run_crawl_activity returns {} for an activity_id not in the queue."""
        result = run_crawl_activity("nonexistent_crawl_id")
        assert result == {}

    def test_run_translation_activity_returns_empty_for_unknown_id(self) -> None:
        """run_translation_activity returns {} for an activity_id not in the queue."""
        result = run_translation_activity("nonexistent_translation_id")
