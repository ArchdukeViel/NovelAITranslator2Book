"""Provider error mapping and request audit record helpers.

Extracted from translate_result_assembly.py. These functions handle:
- Normalising generic exceptions into ``ProviderError`` with appropriate codes
- Building the ``provider_request_record`` audit payload
- Constructing provider error metadata for logging/observation
"""

from __future__ import annotations

from typing import Any

from novelai.core.errors import ProviderError, ProviderErrorCode
from novelai.prompts.models import TranslationRequest
from novelai.translation.pipeline.context import PipelineState
from novelai.translation.pipeline.stages.translate_result_assembly import (
    glossary_hash as _glossary_hash,
)
from novelai.translation.pipeline.stages.translate_result_assembly import (
    hash_text,
    prompt_version,
    translation_run_id,
    utc_now_iso,
)


def provider_error_from_generic(exc: Exception, *, provider_key: str, provider_model: str) -> ProviderError:
    """Map a generic exception to a ``ProviderError`` with an appropriate code.

    Heuristic-based: checks known error substrings in the message.
    Falls back to ``ProviderErrorCode.UNKNOWN``.
    """
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


def provider_error_metadata(
    exc: ProviderError,
    *,
    chunk_id: str,
    attempt_number: int,
) -> dict[str, object]:
    """Build a metadata dict from a ``ProviderError`` for logging."""
    return {
        **exc.activity_details(),
        "chunk_id": chunk_id,
        "attempt_number": attempt_number,
        "timestamp": utc_now_iso(),
    }


def provider_request_record(
    context: PipelineState,
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
    """Build the full audit/replay record for a single provider request.

    Called after every provider call (successful or failed) to persist
    the attempt details for debugging, replay, and cost tracking.
    """
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
