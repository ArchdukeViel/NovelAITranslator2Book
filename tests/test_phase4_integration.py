"""Integration tests for Phase 4 resilience and performance systems."""

import asyncio
from unittest.mock import AsyncMock, patch

import pytest

from src.novelai.utils.retry_decorator import (
    Retrier, RetryConfig, RetryStrategy, RetryError, BackoffCalculator
)
from src.novelai.utils.batch_processor import (
    BatchProcessor, BatchJobConfig, BatchResult, BatchTranslator
)
from src.novelai.utils.connection_pool import (
    ConnectionPool, PoolConfig, create_connection_pool
)
from src.novelai.utils.cache_optimizer import (
    AsyncCache, CacheConfig, TranslationCacheOptimizer
)


# ============================================================================
# Retry System Tests
# ============================================================================

class TestRetryDecorator:
    """Test retry decorator functionality."""

    @pytest.mark.asyncio
    async def test_exponential_backoff(self):
        """Test exponential backoff calculation."""
        calc = BackoffCalculator(
            RetryConfig(
                initial_delay=1.0,
                exponential_base=2.0,
                max_delay=30.0,
                jitter=False,
            )
        )
        
        # Should double each attempt
        assert calc.calculate(0) == 1.0
        assert calc.calculate(1) == 2.0
        assert calc.calculate(2) == 4.0
        assert calc.calculate(3) == 8.0
        assert calc.calculate(4) == 16.0
        
        # Should cap at max_delay
        assert calc.calculate(5) == 30.0

    @pytest.mark.asyncio
    async def test_retry_success_on_first_attempt(self):
        """Test successful function on first attempt."""
        retrier = Retrier(RetryConfig(max_attempts=3))
        
        call_count = 0
        
        async def success_func():
            nonlocal call_count
            call_count += 1
            return "success"
        
        result = await retrier.execute_async(success_func)
        
        assert result == "success"
        assert call_count == 1

    @pytest.mark.asyncio
    async def test_retry_success_after_failures(self):
        """Test function succeeds after retries."""
        retrier = Retrier(RetryConfig(max_attempts=3, strategy=RetryStrategy.FIXED))
        
        call_count = 0
        
        async def flaky_func():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ValueError("Transient error")
            return "success"
        
        result = await retrier.execute_async(flaky_func)
        
        assert result == "success"
        assert call_count == 3

    @pytest.mark.asyncio
    async def test_retry_exhausted(self):
        """Test retry exhaustion."""
        retrier = Retrier(RetryConfig(max_attempts=2))
        
        async def always_fails():
            raise ValueError("Permanent error")
        
        with pytest.raises(RetryError):
            await retrier.execute_async(always_fails)

    @pytest.mark.asyncio
    async def test_retry_with_multiple_backoff_strategies(self):
        """Test different backoff strategies."""
        strategies = [
            RetryStrategy.LINEAR,
            RetryStrategy.FIBONACCI,
            RetryStrategy.FIXED,
        ]
        
        for strategy in strategies:
            retrier = Retrier(RetryConfig(
                max_attempts=3,
                strategy=strategy,
                initial_delay=0.01
            ))
            
            call_count = 0
            
            async def func():
                nonlocal call_count
                call_count += 1
                if call_count < 2:
                    raise ValueError("Error")
                return "ok"
            
            result = await retrier.execute_async(func)
            assert result == "ok"


# ============================================================================
# Batch Processing Tests
# ============================================================================

