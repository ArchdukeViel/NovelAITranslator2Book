from __future__ import annotations

import logging
from typing import Any

from novelai.config.settings import settings
from novelai.providers.registry import get_provider
from novelai.shared.pipeline import ChunkTranslationStatus
from novelai.translation.pipeline.context import PipelineState, TranslationChunk
from novelai.translation.pipeline.stages.base import PipelineStage
from novelai.translation.qa import (
    TranslationQAError,
    TranslationQAResult,
    evaluate_translation_quality,
    evaluate_translation_quality_with_llm,
    normalized_translation_text,
)

logger = logging.getLogger(__name__)


def _extract_glossary_terms(context: PipelineState) -> list[dict] | None:
    """Extract approved glossary terms from context metadata (REQ-5.5)."""
    terms = context.metadata.get("glossary_approved_terms")
    if isinstance(terms, list) and terms:
        return terms
    return None


def _resolve_llm_grader() -> Any | None:
    """Resolve the LLM grader provider when ``LLM_QA_ENABLED`` is set.

    Returns ``None`` if disabled, if the grader provider is the dummy
    (outside test), or if instantiation fails. A failure is logged and the
    pipeline continues with deterministic QA only — LLM grading is a
    best-effort enhancement, never a hard dependency (DEBT-053).
    """
    if not settings.LLM_QA_ENABLED:
        return None
    try:
        provider = get_provider(settings.LLM_QA_PROVIDER)
    except Exception as exc:  # provider unavailable — fail open
        logger.warning("LLM QA provider %s unavailable: %s", settings.LLM_QA_PROVIDER, exc)
        return None
    if getattr(provider, "key", None) == "dummy":
        return None
    return provider


async def _resolve_llm_grader_async() -> Any | None:
    """Async façade over the synchronous provider registry lookup.

    Kept separate so a future implementation can swap to an async provider
    factory without changing the call site.
    """
    return _resolve_llm_grader()


