"""Tests for the retry decorator and backoff calculator."""

from __future__ import annotations

import pytest

from novelai.utils.retry_decorator import (
    BackoffCalculator,
    Retrier,
    RetryConfig,
    RetryError,
    RetryStrategy,
    retry_async,
    retry_sync,
)


class TestBackoffCalculator:
    def test_exponential_strategy(self) -> None:
        cfg = RetryConfig(initial_delay=1.0, strategy=RetryStrategy.EXPONENTIAL, jitter=False)
        calc = BackoffCalculator(cfg)
        assert calc.calculate(0) == 1.0  # 1 * 2^0
        assert calc.calculate(1) == 2.0  # 1 * 2^1
        assert calc.calculate(2) == 4.0  # 1 * 2^2

    def test_linear_strategy(self) -> None:
        cfg = RetryConfig(initial_delay=2.0, strategy=RetryStrategy.LINEAR, jitter=False)
        calc = BackoffCalculator(cfg)
        assert calc.calculate(0) == 2.0  # 2 * 1
        assert calc.calculate(1) == 4.0  # 2 * 2
        assert calc.calculate(2) == 6.0  # 2 * 3

    def test_fibonacci_strategy(self) -> None:
        cfg = RetryConfig(initial_delay=1.0, strategy=RetryStrategy.FIBONACCI, jitter=False)
        calc = BackoffCalculator(cfg)
        assert calc.calculate(0) == 1.0  # fib(1) = 1
        assert calc.calculate(1) == 1.0  # fib(2) = 1
        assert calc.calculate(2) == 2.0  # fib(3) = 2
        assert calc.calculate(3) == 3.0  # fib(4) = 3

    def test_fixed_strategy(self) -> None:
        cfg = RetryConfig(initial_delay=5.0, strategy=RetryStrategy.FIXED, jitter=False)
        calc = BackoffCalculator(cfg)
        assert calc.calculate(0) == 5.0
        assert calc.calculate(3) == 5.0

    def test_max_delay_cap(self) -> None:
        cfg = RetryConfig(
            initial_delay=1.0, max_delay=10.0, strategy=RetryStrategy.EXPONENTIAL, jitter=False
        )
        calc = BackoffCalculator(cfg)
        assert calc.calculate(10) == 10.0  # capped

    def test_jitter_modifies_delay(self) -> None:
        cfg = RetryConfig(initial_delay=10.0, strategy=RetryStrategy.FIXED, jitter=True, jitter_factor=0.5)
        calc = BackoffCalculator(cfg)
        delays = {calc.calculate(0) for _ in range(20)}
        # With jitter, not all delays should be exactly 10.0
        assert len(delays) > 1

    def test_negative_attempt_raises(self) -> None:
        cfg = RetryConfig(jitter=False)
        calc = BackoffCalculator(cfg)
        with pytest.raises(ValueError, match="Attempt must be >= 0"):
            calc.calculate(-1)


class TestRetrier:
    @pytest.mark.asyncio
    async def test_async_succeeds_immediately(self) -> None:
        async def ok() -> str:
            return "ok"

        cfg = RetryConfig(max_attempts=3)
        retrier = Retrier(cfg)
        result = await retrier.execute_async(ok)
        assert result == "ok"

    @pytest.mark.asyncio
    async def test_async_retries_on_failure(self) -> None:
        calls = 0

        async def flaky() -> str:
            nonlocal calls
            calls += 1
            if calls < 3:
                raise ValueError("not yet")
            return "done"

        cfg = RetryConfig(max_attempts=5, initial_delay=0.001, max_delay=0.01, jitter=False)
        retrier = Retrier(cfg)
        result = await retrier.execute_async(flaky)
        assert result == "done"
        assert calls == 3

    @pytest.mark.asyncio
    async def test_async_exhausts_retries(self) -> None:
        async def always_fail() -> None:
            raise RuntimeError("boom")

        cfg = RetryConfig(max_attempts=2, initial_delay=0.001, max_delay=0.01, jitter=False)
        retrier = Retrier(cfg)
        with pytest.raises(RetryError, match="All retry attempts exhausted"):
            await retrier.execute_async(always_fail)

    def test_sync_succeeds(self) -> None:
        cfg = RetryConfig(max_attempts=3)
        retrier = Retrier(cfg)
        assert retrier.execute_sync(lambda: 42) == 42

    def test_sync_retries_on_failure(self) -> None:
        calls = 0

        def flaky() -> str:
            nonlocal calls
            calls += 1
            if calls < 2:
                raise ValueError("fail")
            return "ok"

        cfg = RetryConfig(max_attempts=3, initial_delay=0.001, max_delay=0.01, jitter=False)
        retrier = Retrier(cfg)
        result = retrier.execute_sync(flaky)
        assert result == "ok"

    def test_sync_exhausts_retries(self) -> None:
        cfg = RetryConfig(max_attempts=2, initial_delay=0.001, max_delay=0.01, jitter=False)
        retrier = Retrier(cfg)
        with pytest.raises(RetryError):
            retrier.execute_sync(lambda: (_ for _ in ()).throw(RuntimeError("boom")))


class TestRetryDecorators:
    @pytest.mark.asyncio
    async def test_retry_async_decorator(self) -> None:
        calls = 0

        @retry_async(RetryConfig(max_attempts=3, initial_delay=0.001, jitter=False))
        async def flaky() -> str:
            nonlocal calls
            calls += 1
            if calls < 2:
                raise ValueError("oops")
            return "done"

        result = await flaky()
        assert result == "done"

    def test_retry_sync_decorator(self) -> None:
        calls = 0

        @retry_sync(RetryConfig(max_attempts=3, initial_delay=0.001, jitter=False))
        def flaky() -> str:
            nonlocal calls
            calls += 1
            if calls < 2:
                raise ValueError("oops")
            return "done"

        result = flaky()
        assert result == "done"


class TestRetryError:
    def test_attributes(self) -> None:
        original = ValueError("root cause")
        err = RetryError("msg", original, 5)
        assert err.last_exception is original
        assert err.attempts == 5
        assert "root cause" in str(err)