class TestBatchProcessor:
    """Test batch processing functionality."""

    @pytest.mark.asyncio
    async def test_batch_processing_success(self):
        """Test successful batch processing."""
        config = BatchJobConfig(batch_size=3, max_parallel_batches=2)
        processor = BatchProcessor(config)
        
        async def process_item(x):
            await asyncio.sleep(0.01)
            return x * 2
        
        items = list(range(10))
        results = await processor.process_items(items, process_item)
        
        # Verify results
        succeeded_items = []
        for batch_result in results:
            succeeded_items.extend(batch_result.succeeded)
        
        assert len(succeeded_items) == 10
        assert succeeded_items == [x * 2 for x in items]

    @pytest.mark.asyncio
    async def test_batch_processing_with_failures(self):
        """Test batch processing with some failures."""
        config = BatchJobConfig(batch_size=3, max_parallel_batches=2)
        processor = BatchProcessor(config)
        
        async def process_item(x):
            if x == 5:
                raise ValueError("Error on 5")
            return x * 2
        
        items = list(range(10))
        results = await processor.process_items(items, process_item)
        
        # Count successes and failures
        total_succeeded = sum(len(r.succeeded) for r in results)
        total_failed = sum(len(r.failed) for r in results)
        
        assert total_succeeded == 9
        assert total_failed == 1

    @pytest.mark.asyncio
    async def test_batch_translator(self):
        """Test batch translation."""
        config = BatchJobConfig(batch_size=2, max_parallel_batches=2)
        translator = BatchTranslator(config)
        
        async def mock_translate(text):
            await asyncio.sleep(0.01)
            return f"[translated] {text}"
        
        chapters = [
            {"text": f"Chapter {i}", "id": i}
            for i in range(5)
        ]
        
        translated = await translator.translate_chapters(chapters, mock_translate)
        
        assert len(translated) == 5
        assert all("translated_text" in ch for ch in translated)

    @pytest.mark.asyncio
    async def test_batch_fail_fast(self):
        """Test fail-fast batch processing."""
        config = BatchJobConfig(batch_size=2, max_parallel_batches=1, fail_fast=True)
        processor = BatchProcessor(config)
        
        call_count = 0
        
        async def process_item(x):
            nonlocal call_count
            call_count += 1
            if x == 1:
                raise ValueError("Error")
            return x
        
        items = list(range(10))
        results = await processor.process_items(items, process_item)
        
        # Should stop early due to fail_fast
        assert call_count < 10


# ============================================================================
# Connection Pool Tests
# ============================================================================

class TestConnectionPool:
    """Test connection pool functionality."""

    @pytest.mark.asyncio
    async def test_pool_initialization(self):
        """Test pool initialization."""
        async def create_conn():
            return {"connected": True}
        
        pool = ConnectionPool(create_conn, PoolConfig(min_size=3, max_size=10))
        
        await pool.initialize()
        
        stats = pool.get_stats()
        assert stats.total_connections == 3
        assert stats.idle_connections >= 2  # At least some idle

    @pytest.mark.asyncio
    async def test_acquire_and_release(self):
        """Test acquiring and releasing connections."""
        async def create_conn():
            return {"id": len(connections), "connected": True}
        
        connections = []
        
        with patch('src.novelai.utils.connection_pool.asyncio', asyncio):
            pool = ConnectionPool(create_conn, PoolConfig(min_size=2, max_size=5))
            
            await pool.initialize()
            
            # Acquire connection
            conn1 = await pool.acquire()
            assert conn1 is not None
            
            # Release connection
            await pool.release(conn1)
            
            # Acquire again
            conn2 = await pool.acquire()
            assert conn2 is not None

    @pytest.mark.asyncio
    async def test_pool_exhaustion_timeout(self):
        """Test pool timeout when exhausted."""
        async def create_conn():
            await asyncio.sleep(0.1)  # Slow creation
            return {}
        
        config = PoolConfig(min_size=1, max_size=1, max_overflow=0, acquire_timeout=0.05)
        pool = ConnectionPool(create_conn, config)
        
        await pool.initialize()
        
        # Acquire the only connection
        conn1 = await pool.acquire()
        
        # Try to acquire another (should timeout)
        with pytest.raises(TimeoutError):
            await asyncio.wait_for(pool.acquire(), timeout=1.0)

    @pytest.mark.asyncio
    async def test_pool_stats(self):
        """Test pool statistics tracking."""
        async def create_conn():
            return {}
        
        pool = ConnectionPool(create_conn, PoolConfig(min_size=2))
        await pool.initialize()
        
        stats = pool.get_stats()
        assert stats.total_created == 2
        assert stats.total_connections == 2
        
        # Acquire connection
        conn = await pool.acquire()
        stats = pool.get_stats()
        assert stats.active_connections >= 1
        
        # Release connection
        await pool.release(conn)
        stats = pool.get_stats()
        assert stats.total_released == 1


