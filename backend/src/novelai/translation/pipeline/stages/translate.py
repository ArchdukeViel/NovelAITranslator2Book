from __future__ import annotations

import asyncio
import logging
import uuid
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from novelai.config.settings import settings
from novelai.core.errors import PipelineStageError, ProviderConfigError, ProviderError, ProviderErrorCode
from novelai.prompts.models import TranslationRequest
from novelai.providers.base import TranslationProvider
from novelai.providers.model_fallbacks import model_candidates
from novelai.services.glossary_diagnostics import (
    normalize_glossary_diagnostics,
)
from novelai.services.glossary_prompt_injection import (
    GlossaryPromptInjectionService,
    PromptGlossaryBlock,
)
from novelai.services.glossary_repository import GlossaryRepository
from novelai.services.preferences_service import PreferencesService
from novelai.services.translation_cache import TranslationCache, TranslationCacheService
from novelai.services.usage_service import UsageService
from novelai.shared.pipeline import ChunkAttemptStatus, ChunkTranslationStatus
from novelai.storage.service import StorageService
from novelai.translation.pipeline.context import PipelineContext, TranslationChunk
from novelai.translation.pipeline.stages.base import PipelineStage
from novelai.translation.pipeline.stages.translate_cache_lookup import (
    cached_translation,
    load_existing_chunk_output,
    load_persisted_chunk_states,
    persist_chunk_state,
    save_chunk_attempt,
    save_chunk_output,
    save_chunk_records,
)
from novelai.translation.pipeline.stages.translate_provider_call import (
    provider_error_from_generic,
    provider_error_metadata,
    provider_request_record,
)
from novelai.translation.pipeline.stages.translate_result_assembly import (
    build_prompt_request,
    glossary_prompt_options,
    infer_source_language,
    nonnegative_int,
    normalize_runtime_glossary,
    observe_chunk_context,
    platform_novel_id,
    prompt_version,
    record_prompt_glossary_metadata,
    safe_job_id,
    select_chunk_glossary,
    utc_now_iso,
)
from novelai.translation.pipeline.stages.translate_result_assembly import (
    chapter_ids as chapter_ids_h,
)
from novelai.translation.pipeline.stages.translate_result_assembly import (
    chunk_id as chunk_id_h,
)
from novelai.translation.pipeline.stages.translate_result_assembly import (
    chunk_text as chunk_text_h,
)
from novelai.translation.pipeline.stages.translate_result_assembly import (
    explicit_translation_run_id as explicit_run_id_h,
)
from novelai.translation.pipeline.stages.translate_result_assembly import (
    force_retranslate as force_retranslate_h,
)
from novelai.translation.pipeline.stages.translate_result_assembly import (
    glossary_hash as glossary_hash_h,
)
from novelai.translation.pipeline.stages.translate_result_assembly import (
    paragraph_hashes as paragraph_hashes_h,
)
from novelai.translation.pipeline.stages.translate_result_assembly import (
    paragraph_ids as paragraph_ids_h,
)
from novelai.translation.pipeline.stages.translate_result_assembly import (
    paragraph_lineage as paragraph_lineage_h,
)
from novelai.translation.pipeline.stages.translate_result_assembly import (
    translation_run_id as run_id_h,
)
from novelai.translation.scheduler import (
    SchedulerDecisionRecorder,
    SchedulerPausedError,
    SelectionReason,
    TranslationScheduler,
    normalize_model_configs,
    normalize_policy,
    utc_now,
)

logger = logging.getLogger(__name__)

MAX_ATTEMPTS_EXCEEDED_ERROR_CODE = "max_attempts_exceeded"


