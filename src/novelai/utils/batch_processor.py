"""Batch processing for improved performance."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Generic, List, Optional, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")
R = TypeVar("R")


@dataclass
class BatchJobConfig:
    """Configuration for batch processing."""

    batch_size: int = 10  # Items per batch
    max_parallel_batches: int = 3  # Concurrent batch operations
    timeout_per_batch: float = 300.0  # Seconds
    retry_count: int = 3
    fail_fast: bool = False  # Stop on first error or continue
    progress_callback: Optional[Callable[[int, int], Awaitable[None]]] = None


@dataclass
class BatchResult(Generic[R]):
    """Result of a batch operation."""

    batch_idx: int
    succeeded: List[R]
    failed: List[tuple[Any, Exception]]
    total_time: float


class BatchProcessor(Generic[T, R]):
    """Process items in batches with parallelization."""

    def __init__(self, config: BatchJobConfig):
        self.config = config
        self._semaphore: Optional[asyncio.Semaphore] = None

    async def process_items(
        self,
        items: List[T],
        processor_func: Callable[[T], Awaitable[R]],
        items_description: str = "items",
    ) -> List[BatchResult[R]]:
        """Process items in batches.
        
        Args:
            items: Items to process
            processor_func: Async function that processes one item
            items_description: Description for logging
            
        Returns:
            List of BatchResult objects
        """
        if not items:
            logger.info("No items to process")
            return []
        
        # Create batches
        batches = [
            items[i : i + self.config.batch_size]
            for i in range(0, len(items), self.config.batch_size)
        ]
        
        logger.info(
            f"Processing {len(items)} {items_description} "
            f"in {len(batches)} batches (size: {self.config.batch_size})"
        )
        
        # Create semaphore for parallel batch control
        self._semaphore = asyncio.Semaphore(self.config.max_parallel_batches)
        
        # Process batches
        batch_results = []
        for batch_idx, batch in enumerate(batches):
            try:
                result = await self._process_batch(batch_idx, batch, processor_func)
                batch_results.append(result)
                
                # Progress callback
                if self.config.progress_callback:
                    total_processed = sum(
                        len(r.succeeded) + len(r.failed) for r in batch_results
                    )
                    await self.config.progress_callback(total_processed, len(items))
                
                # Fail fast if configured
                if self.config.fail_fast and result.failed:
                    logger.error(
                        f"Batch {batch_idx} had {len(result.failed)} failures, failing fast"
                    )
                    break
                    
            except Exception as e:
                logger.error(f"Batch {batch_idx} processing failed: {e}")
                if self.config.fail_fast:
                    break
        
        # Summary
        total_succeeded = sum(len(r.succeeded) for r in batch_results)
        total_failed = sum(len(r.failed) for r in batch_results)
        
        logger.info(
            f"Batch processing complete: {total_succeeded} succeeded, {total_failed} failed"
        )
        
        return batch_results

    async def _process_batch(
        self,
        batch_idx: int,
        batch: List[T],
        processor_func: Callable[[T], Awaitable[R]],
    ) -> BatchResult[R]:
        """Process a single batch.
        
        Args:
            batch_idx: Batch index
            batch: Items in batch
            processor_func: Processing function
            
        Returns:
            BatchResult
        """
        assert self._semaphore is not None
        
        async with self._semaphore:
            start_time = asyncio.get_event_loop().time()
            logger.debug(f"Starting batch {batch_idx} with {len(batch)} items")
            
            succeeded = []
            failed = []
            
            # Process items in batch concurrently
            tasks = [self._process_item(item, processor_func) for item in batch]
            
            try:
                results = await asyncio.gather(*tasks, return_exceptions=True)
                
                for item, result in zip(batch, results):
                    if isinstance(result, Exception):
                        failed.append((item, result))
                        logger.warning(
                            f"Batch {batch_idx}: Item failed with {result.__class__.__name__}"
                        )
                    else:
                        succeeded.append(result)
                
            except Exception as e:
                logger.error(f"Batch {batch_idx} gather failed: {e}")
                failed.extend([(item, e) for item in batch])
            
            elapsed_time = asyncio.get_event_loop().time() - start_time
            logger.debug(
                f"Batch {batch_idx} complete: {len(succeeded)} succeeded, "
                f"{len(failed)} failed in {elapsed_time:.2f}s"
            )
            
            return BatchResult(
                batch_idx=batch_idx,
                succeeded=succeeded,
                failed=failed,
                total_time=elapsed_time,
            )

    async def _process_item(
        self,
        item: T,
        processor_func: Callable[[T], Awaitable[R]],
    ) -> R:
        """Process single item with timeout and retry.
        
        Args:
            item: Item to process
            processor_func: Processing function
            
        Returns:
            Processed result
            
        Raises:
            Exception if all retries fail
        """
        last_error: Optional[Exception] = None
        
        for attempt in range(self.config.retry_count):
            try:
                result = await asyncio.wait_for(
                    processor_func(item),
                    timeout=self.config.timeout_per_batch,
                )
                return result
                
            except asyncio.TimeoutError as e:
                last_error = e
                logger.warning(f"Item timeout (attempt {attempt + 1}), retrying...")
                await asyncio.sleep(2 ** attempt)  # Exponential backoff
                
            except Exception as e:
                last_error = e
                logger.warning(
                    f"Item processing failed (attempt {attempt + 1}): {e}, retrying..."
                )
                await asyncio.sleep(2 ** attempt)  # Exponential backoff
        
        # All retries exhausted
        if last_error:
            raise last_error
        
        raise RuntimeError("Unexpected error in item processing")


class BatchTranslator:
    """Batch translator for multiple chapters."""

    def __init__(self, config: Optional[BatchJobConfig] = None):
        self.config = config or BatchJobConfig()
        self.processor = BatchProcessor[str, str](self.config)

    async def translate_chapters(
        self,
        chapters: List[dict[str, Any]],
        translate_func: Callable[[str], Awaitable[str]],
    ) -> List[dict[str, Any]]:
        """Translate multiple chapters in batches.
        
        Args:
            chapters: List of chapter dicts with 'text' key
            translate_func: Async function to translate text
            
        Returns:
            List of translated chapter dicts
        """
        # Extract texts
        texts = [ch["text"] for ch in chapters]
        
        # Process in batches
        batch_results = await self.processor.process_items(
            texts,
            translate_func,
            items_description="chapters",
        )
        
        # Reconstruct chapters
        translated_chapters = []
        item_idx = 0
        
        for batch_result in batch_results:
            for translated_text in batch_result.succeeded:
                chapter = chapters[item_idx].copy()
                chapter["translated_text"] = translated_text
                translated_chapters.append(chapter)
                item_idx += 1
            
            # Add failed chapters with error marker
            for original_item, error in batch_result.failed:
                # Find original chapter
                for ch in chapters[item_idx:]:
                    if ch["text"] == original_item:
                        chapter = ch.copy()
                        chapter["error"] = str(error)
                        translated_chapters.append(chapter)
                        item_idx += 1
                        break
        
        logger.info(f"Translated {len(translated_chapters)} chapters")
        return translated_chapters


def create_batch_processor(
    batch_size: int = 10,
    max_parallel: int = 3,
    timeout: float = 300.0,
) -> BatchProcessor:
    """Create a batch processor with common settings.
    
    Args:
        batch_size: Items per batch
        max_parallel: Maximum concurrent batches
        timeout: Timeout per batch
        
    Returns:
        Configured BatchProcessor
    """
    config = BatchJobConfig(
        batch_size=batch_size,
        max_parallel_batches=max_parallel,
        timeout_per_batch=timeout,
    )
    return BatchProcessor(config)
