from __future__ import annotations

import json
import logging
import re
from collections.abc import Callable
from typing import Any

from novelai.config.settings import settings
from novelai.config.workflow_profiles import normalize_workflow_profile_step
from novelai.core.errors import ProviderConfigError, ProviderErrorCode
from novelai.inputs.base import DocumentAdapter
from novelai.providers.base import TranslationProvider
from novelai.services.catalog_service import safely_refresh_catalog_projection_after_storage_write
from novelai.services.orchestration.common import PreflightIssue, _utc_now_iso
from novelai.services.orchestration.crawler import scrape_chapters, scrape_metadata
from novelai.services.orchestration.glossary import (
    _extract_glossary_terms_with_llm,
    _parse_llm_glossary_terms,
    apply_glossary_to_chapters,
    extract_glossary_terms,
    review_glossary_terms,
    translate_glossary_terms,
)
from novelai.services.orchestration.importer import import_document
from novelai.services.orchestration.ocr import _extract_ocr_candidate_text, ingest_ocr_candidates
from novelai.services.orchestration.translation import (
    _preflight_translation,
    polish_low_confidence_chapters,
    retranslate_chapter,
    run_phased_translation_pipeline,
    translate_chapters,
)
from novelai.services.orchestration.translation_metadata import (
    _translate_metadata_fields,
    _translate_text,
    estimate_translation_requests,
)
from novelai.services.preferences_service import PreferencesService
from novelai.services.translation_cache import TranslationCache
from novelai.services.usage_service import UsageService
from novelai.sources.base import SourceAdapter
from novelai.storage.service import StorageService
from novelai.translation.service import TranslationService
from novelai.utils.chapter_selection import is_full_chapter_selection, parse_chapter_selection

logger = logging.getLogger(__name__)


