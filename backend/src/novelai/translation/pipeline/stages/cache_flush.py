from __future__ import annotations

import logging

from novelai.config.settings import settings
from novelai.services.translation_cache import CacheEntry, TranslationCacheService
from novelai.shared.pipeline import ChunkTranslationStatus
from novelai.translation.pipeline.context import PipelineState
from novelai.translation.pipeline.stages.base import PipelineStage

logger = logging.getLogger(__name__)

# Chunk states that must never have their translated output cached: the
# translation is not accepted, so a later run must not see a cache hit for it.
_NON_TRANSLATED_STATUSES = frozenset(
    {
        ChunkTranslationStatus.NEEDS_RETRY.value,
        ChunkTranslationStatus.NEEDS_REVIEW.value,
        ChunkTranslationStatus.QA_FAILED.value,
    }
)


class CacheFlushStage(PipelineStage):
    """Write pending translation cache entries after QA passes.

    Runs after TranslationQAStage. If QA already raised, this stage never runs
    (pipeline stops). Only successful chunks get their output cached; chunks
    whose QA status is needs_retry, needs_review, or qa_failed are suppressed.
    """

    def __init__(self, cache_service: TranslationCacheService | None = None) -> None:
        self._cache_service = cache_service or TranslationCacheService()

    async def run(self, context: PipelineState) -> PipelineState:
        if not settings.TRANSLATION_CACHE_ENABLED:
            return context

        pending = context.metadata.get("_pending_cache_entries")
        if not isinstance(pending, list) or not pending:
            return context

        written = 0
        failed = 0
        for raw_entry in pending:
            if not isinstance(raw_entry, (tuple, list)) or len(raw_entry) != 2:
                continue
            key, entry = raw_entry
            if not isinstance(entry, CacheEntry):
                continue
            # Filter pending cache entries: suppress caching for chunks that
            # are not in the TRANSLATED state.
            chunk_id = entry.chunk_id
            chunk_state = context.chunk_states.get(chunk_id, {}) if chunk_id else {}
            status = chunk_state.get("status")
            if status in _NON_TRANSLATED_STATUSES:
                logger.info("Suppressing cache write for chunk %s with status %s", chunk_id, status)
                continue
            try:
                self._cache_service.set(key, entry)
                written += 1
            except Exception as exc:
                logger.warning("Cache flush error for key %s: %s", key[:16] if key else "?", exc)
                failed += 1

        logger.debug("Cache flush: %d written, %d failed", written, failed)
        if isinstance(context.metadata.get("progress"), dict):
            context.metadata["progress"]["cache_flush_written"] = written
            context.metadata["progress"]["cache_flush_failed"] = failed

        # Clear pending so we don't re-write on retry
        context.metadata["_pending_cache_entries"] = []
        return context
