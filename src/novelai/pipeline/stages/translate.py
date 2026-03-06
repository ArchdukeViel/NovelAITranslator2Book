from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Optional

from novelai.config.settings import settings
from novelai.pipeline.context import PipelineContext
from novelai.pipeline.stages.base import PipelineStage
from novelai.providers.registry import get_provider
from novelai.services.settings_service import SettingsService
from novelai.services.translation_cache import TranslationCache
from novelai.services.usage_service import UsageService


class TranslateStage(PipelineStage):
    """Translate chunks using a configured provider.

    This stage supports caching and concurrency to reduce both cost and latency.
    """

    def __init__(
        self,
        concurrency: Optional[int] = None,
        cache: TranslationCache | None = None,
        settings_service: SettingsService | None = None,
        usage_service: UsageService | None = None,
    ) -> None:
        self._concurrency = concurrency or settings.TRANSLATION_CONCURRENCY
        self._cache = cache or TranslationCache()
        self._settings = settings_service or SettingsService()
        self._usage = usage_service or UsageService()

    async def _translate_chunk(self, provider_key: str, model: str, chunk: str) -> str:
        provider = get_provider(provider_key)
        cached = self._cache.get(chunk, provider.key, model)
        if cached is not None:
            return cached

        result = await provider.translate(prompt=chunk, model=model)
        text = result.get("text", "")

        # Record usage for diagnostics / cost tracking.
        metadata = result.get("metadata") or {}
        usage_entry = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "provider": provider.key,
            "model": model,
            "tokens": None,
            "metadata": metadata,
        }
        # Some providers (OpenAI) return usage info
        usage = metadata.get("usage") if isinstance(metadata, dict) else None
        if isinstance(usage, dict):
            usage_entry["tokens"] = usage.get("total_tokens")

        self._usage.record(usage_entry)

        self._cache.set(chunk, provider.key, model, text)
        return text

    async def run(self, context: PipelineContext) -> PipelineContext:
        chunks = context.chunks
        provider_key = context.provider_key or self._settings.get_provider_key()
        model = context.provider_model or self._settings.get_provider_model()

        semaphore = asyncio.Semaphore(self._concurrency)

        async def worker(chunk: str) -> str:
            async with semaphore:
                return await self._translate_chunk(provider_key, model, chunk)

        context.translations = await asyncio.gather(*[worker(c) for c in chunks])
        return context
