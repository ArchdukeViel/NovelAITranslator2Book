from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from datetime import UTC, datetime

from novelai.config.settings import settings
from novelai.glossary import (
    GlossaryTerm,
    extract_term_context,
    normalize_glossary_entries,
    rank_glossary_terms_for_text,
    summarize_term_context,
)
from novelai.pipeline.context import PipelineContext
from novelai.pipeline.stages.base import PipelineStage
from novelai.prompts import build_translation_request
from novelai.prompts.models import TranslationRequest
from novelai.providers.base import TranslationProvider
from novelai.services.preferences_service import PreferencesService
from novelai.services.translation_cache import TranslationCache
from novelai.services.usage_service import UsageService

logger = logging.getLogger(__name__)


def _utc_now_iso() -> str:
    """Return a serialized UTC timestamp with a trailing Z."""
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


class TranslateStage(PipelineStage):
    """Translate chunks using a configured provider.

    This stage supports caching and concurrency to reduce both cost and latency.

    Requires injection of:
    - provider_factory: Callable that returns TranslationProvider for a given key
    - cache: TranslationCache instance
    - settings_service: PreferencesService instance
    - usage_service: UsageService instance
    """

    def __init__(
        self,
        provider_factory: Callable[[str], TranslationProvider] | None = None,
        concurrency: int | None = None,
        cache: TranslationCache | None = None,
        settings_service: PreferencesService | None = None,
        usage_service: UsageService | None = None,
    ) -> None:
        if provider_factory is None:
            # Default: import and use registry
            from novelai.providers.registry import get_provider
            provider_factory = get_provider

        self._provider_factory = provider_factory
        self._concurrency = concurrency or settings.TRANSLATION_CONCURRENCY
        self._cache = cache or TranslationCache()
        self._settings = settings_service or PreferencesService()
        self._usage = usage_service or UsageService()

    def _resolve_provider_and_model(self, provider_key: str, model: str) -> tuple[str, str]:
        if provider_key == "openai" and not self._settings.get_api_key():
            logger.warning("OpenAI API key missing; falling back to dummy provider for translation.")
            return "dummy", "dummy"
        return provider_key, model

    @staticmethod
    def _infer_source_language(context: PipelineContext) -> str | None:
        explicit = context.metadata.get("source_language")
        if isinstance(explicit, str) and explicit.strip():
            return explicit.strip()

        source_adapter = context.metadata.get("_source_adapter")
        source_key = getattr(source_adapter, "key", None)
        source_language_map = {
            "syosetu_ncode": "Japanese",
            "novel18_syosetu": "Japanese",
            "kakuyomu": "Japanese",
            "narou": "Japanese",
        }
        if isinstance(source_key, str):
            return source_language_map.get(source_key)
        return None

    @staticmethod
    def _normalize_runtime_glossary(context: PipelineContext) -> dict[str, GlossaryTerm]:
        raw_entries = context.metadata.get("glossary")
        runtime: dict[str, GlossaryTerm] = {}
        for entry in normalize_glossary_entries(raw_entries):
            runtime[entry.source] = entry
        return runtime

    @staticmethod
    def _select_chunk_glossary(
        chunk: str,
        glossary_state: dict[str, GlossaryTerm],
        *,
        chunk_index: int,
        max_entries: int,
        max_context_chars: int,
    ) -> list[GlossaryTerm]:
        return rank_glossary_terms_for_text(
            chunk,
            glossary_state.values(),
            chunk_index=chunk_index,
            max_entries=max_entries,
            max_context_chars=max_context_chars,
        )

    @staticmethod
    def _observe_chunk_context(
        chunk: str,
        glossary_state: dict[str, GlossaryTerm],
        *,
        chunk_index: int,
        max_history: int = 8,
    ) -> None:
        for key, term in glossary_state.items():
            snippet = extract_term_context(chunk, term.source)
            if snippet is None:
                continue

            history = list(term.context_history)
            history.append(snippet)
            if len(history) > max_history:
                history = history[-max_history:]

            glossary_state[key] = GlossaryTerm(
                source=term.source,
                target=term.target,
                locked=term.locked,
                notes=term.notes,
                status=term.status,
                context_history=tuple(history),
                context_summary=summarize_term_context(history),
                occurrence_count=term.occurrence_count + 1,
                last_seen_index=chunk_index,
            ).normalized()

    def _build_prompt_request(
        self,
        context: PipelineContext,
        chunk: str,
        *,
        chunk_glossary: list[GlossaryTerm],
    ) -> TranslationRequest | None:
        source_language = self._infer_source_language(context)
        target_language = context.metadata.get("target_language") or settings.TRANSLATION_TARGET_LANGUAGE
        if not isinstance(source_language, str) or not source_language.strip():
            return None
        if not isinstance(target_language, str) or not target_language.strip():
            return None

        style_preset = context.metadata.get("style_preset")
        consistency_mode = bool(context.metadata.get("consistency_mode", False))
        json_output = bool(context.metadata.get("json_output", False))
        return build_translation_request(
            text=chunk,
            source_language=source_language,
            target_language=target_language,
            glossary_entries=chunk_glossary,
            style_preset=style_preset if isinstance(style_preset, str) else None,
            consistency_mode=consistency_mode,
            json_output=json_output,
        )

    async def _translate_chunk(
        self,
        provider_key: str,
        model: str,
        chunk: str,
        request: TranslationRequest | None = None,
    ) -> str:
        provider_key, model = self._resolve_provider_and_model(provider_key, model)
        provider = self._provider_factory(provider_key)
        cache_key = request.cache_key() if request is not None else chunk
        cached = self._cache.get(cache_key, provider.key, model)
        if cached is not None:
            logger.debug(f"Cache hit for chunk (len={len(chunk)})")
            return cached

        logger.debug(f"Translating chunk (len={len(chunk)}) with {provider_key}/{model}")
        result = await provider.translate(prompt=chunk, model=model, request=request)
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

        self._cache.set(cache_key, provider.key, model, text)
        return text

    async def run(self, context: PipelineContext) -> PipelineContext:
        chunks = context.chunks
        provider_key = context.provider_key or self._settings.get_provider_key()
        model = context.provider_model or self._settings.get_provider_model()
        provider_key, model = self._resolve_provider_and_model(provider_key, model)

        glossary_state = self._normalize_runtime_glossary(context)
        max_glossary_entries = int(context.metadata.get("glossary_max_entries", 12) or 12)
        max_glossary_context_chars = int(context.metadata.get("glossary_max_context_chars", 1200) or 1200)

        logger.info(f"Translating {len(chunks)} chunks with {provider_key}/{model}")
        semaphore = asyncio.Semaphore(self._concurrency)
        glossary_lock = asyncio.Lock()

        async def worker(chunk_index: int, chunk: str) -> str:
            async with semaphore:
                async with glossary_lock:
                    selected_glossary = self._select_chunk_glossary(
                        chunk,
                        glossary_state,
                        chunk_index=chunk_index,
                        max_entries=max_glossary_entries,
                        max_context_chars=max_glossary_context_chars,
                    )
                request = self._build_prompt_request(context, chunk, chunk_glossary=selected_glossary)
                translated = await self._translate_chunk(provider_key, model, chunk, request=request)
                async with glossary_lock:
                    self._observe_chunk_context(chunk, glossary_state, chunk_index=chunk_index)
                return translated

        context.translations = await asyncio.gather(*[worker(i, c) for i, c in enumerate(chunks)])
        context.metadata["glossary_runtime_state"] = [
            {
                "source": term.source,
                "target": term.target,
                "status": term.status,
                "context_summary": term.context_summary,
                "occurrence_count": term.occurrence_count,
                "last_seen_index": term.last_seen_index,
            }
            for term in sorted(glossary_state.values(), key=lambda item: (item.source.casefold(), item.source))
        ]
        logger.info(f"Translation complete: {len(context.translations)} chunks processed")
        return context
