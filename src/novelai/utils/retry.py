from __future__ import annotations

import asyncio
import logging
from functools import wraps
from typing import Any, Callable, Generic, Optional, Type, TypeVar

from novelai.core.errors import ProviderAPIError, ProviderError

logger = logging.getLogger(__name__)

T = TypeVar("T")


class RetryConfig:
    """Configuration for retry behavior."""

    def __init__(
        self,
        max_attempts: int = 3,
        initial_delay: float = 1.0,
        max_delay: float = 30.0,
        backoff_factor: float = 2.0,
        jitter: bool = True,
        retryable_exceptions: tuple[Type[Exception], ...] = (ProviderAPIError,),
    ):
        """
        Args:
            max_attempts: Maximum number of attempts
            initial_delay: Initial delay in seconds before first retry
            max_delay: Maximum delay between retries
            backoff_factor: Exponential backoff multiplier
            jitter: Add random jitter to delay
            retryable_exceptions: Exceptions that trigger retry
        """
        self.max_attempts = max_attempts
        self.initial_delay = initial_delay
        self.max_delay = max_delay
        self.backoff_factor = backoff_factor
        self.jitter = jitter
        self.retryable_exceptions = retryable_exceptions

    def get_delay(self, attempt: int) -> float:
        """Calculate delay for attempt number (0-indexed)."""
        delay = min(
            self.initial_delay * (self.backoff_factor ** attempt),
            self.max_delay,
        )
        
        if self.jitter:
            import random
            delay = delay * (0.5 + random.random())
        
        return delay


def retry_async(
    config: Optional[RetryConfig] = None,
) -> Callable:
    """Decorator for async functions to add retry logic with exponential backoff.
    
    Usage:
        @retry_async()
        async def translate_with_retry(self, text: str) -> str:
            # Will retry up to 3 times on ProviderAPIError
            return await self.provider.translate(text)
            
        @retry_async(RetryConfig(max_attempts=5, initial_delay=0.5))
        async def fetch_chapter(self, url: str) -> str:
            ...
    """
    if config is None:
        config = RetryConfig()
    
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            last_exception: Optional[Exception] = None
            
            for attempt in range(config.max_attempts):
                try:
                    return await func(*args, **kwargs)
                except config.retryable_exceptions as e:
                    last_exception = e
                    
                    if attempt < config.max_attempts - 1:
                        delay = config.get_delay(attempt)
                        logger.warning(
                            f"Attempt {attempt + 1}/{config.max_attempts} failed: {e}. "
                            f"Retrying in {delay:.1f}s..."
                        )
                        await asyncio.sleep(delay)
                    else:
                        logger.error(
                            f"All {config.max_attempts} attempts failed. "
                            f"Last error: {e}"
                        )
            
            if last_exception:
                raise last_exception
        
        return wrapper
    
    return decorator


class FallbackProvider:
    """Wrapper that adds fallback provider support.
    
    If primary provider fails, automatically tries fallback.
    """
    
    def __init__(
        self,
        primary_factory: Callable[[str], Any],
        fallback_factory: Callable[[str], Any],
    ):
        """
        Args:
            primary_factory: Callable that returns primary provider for a key
            fallback_factory: Callable that returns fallback provider for a key
        """
        self.primary_factory = primary_factory
        self.fallback_factory = fallback_factory
    
    async def translate_with_fallback(
        self,
        primary_key: str,
        fallback_key: Optional[str] = None,
        prompt: str = "",
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Try primary provider, fall back if it fails.
        
        Args:
            primary_key: Primary provider key
            fallback_key: Fallback provider key (if None, no fallback)
            prompt: Text to translate
            **kwargs: Additional provider kwargs
            
        Returns:
            Translation result dict
            
        Raises:
            ProviderError: If both primary and fallback fail
        """
        primary = self.primary_factory(primary_key)
        
        try:
            logger.info(f"Trying primary provider: {primary_key}")
            result = await primary.translate(prompt=prompt, **kwargs)
            result["provider_used"] = primary_key
            return result
        except ProviderError as e:
            logger.warning(f"Primary provider failed: {e}")
            
            if not fallback_key:
                raise
            
            try:
                fallback = self.fallback_factory(fallback_key)
                logger.info(f"Trying fallback provider: {fallback_key}")
                result = await fallback.translate(prompt=prompt, **kwargs)
                result["provider_used"] = fallback_key
                result["fallback_used"] = True
                return result
            except ProviderError as fallback_err:
                logger.error(f"Fallback provider also failed: {fallback_err}")
                raise ProviderError(
                    f"Both primary ({primary_key}) and fallback ({fallback_key}) providers failed. "
                    f"Last error: {fallback_err}"
                ) from fallback_err
