from __future__ import annotations

import logging

from novelai.config.settings import settings
from novelai.services.translation_cache import CacheEntry, TranslationCacheService
from novelai.translation.pipeline.context import PipelineState
from novelai.translation.pipeline.stages.base import PipelineStage
from novelai.translation.pipeline.stages.translate_cache_lookup import RETRY_MARKED_STATUSES

logger = logging.getLogger(__name__)


class CacheFlushStage(PipelineStage):
    """Write pending translation cache entries after QA passes.

    Runs after TranslationQAStage. If QA already raised, this stage never runs
    (pipeline stops). Only successful chunks get their output cached; pending
    entries whose chunk is marked needs_retry, needs_review, or qa_failed are
    dropped (invalidated) and never written. When a chunk is retried, retry
    iterations append entries with the same key; only the most recent (final
    accepted attempt) entry is flushed, so a rejected attempt's output can
    never overwrite the accepted one.
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
        dropped = 0
        # Dedupe by key keeping the last entry: a retried chunk appends one
        # pending entry per provider attempt (same key), and only the final
        # attempt — the one that passed QA — may be cached.
        by_key: dict[str, tuple[str, CacheEntry]] = {}
        for raw_entry in pending:
            if not isinstance(raw_entry, (tuple, list)) or len(raw_entry) != 2:
                continue
            key, entry = raw_entry
            if not isinstance(entry, CacheEntry):
                continue
            # Drop pending entries for chunks that were rejected: their output
            # must never reach either cache (Blocker C).
            chunk_id = entry.chunk_id
            chunk_state = context.chunk_states.get(chunk_id, {}) if chunk_id else {}
            status = chunk_state.get("status")
            if status in RETRY_MARKED_STATUSES:
                logger.info("Dropping pending cache entry for chunk %s with status %s", chunk_id, status)
                dropped += 1
                continue
            by_key[key] = (key, entry)

        for key, entry in by_key.values():
            try:
                self._cache_service.set(key, entry)
                written += 1
            except Exception as exc:
                logger.warning("Cache flush error for key %s: %s", key[:16] if key else "?", exc)
                failed += 1

        logger.debug("Cache flush: %d written, %d failed, %d dropped", written, failed, dropped)
        if isinstance(context.metadata.get("progress"), dict):
            context.metadata["progress"]["cache_flush_written"] = written
            context.metadata["progress"]["cache_flush_failed"] = failed
            context.metadata["progress"]["cache_flush_dropped"] = dropped

        # Clear pending so we don't re-write on retry
        context.metadata["_pending_cache_entries"] = []
        return context