class TranslateStage(PipelineStage):
    # Backward-compat shims for extracted static methods
    _glossary_hash = staticmethod(glossary_hash_h)
    _chunk_text = staticmethod(chunk_text_h)
    _chunk_id = staticmethod(chunk_id_h)
    _chapter_ids = staticmethod(chapter_ids_h)
    _paragraph_ids = staticmethod(paragraph_ids_h)
    _paragraph_hashes = staticmethod(paragraph_hashes_h)
    _paragraph_lineage = staticmethod(paragraph_lineage_h)
    _translation_run_id = staticmethod(run_id_h)
    _explicit_translation_run_id = staticmethod(explicit_run_id_h)
    _force_retranslate = staticmethod(force_retranslate_h)
    _safe_job_id = staticmethod(safe_job_id)
    _platform_novel_id = staticmethod(platform_novel_id)
    _infer_source_language = staticmethod(infer_source_language)
    _provider_error_from_generic = staticmethod(provider_error_from_generic)
    _provider_error_metadata = staticmethod(provider_error_metadata)
    _provider_request_record = staticmethod(provider_request_record)
    _build_prompt_request = staticmethod(build_prompt_request)
    _observe_chunk_context = staticmethod(observe_chunk_context)
    _glossary_prompt_options = staticmethod(glossary_prompt_options)
    _record_prompt_glossary_metadata = staticmethod(record_prompt_glossary_metadata)
    _select_chunk_glossary = staticmethod(select_chunk_glossary)
    _normalize_runtime_glossary = staticmethod(normalize_runtime_glossary)
    _nonnegative_int = staticmethod(nonnegative_int)
    _prompt_version = staticmethod(prompt_version)
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
        storage: StorageService | None = None,
        glossary_prompt_service: GlossaryPromptInjectionService | None = None,
        cache_service: TranslationCacheService | None = None,
    ) -> None:
        if provider_factory is None:
            # Default: import and use registry
            from novelai.providers.registry import get_provider
            provider_factory = get_provider

        self._provider_factory = provider_factory
        self._concurrency = concurrency or settings.TRANSLATION_CONCURRENCY
        self._cache = cache or TranslationCache()
        self._cache_service = cache_service or TranslationCacheService()
        self._settings = settings_service or PreferencesService()
        self._usage = usage_service or UsageService()
        self._storage = storage or StorageService()
        self._glossary_prompt_service = glossary_prompt_service
        configured_max_attempts = settings.TRANSLATION_MAX_ATTEMPTS_PER_CHUNK
        self._max_attempts_per_chunk = configured_max_attempts if configured_max_attempts > 0 else 3

    def _resolve_provider_and_model(self, provider_key: str, model: str) -> tuple[str, str]:
        if provider_key == "gemini" and not self._settings.get_api_key(provider_key):
            raise ProviderConfigError(
                ProviderErrorCode.CONFIGURATION,
                provider_key=provider_key,
                provider_model=model,
                message="Gemini provider is not configured. Add an API key in Settings.",
            )
        if provider_key == "dummy" and settings.ENV != "test":
            raise ProviderConfigError(
                ProviderErrorCode.CONFIGURATION,
                provider_key=provider_key,
                provider_model=model,
                message="The dummy provider is available only when ENV=test.",
            )
        return provider_key, model

    def _max_attempts_exceeded_error(
        self,
        context: PipelineContext,
        *,
        chunk_id: str,
        attempt_count: int,
        provider_key: str | None,
        provider_model: str | None,
        latest_error_code: str | None,
        latest_error_message: str | None,
    ) -> PipelineStageError:
        details = {
            "chunk_id": chunk_id,
            "attempt_count": attempt_count,
            "max_attempts": self._max_attempts_per_chunk,
            "request_id": context.metadata.get("request_id"),
            "provider_key": provider_key,
            "provider_model": provider_model,
            "latest_error_code": latest_error_code,
            "latest_error_message": latest_error_message,
        }
        error = PipelineStageError(
            f"Translation max attempts exceeded for chunk {chunk_id}: "
            f"{attempt_count}/{self._max_attempts_per_chunk} attempts."
        )
        error.error_code = MAX_ATTEMPTS_EXCEEDED_ERROR_CODE
        error.details = details
        error.pipeline_context = context
        return error

    def _save_scheduler_state(self, context: PipelineContext, scheduler: TranslationScheduler) -> None:
        context.scheduler_state = scheduler.to_dict()
        context.metadata["model_states"] = scheduler.to_model_state_list()
        progress = context.metadata.setdefault("progress", {})
        if isinstance(progress, dict):
            progress["model_states"] = scheduler.to_model_state_list()
        job_id = safe_job_id(context)
        if job_id is not None:
            self._storage.save_scheduler_state(job_id, scheduler.to_model_state_list())

    def _build_scheduler(
        self,
        context: PipelineContext,
        *,
        provider_key: str,
        model: str,
    ) -> TranslationScheduler:
        try:
            provider = self._provider_factory(provider_key)
            supported = provider.available_models() or []
        except Exception:
            supported = []
        candidates = model_candidates(provider_key, model, supported)
        policy = normalize_policy(context.metadata.get("scheduler_policy") or settings.TRANSLATION_SCHEDULER_POLICY)
        raw_policy = context.metadata.get("scheduler_models")
        admin_policy_consulted = False
        admin_policy_intentionally_empty = False
        if not isinstance(raw_policy, list):
            raw_policy = self._admin_provider_policy_models(
                provider_key=provider_key,
                model=model,
                allow_cross_provider_fallback=context.metadata.get("allow_cross_provider_fallback", True) is not False,
            )
            admin_policy_consulted = True
            if raw_policy is not None and not raw_policy:
                admin_policy_intentionally_empty = True
        if not isinstance(raw_policy, list):
            raw_policy = settings.TRANSLATION_MODEL_POLICY
        allow_cross_provider_fallback = context.metadata.get("allow_cross_provider_fallback", True) is not False
        filtered_count = 0
        if not allow_cross_provider_fallback:
            if isinstance(raw_policy, list):
                original_policy = raw_policy
                raw_policy = [
                    item
                    for item in original_policy
                    if isinstance(item, dict) and (item.get("provider_key") or item.get("provider") or provider_key) == provider_key
                ]
                filtered_count = len(original_policy) - len(raw_policy)
                if not raw_policy:
                    if filtered_count:
                        admin_policy_intentionally_empty = True
                    raw_policy = None
            context.metadata["provider_lock"] = provider_key
            context.metadata["allow_cross_provider_fallback"] = False
            if filtered_count:
                context.metadata["provider_lock_filtered_candidates"] = filtered_count
        # Only fall back to default gemini model if no admin policy was set
        if allow_cross_provider_fallback and not raw_policy and provider_key == "gemini" and not admin_policy_consulted:
            raw_policy = [
                {
                    "provider_key": "gemini",
                    "provider_model": model,
                    "priority_order": 0,
                },
            ]
        configs = normalize_model_configs(raw_policy, default_provider_key=provider_key, default_models=candidates, allow_empty=admin_policy_intentionally_empty)
        existing_state = context.scheduler_state
        job_id = safe_job_id(context)
        if job_id is not None:
            stored = self._storage.load_scheduler_state(job_id)
            if isinstance(stored, dict):
                existing_state = stored
        return TranslationScheduler.from_configs(configs, policy=policy, existing_state=existing_state)

    def _admin_provider_policy_models(
        self,
        *,
        provider_key: str,
        model: str,
        allow_cross_provider_fallback: bool,
    ) -> list[dict[str, Any]] | None:
        management = self._settings.get_provider_management()
        policy = management.get("fallback_policy") if isinstance(management.get("fallback_policy"), dict) else None
        if not isinstance(policy, dict):
            return None
        raw_candidates = policy.get("candidates")
        if not isinstance(raw_candidates, list):
            return None
        configs: list[dict[str, Any]] = []
        skipped: list[dict[str, str]] = []
        credentials = management.get("credentials") if isinstance(management.get("credentials"), dict) else {}
        for index, item in enumerate(raw_candidates):
            if not isinstance(item, dict):
                continue
            candidate_provider = item.get("provider_key") or item.get("provider") or provider_key
            candidate_model = item.get("provider_model") or item.get("model") or model
            credential_id = item.get("credential_id") or candidate_provider
            if not isinstance(candidate_provider, str) or not isinstance(candidate_model, str):
                continue
            if item.get("enabled", True) is False:
                skipped.append({"provider_key": candidate_provider, "provider_model": candidate_model, "reason": "disabled"})
                continue
            if not allow_cross_provider_fallback and candidate_provider != provider_key:
                skipped.append({"provider_key": candidate_provider, "provider_model": candidate_model, "reason": "provider_locked"})
                continue
            credential = credentials.get(credential_id) if isinstance(credentials, dict) else None
            if isinstance(credential, dict) and credential.get("is_active") is False:
                skipped.append({"provider_key": candidate_provider, "provider_model": candidate_model, "reason": "credential_disabled"})
                continue
            if isinstance(credential, dict) and credential.get("validation_status") == "failed":
                skipped.append({"provider_key": candidate_provider, "provider_model": candidate_model, "reason": "credential_invalid"})
                continue
            if isinstance(credential_id, str) and self._settings.get_api_key(credential_id) is None:
                skipped.append({"provider_key": candidate_provider, "provider_model": candidate_model, "reason": "credential_missing"})
                continue
            configs.append(
                {
                    "provider_key": candidate_provider,
                    "provider_model": candidate_model,
                    "priority_order": nonnegative_int(item.get("priority_order"), default=index),
                    "rpm_limit": item.get("rpm_limit"),
                    "rpd_limit": item.get("rpd_limit"),
                }
            )
        if skipped:
            context_skips = getattr(self, "_last_admin_policy_skips", [])
            context_skips.extend(skipped)
            self._last_admin_policy_skips = context_skips
        return configs

    # Backward-compat shims for extracted cache methods
    def _save_chunk_records(self, context: PipelineContext, chunks: list[str | TranslationChunk]) -> None:
        save_chunk_records(self._storage, context, chunks)

    def _load_persisted_chunk_states(self, context: PipelineContext) -> None:
        load_persisted_chunk_states(self._storage, context)

    def _load_existing_chunk_output(
        self,
        context: PipelineContext,
        *,
        chunk_id: str,
        chunk_text: str,
        chapter_ids: list[str],
        glossary_hash: str | None = None,
    ) -> str | None:
        return load_existing_chunk_output(
            self._storage, context,
            chunk_id=chunk_id, chunk_text=chunk_text,
            chapter_ids=chapter_ids, glossary_hash=glossary_hash,
        )

    def _save_chunk_attempt(
        self,
        context: PipelineContext,
        *,
        chunk: str | TranslationChunk,
        chunk_index: int,
        attempt_number: int,
        provider_key: str | None,
        provider_model: str | None,
        scheduler_policy: str | None,
        selection_reason: str | None,
        status: str,
        error_code: str | None = None,
        qa_score: float | None = None,
        qa_status: str | None = None,
    ) -> None:
        save_chunk_attempt(
            self._storage, context,
            chunk=chunk, chunk_index=chunk_index,
            attempt_number=attempt_number,
            provider_key=provider_key, provider_model=provider_model,
            scheduler_policy=scheduler_policy, selection_reason=selection_reason,
            status=status, error_code=error_code,
            qa_score=qa_score, qa_status=qa_status,
        )

    def _save_chunk_output(
        self,
        context: PipelineContext,
        *,
        chunk: str | TranslationChunk,
        chunk_index: int,
        translated_text: str,
        provider_key: str,
        provider_model: str,
        cache_hit: bool,
        attempt_number: int,
        scheduler_policy: str | None,
        selection_reason: str | None,
        glossary_hash: str | None = None,
    ) -> None:
        save_chunk_output(
            self._storage, context,
            chunk=chunk, chunk_index=chunk_index,
            translated_text=translated_text,
            provider_key=provider_key, provider_model=provider_model,
            cache_hit=cache_hit, attempt_number=attempt_number,
            scheduler_policy=scheduler_policy, selection_reason=selection_reason,
            glossary_hash=glossary_hash,
        )

    def _persist_chunk_state(self, context: PipelineContext, chunk_id: str) -> None:
        persist_chunk_state(self._storage, context, chunk_id)

    def _build_prompt_glossary_block(
        self,
        context: PipelineContext,
        chunk_text: str,
    ) -> PromptGlossaryBlock | None:
        novel_id = platform_novel_id(context)
        if novel_id is None:
            return None

        options = glossary_prompt_options(context)
        service = self._glossary_prompt_service
        if service is not None:
            return service.build_for_chapter(novel_id, raw_chapter_text=chunk_text, options=options)

        try:
            from novelai.db.engine import session_scope

            with session_scope() as session:
                repository = GlossaryRepository(session)
                return GlossaryPromptInjectionService(repository).build_for_chapter(
                    novel_id,
                    raw_chapter_text=chunk_text,
                    options=options,
                )
        except Exception as exc:
            warnings = context.metadata.setdefault("glossary_prompt_warnings", [])
            if isinstance(warnings, list):
                warnings.append("glossary_prompt_build_failed")
            logger.warning("Glossary prompt block could not be built: %s", exc.__class__.__name__)
            return None

    def _cached_translation(
        self,
        context: PipelineContext,
        *,
        provider_key: str,
        provider_model: str,
        chunk: str,
        request: TranslationRequest | None,
        glossary_hash: str | None = None,
    ) -> tuple[str, str, str, bool] | None:
        p_key, p_model = self._resolve_provider_and_model(provider_key, provider_model)
        return cached_translation(
            self._cache, self._cache_service, context,
            provider_key=p_key, provider_model=p_model,
            chunk=chunk, request=request, glossary_hash=glossary_hash,
        )

    async def _translate_with_model(
        self,
        context: PipelineContext,
        *,
        provider_key: str,
        provider_model: str,
        chunk_id: str,
        chapter_ids: list[str],
        paragraph_ids: list[str],
        attempt_number: int,
        scheduler_policy: str,
        selection_reason: str,
        chunk: str,
        request: TranslationRequest | None = None,
        glossary_hash: str | None = None,
    ) -> tuple[str, str, str, bool]:
        provider_key, provider_model = self._resolve_provider_and_model(provider_key, provider_model)
        provider = self._provider_factory(provider_key)

        started_at = utc_now_iso()
        try:
            logger.debug("Translating chunk %s (len=%s) with %s/%s", chunk_id, len(chunk), provider.key, provider_model)
            result = await provider.translate(prompt=chunk, model=provider_model, request=request)
        except ProviderError as exc:
            finished_at = utc_now_iso()
            self._storage.save_provider_request_record(
                provider_request_record(
                    context,
                    chunk_id=chunk_id,
                    chunk_text=chunk,
                    request=request,
                    provider_key=exc.provider_key,
                    provider_model=exc.provider_model,
                    glossary_hash=glossary_hash,
                    chapter_ids=chapter_ids,
                    paragraph_ids=paragraph_ids,
                    attempt_number=attempt_number,
                    scheduler_policy=scheduler_policy,
                    selection_reason=selection_reason,
                    started_at=started_at,
                    finished_at=finished_at,
                    success=False,
                    error=exc,
                )
            )
            raise
        except Exception as exc:
            finished_at = utc_now_iso()
            provider_error = provider_error_from_generic(exc, provider_key=provider.key, provider_model=provider_model)
            self._storage.save_provider_request_record(
                provider_request_record(
                    context,
                    chunk_id=chunk_id,
                    chunk_text=chunk,
                    request=request,
                    provider_key=provider.key,
                    provider_model=provider_model,
                    glossary_hash=glossary_hash,
                    chapter_ids=chapter_ids,
                    paragraph_ids=paragraph_ids,
                    attempt_number=attempt_number,
                    scheduler_policy=scheduler_policy,
                    selection_reason=selection_reason,
                    started_at=started_at,
                    finished_at=finished_at,
                    success=False,
                    error=provider_error,
                )
            )
            raise provider_error from exc

        text = str(result.get("text", ""))
        metadata = result.get("metadata") or {}
        usage_entry = {
            "timestamp": utc_now_iso(),
            "provider": provider.key,
            "model": provider_model,
            "tokens": None,
            "metadata": metadata,
        }
        usage = metadata.get("usage") if isinstance(metadata, dict) else None
        if isinstance(usage, dict):
            usage_entry["tokens"] = usage.get("total_tokens")
            logger.debug("Translation tokens: %s", usage_entry["tokens"])

        self._usage.record(usage_entry)

        cache_key: str | None = None
        entry: CacheEntry | None = None
        if settings.TRANSLATION_CACHE_ENABLED:
            try:
                from novelai.services.translation_cache import CacheEntry, make_cache_key
                source_language = infer_source_language(context) or "auto"
                target_language = context.metadata.get("target_language") or settings.TRANSLATION_TARGET_LANGUAGE
                g_hash = glossary_hash or ""
                prompt_version = context.metadata.get("prompt_version") or ""
                cache_key = make_cache_key(
                    chunk, source_language, target_language, g_hash,
                    provider_key=provider.key,
                    provider_model=provider_model,
                    prompt_version=prompt_version,
                )
                entry = CacheEntry(
                    key=cache_key,
                    source_text=chunk,
                    translated_text=text,
                    source_language=source_language,
                    target_language=target_language,
                    glossary_hash=g_hash,
                    provider_key=provider.key,
                    provider_model=provider_model,
                    created_at=datetime.now(UTC).isoformat(),
                    ttl_seconds=settings.TRANSLATION_CACHE_TTL_SECONDS,
                    novel_id=context.novel_id,
                )
                logger.debug("Cache miss for chunk: key=%s, cache_hit=False", cache_key[:16])
            except Exception as exc:
                logger.warning("Cache write error: %s", exc)

        if cache_key is not None and entry is not None:
            pending = context.metadata.setdefault("_pending_cache_entries", [])
            pending.append((cache_key, entry))

        cache_key = request.cache_key() if request is not None else chunk
        self._cache.set(cache_key, provider.key, provider_model, text)
        self._storage.save_provider_request_record(
            provider_request_record(
                context,
                chunk_id=chunk_id,
                chunk_text=chunk,
                request=request,
                provider_key=provider.key,
                provider_model=provider_model,
                glossary_hash=glossary_hash,
                chapter_ids=chapter_ids,
                paragraph_ids=paragraph_ids,
                attempt_number=attempt_number,
                scheduler_policy=scheduler_policy,
                selection_reason=selection_reason,
                started_at=started_at,
                finished_at=utc_now_iso(),
                success=True,
                metadata=metadata,
            )
        )
        return text, provider.key, provider_model, False

    async def run(self, context: PipelineContext) -> PipelineContext:
        chunks: list[str | TranslationChunk] = list(context.translation_chunks or context.chunks)
        request_id = context.metadata.get("request_id")
        if not request_id or not isinstance(request_id, str) or not request_id.strip():
            request_id = str(uuid.uuid4())
            context.metadata["request_id"] = request_id
        provider_key = context.provider_key or self._settings.get_preferred_provider()
        model = context.provider_model or self._settings.get_provider_model()
        provider_key, model = self._resolve_provider_and_model(provider_key, model)
        context.provider_key = provider_key
        context.provider_model = model
        scheduler = self._build_scheduler(context, provider_key=provider_key, model=model)
        context.metadata["model_fallbacks"] = [
            state["provider_model"] for state in scheduler.to_model_state_list()
            if state.get("provider_key") == provider_key
        ]
        load_persisted_chunk_states(self._storage, context)
        save_chunk_records(self._storage, context, chunks)
        self._save_scheduler_state(context, scheduler)

        # Resolve platform_novel_id once if not already in context
        if platform_novel_id(context) is None and isinstance(context.novel_id, str) and context.novel_id.strip():
            try:
                from novelai.db.engine import session_scope
                from novelai.db.models.novel import Novel as NovelModel

                with session_scope() as session:
                    novel_row = session.query(NovelModel).filter_by(
                        slug=context.novel_id.strip()
                    ).one_or_none()
                    if novel_row is not None:
                        context.metadata["platform_novel_id"] = novel_row.id
            except Exception as exc:
                logger.debug(
                    "Could not resolve platform_novel_id for %s: %s",
                    context.novel_id,
                    exc.__class__.__name__,
                )

        glossary_state = normalize_runtime_glossary(context)
        max_glossary_entries = int(context.metadata.get("glossary_max_entries", 12) or 12)
        max_glossary_context_chars = int(context.metadata.get("glossary_max_context_chars", 1200) or 1200)

        logger.info(f"Translating {len(chunks)} chunks with {provider_key}/{model}")
        semaphore = asyncio.Semaphore(self._concurrency)
        glossary_lock = asyncio.Lock()
        scheduler_lock = asyncio.Lock()
        completed = 0
        progress = context.metadata.setdefault("progress", {})
        if isinstance(progress, dict):
            progress.setdefault("cache_hits", 0)
            progress.setdefault("cache_misses", 0)
            progress.update(
                {
                    "status": "running",
                    "current_stage": "TranslateStage",
                    "completed": 0,
                    "total": len(chunks),
                    "errors": progress.get("errors", []),
                    "warnings": progress.get("warnings", []),
                    "paused_reason": None,
                    "resume_after": None,
                    "model_states": scheduler.to_model_state_list(),
                }
            )

        def mark_chunk_completed(chunk_index: int) -> None:
            nonlocal completed
            completed += 1
            if isinstance(progress, dict):
                progress["completed"] = completed
                progress["current_label"] = f"Chunk {chunk_index + 1} / {len(chunks)}"
                progress["model_states"] = scheduler.to_model_state_list()

        async def worker(chunk_index: int, chunk: str | TranslationChunk) -> str:
            cache_hit = False
            chunk_text = chunk_text_h(chunk)
            chunk_id = chunk_id_h(chunk, chunk_index)
            chapter_ids = chapter_ids_h(context, chunk)
            prompt_glossary = self._build_prompt_glossary_block(context, chunk_text)
            prompt_glossary_text = prompt_glossary.rendered_text if prompt_glossary is not None else ""
            prompt_glossary_hash = glossary_hash_h(context, prompt_glossary_text)
            record_prompt_glossary_metadata(
                context,
                chunk_id=chunk_id,
                block=prompt_glossary,
                glossary_hash=prompt_glossary_hash,
            )
            existing = self._load_existing_chunk_output(
                context,
                chunk_id=chunk_id,
                chunk_text=chunk_text,
                chapter_ids=chapter_ids,
                glossary_hash=prompt_glossary_hash,
            )
            if existing is not None and not force_retranslate_h(context):
                existing_state = context.chunk_states.get(chunk_id, {})
                self._save_chunk_attempt(
                    context,
                    chunk=chunk,
                    chunk_index=chunk_index,
                    attempt_number=int(existing_state.get("attempt_number", 0) or 0),
                    provider_key=existing_state.get("provider_key") if isinstance(existing_state.get("provider_key"), str) else None,
                    provider_model=existing_state.get("provider_model") if isinstance(existing_state.get("provider_model"), str) else None,
                    scheduler_policy=scheduler.policy.value,
                    selection_reason="resume_successful_chunk",
                    status=ChunkAttemptStatus.SKIPPED_ALREADY_SUCCEEDED.value,
                )
                mark_chunk_completed(chunk_index)
                return existing
            async with semaphore:
                async with glossary_lock:
                    selected_glossary = select_chunk_glossary(
                        chunk_text,
                        glossary_state,
                        chunk_index=chunk_index,
                        max_entries=max_glossary_entries,
                        max_context_chars=max_glossary_context_chars,
                    )
                request = build_prompt_request(
                    context,
                    chunk_text,
                    chunk_glossary=selected_glossary,
                    prompt_glossary_block=prompt_glossary_text,
                )
                if request is not None:
                    context.metadata["prompt_template_version"] = request.prompt_template_version
                    if request.honorific_policy:
                        context.metadata["applied_honorific_policy"] = request.honorific_policy
                attempted_models: set[tuple[str, str]] = set()
                qa_failed = context.chunk_states.get(chunk_id, {}).get("status") == ChunkTranslationStatus.QA_FAILED.value
                last_provider_error_code: str | None = None
                last_provider_error_message: str | None = None
                try:
                    while True:
                        async with scheduler_lock:
                            recorder = SchedulerDecisionRecorder(
                                request_id=context.metadata.get("request_id"),
                                activity_id=context.metadata.get("activity_id"),
                                job_id=context.metadata.get("job_id"),
                                chapter_id=context.chapter_id,
                            )
                            selection = scheduler.select_model(
                                chapter_id=context.chapter_id,
                                previous_attempts=attempted_models,
                                qa_failed=qa_failed,
                                now=utc_now(),
                                decision_recorder=recorder,
                            )
                            if selection.paused:
                                if isinstance(progress, dict):
                                    progress.update(
                                        {
                                            "status": "paused",
                                            "paused_reason": selection.paused_reason,
                                            "resume_after": selection.resume_after,
                                            "model_states": scheduler.to_model_state_list(),
                                        }
                                    )
                                self._save_scheduler_state(context, scheduler)
                                paused = SchedulerPausedError(
                                    reason=selection.paused_reason or SelectionReason.NO_MODEL_AVAILABLE.value,
                                    resume_after=selection.resume_after,
                                    model_states=scheduler.to_model_state_list(),
                                    error_code=last_provider_error_code,
                                )
                                paused.pipeline_context = context
                                raise paused
                            used_provider_key = str(selection.provider_key)
                            used_provider_model = str(selection.provider_model)

                        # Record scheduler decision for observability (REQ-1)
                        decision = recorder.finalize(
                            selection=selection,
                            policy=scheduler.policy.value,
                            total_candidates=len(scheduler.model_configs),
                        )
                        decision_dict = decision.to_dict()
                        context.metadata.setdefault("scheduler_decisions", []).append(decision_dict)
                        from novelai.translation.scheduler import push_scheduler_decision
                        push_scheduler_decision(decision_dict)

                        attempted_models.add((used_provider_key, used_provider_model))
                        cached = self._cached_translation(
                            context,
                            provider_key=used_provider_key,
                            provider_model=used_provider_model,
                            chunk=chunk_text,
                            request=request,
                            glossary_hash=prompt_glossary_hash,
                        )
                        if cached is not None:
                            translated, used_provider_key, used_provider_model, _cache_hit = cached
                            cache_hit = True
                            logger.debug("Cache hit for chunk %s using %s/%s", chunk_id, used_provider_key, used_provider_model)
                            context.chunk_states[chunk_id] = {
                                **context.chunk_states.get(chunk_id, {}),
                                "chunk_id": chunk_id,
                                "novel_id": context.novel_id or "unknown_novel",
                                "chapter_ids": chapter_ids_h(context, chunk),
                                "paragraph_ids": paragraph_ids_h(chunk),
                                "provider_key": used_provider_key,
                                "provider_model": used_provider_model,
                                "attempt_number": int(context.chunk_states.get(chunk_id, {}).get("attempt_number", 0) or 0),
                                "policy": scheduler.policy.value,
                                "selection_reason": selection.reason,
                                "status": ChunkTranslationStatus.TRANSLATED.value,
                                "error_code": None,
                                "cache_hit": True,
                                "updated_at": utc_now_iso(),
                            }
                            persist_chunk_state(self._storage, context, chunk_id)
                            self._save_chunk_attempt(
                                context,
                                chunk=chunk,
                                chunk_index=chunk_index,
                                attempt_number=int(context.chunk_states.get(chunk_id, {}).get("attempt_number", 0) or 0),
                                provider_key=used_provider_key,
                                provider_model=used_provider_model,
                                scheduler_policy=scheduler.policy.value,
                                selection_reason=selection.reason,
                                status=ChunkAttemptStatus.SKIPPED_CACHE_HIT.value,
                            )
                            self._save_chunk_output(
                                context,
                                chunk=chunk,
                                chunk_index=chunk_index,
                                translated_text=translated,
                                provider_key=used_provider_key,
                                provider_model=used_provider_model,
                                cache_hit=True,
                                attempt_number=int(context.chunk_states.get(chunk_id, {}).get("attempt_number", 0) or 0),
                                scheduler_policy=scheduler.policy.value,
                                selection_reason=selection.reason,
                                glossary_hash=prompt_glossary_hash,
                            )
                            break

                        current_attempts = int(context.chunk_states.get(chunk_id, {}).get("attempt_number", 0) or 0)
                        if current_attempts >= self._max_attempts_per_chunk:
                            context.chunk_states[chunk_id] = {
                                **context.chunk_states.get(chunk_id, {}),
                                "chunk_id": chunk_id,
                                "novel_id": context.novel_id or "unknown_novel",
                                "chapter_ids": chapter_ids_h(context, chunk),
                                "paragraph_ids": paragraph_ids_h(chunk),
                                "provider_key": used_provider_key,
                                "provider_model": used_provider_model,
                                "attempt_number": current_attempts,
                                "policy": scheduler.policy.value,
                                "selection_reason": selection.reason,
                                "status": ChunkTranslationStatus.FAILED.value,
                                "error_code": MAX_ATTEMPTS_EXCEEDED_ERROR_CODE,
                                "max_attempts": self._max_attempts_per_chunk,
                                "latest_error_code": last_provider_error_code,
                                "latest_error_message": last_provider_error_message,
                                "updated_at": utc_now_iso(),
                            }
                            persist_chunk_state(self._storage, context, chunk_id)
                            raise self._max_attempts_exceeded_error(
                                context,
                                chunk_id=chunk_id,
                                attempt_count=current_attempts,
                                provider_key=used_provider_key,
                                provider_model=used_provider_model,
                                latest_error_code=last_provider_error_code,
                                latest_error_message=last_provider_error_message,
                            )

                        attempt_number = current_attempts + 1
                        async with scheduler_lock:
                            scheduler.record_attempt_start(used_provider_key, used_provider_model, utc_now())
                            self._save_scheduler_state(context, scheduler)
                        context.chunk_states[chunk_id] = {
                            **context.chunk_states.get(chunk_id, {}),
                            "chunk_id": chunk_id,
                            "novel_id": context.novel_id or "unknown_novel",
                            "chapter_ids": chapter_ids_h(context, chunk),
                            "paragraph_ids": paragraph_ids_h(chunk),
                            "provider_key": used_provider_key,
                            "provider_model": used_provider_model,
                            "attempt_number": attempt_number,
                            "policy": scheduler.policy.value,
                            "selection_reason": selection.reason,
                            "status": ChunkTranslationStatus.TRANSLATING.value,
                            "updated_at": utc_now_iso(),
                        }
                        persist_chunk_state(self._storage, context, chunk_id)
                        self._save_chunk_attempt(
                            context,
                            chunk=chunk,
                            chunk_index=chunk_index,
                            attempt_number=attempt_number,
                            provider_key=used_provider_key,
                            provider_model=used_provider_model,
                            scheduler_policy=scheduler.policy.value,
                            selection_reason=selection.reason,
                            status=ChunkAttemptStatus.RUNNING.value,
                        )
                        cache_hit = False
                        try:
                            translated, used_provider_key, used_provider_model, cache_hit = await self._translate_with_model(
                                context,
                                provider_key=used_provider_key,
                                provider_model=used_provider_model,
                                chunk_id=chunk_id,
                                chapter_ids=chapter_ids_h(context, chunk),
                                paragraph_ids=paragraph_ids_h(chunk),
                                attempt_number=attempt_number,
                                scheduler_policy=scheduler.policy.value,
                                selection_reason=selection.reason,
                                chunk=chunk_text,
                                request=request,
                                glossary_hash=prompt_glossary_hash,
                            )
                        except ProviderError as exc:
                            last_provider_error_code = exc.provider_error_code.value
                            last_provider_error_message = exc.message
                            async with scheduler_lock:
                                scheduler.record_provider_error(exc, utc_now())
                                self._save_scheduler_state(context, scheduler)
                            provider_errors = context.metadata.setdefault("provider_errors", [])
                            error_metadata = provider_error_metadata(
                                exc,
                                chunk_id=chunk_id,
                                attempt_number=attempt_number,
                            )
                            if isinstance(provider_errors, list):
                                provider_errors.append(error_metadata)
                            exc.details = {**exc.details, "chunk_id": chunk_id, "attempt_number": attempt_number}
                            context.chunk_states[chunk_id] = {
                                **context.chunk_states.get(chunk_id, {}),
                                "provider_key": exc.provider_key,
                                "provider_model": exc.provider_model,
                                "attempt_number": attempt_number,
                                "status": ChunkTranslationStatus.NEEDS_RETRY.value,
                                "error_code": exc.provider_error_code.value,
                                "updated_at": utc_now_iso(),
                            }
                            persist_chunk_state(self._storage, context, chunk_id)
                            self._save_chunk_attempt(
                                context,
                                chunk=chunk,
                                chunk_index=chunk_index,
                                attempt_number=attempt_number,
                                provider_key=exc.provider_key,
                                provider_model=exc.provider_model,
                                scheduler_policy=scheduler.policy.value,
                                selection_reason=selection.reason,
                                status=ChunkAttemptStatus.FAILED.value,
                                error_code=exc.provider_error_code.value,
                            )
                            if exc.provider_error_code in {
                                ProviderErrorCode.RATE_LIMITED,
                                ProviderErrorCode.QUOTA_EXHAUSTED,
                                ProviderErrorCode.MODEL_UNAVAILABLE,
                                ProviderErrorCode.MODEL_DEPRECATED,
                            }:
                                continue
                            raise

                        context.chunk_states[chunk_id] = {
                            **context.chunk_states.get(chunk_id, {}),
                            "chunk_id": chunk_id,
                            "novel_id": context.novel_id or "unknown_novel",
                            "chapter_ids": chapter_ids_h(context, chunk),
                            "paragraph_ids": paragraph_ids_h(chunk),
                            "provider_key": used_provider_key,
                            "provider_model": used_provider_model,
                            "attempt_number": attempt_number,
                            "policy": scheduler.policy.value,
                            "selection_reason": selection.reason,
                            "status": ChunkTranslationStatus.TRANSLATED.value,
                            "error_code": None,
                            "updated_at": utc_now_iso(),
                        }
                        persist_chunk_state(self._storage, context, chunk_id)
                        self._save_chunk_attempt(
                            context,
                            chunk=chunk,
                            chunk_index=chunk_index,
                            attempt_number=attempt_number,
                            provider_key=used_provider_key,
                            provider_model=used_provider_model,
                            scheduler_policy=scheduler.policy.value,
                            selection_reason=selection.reason,
                            status=ChunkAttemptStatus.SUCCEEDED.value,
                        )
                        self._save_chunk_output(
                            context,
                            chunk=chunk,
                            chunk_index=chunk_index,
                            translated_text=translated,
                            provider_key=used_provider_key,
                            provider_model=used_provider_model,
                            cache_hit=cache_hit,
                            attempt_number=attempt_number,
                            scheduler_policy=scheduler.policy.value,
                            selection_reason=selection.reason,
                            glossary_hash=prompt_glossary_hash,
                        )
                        break
                except ProviderError:
                    raise
                async with glossary_lock:
                    observe_chunk_context(chunk_text, glossary_state, chunk_index=chunk_index)
                mark_chunk_completed(chunk_index)
                if isinstance(progress, dict):
                    if cache_hit:
                        progress["cache_hits"] = int(progress.get("cache_hits", 0)) + 1
                    else:
                        progress["cache_misses"] = int(progress.get("cache_misses", 0)) + 1
                return translated

        context.translations = await asyncio.gather(*[worker(i, c) for i, c in enumerate(chunks)])
        self._save_scheduler_state(context, scheduler)
        context.metadata["translated_chunk_ids"] = [
            chunk_id_h(chunk, index)
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
        # Wire glossary diagnostics into translation context (REQ-1.1)
        context.metadata["glossary_diagnostics"] = normalize_glossary_diagnostics(context.metadata)
        logger.info(f"Translation complete: {len(context.translations)} chunks processed")
        return context
