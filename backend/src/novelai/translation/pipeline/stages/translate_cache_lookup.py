"""Translation cache lookup and persistence helpers.

Extracted from ``TranslateStage`` to reduce the class's line count.
These functions handle cache reads/writes and chunk state persistence
using explicitly passed ``StorageService``/``TranslationCache`` instances.
"""

from __future__ import annotations

from typing import Any

from novelai.services.translation_cache import TranslationCache, TranslationCacheService
from novelai.shared.pipeline import ChunkTranslationStatus
from novelai.storage.service import StorageService
from novelai.translation.pipeline.context import PipelineContext, TranslationChunk
from novelai.translation.pipeline.stages.translate_result_assembly import (
    chapter_ids as chapter_ids_fn,
)
from novelai.translation.pipeline.stages.translate_result_assembly import (
    chunk_id as chunk_id_fn,
)
from novelai.translation.pipeline.stages.translate_result_assembly import (
    chunk_text as chunk_text_fn,
)
from novelai.translation.pipeline.stages.translate_result_assembly import (
    explicit_translation_run_id,
    hash_text,
    prompt_version,
    translation_run_id,
)
from novelai.translation.pipeline.stages.translate_result_assembly import (
    glossary_hash as glossary_hash_fn,
)
from novelai.translation.pipeline.stages.translate_result_assembly import (
    paragraph_hashes as paragraph_hashes_fn,
)
from novelai.translation.pipeline.stages.translate_result_assembly import (
    paragraph_ids as paragraph_ids_fn,
)
from novelai.translation.pipeline.stages.translate_result_assembly import (
    paragraph_lineage as paragraph_lineage_fn,
)


def save_chunk_records(
    storage: StorageService,
    context: PipelineContext,
    chunks: list[str | TranslationChunk],
) -> None:
    novel_id = context.novel_id
    if not isinstance(novel_id, str) or not novel_id.strip():
        return
    records: list[dict[str, Any]] = []
    for index, chunk in enumerate(chunks):
        text = chunk_text_fn(chunk)
        cid = chunk_id_fn(chunk, index)
        records.append(
            {
                "chunk_id": cid,
                "novel_id": novel_id,
                "request_id": context.metadata.get("request_id"),
                "translation_run_id": translation_run_id(context),
                "chapter_ids": chapter_ids_fn(context, chunk),
                "paragraph_ids": paragraph_ids_fn(chunk),
                "paragraph_hashes": paragraph_hashes_fn(chunk),
                "paragraph_lineage": paragraph_lineage_fn(chunk),
                "source_text": text,
                "source_text_hash": hash_text(text),
                "char_count": len(text),
                "status": context.chunk_states.get(cid, {}).get("status", ChunkTranslationStatus.PENDING.value),
            }
        )
    if records:
        storage.save_translation_chunks(novel_id, records)


def load_persisted_chunk_states(
    storage: StorageService,
    context: PipelineContext,
) -> None:
    novel_id = context.novel_id
    if not isinstance(novel_id, str) or not novel_id.strip():
        return
    stored_states = storage.load_chunk_states(
        novel_id=novel_id,
        chapter_id=context.chapter_id,
        translation_run_id=translation_run_id(context),
    )
    if not stored_states and not explicit_translation_run_id(context):
        stored_states = storage.load_chunk_states(
            novel_id=novel_id,
            chapter_id=context.chapter_id,
        )
    for stored in stored_states:
        chunk_id = stored.get("chunk_id") if isinstance(stored, dict) else None
        if isinstance(chunk_id, str) and chunk_id.strip():
            context.chunk_states[chunk_id] = {
                **context.chunk_states.get(chunk_id, {}),
                **dict(stored),
            }


def load_existing_chunk_output(
    storage: StorageService,
    context: PipelineContext,
    *,
    chunk_id: str,
    chunk_text: str,
    chapter_ids: list[str],
    glossary_hash: str | None = None,
) -> str | None:
    novel_id = context.novel_id
    if not isinstance(novel_id, str) or not novel_id.strip():
        return None
    existing_state = context.chunk_states.get(chunk_id, {})
    if existing_state.get("status") != ChunkTranslationStatus.TRANSLATED.value:
        return None
    stored = storage.read_translation_output(
        novel_id,
        chunk_id=chunk_id,
        translation_run_id=translation_run_id(context),
        chapter_ids=chapter_ids,
    )
    if not stored and not explicit_translation_run_id(context):
        stored = storage.read_translation_output(
            novel_id,
            chunk_id=chunk_id,
            chapter_ids=chapter_ids,
        )
    if not isinstance(stored, list) or not stored:
        return None
    latest = stored[-1]
    if not isinstance(latest, dict):
        return None
    expected = {
        "source_text_hash": hash_text(chunk_text),
        "prompt_version": prompt_version(context),
        "glossary_hash": glossary_hash or glossary_hash_fn(context),
        "style_preset": context.metadata.get("style_preset"),
        "json_output": bool(context.metadata.get("json_output", False)),
        "consistency_mode": bool(context.metadata.get("consistency_mode", False)),
    }
    for key, value in expected.items():
        if latest.get(key) != value:
            return None
    text = latest.get("translated_text")
    return text if isinstance(text, str) else None


