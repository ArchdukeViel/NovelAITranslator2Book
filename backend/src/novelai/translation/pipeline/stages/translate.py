from __future__ import annotations

import asyncio
import hashlib
import logging
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from novelai.config.settings import settings
from novelai.core.errors import PipelineStageError, ProviderError, ProviderErrorCode
from novelai.glossary import (
    GlossaryTerm,
    extract_term_context,
    normalize_glossary_entries,
    rank_glossary_terms_for_text,
    summarize_term_context,
)
from novelai.translation.pipeline.context import PipelineContext, TranslationChunk
from novelai.translation.pipeline.stages.base import PipelineStage
from novelai.translation.scheduler import (
    SchedulerPausedError,
    SelectionReason,
    TranslationScheduler,
    normalize_model_configs,
    normalize_policy,
    utc_now,
    utc_now_iso,
)
from novelai.prompts import build_translation_request
from novelai.prompts.models import TranslationRequest
from novelai.shared.pipeline import ChunkAttemptStatus, ChunkTranslationStatus
from novelai.providers.base import TranslationProvider
from novelai.providers.model_fallbacks import model_candidates
from novelai.services.preferences_service import PreferencesService
from novelai.services.translation_cache import TranslationCache
from novelai.services.usage_service import UsageService
from novelai.storage.service import StorageService

logger = logging.getLogger(__name__)

MAX_ATTEMPTS_EXCEEDED_ERROR_CODE = "max_attempts_exceeded"