class NovelOrchestrationService:
    """Shared orchestration logic used by the web API and background worker.

    The public API is kept here while workflow implementations live in
    smaller orchestration domain modules.
    """

    def __init__(
        self,
        storage: StorageService,
        translation: TranslationService,
        source_factory: Callable[[str], SourceAdapter] | None = None,
        input_adapter_factory: Callable[[str], DocumentAdapter] | None = None,
        provider_factory: Callable[[str], TranslationProvider] | None = None,
        settings_service: PreferencesService | None = None,
        translation_cache: TranslationCache | None = None,
        usage_service: UsageService | None = None,
    ) -> None:
        if source_factory is None:
            from novelai.sources.registry import get_registry

            def registry_source_factory(key: str) -> SourceAdapter:
                source = get_registry().get_by_key(key)
                if source is None:
                    raise KeyError(key)
                return source

            source_factory = registry_source_factory

        # Wrap to produce a clear OperationError on unknown source key.
        _raw_source_factory = source_factory

        def _source_factory_with_error(key: str) -> SourceAdapter:
            try:
                return _raw_source_factory(key)
            except KeyError:
                from novelai.services.orchestration.operations import OperationError

                raise OperationError(400, f"No adapter found for source: {key}") from None

        if input_adapter_factory is None:
            from novelai.inputs.registry import get_input_adapter
            input_adapter_factory = get_input_adapter
        if provider_factory is None:
            from novelai.providers.registry import get_provider
            provider_factory = get_provider

        self.storage = storage
        self.translation = translation
        self._source_factory = _source_factory_with_error
        self._input_adapter_factory = input_adapter_factory
        self._provider_factory = provider_factory
        self._settings = settings_service or PreferencesService()
        self._cache = translation_cache or TranslationCache()
        self._usage = usage_service or UsageService()


    @staticmethod
    def _infer_source_language(source_key: str, metadata: dict[str, Any] | None = None) -> str | None:
        if isinstance(metadata, dict):
            for key in ("source_language", "language", "lang"):
                value = metadata.get(key)
                if isinstance(value, str) and value.strip():
                    return value.strip()

        language_map = {
            "syosetu_ncode": "Japanese",
            "novel18_syosetu": "Japanese",
            "kakuyomu": "Japanese",
            "narou": "Japanese",
        }
        return language_map.get(source_key)


    @staticmethod
    def _infer_source_language_from_text(text: str) -> str | None:
        if any("\u3040" <= char <= "\u30ff" for char in text):
            return "Japanese"
        if any("\u4e00" <= char <= "\u9fff" for char in text):
            return "Chinese"
        if re.search(r"[A-Za-z]", text):
            return "English"
        return None


    def _resolve_workflow_profile(
        self,
        step: str,
        metadata: dict[str, Any] | None = None,
    ) -> tuple[str | None, str | None]:
        step_config = self._resolve_workflow_step_config(step, metadata)
        provider = step_config.get("provider")
        model = step_config.get("model")
        return (
            provider if isinstance(provider, str) and provider.strip() else None,
            model if isinstance(model, str) and model.strip() else None,
        )


    def _resolve_workflow_step_config(
        self,
        step: str,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        normalized_step = normalize_workflow_profile_step(step)
        step_config = self._settings.resolve_step_llm_config(normalized_step, metadata)

        if isinstance(metadata, dict):
            raw_overrides = metadata.get("translation_step_configs")
            if isinstance(raw_overrides, dict):
                override_payload = raw_overrides.get(normalized_step)
                if isinstance(override_payload, dict):
                    merged = dict(step_config)
                    merged.update(override_payload)
                    if not isinstance(merged.get("kwargs"), dict):
                        merged["kwargs"] = {}
                    return merged

        if not isinstance(step_config.get("kwargs"), dict):
            step_config["kwargs"] = {}
        return step_config


    @staticmethod
    def _provider_requires_api_key(provider_key: str) -> bool:
        return provider_key in {"gemini"}


    @staticmethod
    def _phase_payload(
        *,
        phase: str,
        status: str,
        message: str,
        **data: Any,
    ) -> dict[str, Any]:
        payload = {
            "phase": phase,
            "status": status,
            "message": message,
            "timestamp": _utc_now_iso(),
        }
        payload.update(data)
        return payload


    @staticmethod
    def _score_translation_confidence(source_text: str, translated_text: str) -> float:
        source = source_text.strip()
        translated = translated_text.strip()
        if not source or not translated:
            return 0.0

        source_compact = "".join(source.split())
        translated_compact = "".join(translated.split())
        if not source_compact or not translated_compact:
            return 0.0
        if source_compact == translated_compact:
            return 0.0

        score = 1.0
        length_ratio = len(translated_compact) / max(1, len(source_compact))
        if length_ratio < 0.25:
            score -= 0.45
        elif length_ratio < 0.4:
            score -= 0.2

        cjk_chars = [ch for ch in source_compact if "\u3040" <= ch <= "\u9fff"]
        if cjk_chars:
            unchanged = sum(1 for ch in cjk_chars if ch in translated_compact)
            unchanged_ratio = unchanged / len(cjk_chars)
            if unchanged_ratio > 0.8:
                score -= 0.55
            elif unchanged_ratio > 0.6:
                score -= 0.25

        return max(0.0, min(1.0, score))


    @classmethod
    def _is_low_confidence_translation(
        cls,
        source_text: str,
        translated_text: str,
        threshold: float = 0.55,
    ) -> bool:
        normalized_threshold = max(0.0, min(1.0, threshold))
        return cls._score_translation_confidence(source_text, translated_text) < normalized_threshold


    def _selected_chapter_numbers(self, metadata: dict[str, Any], selection: str) -> list[int]:
        """Resolve a chapter selection string into concrete chapter numbers.

        Returns all chapter IDs when *selection* is ``"all"``; otherwise
        parses the DSL (e.g. ``"1-3;5"``) via :func:`parse_chapter_selection`.
        """
        chapter_map = {
            int(chapter["id"]): chapter
            for chapter in metadata.get("chapters", [])
            if isinstance(chapter, dict) and str(chapter.get("id", "")).isdigit()
        }
        if is_full_chapter_selection(selection):
            return sorted(chapter_map.keys())

        return [spec.chapter for spec in parse_chapter_selection(selection)]


    @staticmethod
    def _chapter_content_signature(text: str, images: list[dict[str, Any]] | None = None) -> str:
        image_items = []
        for image in images or []:
            if not isinstance(image, dict):
                continue
            image_items.append(
                {
                    "index": image.get("index"),
                    "placeholder": image.get("placeholder"),
                    "original_url": image.get("original_url"),
                    "alt": image.get("alt"),
                    "title": image.get("title"),
                }
            )
        payload = {
            "text": text,
            "images": image_items,
        }
        return json.dumps(payload, ensure_ascii=False, sort_keys=True)


    def _resolve_provider_and_model(
        self,
        provider_key: str | None = None,
        provider_model: str | None = None,
    ) -> tuple[str, str]:
        key = provider_key or self._settings.get_preferred_provider()
        model = provider_model or self._settings.get_provider_model()
        if self._provider_requires_api_key(key) and not self._settings.get_api_key(key):
            raise ProviderConfigError(
                ProviderErrorCode.CONFIGURATION,
                provider_key=key,
                provider_model=model,
                message="Gemini provider is not configured. Add an API key in Settings.",
            )
        if key == "dummy":
            if settings.ENV != "test":
                raise ProviderConfigError(
                    ProviderErrorCode.CONFIGURATION,
                    provider_key=key,
                    provider_model="dummy",
                    message="The dummy provider is available only when ENV=test.",
                )
            return "dummy", "dummy"
        return key, model


    def _record_usage(self, provider_key: str, model: str, metadata: Any) -> None:
        usage = metadata.get("usage") if isinstance(metadata, dict) else None
        self._usage.record(
            {
                "timestamp": _utc_now_iso(),
                "provider": provider_key,
                "model": model,
                "tokens": usage.get("total_tokens") if isinstance(usage, dict) else None,
                "metadata": metadata if isinstance(metadata, dict) else {},
            }
        )


    @staticmethod
    def _latest_checkpoint_name(storage: StorageService, novel_id: str, chapter_id: str) -> str | None:
        checkpoints = storage.list_checkpoints(novel_id, chapter_id)
        if not checkpoints:
            return None
        return checkpoints[-1].get("checkpoint_name")


    def _restore_latest_checkpoint_for_resume(self, novel_id: str, chapter_id: str) -> bool:
        checkpoint_name = self._latest_checkpoint_name(self.storage, novel_id, chapter_id)
        if not checkpoint_name:
            return False
        restored = self.storage.restore_from_checkpoint(novel_id, chapter_id, checkpoint_name)
        if restored:
            safely_refresh_catalog_projection_after_storage_write(
                novel_id,
                self.storage,
                context="checkpoint_restore",
            )
            logger.info(
                "Restored latest checkpoint '%s' before resuming chapter %s/%s.",
                checkpoint_name,
                novel_id,
                chapter_id,
            )
        return restored


    # OCR workflows
    _extract_ocr_candidate_text = staticmethod(_extract_ocr_candidate_text)
    ingest_ocr_candidates = ingest_ocr_candidates

    # Document import workflows
    import_document = import_document

    # Glossary workflows
    extract_glossary_terms = extract_glossary_terms
    _extract_glossary_terms_with_llm = _extract_glossary_terms_with_llm
    _parse_llm_glossary_terms = staticmethod(_parse_llm_glossary_terms)
    translate_glossary_terms = translate_glossary_terms
    review_glossary_terms = review_glossary_terms
    apply_glossary_to_chapters = apply_glossary_to_chapters

    # Translation workflows
    _preflight_translation = _preflight_translation
    polish_low_confidence_chapters = polish_low_confidence_chapters
    run_phased_translation_pipeline = run_phased_translation_pipeline
    _translate_text = _translate_text
    _translate_metadata_fields = _translate_metadata_fields
    estimate_translation_requests = estimate_translation_requests
    translate_chapters = translate_chapters
    retranslate_chapter = retranslate_chapter

    # Crawler workflows
    scrape_metadata = scrape_metadata
    scrape_chapters = scrape_chapters


__all__ = ["NovelOrchestrationService", "PreflightIssue"]
