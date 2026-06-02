"""Retry mechanisms with exponential backoff and jitter."""

from __future__ import annotations

import asyncio
import logging
import random
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from enum import Enum
from functools import wraps
from typing import Any

logger = logging.getLogger(__name__)


class RetryStrategy(Enum):
    """Strategy for retrying failed operations."""

    EXPONENTIAL = "exponential"  # 2^attempt
    LINEAR = "linear"  # attempt
    FIBONACCI = "fibonacci"  # Fibonacci sequence
    FIXED = "fixed"  # Same delay each time


@dataclass
class RetryConfig:
    """Configuration for retry behavior."""

    max_attempts: int = 5
    initial_delay: float = 1.0
    max_delay: float = 60.0
    exponential_base: float = 2.0
    strategy: RetryStrategy = RetryStrategy.EXPONENTIAL
    jitter: bool = True
    jitter_factor: float = 0.1
    retry_on: tuple[type[Exception], ...] = (Exception,)
    dont_retry_on: tuple[type[Exception], ...] = ()
    on_retry: Callable[[int, Exception], Awaitable[None]] | None = None
    on_failure: Callable[[Exception], Awaitable[None]] | None = None


class RetryError(Exception):
    """Exception raised when all retries are exhausted."""

    def __init__(self, message: str, last_exception: Exception, attempts: int):
        self.last_exception = last_exception
        self.attempts = attempts
        super().__init__(
            f"{message} (attempts: {attempts}, last error: {last_exception})"
        )


class BackoffCalculator:
    """Calculate backoff delays using various strategies."""

    def __init__(self, config: RetryConfig):
        self.config = config
        self._fibonacci_cache = [0, 1]

    def _get_fibonacci(self, n: int) -> int:
        """Get nth Fibonacci number."""
        while len(self._fibonacci_cache) <= n:
            self._fibonacci_cache.append(
                self._fibonacci_cache[-1] + self._fibonacci_cache[-2]
            )
        return self._fibonacci_cache[n]

    def calculate(self, attempt: int) -> float:
        """Calculate backoff delay for attempt number (0-indexed).

        Args:
            attempt: Attempt number (0 is first attempt)

        Returns:
            Delay in seconds
        """
        if attempt < 0:
            raise ValueError("Attempt must be >= 0")

        # Calculate base delay
        if self.config.strategy == RetryStrategy.EXPONENTIAL:
            base_delay = (
                self.config.initial_delay
                * (self.config.exponential_base ** attempt)
            )
        elif self.config.strategy == RetryStrategy.LINEAR:
            base_delay = self.config.initial_delay * (attempt + 1)
        elif self.config.strategy == RetryStrategy.FIBONACCI:
            fib_value = self._get_fibonacci(attempt + 1)
            base_delay = self.config.initial_delay * fib_value
        elif self.config.strategy == RetryStrategy.FIXED:
            base_delay = self.config.initial_delay
        else:
            base_delay = self.config.initial_delay

        # Cap at max delay
        delay = min(base_delay, self.config.max_delay)

        # Add jitter
        if self.config.jitter:
            jitter_range = delay * self.config.jitter_factor
            delay += random.uniform(-jitter_range / 2, jitter_range / 2)
            delay = max(0.0, delay)  # Ensure non-negative

        return delay


