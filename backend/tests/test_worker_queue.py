"""Tests for the RQ queue factory (worker/queue.py).

Uses fakeredis — no real Redis required.
"""

from __future__ import annotations

import pytest
import fakeredis
from rq import Queue

from novelai.worker.queue import (
    ALL_QUEUES,
    QUEUE_CRAWL,
    QUEUE_DEFAULT,
    QUEUE_TRANSLATION,
    get_queue,
    get_redis_connection,
)


class TestGetRedisConnection:
    def test_raises_without_url(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from novelai.config.settings import settings
        monkeypatch.setattr(settings, "REDIS_URL", None)
        with pytest.raises(RuntimeError, match="REDIS_URL"):
            get_redis_connection()

    def test_accepts_explicit_url(self) -> None:
        # fakeredis doesn't need a real URL — we monkeypatch from_url
        import redis as redis_mod
        fake = fakeredis.FakeRedis()
        original = redis_mod.Redis.from_url
        redis_mod.Redis.from_url = lambda url, **kw: fake  # type: ignore[method-assign]
        try:
            conn = get_redis_connection("redis://localhost:6379/0")
            assert conn is fake
        finally:
            redis_mod.Redis.from_url = original  # type: ignore[method-assign]


class TestGetQueue:
    def _fake_connection(self):
        return fakeredis.FakeRedis()

    def test_returns_rq_queue(self, monkeypatch: pytest.MonkeyPatch) -> None:
        fake = fakeredis.FakeRedis()
        monkeypatch.setattr("novelai.worker.queue.get_redis_connection", lambda url=None: fake)
        q = get_queue(QUEUE_CRAWL)
        assert isinstance(q, Queue)
        assert q.name == QUEUE_CRAWL

    def test_default_queue_name(self, monkeypatch: pytest.MonkeyPatch) -> None:
        fake = fakeredis.FakeRedis()
        monkeypatch.setattr("novelai.worker.queue.get_redis_connection", lambda url=None: fake)
        q = get_queue()
        assert q.name == QUEUE_DEFAULT

    def test_translation_queue(self, monkeypatch: pytest.MonkeyPatch) -> None:
        fake = fakeredis.FakeRedis()
        monkeypatch.setattr("novelai.worker.queue.get_redis_connection", lambda url=None: fake)
        q = get_queue(QUEUE_TRANSLATION)
        assert q.name == QUEUE_TRANSLATION

    def test_all_queues_defined(self) -> None:
        assert QUEUE_CRAWL in ALL_QUEUES
        assert QUEUE_TRANSLATION in ALL_QUEUES
        assert QUEUE_DEFAULT in ALL_QUEUES
        assert len(ALL_QUEUES) == 3


class TestEnqueueIntegration:
    def test_enqueue_function_onto_queue(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Enqueueing a function puts a job on the queue."""
        fake = fakeredis.FakeRedis()
        monkeypatch.setattr("novelai.worker.queue.get_redis_connection", lambda url=None: fake)
        q = get_queue(QUEUE_CRAWL)

        def _noop(x: int) -> int:
            return x

        job = q.enqueue(_noop, 42)
        assert job.id is not None
        assert q.count == 1

    def test_queue_is_empty_initially(self, monkeypatch: pytest.MonkeyPatch) -> None:
        fake = fakeredis.FakeRedis()
        monkeypatch.setattr("novelai.worker.queue.get_redis_connection", lambda url=None: fake)
        q = get_queue(QUEUE_CRAWL)
        assert q.count == 0
