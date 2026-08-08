from __future__ import annotations

import logging
from datetime import UTC, datetime

from novelai.config.settings import settings
from novelai.services.translation_cache import CacheEntry, TranslationCacheService
from novelai.translation.pipeline.context import PipelineState
from novelai.translation.pipeline.stages.base import PipelineStage
from novelai.translation.pipeline.stages.translate_cache_lookup import RETRY_MARKED_STATUSES

logger = logging.getLogger(__name__)


class CacheFlushStage(PipelineStage):
    """Write pending translation cache entries after QA passes.

    Runs after TranslationQAStage. If QA already raised, this stage never runs
    (pipeline stops).

    Section 9: the acceptance rule is the exact QA-accepted attempt tuple, not
    chunk status + cache-key dedup. TranslationQAStage stamps
    ``accepted_attempt_number`` / ``accepted_provider_key`` /
    ``accepted_provider_model`` / ``accepted_cache_key`` /
    ``accepted_output_hash`` on the chunk state and removes rejected
    attempts' pending entries. This stage writes ONLY the pending entry
    matching that accepted tuple — a rejected attempt's output can never
    enter the cache, even when a retry later accepts a different provider's
    output under a different cache key.
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
        for key, entry in pending:
            if not isinstance(entry, CacheEntry):
                continue
            chunk_id = entry.chunk_id
            chunk_state = context.chunk_states.get(chunk_id, {}) if chunk_id else {}
            status = chunk_state.get("status")
            # Backstop: a rejected chunk's entries are never cached even if
            # the accepted tuple is missing (e.g. legacy state).
            if status in RETRY_MARKED_STATUSES:
                logger.info("Dropping pending cache entry for chunk %s with status %s", chunk_id, status)
                dropped += 1
                continue
            # Exact acceptance rule: write only the entry matching the
            # QA-accepted attempt tuple.
            accepted = (
                chunk_state.get("accepted_attempt_number") == entry.attempt_number
                and chunk_state.get("accepted_provider_key") == entry.provider_key
                and chunk_state.get("accepted_provider_model") == entry.provider_model
                and chunk_state.get("accepted_cache_key") == key
                and chunk_state.get("accepted_output_hash") == entry.output_hash
            )
            if not accepted:
                logger.info(
                    "Dropping pending cache entry for chunk %s (attempt %s) not matching accepted tuple",
                    chunk_id,
                    entry.attempt_number,
                )
                dropped += 1
                continue
            try:
                # Stamp acceptance provenance: the entry only reaches this
                # point after QA accepted exactly this attempt.
                if entry.accepted_at is None:
                    entry.accepted_at = datetime.now(UTC).isoformat()
                if entry.qa_status is None:
                    entry.qa_status = str(chunk_state.get("qa_status") or "passed")
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