def save_chunk_attempt(
    storage: StorageService,
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
    cid = chunk_id_fn(chunk, chunk_index)
    text = chunk_text_fn(chunk)
    storage.save_chunk_attempt_record(
        {
            "chunk_id": cid,
            "novel_id": novel_id,
            "request_id": context.metadata.get("request_id"),
            "translation_run_id": translation_run_id(context),
            "chapter_ids": chapter_ids_fn(context, chunk),
            "paragraph_ids": paragraph_ids_fn(chunk),
            "paragraph_hashes": paragraph_hashes_fn(chunk),
            "paragraph_lineage": paragraph_lineage_fn(chunk),
            "source_text_hash": hash_text(text),
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


def save_chunk_output(
    storage: StorageService,
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
    novel_id = context.novel_id
    if not isinstance(novel_id, str) or not novel_id.strip():
        return
    cid = chunk_id_fn(chunk, chunk_index)
    text = chunk_text_fn(chunk)
    storage.save_translation_output(
        {
            "output_id": f"{cid}:attempt_{attempt_number:04d}",
            "chunk_id": cid,
            "novel_id": novel_id,
            "translation_run_id": translation_run_id(context),
            "chapter_ids": chapter_ids_fn(context, chunk),
            "paragraph_ids": paragraph_ids_fn(chunk),
            "paragraph_hashes": paragraph_hashes_fn(chunk),
            "paragraph_lineage": paragraph_lineage_fn(chunk),
            "translated_text": translated_text,
            "source_text_hash": hash_text(text),
            "output_hash": hash_text(translated_text),
            "provider_key": provider_key,
            "provider_model": provider_model,
            "prompt_version": prompt_version(context),
            "glossary_hash": glossary_hash or glossary_hash_fn(context),
            "glossary_revision": int(context.metadata.get("glossary_revision", 0) or 0),
            "glossary_injected_term_count": int(
                context.metadata.get("glossary_injected_term_count", 0) or 0
            ),
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


def persist_chunk_state(
    storage: StorageService,
    context: PipelineContext,
    chunk_id: str,
) -> None:
    state = context.chunk_states.get(chunk_id)
    if not isinstance(state, dict):
        return
    state["translation_run_id"] = translation_run_id(context)
    storage.upsert_chunk_state(state)
    novel_id = state.get("novel_id") or context.novel_id
    status = state.get("status")
    if isinstance(novel_id, str) and novel_id.strip() and isinstance(status, str) and status.strip():
        fields = {key: value for key, value in state.items() if key not in {"chunk_id", "novel_id", "status"}}
        storage.update_translation_chunk_status(novel_id, chunk_id, status, **fields)


def cached_translation(
    cache: TranslationCache,
    cache_service: TranslationCacheService,
    context: PipelineContext,
    *,
    provider_key: str,
    provider_model: str,
    chunk: str,
    request: Any,
    glossary_hash: str | None = None,
) -> tuple[str, str, str, bool] | None:
    from novelai.config.settings import settings
    from novelai.translation.pipeline.stages.translate_result_assembly import infer_source_language

    if settings.TRANSLATION_CACHE_ENABLED:
        try:
            from novelai.services.translation_cache import make_cache_key

            source_language = infer_source_language(context) or "auto"
            target_language = context.metadata.get("target_language") or settings.TRANSLATION_TARGET_LANGUAGE
            g_hash = glossary_hash or ""
            pv = context.metadata.get("prompt_version") or ""
            cache_key = make_cache_key(
                chunk, source_language, target_language, g_hash,
                provider_key=provider_key,
                provider_model=provider_model,
                prompt_version=pv,
            )
            entry = cache_service.get(cache_key)
            if entry is not None:
                return entry.translated_text, provider_key, provider_model, True
        except Exception:
            pass

    cache_key = request.cache_key() if request is not None else chunk
    cached = cache.get(cache_key, provider_key, provider_model)
    if cached is None:
        return None
    return cached, provider_key, provider_model, True
