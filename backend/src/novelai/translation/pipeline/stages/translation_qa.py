from __future__ import annotations

import logging
from typing import Any

from novelai.shared.pipeline import ChunkTranslationStatus
from novelai.translation.pipeline.context import PipelineState, TranslationChunk
from novelai.translation.pipeline.stages.base import PipelineStage
from novelai.translation.qa import (
    TranslationQAError,
    TranslationQAResult,
    evaluate_translation_quality,
    normalized_translation_text,
)

logger = logging.getLogger(__name__)


def _extract_glossary_terms(context: PipelineState) -> list[dict] | None:
    """Extract approved glossary terms from context metadata (REQ-5.5)."""
    terms = context.metadata.get("glossary_approved_terms")
    if isinstance(terms, list) and terms:
        return terms
    return None


class TranslationQAStage(PipelineStage):
    """Deterministic validation of translated chunks before final post-processing."""

    @staticmethod
    def _chunk_for_index(context: PipelineState, index: int) -> TranslationChunk | None:
        if index < len(context.translation_chunks):
            return context.translation_chunks[index]
        return None

    @staticmethod
    def _source_for_chunk(context: PipelineState, index: int, chunk: TranslationChunk | None) -> str:
        if chunk is not None:
            return chunk.source_text
        if index < len(context.chunks):
            return context.chunks[index]
        return context.normalized_text or context.raw_text or ""

    @staticmethod
    def _chunk_id(index: int, chunk: TranslationChunk | None) -> str:
        if chunk is not None:
            return chunk.chunk_id
        return f"legacy_{index + 1:04d}"

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
        context.metadata["raw_provider_translations"] = list(raw_translations)
        structured_output = bool(context.metadata.get("json_output", False))
        qa_payloads: list[dict[str, Any]] = []
        normalized_translations: list[str] = []
        results: list[TranslationQAResult] = []
        failed_chunk_ids: list[str] = []

        multi_model_warning = len(self._provider_models(context)) > 1
        approved_glossary = _extract_glossary_terms(context)

        for index, translated in enumerate(raw_translations):
            chunk = self._chunk_for_index(context, index)
            chunk_id = self._chunk_id(index, chunk)
            result = evaluate_translation_quality(
                source_text=self._source_for_chunk(context, index, chunk),
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
                "novel_id": (chunk.novel_id if chunk is not None else context.novel_id) or "unknown_novel",
                "qa_score": result.score,
                "qa_warnings": list(result.warnings),
                "qa_errors": list(result.errors),
                "qa_diagnostics": dict(result.diagnostics),
            }
            if result.passed:
                chunk_state["status"] = ChunkTranslationStatus.TRANSLATED.value
                chunk_state["qa_status"] = "passed"
            else:
                chunk_state["status"] = ChunkTranslationStatus.QA_FAILED.value
                chunk_state["qa_status"] = "qa_failed"
                chunk_state["error_code"] = result.errors[0] if result.errors else "translation_qa_failed"
                failed_chunk_ids.append(chunk_id)
            context.chunk_states[chunk_id] = chunk_state

        combined = self._merge_results(results)
        context.metadata["qa_results"] = qa_payloads
        context.metadata["qa_result"] = combined.to_dict()
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
