"""Cache optimization and warmup strategies."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Optional, Dict, List, Callable, Awaitable

logger = logging.getLogger(__name__)


@dataclass
class CacheEntry:
    """Single cache entry."""

    key: str
    value: Any
    created_at: datetime = field(default_factory=datetime.now)
    accessed_at: datetime = field(default_factory=datetime.now)
    access_count: int = 0
    ttl_seconds: Optional[int] = None

    def is_expired(self) -> bool:
        """Check if entry has expired."""
        if self.ttl_seconds is None:
            return False
        
        age = (datetime.now() - self.created_at).total_seconds()
        return age > self.ttl_seconds

    def update_access(self):
        """Update access timestamp and count."""
        self.accessed_at = datetime.now()
        self.access_count += 1


@dataclass
class CacheStats:
    """Cache statistics."""

    total_hits: int = 0
    total_misses: int = 0
    total_entries: int = 0
    total_size_bytes: int = 0
    evictions: int = 0
    
    @property
    def hit_rate(self) -> float:
        """Calculate cache hit rate."""
        total = self.total_hits + self.total_misses
        if total == 0:
            return 0.0
        return self.total_hits / total


@dataclass
class CacheConfig:
    """Cache configuration."""

    max_entries: int = 10000
    max_size_bytes: int = 100 * 1024 * 1024  # 100MB
    default_ttl_seconds: Optional[int] = 86400  # 24 hours
    eviction_policy: str = "lru"  # lru, lfu, fifo
    cleanup_interval: float = 3600.0  # Check for expired entries hourly
    enable_compression: bool = False  # Compress cached values


class AsyncCache:
    """High-performance async cache with eviction policies."""

    def __init__(self, config: Optional[CacheConfig] = None):
        self.config = config or CacheConfig()
        self._cache: Dict[str, CacheEntry] = {}
        self._stats = CacheStats()
        self._size_bytes = 0
        self._lock = asyncio.Lock()
        self._cleanup_task: Optional[asyncio.Task] = None

    async def initialize(self) -> None:
        """Initialize cache and start cleanup task."""
        if self._cleanup_task is None:
            self._cleanup_task = asyncio.create_task(self._cleanup_loop())
            logger.info("Cache initialized with cleanup task")

    async def shutdown(self) -> None:
        """Shutdown cache and cancel cleanup task."""
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
            logger.info("Cache shutdown complete")

    async def get(self, key: str) -> Optional[Any]:
        """Get value from cache.
        
        Args:
            key: Cache key
            
        Returns:
            Cached value or None
        """
        async with self._lock:
            entry = self._cache.get(key)
            
            if entry is None:
                self._stats.total_misses += 1
                logger.debug(f"Cache miss: {key}")
                return None
            
            # Check expiration
            if entry.is_expired():
                logger.debug(f"Cache entry expired: {key}")
                del self._cache[key]
                self._size_bytes -= self._estimate_size(entry.value)
                self._stats.total_misses += 1
                return None
            
            # Update access info
            entry.update_access()
            self._stats.total_hits += 1
            logger.debug(f"Cache hit: {key}")
            
            return entry.value

    async def set(
        self,
        key: str,
        value: Any,
        ttl_seconds: Optional[int] = None,
    ) -> None:
        """Set cache value.
        
        Args:
            key: Cache key
            value: Value to cache
            ttl_seconds: Time to live in seconds
        """
        async with self._lock:
            # Check if we need to evict
            if key not in self._cache:
                if (
                    len(self._cache) >= self.config.max_entries or
                    self._size_bytes + self._estimate_size(value) > self.config.max_size_bytes
                ):
                    await self._evict_entry()
            
            # Remove old entry if exists
            if key in self._cache:
                old_entry = self._cache[key]
                self._size_bytes -= self._estimate_size(old_entry.value)
            
            # Create new entry
            entry = CacheEntry(
                key=key,
                value=value,
                ttl_seconds=ttl_seconds or self.config.default_ttl_seconds,
            )
            
            self._cache[key] = entry
            self._size_bytes += self._estimate_size(value)
            
            logger.debug(f"Cache set: {key}")

    async def get_or_fetch(
        self,
        key: str,
        fetch_func: Callable[[], Awaitable[Any]],
        ttl_seconds: Optional[int] = None,
    ) -> Any:
        """Get from cache or fetch if missing.
        
        Args:
            key: Cache key
            fetch_func: Async function to fetch value
            ttl_seconds: Time to live
            
        Returns:
            Cached or fetched value
        """
        # Try cache first
        cached = await self.get(key)
        if cached is not None:
            return cached
        
        # Fetch value
        logger.debug(f"Fetching value for cache key: {key}")
        value = await fetch_func()
        
        # Cache it
        await self.set(key, value, ttl_seconds)
        
        return value

    async def delete(self, key: str) -> bool:
        """Delete cache entry.
        
        Args:
            key: Cache key
            
        Returns:
            True if deleted, False if not found
        """
        async with self._lock:
            if key in self._cache:
                entry = self._cache[key]
                self._size_bytes -= self._estimate_size(entry.value)
                del self._cache[key]
                logger.debug(f"Cache entry deleted: {key}")
                return True
            
            return False

    async def clear(self) -> None:
        """Clear all cache entries."""
        async with self._lock:
            self._cache.clear()
            self._size_bytes = 0
            self._stats.total_entries = 0
            logger.info("Cache cleared")

    async def warmup(
        self,
        warmup_func: Callable[[], Awaitable[Dict[str, Any]]],
    ) -> None:
        """Warm up cache with initial data.
        
        Args:
            warmup_func: Async function that returns dict of key->value
        """
        logger.info("Starting cache warmup")
        
        try:
            data = await warmup_func()
            
            for key, value in data.items():
                await self.set(key, value)
            
            logger.info(f"Cache warmup complete: {len(data)} entries")
            
        except Exception as e:
            logger.error(f"Cache warmup failed: {e}")

    def get_stats(self) -> CacheStats:
        """Get cache statistics.
        
        Returns:
            CacheStats
        """
        self._stats.total_entries = len(self._cache)
        self._stats.total_size_bytes = self._size_bytes
        return self._stats

    async def _evict_entry(self) -> None:
        """Evict entry based on policy."""
        if not self._cache:
            return
        
        policy = self.config.eviction_policy
        
        if policy == "lru":
            # Least recently used
            evict_key = min(
                self._cache.keys(),
                key=lambda k: self._cache[k].accessed_at,
            )
        elif policy == "lfu":
            # Least frequently used
            evict_key = min(
                self._cache.keys(),
                key=lambda k: self._cache[k].access_count,
            )
        elif policy == "fifo":
            # First in, first out
            evict_key = min(
                self._cache.keys(),
                key=lambda k: self._cache[k].created_at,
            )
        else:
            # Default to LRU
            evict_key = min(
                self._cache.keys(),
                key=lambda k: self._cache[k].accessed_at,
            )
        
        entry = self._cache[evict_key]
        self._size_bytes -= self._estimate_size(entry.value)
        del self._cache[evict_key]
        self._stats.evictions += 1
        
        logger.debug(f"Evicted cache entry: {evict_key}")

    async def _cleanup_loop(self) -> None:
        """Periodically clean up expired entries."""
        try:
            while True:
                await asyncio.sleep(self.config.cleanup_interval)
                
                async with self._lock:
                    expired_keys = [
                        key
                        for key, entry in self._cache.items()
                        if entry.is_expired()
                    ]
                    
                    for key in expired_keys:
                        entry = self._cache[key]
                        self._size_bytes -= self._estimate_size(entry.value)
                        del self._cache[key]
                    
                    if expired_keys:
                        logger.debug(f"Cleaned up {len(expired_keys)} expired entries")
        
        except asyncio.CancelledError:
            pass

    @staticmethod
    def _estimate_size(obj: Any) -> int:
        """Estimate object size in bytes."""
        try:
            import sys
            return sys.getsizeof(obj)
        except Exception:
            return 0


class TranslationCacheOptimizer:
    """Specialized cache for translation results."""

    def __init__(self, cache: Optional[AsyncCache] = None):
        self.cache = cache or AsyncCache(
            CacheConfig(
                max_entries=50000,  # More entries for translations
                max_size_bytes=500 * 1024 * 1024,  # 500MB
                default_ttl_seconds=7 * 86400,  # 7 days
                eviction_policy="lru",
            )
        )

    async def get_translation(
        self,
        source_text: str,
        provider: str,
    ) -> Optional[str]:
        """Get cached translation.
        
        Args:
            source_text: Original text
            provider: Provider name
            
        Returns:
            Translated text or None
        """
        key = self._make_key(source_text, provider)
        return await self.cache.get(key)

    async def cache_translation(
        self,
        source_text: str,
        translated_text: str,
        provider: str,
    ) -> None:
        """Cache translation result.
        
        Args:
            source_text: Original text
            translated_text: Translated text
            provider: Provider name
        """
        key = self._make_key(source_text, provider)
        await self.cache.set(key, translated_text)

    async def warmup_translations(
        self,
        translations: Dict[str, str],
        provider: str,
    ) -> None:
        """Warmup cache with translations.
        
        Args:
            translations: Dict of source -> translated text
            provider: Provider name
        """
        logger.info(f"Warming up translation cache with {len(translations)} entries")
        
        for source_text, translated_text in translations.items():
            key = self._make_key(source_text, provider)
            await self.cache.set(key, translated_text)

    @staticmethod
    def _make_key(text: str, provider: str) -> str:
        """Create cache key from text and provider."""
        return f"trans_{provider}_{hash(text)}"


def create_cache(
    max_entries: int = 10000,
    ttl_seconds: int = 86400,
) -> AsyncCache:
    """Create an async cache instance.
    
    Args:
        max_entries: Maximum cache entries
        ttl_seconds: Default time to live
        
    Returns:
        AsyncCache
    """
    config = CacheConfig(
        max_entries=max_entries,
        default_ttl_seconds=ttl_seconds,
    )
    return AsyncCache(config)
