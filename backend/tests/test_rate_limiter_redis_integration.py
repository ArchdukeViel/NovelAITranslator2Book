"""Redis-backed rate limiter cross-instance integration tests.

Verifies that two independent RedisRateLimiter instances sharing the same
Redis backend see consistent counters (proving multi-process behavior).
"""

from __future__ import annotations

import importlib.util
from unittest.mock import patch

import pytest

from novelai.infrastructure.http.rate_limiter import RedisRateLimiter

HAS_FAKEREDIS = importlib.util.find_spec("fakeredis") is not None


@pytest.mark.skipif(not HAS_FAKEREDIS, reason="fakeredis not installed")
class TestRedisRateLimiterCrossInstance:
    @pytest.fixture(autouse=True)
    def setup_redis(self, monkeypatch):
        import fakeredis

        self.fake_redis = fakeredis.FakeStrictRedis()
        monkeypatch.setattr(
            "novelai.infrastructure.http.rate_limiter.settings.REDIS_URL",
            "redis://localhost:6379/0",
        )
        monkeypatch.setattr(
            "novelai.infrastructure.http.rate_limiter.redis.from_url",
            lambda url: self.fake_redis,
        )

    def test_two_instances_share_counter(self):
        """Two independent limiters with same config share same Redis
        and see the same counter — proves multi-instance behavior."""
        limiter_a = RedisRateLimiter(limits={"action": 3}, window_seconds=60)
        limiter_b = RedisRateLimiter(limits={"action": 3}, window_seconds=60)

        assert limiter_a.hit("client1", "action") is True  # 1
        assert limiter_b.hit("client1", "action") is True  # 2
        assert limiter_a.hit("client1", "action") is True  # 3
        assert limiter_b.hit("client1", "action") is False  # 4 — blocked

    def test_burst_blocked(self):
        """Burst of hits beyond limit is blocked."""
        limiter = RedisRateLimiter(limits={"burst": 2}, window_seconds=60)
        assert limiter.hit("client1", "burst") is True
        assert limiter.hit("client1", "burst") is True
        assert limiter.hit("client1", "burst") is False

    def test_different_clients_independent_pools(self):
        """Different clients each get their own counter."""
        limiter = RedisRateLimiter(limits={"action": 1}, window_seconds=60)
        assert limiter.hit("client_a", "action") is True
        assert limiter.hit("client_b", "action") is True
        assert limiter.hit("client_a", "action") is False
        assert limiter.hit("client_b", "action") is False

    def test_window_expiry(self):
        """Hits in old window do not affect new window."""
        with patch("novelai.infrastructure.http.rate_limiter.time.time", return_value=1000.0):
            limiter = RedisRateLimiter(limits={"action": 1}, window_seconds=1)
            assert limiter.hit("client1", "action") is True
            assert limiter.hit("client1", "action") is False

        # Next window
        with patch("novelai.infrastructure.http.rate_limiter.time.time", return_value=2000.0):
            assert limiter.hit("client1", "action") is True

    def test_redis_failure_fails_closed(self):
        """When Redis is unreachable, raise RuntimeError (fail closed)."""
        limiter = RedisRateLimiter(limits={"action": 1}, window_seconds=60)
        # Simulate redis failure
        import fakeredis

        broken_redis = fakeredis.FakeStrictRedis()
        def broken_incr(*args: object, **kwargs: object) -> object:
            raise ConnectionError("Connection refused")

        broken_redis.incr = broken_incr  # type: ignore[method-assign]
        # Replace the limiter's redis client
        limiter._redis = broken_redis

        with pytest.raises(RuntimeError, match="Redis rate limiter unavailable"):
            limiter.hit("client1", "action")