class TranslationQAStage(PipelineStage):
    """Deterministic validation of translated chunks before final post-processing."""

    @staticmethod
    def _chunk_for_index(context: PipelineState, index: int) -> TranslationChunk:
        return context.translation_chunks[index]

    @staticmethod
    def _source_for_chunk(chunk: TranslationChunk) -> str:
        return chunk.source_text

    @staticmethod
    def _chunk_id(chunk: TranslationChunk) -> str:
        return chunk.chunk_id

    @staticmethod
    def _provider_models(context: PipelineState) -> set[str]:
        models: set[str] = set()
        for state in context.chunk_states.values():
            model = state.get("provider_model") if isinstance(state, dict) else None
            if isinstance(model, str) and model.strip():
                models.add(model.strip())
        return models

    @staticmethod
    def _merge_results(results: list[TranslationQAResult]) -> TranslationQAResult:
        warnings: list[str] = []
        errors: list[str] = []
        for result in results:
            warnings.extend(result.warnings)
            errors.extend(result.errors)
        unique_warnings = list(dict.fromkeys(warnings))
        unique_errors = list(dict.fromkeys(errors))
        score = min((result.score for result in results), default=1.0)
        return TranslationQAResult(
            score=score,
            passed=not unique_errors and score >= 0.75,
            warnings=unique_warnings,
            errors=unique_errors,
        )

    async def run(self, context: PipelineState) -> PipelineState:
        raw_translations = list(context.translations)
        if len(raw_translations) != len(context.translation_chunks):
            raise ValueError("Translation QA requires one canonical translation chunk per translation.")
        context.metadata["raw_provider_translations"] = list(raw_translations)
        structured_output = bool(context.metadata.get("json_output", False))
        qa_payloads: list[dict[str, Any]] = []
        normalized_translations: list[str] = []
        results: list[TranslationQAResult] = []
        failed_chunk_ids: list[str] = []

        multi_model_warning = len(self._provider_models(context)) > 1
        approved_glossary = _extract_glossary_terms(context)
        llm_grader = await _resolve_llm_grader_async()
        # DEBT-053: the deterministic gate stays authoritative; the optional
        # LLM grader only refines chunk disposition. ``settings.LLM_QA_POLICY``
        # decides how below-threshold chunks are handled (see settings):
        #   advisory      -> warning only, status stays "translated";
        #   blocking_retry-> status "needs_retry" (bounded attempts), then
        #                    "needs_review" once exhausted;
        #   review        -> status "needs_review" immediately.
        # A retry marker is always backed by a real chunk status, and retry
        # accounting survives stage re-runs via chunk_state. Grader failures
        # never raise.
        llm_qa_policy = settings.LLM_QA_POLICY
        llm_retry_counts: dict[str, int] = {}

        for index, translated in enumerate(raw_translations):
            chunk = self._chunk_for_index(context, index)
            chunk_id = self._chunk_id(chunk)
            result = evaluate_translation_quality(
                source_text=self._source_for_chunk(chunk),
                translated_text=translated,
                chunk=chunk,
                structured_output=structured_output,
                approved_glossary=approved_glossary,
            )
            if multi_model_warning and "model_switch_warning" not in result.warnings:
                result = TranslationQAResult(
                    score=max(0.0, round(result.score - 0.08, 3)),
                    passed=result.passed,
                    warnings=[*result.warnings, "model_switch_warning"],
                    errors=result.errors,
                )
            results.append(result)
            normalized_text = normalized_translation_text(translated)
            normalized_translations.append(normalized_text)
            qa_payloads.append({"chunk_id": chunk_id, **result.to_dict()})

            chunk_state = {
                **context.chunk_states.get(chunk_id, {}),
                "chunk_id": chunk_id,
                "novel_id": chunk.novel_id or "unknown_novel",
                "qa_score": result.score,
                "qa_warnings": list(result.warnings),
                "qa_errors": list(result.errors),
                "qa_diagnostics": dict(result.diagnostics),
            }
            if result.passed:
                chunk_state["status"] = ChunkTranslationStatus.TRANSLATED.value
                chunk_state["qa_status"] = "passed"
                # DEBT-053: optional LLM grader for passed chunks only.
                if llm_grader is not None:
                    llm_score = await evaluate_translation_quality_with_llm(
                        llm_grader,
                        source_text=self._source_for_chunk(chunk),
                        translated_text=normalized_text,
                        model=settings.LLM_QA_MODEL or None,
                    )
                    chunk_state["llm_qa_score"] = llm_score
                    if llm_score < settings.LLM_QA_MIN_SCORE:
                        if llm_qa_policy == "blocking_retry":
                            # Retry accounting persists on the chunk state so
                            # bounded retries survive stage re-runs.
                            retries = int(chunk_state.get("llm_qa_retry_count", 0) or 0)
                            if retries >= settings.LLM_QA_MAX_RETRY_ATTEMPTS:
                                chunk_state["status"] = ChunkTranslationStatus.NEEDS_REVIEW.value
                                chunk_state["qa_status"] = "llm_score_below_threshold_no_retry"
                                chunk_state["qa_warnings"] = [
                                    *list(result.warnings),
                                    "llm_qa_below_threshold_no_retry",
                                ]
                            else:
                                chunk_state["status"] = ChunkTranslationStatus.NEEDS_RETRY.value
                                chunk_state["qa_status"] = "needs_llm_retry"
                                chunk_state["qa_warnings"] = [
                                    *list(result.warnings),
                                    "llm_qa_below_threshold",
                                ]
                                chunk_state["llm_qa_retry_count"] = retries + 1
                                llm_retry_counts[chunk_id] = retries + 1
                        elif llm_qa_policy == "review":
                            chunk_state["status"] = ChunkTranslationStatus.NEEDS_REVIEW.value
                            chunk_state["qa_status"] = "needs_review"
                            chunk_state["qa_warnings"] = [
                                *list(result.warnings),
                                "llm_qa_below_threshold",
                            ]
                        else:
                            # advisory (default): deterministic QA stays green;
                            # a warning is recorded and no retry marker is set.
                            chunk_state["qa_status"] = "llm_qa_advisory_below_threshold"
                            chunk_state["qa_warnings"] = [
                                *list(result.warnings),
                                "llm_qa_below_threshold",
                            ]
            else:
                chunk_state["status"] = ChunkTranslationStatus.QA_FAILED.value
                chunk_state["qa_status"] = "qa_failed"
                chunk_state["error_code"] = result.errors[0] if result.errors else "translation_qa_failed"
                failed_chunk_ids.append(chunk_id)
            context.chunk_states[chunk_id] = chunk_state

        combined = self._merge_results(results)
        context.metadata["qa_results"] = qa_payloads
        context.metadata["qa_result"] = combined.to_dict()
        if llm_grader is not None:
            context.metadata["llm_qa_enabled"] = True
            context.metadata["llm_qa_retry_counts"] = llm_retry_counts
            context.metadata["llm_qa_min_score"] = settings.LLM_QA_MIN_SCORE
        else:
            context.metadata["llm_qa_enabled"] = False
        if combined.warnings:
            context.warnings.extend(f"qa:{warning}" for warning in combined.warnings)
            context.metadata["warnings"] = context.warnings

        if not combined.passed:
            error = TranslationQAError(combined)
            error.details = {
                **error.details,
                "chunk_id": failed_chunk_ids[0] if failed_chunk_ids else None,
                "failed_chunk_ids": failed_chunk_ids,
                "qa_results": qa_payloads,
            }
            raise error

        context.translations = normalized_translations
        logger.info("Translation QA passed for %s chunks", len(raw_translations))
        return context
