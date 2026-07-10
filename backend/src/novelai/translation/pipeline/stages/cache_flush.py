from __future__ import annotations

import logging

from novelai.config.settings import settings
from novelai.services.translation_cache import TranslationCacheService
from novelai.translation.pipeline.context import PipelineContext
from novelai.translation.pipeline.stages.base import PipelineStage

logger = logging.getLogger(__name__)


class CacheFlushStage(PipelineStage):
    """Write pending translation cache entries after QA passes.

    Runs after TranslationQAStage. If QA already raised, this stage never runs
    (pipeline stops). Only successful chunks get their output cached.
    """

    def __init__(self, cache_service: TranslationCacheService | None = None) -> None:
        self._cache_service = cache_service or TranslationCacheService()

    async def run(self, context: PipelineContext) -> PipelineContext:
        if not settings.TRANSLATION_CACHE_ENABLED:
            return context

        pending = context.metadata.get("_pending_cache_entries")
        if not isinstance(pending, list) or not pending:
            return context

        written = 0
        failed = 0
        for key, entry in pending:
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
