"""Context helpers extracted from ``TranslateStage``.

All methods here are pure functions or ``@staticmethod``-equivalent helpers
that depend only on their arguments — no ``self`` or instance state.
"""

from __future__ import annotations

import hashlib
import logging
from datetime import UTC, datetime
from typing import Any

from novelai.config.settings import settings
from novelai.core.errors import ProviderError, ProviderErrorCode
from novelai.glossary import (
    GlossaryTerm,
    extract_term_context,
    normalize_glossary_entries,
    rank_glossary_terms_for_text,
    summarize_term_context,
)
from novelai.prompts import build_translation_request
from novelai.prompts.models import TranslationRequest
from novelai.translation.pipeline.context import PipelineContext, TranslationChunk

logger = logging.getLogger(__name__)


def utc_now_iso() -> str:
    """Return a serialized UTC timestamp with a trailing Z."""
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def hash_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def infer_source_language(context: PipelineContext) -> str | None:
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


def normalize_runtime_glossary(context: PipelineContext) -> dict[str, GlossaryTerm]:
    raw_entries = context.metadata.get("glossary")
    runtime: dict[str, GlossaryTerm] = {}
    for entry in normalize_glossary_entries(raw_entries):
        runtime[entry.source] = entry
    return runtime


def select_chunk_glossary(
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


def chunk_text(chunk: str | TranslationChunk) -> str:
    if isinstance(chunk, TranslationChunk):
        return chunk.source_text
    return chunk


def chunk_id(chunk: str | TranslationChunk, chunk_index: int) -> str:
    if isinstance(chunk, TranslationChunk):
        return chunk.chunk_id
    return f"legacy_{chunk_index + 1:04d}"


def chapter_ids(context: PipelineContext, chunk: str | TranslationChunk) -> list[str]:
    if isinstance(chunk, TranslationChunk):
        return list(chunk.chapter_ids)
    return [context.chapter_id] if isinstance(context.chapter_id, str) and context.chapter_id.strip() else []


def paragraph_ids(chunk: str | TranslationChunk) -> list[str]:
    if isinstance(chunk, TranslationChunk):
        return list(chunk.paragraph_ids)
    return []


def paragraph_hashes(chunk: str | TranslationChunk) -> list[str]:
    if isinstance(chunk, TranslationChunk):
        return list(chunk.paragraph_hashes)
    return []


def paragraph_lineage(chunk: str | TranslationChunk) -> list[dict[str, Any]]:
    if isinstance(chunk, TranslationChunk):
        return [dict(item) for item in chunk.paragraph_lineage]
    return []


def provider_error_metadata(
    exc: ProviderError,
    *,
    chunk_id: str,
    attempt_number: int,
) -> dict[str, object]:
    return {
        **exc.activity_details(),
        "chunk_id": chunk_id,
        "attempt_number": attempt_number,
        "timestamp": utc_now_iso(),
    }


def prompt_version(context: PipelineContext) -> str:
    value = context.metadata.get("prompt_version")
    return value if isinstance(value, str) and value.strip() else "translation_request_v1"


def glossary_hash(context: PipelineContext, glossary_block_text: str | None = None) -> str:
    if isinstance(glossary_block_text, str):
        return hash_text(glossary_block_text)
    return hash_text(str(context.metadata.get("glossary") or ""))


# Backward-compat alias for use inside provider_request_record
_glossary_hash = glossary_hash


def force_retranslate(context: PipelineContext) -> bool:
    return bool(context.metadata.get("force_retranslate_chunks") or context.metadata.get("force_retranslate"))


def safe_job_id(context: PipelineContext) -> str | None:
    for value in (context.job_id, context.activity_id, context.novel_id):
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def translation_run_id(context: PipelineContext) -> str:
    for value in (
        context.metadata.get("translation_run_id"),
        context.job_id,
        context.activity_id,
    ):
        if isinstance(value, str) and value.strip():
            return value.strip()
    return "run_manual"


def explicit_translation_run_id(context: PipelineContext) -> bool:
    return any(
        isinstance(context.metadata.get(key), str) and context.metadata[key].strip()
        for key in ("translation_run_id", "run_id")
    )


def platform_novel_id(context: PipelineContext) -> int | None:
    for key in ("platform_novel_id", "db_novel_id", "glossary_novel_id"):
        value = context.metadata.get(key)
        if isinstance(value, int) and value > 0:
            return value
    if isinstance(context.novel_id, int) and context.novel_id > 0:
        return context.novel_id
    return None


def nonnegative_int(value: Any, *, default: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return parsed if parsed >= 0 else default


def provider_error_from_generic(exc: Exception, *, provider_key: str, provider_model: str) -> ProviderError:
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


def provider_request_record(
    context: PipelineContext,
    *,
    chunk_id: str,
    chunk_text: str,
    request: TranslationRequest | None,
    provider_key: str,
    provider_model: str,
    glossary_hash: str | None = None,
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
        "translation_run_id": translation_run_id(context),
        "novel_id": context.novel_id,
        "chapter_id": context.chapter_id,
        "chapter_ids": list(chapter_ids or []),
        "paragraph_ids": list(paragraph_ids or []),
        "chunk_id": chunk_id,
        "provider_key": provider_key,
        "provider_model": provider_model,
        "prompt_version": prompt_version(context),
        "source_text_hash": hash_text(chunk_text),
        "prompt_hash": hash_text(prompt_text),
        "glossary_hash": glossary_hash or _glossary_hash(context),
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


def observe_chunk_context(
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


def build_prompt_request(
    context: PipelineContext,
    chunk: str,
    *,
    chunk_glossary: list[GlossaryTerm],
    prompt_glossary_block: str | None = None,
) -> TranslationRequest | None:
    source_language = infer_source_language(context)
    target_language = context.metadata.get("target_language") or settings.TRANSLATION_TARGET_LANGUAGE
    if not isinstance(source_language, str) or not source_language.strip():
        return None
    if not isinstance(target_language, str) or not target_language.strip():
        return None

    style_preset = context.metadata.get("style_preset")
    consistency_mode = bool(context.metadata.get("consistency_mode", False))
    json_output = bool(context.metadata.get("json_output", False))
    honorific_policy = context.metadata.get("honorific_policy")
    if not isinstance(honorific_policy, str) or not honorific_policy.strip():
        honorific_policy = None
    return build_translation_request(
        text=chunk,
        source_language=source_language,
        target_language=target_language,
        glossary_entries=chunk_glossary,
        prompt_glossary_block=prompt_glossary_block,
        style_preset=style_preset if isinstance(style_preset, str) else None,
        consistency_mode=consistency_mode,
        json_output=json_output,
        honorific_policy=honorific_policy,
    )


def glossary_prompt_options(context: PipelineContext):
    from novelai.services.glossary_prompt_injection import GlossaryPromptInjectionOptions

    return GlossaryPromptInjectionOptions(
        max_terms=int(context.metadata.get("glossary_prompt_max_terms", 20) or 20),
        max_block_chars=int(context.metadata.get("glossary_prompt_max_block_chars", 2000) or 2000),
        max_avoid_variants_per_term=int(
            context.metadata.get("glossary_prompt_max_avoid_variants_per_term", 3) or 3
        ),
    )


def record_prompt_glossary_metadata(
    context: PipelineContext,
    *,
    chunk_id: str,
    block: Any,
    glossary_hash: str,
) -> None:
    context.metadata["glossary_injected_term_count"] = int(
        context.metadata.get("glossary_injected_term_count", 0) or 0
    ) + (len(block.included_terms) if block is not None else 0)
    records = context.metadata.setdefault("glossary_prompt_blocks", [])
    if isinstance(records, list):
        records.append(
            {
                "chunk_id": chunk_id,
                "terms_injected": len(block.included_terms) if block is not None else 0,
                "skipped_count": len(block.skipped_terms) if block is not None else 0,
                "truncated": bool(block.truncated) if block is not None else False,
                "conflict_warning_count": len(block.conflict_warnings) if block is not None else 0,
                "empty": True if block is None else block.empty,
                "glossary_hash": glossary_hash,
                "prompt_template_version": context.metadata.get("prompt_template_version", ""),
            }
        )
    if block is not None and block.included_terms:
        existing = context.metadata.get("glossary_approved_terms")
        if not isinstance(existing, list):
            existing = []
        for term in block.included_terms:
            existing.append({"source": term.term, "target": term.translation})
        context.metadata["glossary_approved_terms"] = existing
    if block is None:
        return
    warnings = context.metadata.setdefault("glossary_prompt_warnings", [])
    if isinstance(warnings, list):
        warnings.extend(block.warnings)
        warnings.extend(block.conflict_warnings)
