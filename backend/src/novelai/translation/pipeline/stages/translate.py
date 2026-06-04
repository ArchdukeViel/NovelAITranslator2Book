from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from datetime import UTC, datetime

from novelai.config.settings import settings
from novelai.core.errors import ProviderError
from novelai.glossary import (
    GlossaryTerm,
    extract_term_context,
    normalize_glossary_entries,
    rank_glossary_terms_for_text,
    summarize_term_context,
)
from novelai.translation.pipeline.context import PipelineContext, TranslationChunk
from novelai.translation.pipeline.stages.base import PipelineStage
from novelai.prompts import build_translation_request
from novelai.prompts.models import TranslationRequest
from novelai.providers.base import TranslationProvider
from novelai.providers.model_fallbacks import model_candidates
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
        if provider_key in {"openai", "gemini"} and not self._settings.get_api_key(provider_key):
            logger.warning("%s API key missing; falling back to dummy provider for translation.", provider_key.capitalize())
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
    def _chunk_text(chunk: str | TranslationChunk) -> str:
        if isinstance(chunk, TranslationChunk):
            return chunk.source_text
        return chunk

    @staticmethod
    def _chunk_id(chunk: str | TranslationChunk, chunk_index: int) -> str:
        if isinstance(chunk, TranslationChunk):
            return chunk.chunk_id
        return f"legacy_{chunk_index + 1:04d}"

    @staticmethod
    def _provider_error_metadata(
        exc: ProviderError,
        *,
        chunk_id: str,
        attempt_number: int,
    ) -> dict[str, object]:
        metadata: dict[str, object] = {
            **exc.activity_details(),
            "chunk_id": chunk_id,
            "attempt_number": attempt_number,
            "timestamp": _utc_now_iso(),
        }
        return metadata

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
        try:
            supported = provider.available_models() or []
        except Exception:
            supported = []
        cache_key = request.cache_key() if request is not None else chunk
        candidates = model_candidates(provider_key, model, supported)
        last_error: Exception | None = None

        for candidate_model in candidates:
            cached = self._cache.get(cache_key, provider.key, candidate_model)
            if cached is not None:
                logger.debug("Cache hit for chunk (len=%s) using %s/%s", len(chunk), provider.key, candidate_model)
                return cached

            try:
                logger.debug("Translating chunk (len=%s) with %s/%s", len(chunk), provider_key, candidate_model)
                result = await provider.translate(prompt=chunk, model=candidate_model, request=request)
            except Exception as exc:
                last_error = exc
                if len(candidates) > 1:
                    logger.warning(
                        "Translation failed with %s/%s; trying fallback model if available: %s",
                        provider_key,
                        candidate_model,
                        exc,
                    )
                    continue
                raise

            text = result.get("text", "")

            metadata = result.get("metadata") or {}
            usage_entry = {
                "timestamp": _utc_now_iso(),
                "provider": provider.key,
                "model": candidate_model,
                "tokens": None,
                "metadata": metadata,
            }
            usage = metadata.get("usage") if isinstance(metadata, dict) else None
            if isinstance(usage, dict):
                usage_entry["tokens"] = usage.get("total_tokens")
                logger.debug("Translation tokens: %s", usage_entry["tokens"])

            self._usage.record(usage_entry)
            self._cache.set(cache_key, provider.key, candidate_model, text)
            return text

        if last_error is not None:
            raise last_error
        raise RuntimeError(f"No translation models available for provider {provider_key}.")

    async def run(self, context: PipelineContext) -> PipelineContext:
        chunks: list[str | TranslationChunk] = list(context.translation_chunks or context.chunks)
        provider_key = context.provider_key or self._settings.get_provider_key()
        model = context.provider_model or self._settings.get_provider_model()
        provider_key, model = self._resolve_provider_and_model(provider_key, model)
        context.provider_key = provider_key
        context.provider_model = model
        if provider_key == "gemini":
            context.metadata["model_fallbacks"] = model_candidates(provider_key, model)

        glossary_state = self._normalize_runtime_glossary(context)
        max_glossary_entries = int(context.metadata.get("glossary_max_entries", 12) or 12)
        max_glossary_context_chars = int(context.metadata.get("glossary_max_context_chars", 1200) or 1200)

        logger.info(f"Translating {len(chunks)} chunks with {provider_key}/{model}")
        semaphore = asyncio.Semaphore(self._concurrency)
        glossary_lock = asyncio.Lock()

        async def worker(chunk_index: int, chunk: str | TranslationChunk) -> str:
            chunk_text = self._chunk_text(chunk)
            chunk_id = self._chunk_id(chunk, chunk_index)
            async with semaphore:
                async with glossary_lock:
                    selected_glossary = self._select_chunk_glossary(
                        chunk_text,
                        glossary_state,
                        chunk_index=chunk_index,
                        max_entries=max_glossary_entries,
                        max_context_chars=max_glossary_context_chars,
                    )
                request = self._build_prompt_request(context, chunk_text, chunk_glossary=selected_glossary)
                try:
                    translated = await self._translate_chunk(provider_key, model, chunk_text, request=request)
                except ProviderError as exc:
                    provider_errors = context.metadata.setdefault("provider_errors", [])
                    error_metadata = self._provider_error_metadata(
                        exc,
                        chunk_id=chunk_id,
                        attempt_number=1,
                    )
                    if isinstance(provider_errors, list):
                        provider_errors.append(error_metadata)
                    exc.details = {**exc.details, "chunk_id": chunk_id, "attempt_number": 1}
                    raise
                async with glossary_lock:
                    self._observe_chunk_context(chunk_text, glossary_state, chunk_index=chunk_index)
                return translated

        context.translations = await asyncio.gather(*[worker(i, c) for i, c in enumerate(chunks)])
        context.metadata["translated_chunk_ids"] = [
            self._chunk_id(chunk, index)
            for index, chunk in enumerate(chunks)
        ]
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