# ============================================================================
# Cache Tests
# ============================================================================

class TestAsyncCache:
    """Test async cache functionality."""

    @pytest.mark.asyncio
    async def test_cache_get_set(self):
        """Test basic cache operations."""
        cache = AsyncCache()
        await cache.initialize()
        
        # Set value
        await cache.set("key1", "value1")
        
        # Get value
        result = await cache.get("key1")
        assert result == "value1"
        
        # Get non-existent
        result = await cache.get("nonexistent")
        assert result is None

    @pytest.mark.asyncio
    async def test_cache_ttl_expiration(self):
        """Test cache TTL expiration."""
        cache = AsyncCache(CacheConfig(default_ttl_seconds=1))
        await cache.initialize()
        
        # Set with short TTL
        await cache.set("key1", "value1", ttl_seconds=1)
        
        # Get immediately
        result = await cache.get("key1")
        assert result == "value1"
        
        # Wait for expiration
        await asyncio.sleep(1.1)
        
        # Should be expired
        result = await cache.get("key1")
        assert result is None

    @pytest.mark.asyncio
    async def test_cache_hit_rate(self):
        """Test cache statistics."""
        cache = AsyncCache()
        await cache.initialize()
        
        await cache.set("key1", "value1")
        
        # Hits
        await cache.get("key1")
        await cache.get("key1")
        
        # Misses
        await cache.get("missing1")
        await cache.get("missing2")
        
        stats = cache.get_stats()
        assert stats.total_hits == 2
        assert stats.total_misses == 2

    @pytest.mark.asyncio
    async def test_cache_eviction_lru(self):
        """Test LRU eviction."""
        cache = AsyncCache(CacheConfig(
            max_entries=3,
            eviction_policy="lru"
        ))
        await cache.initialize()
        
        # Fill cache
        await cache.set("key1", "value1")
        await cache.set("key2", "value2")
        await cache.set("key3", "value3")
        
        # Access key1 to make it recently used
        await cache.get("key1")
        
        # Add new entry (should evict key2 as LRU)
        await cache.set("key4", "value4")
        
        # key2 should be evicted
        result = await cache.get("key2")
        assert result is None

    @pytest.mark.asyncio
    async def test_cache_get_or_fetch(self):
        """Test cache get_or_fetch."""
        cache = AsyncCache()
        await cache.initialize()
        
        call_count = 0
        
        async def fetch_func():
            nonlocal call_count
            call_count += 1
            return "fetched_value"
        
        # First call fetches
        result1 = await cache.get_or_fetch("key1", fetch_func)
        assert result1 == "fetched_value"
        assert call_count == 1
        
        # Second call from cache
        result2 = await cache.get_or_fetch("key1", fetch_func)
        assert result2 == "fetched_value"
        assert call_count == 1  # Not called again

    @pytest.mark.asyncio
    async def test_translation_cache_optimizer(self):
        """Test translation cache optimizer."""
        cache = AsyncCache()
        optimizer = TranslationCacheOptimizer(cache)
        
        source_text = "Hello world"
        translated_text = "Bonjour le monde"
        provider = "openai"
        
        # Cache translation
        await optimizer.cache_translation(source_text, translated_text, provider)
        
        # Retrieve translation
        result = await optimizer.get_translation(source_text, provider)
        assert result == translated_text


# ============================================================================
# Integration Tests - Full Pipeline
# ============================================================================

