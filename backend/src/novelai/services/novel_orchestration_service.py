from __future__ import annotations

import json
import logging
import re
from collections.abc import Callable
from typing import Any

from novelai.config.settings import GEMINI_DEFAULT_MODEL, settings
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
from novelai.utils.chapter_selection import (
    ResolvedChapterSelection,
    resolve_chapter_ids,
    resolve_chapter_selection,
    select_sequence_numbers,
)

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
        provider_key = step_config.get("provider_key")
        provider_model = step_config.get("provider_model")
        return (
            provider_key if isinstance(provider_key, str) and provider_key.strip() else None,
            provider_model if isinstance(provider_model, str) and provider_model.strip() else None,
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
                    unsupported_fields = set(override_payload) - set(step_config)
                    if unsupported_fields:
                        raise ValueError(
                            f"Unsupported translation step fields: {', '.join(sorted(unsupported_fields))}"
                        )
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
        """Resolve a chapter selection string into concrete sequence numbers.

        Section 2: the orchestrator and downstream storage/translation paths
        operate on stable ``chapter_id`` values, but legacy entry points and
        downstream comparisons still consume the integer sequence position.
        Numeric and stable-id selections both resolve here, so calling
        ``is_translation_valid`` and chapter-state plumbing never treats a
        non-numeric id as a missing chapter.
        """
        return select_sequence_numbers(metadata, selection)

    def _selected_chapter_ids(self, metadata: dict[str, Any], selection: str) -> list[str]:
        """Stable chapter_ids backing the current selection."""
        return resolve_chapter_ids(metadata, selection)

    def _resolve_selection(
        self,
        metadata: dict[str, Any],
        selection: str,
    ) -> list[ResolvedChapterSelection]:
        """Full resolved-selection records (chapter_id, source_episode_id, sequence)."""
        return resolve_chapter_selection(metadata, selection)

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

    @staticmethod
    def _normalize_identity(value: str | None) -> str | None:
        """Normalize a provider/model identity input.

        Surrounding whitespace is stripped; empty / whitespace-only values and
        non-strings are treated as absent (``None``). The resolver never emits
        a malformed-whitespace identity as part of a contract.
        """
        if not isinstance(value, str):
            return None
        stripped = value.strip()
        return stripped or None

    @staticmethod
    def _available_models_for(provider: TranslationProvider) -> list[str]:
        """Return the provider's authoritative model list, or ``[]`` (free-form).

        ``available_models() == []`` means the provider accepts free-form model
        identifiers (any non-empty model is valid); a non-empty list is the
        authoritative set the model must belong to. An exception raised by
        ``available_models()`` means the provider contract cannot be determined
        and must fail closed with ``ProviderConfigError``.
        """
        try:
            models = provider.available_models()
        except Exception as exc:
            pkey = getattr(provider, "key", None) or getattr(provider, "name", "unknown")
            logger.warning(
                "Failed to resolve available models for provider %r (%s)",
                pkey,
                type(exc).__name__,
            )
            raise ProviderConfigError(
                ProviderErrorCode.CONFIGURATION,
                provider_key=str(pkey),
                message=f"Failed to resolve available models for provider {pkey!r}: {type(exc).__name__}",
            ) from None
        return [str(model) for model in models] if isinstance(models, list) else []

    def _provider_instance(self, key: str, *, for_model: str | None = None) -> TranslationProvider:
        """Return the provider registered for *key*.

        Converts factory lookup failures (an incidental ``KeyError`` from an
        unregistered provider) into the established ``ProviderConfigError``
        configuration-error contract so a translation run never persists a
        manifest for a provider that does not exist. Called at resolution time
        (here, for validation) and again later by ``TranslateStage`` for the
        real execution; both are deterministic constructor calls with no
        network side effects.
        """
        try:
            return self._provider_factory(key)
        except KeyError:
            raise ProviderConfigError(
                ProviderErrorCode.CONFIGURATION,
                provider_key=key,
                provider_model=for_model,
                message=f"Unknown translation provider: {key!r}. "
                f"Registered providers are managed in the provider registry.",
            ) from None
        except ProviderConfigError:
            raise
        except Exception as exc:
            logger.warning("Translation provider %r creation failed (%s)", key, type(exc).__name__)
            raise ProviderConfigError(
                ProviderErrorCode.CONFIGURATION,
                provider_key=key,
                provider_model=for_model,
                message=f"Translation provider {key!r} could not be created: {type(exc).__name__}.",
            ) from None

    def _assert_special_provider_guards(
        self,
        key: str,
        *,
        model: str | None = None,
        contributor_mode: bool = False,
    ) -> None:
        """Preserve the established fail-closed configuration guards.

        Gemini requires a configured API key and ``dummy`` is available only
        when ``ENV=test``. Both are checked here so they run before any
        TranslationRunManifest is created — the pipeline stage never discovers
        these misconfigurations late.
        """
        if self._provider_requires_api_key(key) and not contributor_mode and not self._settings.get_api_key(key):
            raise ProviderConfigError(
                ProviderErrorCode.CONFIGURATION,
                provider_key=key,
                provider_model=model,
                message="Gemini provider is not configured. Add an API key in Settings.",
            )
        if key == "dummy" and settings.ENV != "test":
            raise ProviderConfigError(
                ProviderErrorCode.CONFIGURATION,
                provider_key=key,
                provider_model=model or "dummy",
                message="The dummy provider is available only when ENV=test.",
            )

    def _resolve_effective_provider_contract(
        self,
        *,
        step: str | None,
        metadata: dict[str, Any] | None,
        provider_key: str | None,
        provider_model: str | None,
        contributor_mode: bool = False,
    ) -> tuple[str, str]:
        """Resolve the authoritative provider/model contract identity for a
        workflow step as ONE validated pair.

        This is the SINGLE resolution point for the requested provider/model
        contract identity (Section 3, PR 41 closure). The pair is resolved,
        validated and returned atomically — every consumer (run manifest,
        resume gate, delta retranslation, pipeline execution, stored lineage)
        records and compares the same pair, so a translation version never
        records a provider identity while silently executing a model selected
        for a different provider.

        Provider precedence is strict:

        1. Explicit caller values (``provider_key`` / ``provider_model``)
        2. The effective workflow profile for ``step`` (novel-level profiles,
           then global step configs, then endpoint profiles — already merged by
           ``_resolve_workflow_step_config`` / ``resolve_step_llm_config``)
        3. The global preferred provider / model preferences

        The model is resolved FOR the selected provider so a model validated
        against a different provider is never carried across. Inputs are
        normalized (whitespace stripped; empty / whitespace-only treated as
        absent); the result is guaranteed non-empty (never ``""`` / ``None``).
        Configuration errors — unknown provider, Gemini without an API key,
        ``dummy`` outside ``ENV=test``, an explicit model the provider contract
        declares unsupported — fail closed here, before any contract is
        created. A provider with ``available_models() == []`` is treated as
        free-form (any non-empty explicit/identifiable model is valid); a
        provider with an authoritative list validates against it.

        ``step`` may be ``None`` to skip the workflow-profile layer entirely
        (used by the metadata/glossary/crawler steps that predate profiles).
        """
        explicit_provider = self._normalize_identity(provider_key)
        explicit_model = self._normalize_identity(provider_model)
        profile_provider: str | None = None
        profile_model: str | None = None
        if step is not None:
            raw_profile_provider, raw_profile_model = self._resolve_workflow_profile(step, metadata)
            profile_provider = self._normalize_identity(raw_profile_provider)
            profile_model = self._normalize_identity(raw_profile_model)
        global_provider = self._normalize_identity(self._settings.get_preferred_provider())
        global_model = self._normalize_identity(self._settings.get_preferred_model())

        # 1) Resolve the provider (explicit > workflow > global); never None.
        resolved_provider = explicit_provider or profile_provider or global_provider
        if not resolved_provider:
            raise ProviderConfigError(
                ProviderErrorCode.CONFIGURATION,
                provider_key=explicit_provider,
                provider_model=explicit_model,
                message="No translation provider is configured. "
                "Set a preferred provider or pass an explicit provider key.",
            )

        # 2) Validate provider existence + the established config guards BEFORE
        #    the model is even chosen, so a manifest is never created for a
        #    provider that does not exist or cannot authenticate.
        provider = self._provider_instance(resolved_provider, for_model=explicit_model)
        self._assert_special_provider_guards(
            resolved_provider,
            model=explicit_model,
            contributor_mode=contributor_mode,
        )
        supported = self._available_models_for(provider)

        if resolved_provider == "gemini" and explicit_model is None:
            # Stored workflow/preferences may still carry a retired model
            # name. Resolve the known production contract explicitly instead
            # of treating that stale value as a fallback candidate.
            return resolved_provider, GEMINI_DEFAULT_MODEL

        # 3) Validate an explicit model up front (fail closed, do not silently
        #    fall back to a default — the caller asked for a specific model).
        #    Section 4.3 A/E: an unsupported explicit model is a configuration
        #    error, not an opportunity to pick another model.
        if explicit_model:
            if supported and explicit_model not in supported:
                raise ProviderConfigError(
                    ProviderErrorCode.CONFIGURATION,
                    provider_key=resolved_provider,
                    provider_model=explicit_model,
                    message=(
                        f"Translation provider {resolved_provider!r} does not support "
                        f"model {explicit_model!r}. Supported models: {', '.join(supported)}."
                    ),
                )
            return resolved_provider, explicit_model

        # 4) Resolve the model FOR the selected provider when the caller did
        #    not give one. Candidates, in precedence order:
        #    - the workflow profile's model ONLY when it is coherent with the
        #      selected provider (i.e. the workflow provider equals the
        #      resolved provider); a workflow model validated against a
        #      different provider is never carried across (Section 4.3 B/D).
        #    - the global preferred model ONLY when the global preferred
        #      provider equals the resolved provider (Section 4.3 F).
        #    - the provider's own preferred/default model.
        candidate_models: list[str] = []
        if profile_model and profile_provider == resolved_provider:
            candidate_models.append(profile_model)
        if global_model and global_provider == resolved_provider:
            candidate_models.append(global_model)
        provider_default = supported[0] if supported else None
        if provider_default:
            candidate_models.append(provider_default)

        resolved_model: str | None = None
        for candidate in candidate_models:
            if not candidate:
                continue
            # Free-form (supported == []) accepts any non-empty model.
            if not supported or candidate in supported:
                resolved_model = candidate
                break
        if not resolved_model:
            raise ProviderConfigError(
                ProviderErrorCode.CONFIGURATION,
                provider_key=resolved_provider,
                provider_model=None,
                message=(
                    f"No translation model is configured for provider {resolved_provider!r}. "
                    "Configure a preferred model or pass an explicit model."
                ),
            )
        return resolved_provider, resolved_model

    def _resolve_provider_and_model(
        self,
        provider_key: str | None = None,
        provider_model: str | None = None,
    ) -> tuple[str, str]:
        """Legacy two-level resolution (explicit caller > global preferred).

        Used by the metadata translation / glossary / crawler steps that do not
        participate in workflow profiles; delegates to the authoritative
        contract resolver with no profile layer so the normalization,
        provider-existence and Gemini/dummy guards stay in exactly one place.
        """
        return self._resolve_effective_provider_contract(
            step=None,
            metadata=None,
            provider_key=provider_key,
            provider_model=provider_model,
        )

    def _record_usage(self, provider_key: str, model: str, metadata: Any) -> None:
        if isinstance(metadata, dict) and metadata.get("usage_accounting_recorded") is True:
            return
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