class Retrier:
    """Retry handler for operations."""

    def __init__(self, config: RetryConfig):
        self.config = config
        self.backoff = BackoffCalculator(config)

    async def execute_async(
        self, func: Callable[..., Awaitable[Any]], *args: Any, **kwargs: Any
    ) -> Any:
        """Execute async function with retries.

        Args:
            func: Async function to execute
            *args: Positional arguments
            **kwargs: Keyword arguments

        Returns:
            Result of function

        Raises:
            RetryError: If all retries exhausted
        """
        last_exception: Exception | None = None

        for attempt in range(self.config.max_attempts):
            try:
                logger.debug(f"Attempt {attempt + 1}/{self.config.max_attempts}")
                result = await func(*args, **kwargs)
                return result

            except Exception as e:
                last_exception = e

                # Check if we should retry this exception
                should_retry = isinstance(e, self.config.retry_on)
                should_not_retry = isinstance(e, self.config.dont_retry_on)

                if should_not_retry or not should_retry:
                    logger.error(f"Non-retryable exception: {e}")
                    raise

                # Check if we have more attempts
                if attempt >= self.config.max_attempts - 1:
                    logger.error(
                        f"Retry exhausted after {self.config.max_attempts} attempts"
                    )
                    break

                # Calculate delay
                delay = self.backoff.calculate(attempt)
                logger.warning(
                    f"Attempt {attempt + 1} failed: {e}, retrying in {delay:.2f}s..."
                )

                # Call on_retry callback if provided
                if self.config.on_retry:
                    await self.config.on_retry(attempt, e)

                # Wait before retrying
                await asyncio.sleep(delay)

        # All retries exhausted
        if last_exception:
            await self._call_on_failure(last_exception)
            raise RetryError(
                "All retry attempts exhausted",
                last_exception,
                self.config.max_attempts,
            )

        raise RuntimeError("Unexpected error in retry logic")

    def execute_sync(
        self, func: Callable[..., Any], *args: Any, **kwargs: Any
    ) -> Any:
        """Execute sync function with retries.

        Args:
            func: Sync function to execute
            *args: Positional arguments
            **kwargs: Keyword arguments

        Returns:
            Result of function

        Raises:
            RetryError: If all retries exhausted
        """
        last_exception: Exception | None = None

        for attempt in range(self.config.max_attempts):
            try:
                logger.debug(f"Attempt {attempt + 1}/{self.config.max_attempts}")
                result = func(*args, **kwargs)
                return result

            except Exception as e:
                last_exception = e

                # Check if we should retry this exception
                should_retry = isinstance(e, self.config.retry_on)
                should_not_retry = isinstance(e, self.config.dont_retry_on)

                if should_not_retry or not should_retry:
                    logger.error(f"Non-retryable exception: {e}")
                    raise

                # Check if we have more attempts
                if attempt >= self.config.max_attempts - 1:
                    logger.error(
                        f"Retry exhausted after {self.config.max_attempts} attempts"
                    )
                    break

                # Calculate delay
                delay = self.backoff.calculate(attempt)
                logger.warning(
                    f"Attempt {attempt + 1} failed: {e}, retrying in {delay:.2f}s..."
                )

                # Wait before retrying
                time.sleep(delay)

        # All retries exhausted
        if last_exception:
            raise RetryError(
                "All retry attempts exhausted",
                last_exception,
                self.config.max_attempts,
            )

        raise RuntimeError("Unexpected error in retry logic")

    async def _call_on_failure(self, exception: Exception) -> None:
        """Call on_failure callback if configured."""
        if self.config.on_failure:
            try:
                await self.config.on_failure(exception)
            except Exception as e:
                logger.error(f"Error in on_failure callback: {e}")


def retry_async(
    config: RetryConfig | None = None,
) -> Callable[[Callable[..., Awaitable[Any]]], Callable[..., Awaitable[Any]]]:
    """Decorator for retrying async functions.

    Args:
        config: Retry configuration

    Returns:
        Decorator function

    Example:
        @retry_async()
        async def fetch_data(url: str) -> dict:
            ...
    """

    def decorator(
        func: Callable[..., Awaitable[Any]]
    ) -> Callable[..., Awaitable[Any]]:
        retry_config = config or RetryConfig()
        retrier = Retrier(retry_config)

        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            return await retrier.execute_async(func, *args, **kwargs)

        return wrapper

    return decorator


def retry_sync(
    config: RetryConfig | None = None,
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Decorator for retrying sync functions.

    Args:
        config: Retry configuration

    Returns:
        Decorator function

    Example:
        @retry_sync()
        def read_file(path: str) -> str:
            ...
    """

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        retry_config = config or RetryConfig()
        retrier = Retrier(retry_config)

        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            return retrier.execute_sync(func, *args, **kwargs)

        return wrapper

    return decorator
