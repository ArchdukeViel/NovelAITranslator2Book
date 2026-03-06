from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Callable, Optional

from novelai.config.settings import settings
from novelai.pipeline.context import PipelineContext
from novelai.pipeline.stages.base import PipelineStage
from novelai.providers.base import TranslationProvider
from novelai.services.settings_service import SettingsService
from novelai.services.translation_cache import TranslationCache
from novelai.services.usage_service import UsageService

logger = logging.getLogger(__name__)


def _utc_now_iso() -> str:
    """Return a serialized UTC timestamp with a trailing Z."""
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


class TranslateStage(PipelineStage):
    """Translate chunks using a configured provider.

    This stage supports caching and concurrency to reduce both cost and latency.
    
    Requires injection of:
    - provider_factory: Callable that returns TranslationProvider for a given key
    - cache: TranslationCache instance
    - settings_service: SettingsService instance
    - usage_service: UsageService instance
    """

    def __init__(
        self,
        provider_factory: Optional[Callable[[str], TranslationProvider]] = None,
        concurrency: Optional[int] = None,
        cache: Optional[TranslationCache] = None,
        settings_service: Optional[SettingsService] = None,
        usage_service: Optional[UsageService] = None,
    ) -> None:
        if provider_factory is None:
            # Default: import and use registry
            from novelai.providers.registry import get_provider
            provider_factory = get_provider
        
        self._provider_factory = provider_factory
        self._concurrency = concurrency or settings.TRANSLATION_CONCURRENCY
        self._cache = cache or TranslationCache()
        self._settings = settings_service or SettingsService()
        self._usage = usage_service or UsageService()

    async def _translate_chunk(self, provider_key: str, model: str, chunk: str) -> str:
        provider = self._provider_factory(provider_key)
        cached = self._cache.get(chunk, provider.key, model)
        if cached is not None:
            logger.debug(f"Cache hit for chunk (len={len(chunk)})")
            return cached

        logger.debug(f"Translating chunk (len={len(chunk)}) with {provider_key}/{model}")
        result = await provider.translate(prompt=chunk, model=model)
        text = result.get("text", "")

        # Record usage for diagnostics / cost tracking.
        metadata = result.get("metadata") or {}
        usage_entry = {
            "timestamp": _utc_now_iso(),
            "provider": provider.key,
            "model": model,
            "tokens": None,
            "metadata": metadata,
        }
        # Some providers (OpenAI) return usage info
        usage = metadata.get("usage") if isinstance(metadata, dict) else None
        if isinstance(usage, dict):
            usage_entry["tokens"] = usage.get("total_tokens")
            logger.debug(f"Translation tokens: {usage_entry['tokens']}")

        self._usage.record(usage_entry)

        self._cache.set(chunk, provider.key, model, text)
        return text

    async def run(self, context: PipelineContext) -> PipelineContext:
        chunks = context.chunks
        provider_key = context.provider_key or self._settings.get_provider_key()
        model = context.provider_model or self._settings.get_provider_model()

        logger.info(f"Translating {len(chunks)} chunks with {provider_key}/{model}")
        semaphore = asyncio.Semaphore(self._concurrency)

        async def worker(chunk: str) -> str:
            async with semaphore:
                return await self._translate_chunk(provider_key, model, chunk)

        context.translations = await asyncio.gather(*[worker(c) for c in chunks])
        logger.info(f"Translation complete: {len(context.translations)} chunks processed")
        return context