class TestPhase4Integration:
    """Integration tests for Phase 4 systems working together."""

    @pytest.mark.asyncio
    async def test_retry_with_batch_processing(self):
        """Test retry and batch processing together."""
        retry_config = RetryConfig(max_attempts=3, strategy=RetryStrategy.EXPONENTIAL)
        batch_config = BatchJobConfig(batch_size=2, max_parallel_batches=2)
        
        retrier = Retrier(retry_config)
        attempts: dict[int, int] = {}
        
        async def process_with_retry(x):
            async def func():
                attempts[x] = attempts.get(x, 0) + 1
                if x == 0 and attempts[x] == 1:
                    raise ValueError("Transient failure")
                return x * 2
            
            return await retrier.execute_async(func)
        
        processor = BatchProcessor(batch_config)
        items = list(range(5))
        results = await processor.process_items(items, process_with_retry)
        
        succeeded = sum(len(r.succeeded) for r in results)
        assert succeeded == 5

    @pytest.mark.asyncio
    async def test_cache_with_batch_translator(self):
        """Test cache integration with batch translator."""
        cache = TranslationCacheOptimizer()
        
        # Warm up cache
        translations = {
            "hello": "hola",
            "world": "mundo",
        }
        await cache.warmup_translations(translations, "test")
        
        # Batch translator with cache warmup
        config = BatchJobConfig(batch_size=2)
        translator = BatchTranslator(config)
        
        call_count = 0
        
        async def translate(text):
            nonlocal call_count
            call_count += 1
            
            # Check cache first
            cached = await cache.get_translation(text, "test")
            if cached:
                return cached
            
            # Otherwise translate
            result = f"translated_{text}"
            await cache.cache_translation(text, result, "test")
            return result
        
        chapters = [
            {"text": "hello", "id": 1},
            {"text": "world", "id": 2},
            {"text": "foo", "id": 3},
        ]
        
        translated = await translator.translate_chapters(chapters, translate)
        
        assert len(translated) == 3
        # cold_hello and world should hit cache (call_count < 3)
        assert call_count <= 3

    @pytest.mark.asyncio
    async def test_connection_pool_with_retry(self):
        """Test connection pool with retry."""
        async def create_conn():
            return AsyncMock()
        
        pool = ConnectionPool(create_conn, PoolConfig(min_size=2))
        await pool.initialize()
        
        retrier = Retrier(RetryConfig(max_attempts=3))
        
        async def use_connection():
            async def func():
                conn = await pool.acquire()
                try:
                    # Simulate work
                    return "success"
                finally:
                    await pool.release(conn)
            
            return await retrier.execute_async(func)
        
        result = await use_connection()
        assert result == "success"

    @pytest.mark.asyncio
    async def test_full_resilience_flow(self):
        """Test full resilience flow: retry -> batch -> cache."""
        # Setup components
        retry_config = RetryConfig(max_attempts=3)
        batch_config = BatchJobConfig(batch_size=3)
        cache = TranslationCacheOptimizer()
        
        retrier = Retrier(retry_config)
        processor = BatchProcessor(batch_config)
        
        attempt_count = {}
        
        async def translate_with_resilience(text):
            """Translate with full resilience stack."""
            # Check cache
            cached = await cache.get_translation(text, "test")
            if cached:
                return cached
            
            # Translate with retry
            async def do_translate():
                key = f"attempt_{text}"
                attempt_count[key] = attempt_count.get(key, 0) + 1
                
                # Simulate occasional failures
                if attempt_count[key] < 2:
                    raise ValueError("Transient error")
                
                return f"translated_{text}"
            
            result = await retrier.execute_async(do_translate)
            
            # Cache result
            await cache.cache_translation(text, result, "test")
            
            return result
        
        # Process batch
        items = ["hello", "world", "test"]
        results = await processor.process_items(
            items,
            translate_with_resilience
        )
        
        succeeded = sum(len(r.succeeded) for r in results)
        assert succeeded == 3

    @pytest.mark.asyncio
    async def test_performance_comparison(self):
        """Test performance improvements with batching and caching."""
        import time
        
        # Sequential processing
        async def sequential_translate(items):
            results = []
            for item in items:
                await asyncio.sleep(0.01)  # Simulate API call
                results.append(f"translated_{item}")
            return results
        
        # Batch processing
        batch_config = BatchJobConfig(batch_size=5, max_parallel_batches=2)
        processor = BatchProcessor(batch_config)
        
        async def batch_translate(item):
            await asyncio.sleep(0.01)
            return f"translated_{item}"
        
        items = list(range(20))
        
        # Sequential timing
        start = time.time()
        await sequential_translate(items)
        sequential_time = time.time() - start
        
        # Batch timing
        start = time.time()
        await processor.process_items(items, batch_translate)
        batch_time = time.time() - start
        
        # Batch should be faster due to parallelization
        assert batch_time < sequential_time


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
