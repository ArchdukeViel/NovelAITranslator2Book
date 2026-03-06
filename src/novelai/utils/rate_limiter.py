"""Rate limiting utilities for API providers."""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from functools import wraps
from typing import Any, Awaitable, Callable, Dict, Optional

logger = logging.getLogger(__name__)


@dataclass
class RateLimitConfig:
    """Configuration for rate limiting."""

    max_requests: int = 100  # Maximum requests in time window
    time_window: float = 60.0  # Time window in seconds
    per_provider: bool = True  # Track limits per provider
    raise_on_limit: bool = True  # Raise exception or wait


class TokenBucket:
    """Token bucket for rate limiting."""

    def __init__(self, config: RateLimitConfig):
        """Initialize token bucket.
        
        Args:
            config: Rate limit configuration
        """
        self.config = config
        self.tokens = float(config.max_requests)
        self.last_refill = time.time()

    def _refill(self) -> None:
        """Refill tokens based on elapsed time."""
        now = time.time()
        elapsed = now - self.last_refill
        
        # Calculate tokens to add
        tokens_to_add = (elapsed / self.config.time_window) * self.config.max_requests
        self.tokens = min(
            self.config.max_requests,
            self.tokens + tokens_to_add
        )
        self.last_refill = now

    def consume(self, tokens: int = 1) -> bool:
        """Attempt to consume tokens.
        
        Args:
            tokens: Number of tokens to consume
            
        Returns:
            True if tokens were consumed, False if not enough tokens
        """
        self._refill()
        
        if self.tokens >= tokens:
            self.tokens -= tokens
            return True
        return False

    async def wait_for_tokens(self, tokens: int = 1) -> None:
        """Wait until tokens are available, then consume them.
        
        Args:
            tokens: Number of tokens to consume
        """
        while not self.consume(tokens):
            # Wait a bit before retrying
            await asyncio.sleep(0.1)

    def get_available(self) -> float:
        """Get number of available tokens."""
        self._refill()
        return self.tokens

    def get_wait_time(self, tokens: int = 1) -> float:
        """Get estimated wait time for tokens.
        
        Args:
            tokens: Number of tokens needed
            
        Returns:
            Wait time in seconds, or 0 if tokens available
        """
        self._refill()
        
        if self.tokens >= tokens:
            return 0.0
        
        tokens_needed = tokens - self.tokens
        refill_rate = self.config.max_requests / self.config.time_window
        return tokens_needed / refill_rate


class RateLimiter:
    """Rate limiter with per-provider tracking."""

    def __init__(self, config: RateLimitConfig):
        """Initialize rate limiter.
        
        Args:
            config: Rate limit configuration
        """
        self.config = config
        self._buckets: Dict[str, TokenBucket] = {}
        self._lock = asyncio.Lock()

    def _get_key(self, provider_key: Optional[str] = None) -> str:
        """Get bucket key for provider."""
        if self.config.per_provider and provider_key:
            return f"provider:{provider_key}"
        return "global"

    async def _get_bucket(self, key: str) -> TokenBucket:
        """Get or create bucket for key."""
        async with self._lock:
            if key not in self._buckets:
                self._buckets[key] = TokenBucket(self.config)
            return self._buckets[key]

    async def acquire(
        self,
        tokens: int = 1,
        provider_key: Optional[str] = None,
        wait: bool = True,
    ) -> None:
        """Acquire tokens for operation.
        
        Args:
            tokens: Number of tokens needed
            provider_key: Provider identifier
            wait: If True, wait for tokens. If False, raise on insufficient tokens.
            
        Raises:
            RuntimeError: If wait=False and insufficient tokens
        """
        key = self._get_key(provider_key)
        bucket = await self._get_bucket(key)

        if wait:
            await bucket.wait_for_tokens(tokens)
            logger.debug(f"Rate limit: acquired {tokens} tokens for {key}")
        else:
            if not bucket.consume(tokens):
                available = bucket.get_available()
                wait_time = bucket.get_wait_time(tokens)
                raise RuntimeError(
                    f"Rate limit exceeded for {key}: "
                    f"need {tokens} tokens, have {available:.1f}, "
                    f"wait {wait_time:.1f}s"
                )

    async def get_status(self, provider_key: Optional[str] = None) -> Dict[str, Any]:
        """Get rate limit status.
        
        Args:
            provider_key: Provider identifier
            
        Returns:
            Status dict with available tokens and wait times
        """
        key = self._get_key(provider_key)
        bucket = await self._get_bucket(key)

        return {
            "key": key,
            "available_tokens": bucket.get_available(),
            "max_tokens": self.config.max_requests,
            "wait_time_1_token": bucket.get_wait_time(1),
            "wait_time_10_tokens": bucket.get_wait_time(10),
        }

    async def reset(self, provider_key: Optional[str] = None) -> None:
        """Reset rate limit for provider.
        
        Args:
            provider_key: Provider identifier, or None for all
        """
        async with self._lock:
            if provider_key:
                key = self._get_key(provider_key)
                if key in self._buckets:
                    del self._buckets[key]
                    logger.info(f"Reset rate limit for {key}")
            else:
                self._buckets.clear()
                logger.info("Reset all rate limits")


# Global rate limiter instances
_rate_limiters: Dict[str, RateLimiter] = {}


def get_rate_limiter(name: str = "default", config: Optional[RateLimitConfig] = None) -> RateLimiter:
    """Get or create named rate limiter.
    
    Args:
        name: Rate limiter name
        config: Configuration (used on creation)
        
    Returns:
        RateLimiter instance
    """
    if name not in _rate_limiters:
        _rate_limiters[name] = RateLimiter(config or RateLimitConfig())
    return _rate_limiters[name]


def rate_limit_async(
    config: Optional[RateLimitConfig] = None,
    provider_arg: str = "provider_key",
    limiter_name: str = "default",
) -> Callable:
    """Decorator for rate-limited async functions.
    
    Args:
        config: Rate limit configuration
        provider_arg: Name of argument containing provider key
        limiter_name: Name of rate limiter to use
        
    Returns:
        Decorator function
        
    Example:
        @rate_limit_async()
        async def translate(self, text: str, provider_key: str) -> str:
            ...
    """
    def decorator(func: Callable[..., Awaitable]) -> Callable[..., Awaitable]:
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            provider_key = kwargs.get(provider_arg)
            limiter = get_rate_limiter(limiter_name, config)
            
            try:
                await limiter.acquire(1, provider_key=provider_key, wait=True)
                return await func(*args, **kwargs)
            except Exception as e:
                logger.error(f"Rate limited call failed: {e}")
                raise

        return wrapper

    return decorator


def rate_limit_sync(
    config: Optional[RateLimitConfig] = None,
    provider_arg: str = "provider_key",
    limiter_name: str = "default",
) -> Callable:
    """Decorator for rate-limited sync functions.
    
    Note: This uses asyncio.run internally for sync functions.
    
    Args:
        config: Rate limit configuration
        provider_arg: Name of argument containing provider key
        limiter_name: Name of rate limiter to use
        
    Returns:
        Decorator function
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            provider_key = kwargs.get(provider_arg)
            limiter = get_rate_limiter(limiter_name, config)
            
            try:
                # Run the async acquire in a sync context
                asyncio.run(limiter.acquire(1, provider_key=provider_key, wait=True))
                return func(*args, **kwargs)
            except Exception as e:
                logger.error(f"Rate limited call failed: {e}")
                raise

        return wrapper

    return decorator
