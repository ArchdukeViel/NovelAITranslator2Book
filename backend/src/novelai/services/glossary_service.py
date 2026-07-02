from __future__ import annotations

import logging

from novelai.services.cache.translation_cache import TranslationCacheService

logger = logging.getLogger(__name__)


class GlossaryService:
    @staticmethod
    def invalidate(novel_id: str) -> int:
        """Invalidate all cache entries associated with a novel when its glossary changes."""
        try:
            service = TranslationCacheService()
            count = service.invalidate(novel_id)
            logger.info("Invalidated %d cache entries for novel %s", count, novel_id)
            return count
        except Exception as exc:
            logger.warning("Cache invalidation failed for novel %s: %s", novel_id, exc)
            return 0