def _utc_now_iso() -> str:
    """Return a serialized UTC timestamp with a trailing Z."""
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _hash_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


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
        storage: StorageService | None = None,
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
        self._storage = storage or StorageService()
        configured_max_attempts = settings.TRANSLATION_MAX_ATTEMPTS_PER_CHUNK
        self._max_attempts_per_chunk = configured_max_attempts if configured_max_attempts > 0 else 3

    def _resolve_provider_and_model(self, provider_key: str, model: str) -> tuple[str, str]:
        if provider_key in {"gemini", "nvidia"} and not self._settings.get_api_key(provider_key):
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
    def _chapter_ids(context: PipelineContext, chunk: str | TranslationChunk) -> list[str]:
        if isinstance(chunk, TranslationChunk):
            return list(chunk.chapter_ids)
        return [context.chapter_id] if isinstance(context.chapter_id, str) and context.chapter_id.strip() else []

    @staticmethod
    def _paragraph_ids(chunk: str | TranslationChunk) -> list[str]:
        if isinstance(chunk, TranslationChunk):
            return list(chunk.paragraph_ids)
        return []

    @staticmethod
    def _paragraph_hashes(chunk: str | TranslationChunk) -> list[str]:
        if isinstance(chunk, TranslationChunk):
            return list(chunk.paragraph_hashes)
        return []

    @staticmethod
    def _paragraph_lineage(chunk: str | TranslationChunk) -> list[dict[str, Any]]:
        if isinstance(chunk, TranslationChunk):
            return [dict(item) for item in chunk.paragraph_lineage]
        return []

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
    def _prompt_version(context: PipelineContext) -> str:
        value = context.metadata.get("prompt_version")
        return value if isinstance(value, str) and value.strip() else "translation_request_v1"

    @staticmethod
    def _glossary_hash(context: PipelineContext) -> str:
        return _hash_text(str(context.metadata.get("glossary") or ""))

    @staticmethod
    def _force_retranslate(context: PipelineContext) -> bool:
        return bool(context.metadata.get("force_retranslate_chunks") or context.metadata.get("force_retranslate"))

    @staticmethod
    def _safe_job_id(context: PipelineContext) -> str | None:
        for value in (context.job_id, context.activity_id, context.novel_id):
            if isinstance(value, str) and value.strip():
                return value.strip()
        return None

    @staticmethod
    def _translation_run_id(context: PipelineContext) -> str:
        for value in (
            context.metadata.get("translation_run_id"),
            context.job_id,
            context.activity_id,
        ):
            if isinstance(value, str) and value.strip():
                return value.strip()
        return "run_manual"

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
            "provider_key": provider_key,
            "provider_model": provider_model,
            "latest_error_code": latest_error_code,
            "latest_error_message": latest_error_message,
        }
        error = PipelineStageError(
            f"Translation max attempts exceeded for chunk {chunk_id}: "
            f"{attempt_count}/{self._max_attempts_per_chunk} attempts."
        )
        setattr(error, "error_code", MAX_ATTEMPTS_EXCEEDED_ERROR_CODE)
        setattr(error, "details", details)
        setattr(error, "pipeline_context", context)
        return error

    @staticmethod
    def _provider_request_record(
        context: PipelineContext,
        *,
        chunk_id: str,
        chunk_text: str,
        request: TranslationRequest | None,
        provider_key: str,
        provider_model: str,
        chapter_ids: list[str] | None = None,
        paragraph_ids: list[str] | None = None,
        attempt_number: int | None = None,
        scheduler_policy: str | None = None,
        selection_reason: str | None = None,
        started_at: str,
        finished_at: str,
        success: bool,
        metadata: Any = None,
        error: ProviderError | None = None,
    ) -> dict[str, Any]:
        prompt_text = request.user_prompt if request is not None else chunk_text
        payload: dict[str, Any] = {
            "job_id": context.job_id,
            "activity_id": context.activity_id,
            "translation_run_id": TranslateStage._translation_run_id(context),
            "novel_id": context.novel_id,
            "chapter_id": context.chapter_id,
            "chapter_ids": list(chapter_ids or []),
            "paragraph_ids": list(paragraph_ids or []),
            "chunk_id": chunk_id,
            "provider_key": provider_key,
            "provider_model": provider_model,
            "prompt_version": TranslateStage._prompt_version(context),
            "source_text_hash": _hash_text(chunk_text),
            "prompt_hash": _hash_text(prompt_text),
            "glossary_hash": TranslateStage._glossary_hash(context),
            "style_preset": context.metadata.get("style_preset"),
            "json_output": bool(context.metadata.get("json_output", False)),
            "consistency_mode": bool(context.metadata.get("consistency_mode", False)),
            "scheduler_policy": scheduler_policy,
            "selection_reason": selection_reason,
            "attempt_number": attempt_number,
            "request_started_at": started_at,
            "request_finished_at": finished_at,
            "status": "success" if success else "failed",
            "success": success,
        }
        if isinstance(metadata, dict):
            payload["usage_metadata"] = metadata
            usage = metadata.get("usage")
            if isinstance(usage, dict):
                payload["input_tokens"] = usage.get("input_tokens") or usage.get("prompt_tokens")
                payload["output_tokens"] = usage.get("output_tokens") or usage.get("completion_tokens")
                payload["total_tokens"] = usage.get("total_tokens")
        if error is not None:
            payload.update(
                {
                    "normalized_provider_error_code": error.provider_error_code.value,
                    "retry_after_seconds": error.retry_after_seconds,
                    "cooldown_until": error.cooldown_until,
                    "exhausted_until": error.exhausted_until,
                }
            )
        return payload

    @staticmethod
    def _provider_error_from_generic(exc: Exception, *, provider_key: str, provider_model: str) -> ProviderError:
        message = str(exc)
        lowered = message.lower()
        code = ProviderErrorCode.UNKNOWN
        if "quota" in lowered or "resource_exhausted" in lowered:
            code = ProviderErrorCode.QUOTA_EXHAUSTED
        elif "rate" in lowered or "429" in lowered:
            code = ProviderErrorCode.RATE_LIMITED
        elif "model" in lowered and any(token in lowered for token in ("not found", "unavailable", "unsupported")):
            code = ProviderErrorCode.MODEL_UNAVAILABLE
        return ProviderError(
            code,
            provider_key=provider_key,
            provider_model=provider_model,
            message=message,
        )

    def _save_scheduler_state(self, context: PipelineContext, scheduler: TranslationScheduler) -> None:
        context.scheduler_state = scheduler.to_dict()
        context.metadata["model_states"] = scheduler.to_model_state_list()
        progress = context.metadata.setdefault("progress", {})
        if isinstance(progress, dict):
            progress["model_states"] = scheduler.to_model_state_list()
        job_id = self._safe_job_id(context)
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
        if not isinstance(raw_policy, list):
            raw_policy = self._admin_provider_policy_models(
                provider_key=provider_key,
                model=model,
                allow_cross_provider_fallback=context.metadata.get("allow_cross_provider_fallback", True) is not False,
            )
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
                    raw_policy = None
            context.metadata["provider_lock"] = provider_key
            context.metadata["allow_cross_provider_fallback"] = False
            if filtered_count:
                context.metadata["provider_lock_filtered_candidates"] = filtered_count
        if allow_cross_provider_fallback and not raw_policy and provider_key == "gemini":
            raw_policy = [
                {
                    "provider_key": "gemini",
                    "provider_model": model,
                    "priority_order": 0,
                },
                {
                    "provider_key": "nvidia",
                    "provider_model": settings.NVIDIA_DEFAULT_MODEL,
                    "priority_order": 1,
                },
            ]
        configs = normalize_model_configs(raw_policy, default_provider_key=provider_key, default_models=candidates)
        existing_state = context.scheduler_state
        job_id = self._safe_job_id(context)
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
                    "priority_order": self._nonnegative_int(item.get("priority_order"), default=index),
                    "rpm_limit": item.get("rpm_limit"),
                    "rpd_limit": item.get("rpd_limit"),
                }
            )
        if skipped:
            context_skips = getattr(self, "_last_admin_policy_skips", [])
            context_skips.extend(skipped)
            self._last_admin_policy_skips = context_skips
        return configs or None

    @staticmethod
    def _nonnegative_int(value: Any, *, default: int) -> int:
        try:
            parsed = int(value)
        except (TypeError, ValueError):
            return default
        return parsed if parsed >= 0 else default

    def _save_chunk_records(self, context: PipelineContext, chunks: list[str | TranslationChunk]) -> None:
        novel_id = context.novel_id
        if not isinstance(novel_id, str) or not novel_id.strip():
            return
        records: list[dict[str, Any]] = []
        for index, chunk in enumerate(chunks):
            chunk_text = self._chunk_text(chunk)
            chunk_id = self._chunk_id(chunk, index)
            records.append(
                {
                    "chunk_id": chunk_id,
                    "novel_id": novel_id,
                    "translation_run_id": self._translation_run_id(context),
                    "chapter_ids": self._chapter_ids(context, chunk),
                    "paragraph_ids": self._paragraph_ids(chunk),
                    "paragraph_hashes": self._paragraph_hashes(chunk),
                    "paragraph_lineage": self._paragraph_lineage(chunk),
                    "source_text": chunk_text,
                    "source_text_hash": _hash_text(chunk_text),
                    "char_count": len(chunk_text),
                    "status": context.chunk_states.get(chunk_id, {}).get("status", ChunkTranslationStatus.PENDING.value),
                }
            )
        if records:
            self._storage.save_translation_chunks(novel_id, records)

    def _load_persisted_chunk_states(self, context: PipelineContext) -> None:
        novel_id = context.novel_id
        if not isinstance(novel_id, str) or not novel_id.strip():
            return
        for stored in self._storage.load_chunk_states(
            novel_id=novel_id,
            chapter_id=context.chapter_id,
            translation_run_id=self._translation_run_id(context),
        ):
            chunk_id = stored.get("chunk_id") if isinstance(stored, dict) else None
            if isinstance(chunk_id, str) and chunk_id.strip():
                context.chunk_states[chunk_id] = {
                    **context.chunk_states.get(chunk_id, {}),
                    **dict(stored),
                }

    def _load_existing_chunk_output(
        self,
        context: PipelineContext,
        *,
        chunk_id: str,
        chunk_text: str,
        chapter_ids: list[str],
    ) -> str | None:
        novel_id = context.novel_id
        if not isinstance(novel_id, str) or not novel_id.strip():
            return None
        existing_state = context.chunk_states.get(chunk_id, {})
        if existing_state.get("status") != ChunkTranslationStatus.TRANSLATED.value:
            return None
        stored = self._storage.read_translation_output(
            novel_id,
            chunk_id=chunk_id,
            translation_run_id=self._translation_run_id(context),
            chapter_ids=chapter_ids,
        )
        if not isinstance(stored, list) or not stored:
            return None
        latest = stored[-1]
        if not isinstance(latest, dict):
            return None
        expected = {
            "source_text_hash": _hash_text(chunk_text),
            "prompt_version": self._prompt_version(context),
            "glossary_hash": self._glossary_hash(context),
            "style_preset": context.metadata.get("style_preset"),
            "json_output": bool(context.metadata.get("json_output", False)),
            "consistency_mode": bool(context.metadata.get("consistency_mode", False)),
        }
        for key, value in expected.items():
            if latest.get(key) != value:
                return None
        text = latest.get("translated_text")
        return text if isinstance(text, str) else None

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
        novel_id = context.novel_id
        if not isinstance(novel_id, str) or not novel_id.strip():
            return
        chunk_id = self._chunk_id(chunk, chunk_index)
        chunk_text = self._chunk_text(chunk)
        self._storage.save_chunk_attempt_record(
            {
                "chunk_id": chunk_id,
                "novel_id": novel_id,
                "translation_run_id": self._translation_run_id(context),
                "chapter_ids": self._chapter_ids(context, chunk),
                "paragraph_ids": self._paragraph_ids(chunk),
                "paragraph_hashes": self._paragraph_hashes(chunk),
                "paragraph_lineage": self._paragraph_lineage(chunk),
                "source_text_hash": _hash_text(chunk_text),
                "attempt_number": attempt_number,
                "provider_key": provider_key,
                "provider_model": provider_model,
                "scheduler_policy": scheduler_policy,
                "selection_reason": selection_reason,
                "status": status,
                "error_code": error_code,
                "qa_score": qa_score,
                "qa_status": qa_status,
            }
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
    ) -> None:
        novel_id = context.novel_id
        if not isinstance(novel_id, str) or not novel_id.strip():
            return
        chunk_id = self._chunk_id(chunk, chunk_index)
        chunk_text = self._chunk_text(chunk)
        self._storage.save_translation_output(
            {
                "output_id": f"{chunk_id}:attempt_{attempt_number:04d}",
                "chunk_id": chunk_id,
                "novel_id": novel_id,
                "translation_run_id": self._translation_run_id(context),
                "chapter_ids": self._chapter_ids(context, chunk),
                "paragraph_ids": self._paragraph_ids(chunk),
                "paragraph_hashes": self._paragraph_hashes(chunk),
                "paragraph_lineage": self._paragraph_lineage(chunk),
                "translated_text": translated_text,
                "source_text_hash": _hash_text(chunk_text),
                "output_hash": _hash_text(translated_text),
                "provider_key": provider_key,
                "provider_model": provider_model,
                "prompt_version": self._prompt_version(context),
                "glossary_hash": self._glossary_hash(context),
                "style_preset": context.metadata.get("style_preset"),
                "json_output": bool(context.metadata.get("json_output", False)),
                "consistency_mode": bool(context.metadata.get("consistency_mode", False)),
                "scheduler_policy": scheduler_policy,
                "selection_reason": selection_reason,
                "attempt_number": attempt_number,
                "qa_status": "pending",
                "cache_hit": cache_hit,
            }
        )

    def _persist_chunk_state(self, context: PipelineContext, chunk_id: str) -> None:
        state = context.chunk_states.get(chunk_id)
        if not isinstance(state, dict):
            return
        state["translation_run_id"] = self._translation_run_id(context)
        self._storage.upsert_chunk_state(state)
        novel_id = state.get("novel_id") or context.novel_id
        status = state.get("status")
        if isinstance(novel_id, str) and novel_id.strip() and isinstance(status, str) and status.strip():
            fields = {key: value for key, value in state.items() if key not in {"chunk_id", "novel_id", "status"}}
            self._storage.update_translation_chunk_status(novel_id, chunk_id, status, **fields)

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

    def _cached_translation(
        self,
        *,
        provider_key: str,
        provider_model: str,
        chunk: str,
        request: TranslationRequest | None,
    ) -> tuple[str, str, str] | None:
        provider_key, provider_model = self._resolve_provider_and_model(provider_key, provider_model)
        provider = self._provider_factory(provider_key)
        cache_key = request.cache_key() if request is not None else chunk
        cached = self._cache.get(cache_key, provider.key, provider_model)
        if cached is None:
            return None
        return cached, provider.key, provider_model

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
                self._provider_request_record(
                    context,
                    chunk_id=chunk_id,
                    chunk_text=chunk,
                    request=request,
                    provider_key=exc.provider_key,
                    provider_model=exc.provider_model,
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
            provider_error = self._provider_error_from_generic(exc, provider_key=provider.key, provider_model=provider_model)
            self._storage.save_provider_request_record(
                self._provider_request_record(
                    context,
                    chunk_id=chunk_id,
                    chunk_text=chunk,
                    request=request,
                    provider_key=provider.key,
                    provider_model=provider_model,
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
            "timestamp": _utc_now_iso(),
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
        cache_key = request.cache_key() if request is not None else chunk
        self._cache.set(cache_key, provider.key, provider_model, text)
        self._storage.save_provider_request_record(
            self._provider_request_record(
                context,
                chunk_id=chunk_id,
                chunk_text=chunk,
                request=request,
                provider_key=provider.key,
                provider_model=provider_model,
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
        provider_key = context.provider_key or self._settings.get_provider_key()
        model = context.provider_model or self._settings.get_provider_model()
        provider_key, model = self._resolve_provider_and_model(provider_key, model)
        context.provider_key = provider_key
        context.provider_model = model
        scheduler = self._build_scheduler(context, provider_key=provider_key, model=model)
        context.metadata["model_fallbacks"] = [
            state["provider_model"] for state in scheduler.to_model_state_list()
            if state.get("provider_key") == provider_key
        ]
        self._load_persisted_chunk_states(context)
        self._save_chunk_records(context, chunks)
        self._save_scheduler_state(context, scheduler)

        glossary_state = self._normalize_runtime_glossary(context)
        max_glossary_entries = int(context.metadata.get("glossary_max_entries", 12) or 12)
        max_glossary_context_chars = int(context.metadata.get("glossary_max_context_chars", 1200) or 1200)

        logger.info(f"Translating {len(chunks)} chunks with {provider_key}/{model}")
        semaphore = asyncio.Semaphore(self._concurrency)
        glossary_lock = asyncio.Lock()
        scheduler_lock = asyncio.Lock()
        completed = 0
        progress = context.metadata.setdefault("progress", {})
        if isinstance(progress, dict):
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
            chunk_text = self._chunk_text(chunk)
            chunk_id = self._chunk_id(chunk, chunk_index)
            chapter_ids = self._chapter_ids(context, chunk)
            existing = self._load_existing_chunk_output(
                context,
                chunk_id=chunk_id,
                chunk_text=chunk_text,
                chapter_ids=chapter_ids,
            )
            if existing is not None and not self._force_retranslate(context):
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
                    selected_glossary = self._select_chunk_glossary(
                        chunk_text,
                        glossary_state,
                        chunk_index=chunk_index,
                        max_entries=max_glossary_entries,
                        max_context_chars=max_glossary_context_chars,
                    )
                request = self._build_prompt_request(context, chunk_text, chunk_glossary=selected_glossary)
                attempted_models: set[tuple[str, str]] = set()
                qa_failed = context.chunk_states.get(chunk_id, {}).get("status") == ChunkTranslationStatus.QA_FAILED.value
                last_provider_error_code: str | None = None
                last_provider_error_message: str | None = None
                try:
                    while True:
                        async with scheduler_lock:
                            selection = scheduler.select_model(
                                chapter_id=context.chapter_id,
                                previous_attempts=attempted_models,
                                qa_failed=qa_failed,
                                now=utc_now(),
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
                                setattr(paused, "pipeline_context", context)
                                raise paused
                            used_provider_key = str(selection.provider_key)
                            used_provider_model = str(selection.provider_model)

                        attempted_models.add((used_provider_key, used_provider_model))
                        cached = self._cached_translation(
                            provider_key=used_provider_key,
                            provider_model=used_provider_model,
                            chunk=chunk_text,
                            request=request,
                        )
                        if cached is not None:
                            translated, used_provider_key, used_provider_model = cached
                            logger.debug("Cache hit for chunk %s using %s/%s", chunk_id, used_provider_key, used_provider_model)
                            context.chunk_states[chunk_id] = {
                                **context.chunk_states.get(chunk_id, {}),
                                "chunk_id": chunk_id,
                                "novel_id": context.novel_id or "unknown_novel",
                                "chapter_ids": self._chapter_ids(context, chunk),
                                "paragraph_ids": self._paragraph_ids(chunk),
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
                            self._persist_chunk_state(context, chunk_id)
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
                            )
                            break

                        current_attempts = int(context.chunk_states.get(chunk_id, {}).get("attempt_number", 0) or 0)
                        if current_attempts >= self._max_attempts_per_chunk:
                            context.chunk_states[chunk_id] = {
                                **context.chunk_states.get(chunk_id, {}),
                                "chunk_id": chunk_id,
                                "novel_id": context.novel_id or "unknown_novel",
                                "chapter_ids": self._chapter_ids(context, chunk),
                                "paragraph_ids": self._paragraph_ids(chunk),
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
                            self._persist_chunk_state(context, chunk_id)
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
                            "chapter_ids": self._chapter_ids(context, chunk),
                            "paragraph_ids": self._paragraph_ids(chunk),
                            "provider_key": used_provider_key,
                            "provider_model": used_provider_model,
                            "attempt_number": attempt_number,
                            "policy": scheduler.policy.value,
                            "selection_reason": selection.reason,
                            "status": ChunkTranslationStatus.TRANSLATING.value,
                            "updated_at": utc_now_iso(),
                        }
                        self._persist_chunk_state(context, chunk_id)
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
                        try:
                            translated, used_provider_key, used_provider_model, cache_hit = await self._translate_with_model(
                                context,
                                provider_key=used_provider_key,
                                provider_model=used_provider_model,
                                chunk_id=chunk_id,
                                chapter_ids=self._chapter_ids(context, chunk),
                                paragraph_ids=self._paragraph_ids(chunk),
                                attempt_number=attempt_number,
                                scheduler_policy=scheduler.policy.value,
                                selection_reason=selection.reason,
                                chunk=chunk_text,
                                request=request,
                            )
                        except ProviderError as exc:
                            last_provider_error_code = exc.provider_error_code.value
                            last_provider_error_message = exc.message
                            async with scheduler_lock:
                                scheduler.record_provider_error(exc, utc_now())
                                self._save_scheduler_state(context, scheduler)
                            provider_errors = context.metadata.setdefault("provider_errors", [])
                            error_metadata = self._provider_error_metadata(
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
                            self._persist_chunk_state(context, chunk_id)
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
                            "chapter_ids": self._chapter_ids(context, chunk),
                            "paragraph_ids": self._paragraph_ids(chunk),
                            "provider_key": used_provider_key,
                            "provider_model": used_provider_model,
                            "attempt_number": attempt_number,
                            "policy": scheduler.policy.value,
                            "selection_reason": selection.reason,
                            "status": ChunkTranslationStatus.TRANSLATED.value,
                            "error_code": None,
                            "updated_at": utc_now_iso(),
                        }
                        self._persist_chunk_state(context, chunk_id)
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
                        )
                        break
                except ProviderError as exc:
                    raise
                async with glossary_lock:
                    self._observe_chunk_context(chunk_text, glossary_state, chunk_index=chunk_index)
                mark_chunk_completed(chunk_index)
                return translated

        context.translations = await asyncio.gather(*[worker(i, c) for i, c in enumerate(chunks)])
        self._save_scheduler_state(context, scheduler)
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
