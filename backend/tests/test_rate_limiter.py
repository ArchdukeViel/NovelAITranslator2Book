from __future__ import annotations

import time
from unittest.mock import patch

import pytest

from novelai.utils.rate_limiter import (
    DisabledRateLimiter,
    InMemoryRateLimiter,
    RedisRateLimiter,
    create_rate_limiter,
    get_default_rate_limiter,
    set_default_rate_limiter,
)

try:
    import fakeredis
    HAS_FAKEREDIS = True
except ImportError:
    HAS_FAKEREDIS = False
    fakeredis = None  # type: ignore


class TestInMemoryRateLimiter:
    def test_allows_under_limit(self):
        limiter = InMemoryRateLimiter(limits={"test_action": 2}, window_seconds=60)
        assert limiter.hit("client1", "test_action") is True
        assert limiter.hit("client1", "test_action") is True

    def test_blocks_over_limit(self):
        limiter = InMemoryRateLimiter(limits={"test_action": 1}, window_seconds=60)
        assert limiter.hit("client1", "test_action") is True
        assert limiter.hit("client1", "test_action") is False

    def test_allows_different_clients(self):
        limiter = InMemoryRateLimiter(limits={"test_action": 1}, window_seconds=60)
        assert limiter.hit("client1", "test_action") is True
        assert limiter.hit("client2", "test_action") is True


class TestDisabledRateLimiter:
    def test_always_allows(self):
        limiter = DisabledRateLimiter()
        assert limiter.hit("client1", "test_action") is True
        assert limiter.hit("client1", "test_action") is True


@pytest.mark.skipif(not HAS_FAKEREDIS, reason="fakeredis not installed")
class TestRedisRateLimiter:
    @pytest.fixture(autouse=True)
    def setup_redis(self, monkeypatch):
        import fakeredis
        # Create a fresh fake redis instance for each test
        self.fake_redis = fakeredis.FakeStrictRedis()
        monkeypatch.setattr("novelai.utils.rate_limiter.settings.REDIS_URL", "redis://localhost:6379/0")
        monkeypatch.setattr("novelai.utils.rate_limiter.redis.from_url", lambda url: self.fake_redis)

    def test_allows_under_limit(self):
        limiter = RedisRateLimiter(limits={"test_action": 2}, window_seconds=60)
        assert limiter.hit("client1", "test_action") is True
        assert limiter.hit("client1", "test_action") is True

    def test_blocks_over_limit(self):
        limiter = RedisRateLimiter(limits={"test_action": 1}, window_seconds=60)
        assert limiter.hit("client1", "test_action") is True
        assert limiter.hit("client1", "test_action") is False

    def test_allows_different_clients(self):
        limiter = RedisRateLimiter(limits={"test_action": 1}, window_seconds=60)
        assert limiter.hit("client1", "test_action") is True
        assert limiter.hit("client2", "test_action") is True

    def test_expires_after_window(self):
        # Use a fixed time to ensure consistent window_id calculation
        with patch("novelai.utils.rate_limiter.time.time", return_value=1000.0):
            limiter = RedisRateLimiter(limits={"test_action": 1}, window_seconds=1)
            assert limiter.hit("client1", "test_action") is True
            assert limiter.hit("client1", "test_action") is False
            
            # Simulate time passing to the next window
            with patch("novelai.utils.rate_limiter.time.time", return_value=1002.0):
                assert limiter.hit("client1", "test_action") is True

    def test_missing_redis_url_raises_error(self, monkeypatch):
        monkeypatch.setattr("novelai.utils.rate_limiter.settings.REDIS_URL", None)
        with pytest.raises(ValueError, match="REDIS_URL environment variable is required"):
            RedisRateLimiter(limits={"test_action": 1}, window_seconds=60)


class TestRateLimiterFactory:
    def test_unknown_backend_raises_error(self):
        with pytest.raises(ValueError, match="Unknown rate limiter backend"):
            create_rate_limiter("unknown_backend")

    def test_missing_redis_url_with_redis_backend_raises_error(self, monkeypatch):
        monkeypatch.setattr("novelai.utils.rate_limiter.settings.REDIS_URL", None)
        with pytest.raises(ValueError, match="REDIS_URL environment variable is required"):
            create_rate_limiter("redis")

    def test_get_default_rate_limiter_caches(self):
        set_default_rate_limiter(None)
        limiter1 = get_default_rate_limiter(backend="memory", limits={"a": 1}, window_seconds=60)
        limiter2 = get_default_rate_limiter(backend="memory", limits={"a": 1}, window_seconds=60)
        assert limiter1 is limiter2

    def test_get_default_rate_limiter_recreates_on_change(self):
        set_default_rate_limiter(None)
        limiter1 = get_default_rate_limiter(backend="memory", limits={"a": 1}, window_seconds=60)
        limiter2 = get_default_rate_limiter(backend="memory", limits={"a": 2}, window_seconds=60)
        assert limiter1 is not limiter2
