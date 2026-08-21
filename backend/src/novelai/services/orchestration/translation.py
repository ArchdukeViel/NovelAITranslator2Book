"""Core translation orchestration.

This module holds the core orchestration functions:
- DB state helpers, exception helpers, platform/glossary resolution
- Preflight checks, polish phase, phased pipeline
- Main ``translate_chapters`` and ``retranslate_chapter``

Metadata translation and request estimation are in ``translation_metadata.py``.
Paragraph lineage and delta retranslation are in ``translation_lineage.py``.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from novelai.config.settings import settings
from novelai.core.chapter_state import ChapterState, TranslationState
from novelai.core.errors import TranslationInProgressError
from novelai.db.engine import session_scope
from novelai.db.models.chapter import Chapter
from novelai.db.models.novel import Novel
from novelai.glossary import (
    canonical_glossary_hash,
    glossary_status_counts,
    normalize_glossary_entries,
)
from novelai.services.catalog_service import safely_refresh_catalog_projection_after_storage_write
from novelai.services.library_summary_service import best_effort_invalidate
from novelai.services.orchestration.common import PreflightIssue, _make_state_data
from novelai.services.orchestration.translation_lineage import (
    _count_pending_glossary_entries,
    _try_delta_translate_chapter,
)
from novelai.services.orchestration.translation_progress import _build_chapter_summary
from novelai.services.pipeline.checkpoint import Checkpoint
from novelai.sources.base import SourceAdapter
from novelai.storage.generations import resolve_active_generation_id
from novelai.translation.pipeline.stages.translate_result_assembly import hash_text
from novelai.translation.run_manifest import TranslationRunManifest
from novelai.utils.chapter_selection import ResolvedChapterSelection, resolve_chapter_selection

logger = logging.getLogger(__name__)

# Per-chapter lock to prevent concurrent translation of the same chapter
_translation_locks: dict[str, asyncio.Lock] = {}


def _get_translation_lock(novel_id: str, chapter_id: str) -> asyncio.Lock:
    key = f"{novel_id}:{chapter_id}"
    if key not in _translation_locks:
        _translation_locks[key] = asyncio.Lock()
    return _translation_locks[key]


def _resolve_effective_prompt_version(self: Any, meta: dict[str, Any]) -> str:
    """Resolve the effective prompt template version for a translation run.

    Section 9: do not hard-code ``translation_request_v1``. The pipeline
    records the actual prompt template version produced by
    :func:`build_translation_request`; if that import is unavailable
    (e.g. during early import ordering) we fall back to whatever version
    the metadata carries.
    """
    try:
        from novelai.prompts import PROMPT_TEMPLATE_VERSION  # type: ignore[attr-defined]
    except Exception:  # pragma: no cover - defensive
        PROMPT_TEMPLATE_VERSION = None

    if isinstance(PROMPT_TEMPLATE_VERSION, str) and PROMPT_TEMPLATE_VERSION.strip():
        return PROMPT_TEMPLATE_VERSION.strip()
    metadata_version = meta.get("prompt_template_version")
    if isinstance(metadata_version, str) and metadata_version.strip():
        return metadata_version.strip()
    return "translation_request_v1"


def _qa_policy_fingerprint(
    *,
    prompt_template_version: str | None,
) -> str:
    """Section 9: deterministic fingerprint of relevant QA policy inputs.

    Captures the structural QA inputs (policy mode, deterministic-qa
    version, LLM grader model, min-score, retry budget, structured-output
    policy) plus the prompt template version so any change to one of them
    invalidates downstream translation records.
    """
    payload = {
        "qa_policy_mode": str(getattr(settings, "LLM_QA_POLICY", "") or ""),
        "llm_qa_enabled": bool(getattr(settings, "LLM_QA_ENABLED", False)),
        "llm_qa_min_score": float(getattr(settings, "LLM_QA_MIN_SCORE", 0.0) or 0.0),
        "llm_qa_max_retry_attempts": int(getattr(settings, "LLM_QA_MAX_RETRY_ATTEMPTS", 0) or 0),
        "deterministic_qa_version": str(getattr(settings, "DETERMINISTIC_QA_VERSION", "") or "v1"),
        "structured_output_policy_version": str(getattr(settings, "STRUCTURED_OUTPUT_POLICY_VERSION", "") or "v1"),
        "llm_grader_model": str(getattr(settings, "LLM_QA_GRADER_MODEL", "") or "default"),
        "prompt_template_version": prompt_template_version or "",
    }
    serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hash_text(serialized)


def _resolve_effective_translation_source(
    storage: Any,
    novel_id: str,
    chapter_id: str,
    raw_chapter: dict[str, Any] | None,
) -> tuple[str | None, str]:
    """Resolve the effective translation source text for a chapter.

    Section 4: mutable OCR state lives in the novel-root media overlay and
    wins over the committed raw snapshot. When OCR is required, the review
    is complete (``ocr_status == "reviewed"``) and reviewed text exists, the
    reviewed OCR text IS the source; otherwise the raw chapter text is used.
    Every consumer (resume gate, run-manifest source hash, delta and full
    translation, stored ``source_hash`` lineage) must hash and translate the
    SAME effective text, so this helper is the single resolution point.

    Returns ``(effective_text, effective_source_hash)``; ``effective_text``
    is ``None`` when no usable source exists and the hash is ``""``.
    """
    media_state = storage.load_chapter_media_state(novel_id, chapter_id) or {}
    effective_text: str | None = None
    if isinstance(raw_chapter, dict):
        reviewed_ocr_text = media_state.get("ocr_text")
        if (
            bool(media_state.get("ocr_required", False))
            and str(media_state.get("ocr_status") or "").strip().lower() == "reviewed"
            and isinstance(reviewed_ocr_text, str)
            and reviewed_ocr_text.strip()
        ):
            effective_text = reviewed_ocr_text
        else:
            raw_text_obj = raw_chapter.get("text")
            if isinstance(raw_text_obj, str):
                effective_text = raw_text_obj
    effective_hash = storage._hash_text(effective_text) if effective_text else ""
    return effective_text, effective_hash


def _resolve_effective_output_policy(
    *,
    style_preset: str | None,
    consistency_mode: bool | None,
    json_output: bool | None,
    honorific_policy: str | None,
    workflow_defaults: dict[str, Any] | None,
) -> tuple[str | None, bool, bool, str | None]:
    """Resolve caller-supplied output-shaping settings against workflow defaults.

    The resolution is symmetric with the stored-version validity contract
    (``is_translation_valid``): a caller-supplied value is always the
    effective identity; workflow defaults apply ONLY when the caller did not
    supply a value (``None`` means "not supplied" for every dimension).
    ``consistency_mode`` and ``json_output`` are ``bool | None`` so an
    explicit ``False`` is preserved instead of being indistinguishable from
    an omitted value (which must fall back to the workflow default for
    ``consistency_mode``). ``json_output`` has no workflow default, so an
    omitted value resolves to ``False`` and an explicit value passes through.
    """
    defaults = workflow_defaults if isinstance(workflow_defaults, dict) else {}
    effective_style_preset = style_preset if style_preset is not None else defaults.get("style_preset")
    effective_consistency_mode = (
        consistency_mode if consistency_mode is not None else bool(defaults.get("consistency_mode", False))
    )
    effective_json_output = json_output if json_output is not None else False
    effective_honorific_policy = honorific_policy if honorific_policy is not None else defaults.get("honorific_policy")
    return effective_style_preset, effective_consistency_mode, effective_json_output, effective_honorific_policy


def _translation_lineage_kwargs(
    storage: Any,
    novel_id: str,
    chapter_id: str,
    *,
    raw_text: str,
    translated: str,
    translation_run_id: str,
    raw_generation_id: str,
    source_language: str | None,
    target_language: str | None,
    style_preset: str | None,
    consistency_mode: bool,
    json_output: bool,
    qa_policy_fingerprint: str | None,
    auto_activate: bool,
    honorific_policy: str | None = None,
    # Source-native episode id (Kakuyomu ``episode_id``, Syosetu ``num``).
    # ``load_chapter`` does not expose it, so the caller must pass the value
    # resolved from the source index; the logical ``chapter_id`` is only the
    # fallback (e.g. imported documents with no native episode identity).
    source_episode_id: str | None = None,
    # Effective canonical glossary hash the validator will compare against.
    # Production passes ``canonical_glossary_hash(glossary)`` so the stored
    # lineage matches the effective contract even when the novel metadata has
    # no ``glossary_hash`` (e.g. no glossary applied); the metadata fallback
    # below keeps older callers consistent when no hash is supplied.
    glossary_hash: str | None = None,
    # Effective prompt template version the validator compares against; the
    # fallback below resolves the same value when not supplied.
    prompt_template_version: str | None = None,
) -> dict[str, Any]:
    """Section 8: assemble the complete raw-to-version lineage fields for a
    stored machine translation version so validity checks can consume the
    actual stored fields instead of the run manifest alone."""
    raw_bundle = storage.load_chapter(novel_id, chapter_id) or {}

    def _json_hash(value: Any) -> str:
        return storage._hash_text(json.dumps(value, ensure_ascii=False, sort_keys=True, default=str))

    glossary_hash_value: str | None = glossary_hash
    if not glossary_hash_value and hasattr(storage, "load_metadata"):
        try:
            meta = storage.load_metadata(novel_id) or {}
            if isinstance(meta, dict):
                gh = meta.get("glossary_hash")
                if isinstance(gh, str) and gh.strip():
                    glossary_hash_value = gh.strip()
        except Exception:
            glossary_hash_value = None

    return {
        "source_hash": storage._hash_text(raw_text or ""),
        "translation_run_id": translation_run_id,
        "raw_generation_id": raw_generation_id,
        "source_episode_id": str(source_episode_id or chapter_id),
        "source_structure_hash": _json_hash(raw_bundle.get("source_blocks") or []),
        "source_image_manifest_hash": _json_hash(raw_bundle.get("images") or []),
        "glossary_hash": glossary_hash_value,
        "prompt_template_version": prompt_template_version or _resolve_effective_prompt_version(storage, raw_bundle),
        "qa_policy_fingerprint": qa_policy_fingerprint,
        "source_language": source_language,
        "target_language": target_language,
        "style_preset": style_preset,
        "consistency_mode": consistency_mode,
        "json_output": json_output,
        "output_hash": storage._hash_text(translated),
        "activation_disposition": "auto_activate" if auto_activate else "low_confidence",
        "honorific_policy": honorific_policy,
    }


def _update_db_translation_state(
    novel_id: str,
    chapter_id: str,
    state: TranslationState,
    error: str | None = None,
) -> None:
    """Update ``translation_state`` and ``translation_error`` on Chapter row.

    REQ-1.4: State must be updated before/after each pipeline stage.

    Section 2: ``chapter_id`` is the stable logical identifier. The lookup
    prefers ``logical_chapter_id`` (canonical stable key for both
    numeric and Kakuyomu ids) and falls back to ``chapter_number`` for
    legacy rows pre-dating the stable-id migration.
    """
    try:
        with session_scope() as session:
            novel = session.query(Novel).filter_by(slug=novel_id).one_or_none()
            if novel is None:
                return
            row = _lookup_chapter_row(session, novel.id, chapter_id)
            if row is not None:
                row.translation_state = state.value  # type: ignore[assignment]
                if error is not None:
                    row.translation_error = error[:1024] if len(error) > 1024 else error
                session.commit()
    except Exception:
        logger.warning("Failed to update DB translation state %s/%s", novel_id, chapter_id, exc_info=True)


def _load_db_translation_state(novel_id: str, chapter_id: str) -> str:
    """Read ``translation_state`` from the Chapter row (REQ-3.1, Section 2)."""
    try:
        with session_scope() as session:
            novel = session.query(Novel).filter_by(slug=novel_id).one_or_none()
            if novel is None:
                return TranslationState.PENDING.value
            row = _lookup_chapter_row(session, novel.id, chapter_id)
            if row is not None:
                state_attr = getattr(row, "translation_state", None)
                if state_attr is not None:
                    return state_attr or TranslationState.PENDING.value
                if isinstance(row, tuple):
                    return row[0] or TranslationState.PENDING.value
    except Exception:
        logger.warning("Failed to load DB translation state %s/%s", novel_id, chapter_id, exc_info=True)
    return TranslationState.PENDING.value


def _lookup_chapter_row(session: Any, novel_id: int, chapter_id: str) -> Any | None:
    """Resolve a Chapter row by stable id then by numeric fallback (Section 2).

    The lookup prefers the optional ``logical_chapter_id`` column when
    the stable-id migration has been applied; before the migration is
    in place we fall back to ``chapter_number`` so legacy rows remain
    reachable.
    """
    from sqlalchemy import inspect

    try:
        mapper = inspect(Chapter)
        if "logical_chapter_id" in {col.key for col in mapper.columns}:
            stable = (
                session.query(Chapter)
                .filter(
                    Chapter.novel_id == novel_id,
                    Chapter.logical_chapter_id == str(chapter_id),
                )
                .one_or_none()
            )
            if stable is not None:
                return stable
    except Exception:
        pass
    if str(chapter_id).isdigit():
        return (
            session.query(Chapter)
            .filter(Chapter.novel_id == novel_id, Chapter.chapter_number == int(chapter_id))
            .one_or_none()
        )
    return None


def _pipeline_context_from_exception(exc: BaseException) -> Any | None:
    context = getattr(exc, "pipeline_context", None)
    if context is not None:
        return context
    cause = getattr(exc, "__cause__", None)
    if cause is not None:
        return getattr(cause, "pipeline_context", None)
    return None


def _metadata_platform_novel_id(meta: dict[str, Any]) -> int | None:
    for key in ("platform_novel_id", "db_novel_id", "glossary_novel_id"):
        value = meta.get(key)
        if isinstance(value, int) and value > 0:
            return value
    return None


def _resolve_platform_novel_id(novel_id: str, meta: dict[str, Any]) -> int | None:
    explicit = _metadata_platform_novel_id(meta)
    if explicit is not None:
        return explicit
    try:
        with session_scope() as session:
            novel = session.query(Novel).filter_by(slug=novel_id).one_or_none()
            if novel is not None:
                return int(novel.id)
    except Exception:
        return None
    return None


def _resolve_glossary_revision(novel_id: str, platform_novel_id: int | None) -> int:
    try:
        with session_scope() as session:
            novel = session.get(Novel, platform_novel_id) if platform_novel_id is not None else None
            if novel is None:
                novel = session.query(Novel).filter_by(slug=novel_id).one_or_none()
            if novel is not None:
                return int(novel.glossary_revision or 0)
    except Exception:
        return 0
    return 0


def _pipeline_events_from_exception(exc: BaseException) -> list[dict[str, Any]]:
    events = getattr(exc, "pipeline_events", None)
    if not isinstance(events, list):
        cause = getattr(exc, "__cause__", None)
        if cause is not None:
            events = getattr(cause, "pipeline_events", None)
    if not isinstance(events, list):
        context = _pipeline_context_from_exception(exc)
        events = getattr(context, "pipeline_events", None)
    if not isinstance(events, list):
        return []
    return [dict(event) for event in events if isinstance(event, dict)]


def _failed_stage_name_from_exception(exc: BaseException) -> str:
    failed_stage = getattr(exc, "failed_stage_name", None)
    if not isinstance(failed_stage, str) or not failed_stage.strip():
        cause = getattr(exc, "__cause__", None)
        if cause is not None:
            failed_stage = getattr(cause, "failed_stage_name", None)
    if isinstance(failed_stage, str) and failed_stage.strip():
        return failed_stage.strip()
    for event in reversed(_pipeline_events_from_exception(exc)):
        if event.get("status_after") == "failed" and isinstance(event.get("stage_name"), str):
            return str(event["stage_name"])
    context = _pipeline_context_from_exception(exc)
    current_stage = getattr(context, "current_stage", None)
    if isinstance(current_stage, str) and current_stage.strip():
        return current_stage.strip()
    return "Pipeline"


def _persist_chunk_qa_results_to_outputs(storage: Any, novel_id: str, chunk_states: dict[str, Any]) -> dict[str, str]:
    """Persist QA results onto the latest stored translation output per chunk.

    Returns a mapping of ``chunk_id -> output_hash`` for every chunk that had
    an existing output record, used as run-manifest evidence (Blocker D).
    """
    chunk_output_hashes: dict[str, str] = {}
    if not isinstance(novel_id, str) or not novel_id.strip():
        return chunk_output_hashes
    for chunk_id, state in chunk_states.items():
        if not isinstance(chunk_id, str) or not chunk_id.strip() or not isinstance(state, dict):
            continue
        outputs = storage.read_translation_output(
            novel_id,
            chunk_id=chunk_id,
            translation_run_id=state.get("translation_run_id")
            if isinstance(state.get("translation_run_id"), str)
            else None,
            chapter_ids=state.get("chapter_ids") if isinstance(state.get("chapter_ids"), list) else None,
            chapter_id=state.get("chapter_id") if isinstance(state.get("chapter_id"), str) else None,
        )
        if not isinstance(outputs, list) or not outputs:
            continue
        latest = outputs[-1]
        if not isinstance(latest, dict):
            continue
        qa_status = state.get("status")
        storage.save_translation_output(
            {
                **latest,
                "output_id": latest.get("output_id"),
                "qa_score": state.get("qa_score"),
                "qa_warnings": state.get("qa_warnings") or [],
                "qa_errors": state.get("qa_errors") or [],
                "qa_status": qa_status,
            }
        )
        output_hash = latest.get("output_hash")
        if isinstance(output_hash, str) and output_hash.strip():
            chunk_output_hashes[chunk_id] = output_hash
    return chunk_output_hashes


def _preflight_translation(
    self: Any,
    *,
    novel_id: str,
    source_key: str,
    meta: dict[str, Any],
    selected: list[ResolvedChapterSelection],
    force: bool,
    source_language: str | None,
    target_language: str | None,
    glossary: Any | None,
    skip_glossary_gate: bool = False,
) -> list[PreflightIssue]:

    issues: list[PreflightIssue] = []

    if not selected:
        issues.append(
            PreflightIssue(
                code="empty_selection",
                reason="No chapters match the requested selection.",
            )
        )
        return issues

    onboarding_status = self.storage.resolve_onboarding_status(novel_id)
    if onboarding_status != "ready_for_translation":
        issues.append(
            PreflightIssue(
                code="onboarding_not_ready",
                reason=(f"Novel onboarding is {onboarding_status!r}; complete chapter scraping before translation."),
                details={"onboarding_status": onboarding_status},
            )
        )

    chapter_by_id = {record.chapter_id: record for record in selected}

    missing_chapters = [record.chapter_id for record in selected if record.chapter_id not in chapter_by_id]
    if missing_chapters:
        issues.append(
            PreflightIssue(
                code="metadata_mismatch",
                reason=("Selected chapters are missing from metadata: " + ", ".join(missing_chapters)),
            )
        )

    unresolved_urls: list[str] = []
    for record in selected:
        chapter_id = record.chapter_id
        chapter_meta = record.metadata
        raw_chapter = self.storage.load_chapter(novel_id, chapter_id)
        if chapter_meta.get("url") or (raw_chapter and isinstance(raw_chapter.get("text"), str)):
            continue
        unresolved_urls.append(chapter_id)
    if unresolved_urls:
        issues.append(
            PreflightIssue(
                code="missing_chapter_url",
                reason=("Some selected chapters have no source URL: " + ", ".join(unresolved_urls)),
            )
        )

    effective_source_language = source_language or self._infer_source_language(source_key, meta)
    if not effective_source_language:
        for record in selected:
            raw_chapter = self.storage.load_chapter(novel_id, record.chapter_id)
            if raw_chapter is None:
                continue
            raw_text = raw_chapter.get("text")
            if isinstance(raw_text, str) and raw_text.strip():
                effective_source_language = self._infer_source_language_from_text(raw_text)
                if effective_source_language:
                    break
    if not isinstance(effective_source_language, str) or not effective_source_language.strip():
        issues.append(
            PreflightIssue(
                code="missing_source_language",
                reason=("Source language is unknown. Provide source_language explicitly or include it in metadata."),
            )
        )

    if not isinstance(target_language, str) or not target_language.strip():
        issues.append(
            PreflightIssue(
                code="missing_target_language",
                reason="Target language is empty. Configure translation target language before running.",
            )
        )

    try:
        normalized_glossary = normalize_glossary_entries(glossary)
    except Exception as exc:
        issues.append(
            PreflightIssue(
                code="invalid_glossary",
                reason=f"Glossary entries are invalid: {exc}",
            )
        )
        normalized_glossary = []

    incremental_pending = {
        str(term).strip()
        for term in (meta.get("_incremental_pending_terms") or [])
        if isinstance(term, str) and term.strip()
    }
    pending_terms = [
        entry.source
        for entry in normalized_glossary
        if entry.status == "pending" and entry.source not in incremental_pending
    ]
    if pending_terms:
        preview = ", ".join(pending_terms[:5])
        if len(pending_terms) > 5:
            preview += f", +{len(pending_terms) - 5} more"
        issues.append(
            PreflightIssue(
                code="pending_glossary_terms",
                reason=(f"Review glossary terms before translation. Pending terms: {preview}."),
            )
        )

    # --- Glossary gate ---
    if not skip_glossary_gate:
        _novel_is_pending = False
        with session_scope() as session:
            _novel = session.query(Novel).filter_by(slug=novel_id).one_or_none()
            if _novel is not None:
                _novel_is_pending = _novel.glossary_status == "glossary_pending"
        pending_count = _count_pending_glossary_entries(novel_id) if _novel_is_pending else 0
        incremental = meta.get("_incremental_glossary_preflight")
        nonblocking_incremental_pending = (
            isinstance(incremental, dict)
            and incremental.get("status") in {"completed", "deferred"}
            and isinstance(incremental.get("pending"), list)
            and incremental.get("pending_only_new_terms") is True
            and pending_count <= len(incremental.get("pending", []))
        )
        if _novel_is_pending and not nonblocking_incremental_pending:
            if pending_count == 0:
                logger.info(
                    "Novel %r glossary_status=%r but no pending entries; skipping gate.",
                    novel_id,
                    "glossary_pending",
                )
            else:
                review_path = f"/admin/novels/{novel_id}/glossary"
                issues.append(
                    PreflightIssue(
                        code="glossary_gate_pending",
                        reason="Glossary review required before translation.",
                        details={
                            "glossary_status": "glossary_pending",
                            "glossary_pending_count": pending_count,
                            "glossary_review_url": review_path,
                        },
                    )
                )
    else:
        logger.info(
            "Glossary gate bypassed via skip_glossary_gate override for novel %r.",
            novel_id,
        )

    chapters_missing_ocr_review: list[str] = []
    for record in selected:
        chapter_id = record.chapter_id
        media_state = self.storage.load_chapter_media_state(novel_id, chapter_id)
        if media_state is None:
            continue

        if not bool(media_state.get("ocr_required", False)):
            continue

        ocr_status = str(media_state.get("ocr_status") or "pending").strip().lower()
        if ocr_status != "reviewed":
            chapters_missing_ocr_review.append(chapter_id)

    if chapters_missing_ocr_review:
        issues.append(
            PreflightIssue(
                code="missing_ocr_review",
                reason=(
                    "OCR review is required before translation for chapter(s): "
                    + ", ".join(chapters_missing_ocr_review)
                ),
            )
        )

    if not force:
        translatable = 0
        for record in selected:
            chapter_id = record.chapter_id
            raw_chapter = self.storage.load_chapter(novel_id, chapter_id)
            has_raw_text = isinstance(raw_chapter, dict) and isinstance(raw_chapter.get("text"), str)
            if self.storage.load_translated_chapter(novel_id, chapter_id) is None or (
                settings.TRANSLATION_DELTA_RETRANSLATION_ENABLED and has_raw_text
            ):
                translatable += 1
        if translatable == 0:
            issues.append(
                PreflightIssue(
                    code="nothing_to_translate",
                    reason="All selected chapters are already translated. Use force=True to retranslate.",
                )
            )

    return issues


async def polish_low_confidence_chapters(
    self: Any,
    *,
    source_key: str,
    novel_id: str,
    chapters: str = "all",
    provider_key: str | None = None,
    provider_model: str | None = None,
    source_language: str | None = None,
    target_language: str | None = None,
    confidence_threshold: float = 0.55,
    low_confidence_only: bool = True,
    consistency_mode: bool = True,
    json_output: bool = False,
    allow_cross_provider_fallback: bool = True,
) -> dict[str, Any]:
    """Retranslate only chapters that look low-confidence via heuristics."""
    meta = self.storage.load_metadata(novel_id)
    if not meta:
        raise RuntimeError("Metadata not found; import or scrape a novel first.")
    # Section 3: ONE authoritative provider identity per run, resolved here
    # before the manifest / resume gate / delta / execution / lineage are
    # created. Precedence: explicit caller > workflow profile > global
    # preferred. Never None: the pipeline stage must never silently execute a
    # different provider than the one the contract records.
    effective_provider, effective_model = self._resolve_effective_provider_contract(
        step="polish",
        metadata=meta,
        provider_key=provider_key,
        provider_model=provider_model,
    )

    resolved = resolve_chapter_selection(meta, chapters)
    _chapter_by_id = {record.chapter_id: record for record in resolved}
    selected_numbers = [record.sequence_number for record in resolved]
    low_confidence_ids: list[str] = []
    normalized_threshold = max(0.0, min(1.0, confidence_threshold))

    for record in resolved:
        chapter_id = record.chapter_id
        if chapter_id not in _chapter_by_id:
            continue
        raw = self.storage.load_chapter(novel_id, chapter_id) or {}
        translated = self.storage.load_translated_chapter(novel_id, chapter_id) or {}

        raw_text = raw.get("text")
        translated_raw_text = translated.get("text")
        source_text = raw_text if isinstance(raw_text, str) else ""
        translated_text = translated_raw_text if isinstance(translated_raw_text, str) else ""
        stored_score = (
            translated.get("confidence_score") if isinstance(translated.get("confidence_score"), float) else None
        )
        polish_needed_flag = (
            translated.get("polish_needed") if isinstance(translated.get("polish_needed"), bool) else None
        )

        if low_confidence_only and isinstance(polish_needed_flag, bool):
            if polish_needed_flag:
                low_confidence_ids.append(chapter_id)
            continue

        confidence_score = (
            stored_score
            if isinstance(stored_score, float)
            else self._score_translation_confidence(source_text, translated_text)
        )

        if confidence_score < normalized_threshold:
            low_confidence_ids.append(chapter_id)

    if not low_confidence_ids:
        return self._phase_payload(
            phase="phase3_polish",
            status="completed",
            message="No low-confidence chapters required polishing.",
            novel_id=novel_id,
            selected_chapters=len(selected_numbers),
            polished=0,
            candidates=0,
            threshold=normalized_threshold,
        )

    approved_glossary = [
        dict(entry)
        for entry in self.storage.load_glossary(novel_id)
        if isinstance(entry, dict)
        and str(entry.get("status") or "pending").strip().lower() in {"approved", "translated"}
    ]
    retranslate_selection = ",".join(low_confidence_ids)
    await self.translate_chapters(
        source_key=source_key,
        novel_id=novel_id,
        chapters=retranslate_selection,
        provider_key=effective_provider,
        provider_model=effective_model,
        force=True,
        source_language=source_language,
        target_language=target_language,
        glossary=approved_glossary,
        style_preset="polish",
        confidence_threshold=normalized_threshold,
        mark_polish_needed=True,
        consistency_mode=consistency_mode,
        json_output=json_output,
        allow_cross_provider_fallback=allow_cross_provider_fallback,
    )
    return self._phase_payload(
        phase="phase3_polish",
        status="completed",
        message="Low-confidence chapters polished.",
        novel_id=novel_id,
        selected_chapters=len(selected_numbers),
        polished=len(low_confidence_ids),
        candidates=len(low_confidence_ids),
        chapter_ids=low_confidence_ids,
        threshold=normalized_threshold,
    )


async def run_phased_translation_pipeline(
    self: Any,
    *,
    source_key: str,
    novel_id: str,
    chapters: str = "all",
    phase: str = "full",
    glossary_provider_key: str | None = None,
    glossary_provider_model: str | None = None,
    review_auto_approve: bool = True,
    review_min_target_length: int = 2,
    body_provider_key: str | None = None,
    body_provider_model: str | None = None,
    source_language: str | None = None,
    target_language: str | None = None,
    confidence_threshold: float = 0.55,
    polish_low_confidence_only: bool = True,
    consistency_mode: bool = False,
    json_output: bool = False,
    run_polish_phase: bool = False,
    body_allow_cross_provider_fallback: bool = True,
) -> dict[str, Any]:
    """Run one phase or the full phase chain with a shared payload schema."""
    normalized_phase = phase.strip().lower()
    if normalized_phase not in {"1", "1b", "2", "3", "full"}:
        raise ValueError("phase must be one of: 1, 1b, 2, 3, full")

    results: dict[str, Any] = {}

    if normalized_phase in {"1", "full"}:
        results["phase1"] = await self.extract_glossary_terms(
            novel_id=novel_id,
            chapters=chapters,
            max_terms=50,
        )
        if normalized_phase == "1":
            return self._phase_payload(
                phase="phase1_glossary_extraction",
                status="completed",
                message="Phase 1 completed.",
                novel_id=novel_id,
                blocked=False,
                results=results,
            )

    if normalized_phase in {"1b", "full"}:
        results["phase1b"] = await self.translate_glossary_terms(
            novel_id=novel_id,
            provider_key=glossary_provider_key,
            provider_model=glossary_provider_model,
            only_pending=True,
        )
        if normalized_phase == "1b":
            return self._phase_payload(
                phase="phase1b_glossary_translation",
                status="completed",
                message="Phase 1b completed.",
                novel_id=novel_id,
                blocked=False,
                results=results,
            )

    if normalized_phase == "full":
        results["phase1c"] = await self.review_glossary_terms(
            novel_id=novel_id,
            auto_approve_translated=review_auto_approve,
            min_target_length=review_min_target_length,
        )

    if normalized_phase in {"2", "full"}:
        counts = glossary_status_counts(self.storage.load_glossary(novel_id))
        pending = int(counts.get("pending", 0))
        if pending > 0:
            return self._phase_payload(
                phase="phase2_body_translation",
                status="blocked",
                message="Glossary review required before phase 2.",
                novel_id=novel_id,
                blocked=True,
                blocked_reason=f"Pending glossary terms: {pending}.",
                results=results,
            )

        await self.translate_chapters(
            source_key=source_key,
            novel_id=novel_id,
            chapters=chapters,
            provider_key=body_provider_key,
            provider_model=body_provider_model,
            force=False,
            source_language=source_language,
            target_language=target_language,
            confidence_threshold=confidence_threshold,
            mark_polish_needed=True,
            consistency_mode=consistency_mode,
            json_output=json_output,
            allow_cross_provider_fallback=body_allow_cross_provider_fallback,
        )
        results["phase2"] = self._phase_payload(
            phase="phase2_body_translation",
            status="completed",
            message="Phase 2 completed.",
            novel_id=novel_id,
            chapters=chapters,
            threshold=max(0.0, min(1.0, confidence_threshold)),
        )

        if normalized_phase == "2":
            return self._phase_payload(
                phase="phase2_body_translation",
                status="completed",
                message="Phase 2 completed.",
                novel_id=novel_id,
                blocked=False,
                results=results,
            )

    if normalized_phase in {"3", "full"} and (normalized_phase == "3" or run_polish_phase):
        results["phase3"] = await self.polish_low_confidence_chapters(
            source_key=source_key,
            novel_id=novel_id,
            chapters=chapters,
            provider_key=body_provider_key,
            provider_model=body_provider_model,
            source_language=source_language,
            target_language=target_language,
            confidence_threshold=confidence_threshold,
            low_confidence_only=polish_low_confidence_only,
            consistency_mode=True,
            json_output=json_output,
            allow_cross_provider_fallback=body_allow_cross_provider_fallback,
        )

        if normalized_phase == "3":
            return self._phase_payload(
                phase="phase3_polish",
                status="completed",
                message="Phase 3 completed.",
                novel_id=novel_id,
                blocked=False,
                results=results,
            )

    return self._phase_payload(
        phase="pipeline_full",
        status="completed",
        message="Phased pipeline completed.",
        novel_id=novel_id,
        blocked=False,
        results=results,
    )


async def translate_chapters(
    self: Any,
    source_key: str,
    novel_id: str,
    chapters: str,
    provider_key: str | None = None,
    provider_model: str | None = None,
    job_id: str | None = None,
    activity_id: str | None = None,
    force: bool = False,
    source_language: str | None = None,
    target_language: str | None = None,
    glossary: Any | None = None,
    style_preset: str | None = None,
    confidence_threshold: float = 0.55,
    mark_polish_needed: bool = True,
    consistency_mode: bool | None = None,
    json_output: bool | None = None,
    honorific_policy: str | None = None,
    allow_cross_provider_fallback: bool = True,
    skip_glossary_gate: bool = False,
    contribution_mode: str | None = None,
    requesting_user_id: int | None = None,
) -> dict[str, Any]:
    """Translate selected chapters through the pipeline.

    Loads metadata and glossary, then translates the requested chapters
    with bounded per-chapter concurrency controlled by
    ``TRANSLATION_CHAPTER_CONCURRENCY`` (default ``1`` for safe sequential
    behavior).  Each chapter's state is tracked via checkpoints
    (SEGMENTED -> TRANSLATED) for crash recovery.  Already-translated
    chapters are skipped unless *force* is ``True``.

    Returns a summary dict with per-chapter progress, succeeded/failed/
    skipped counts, and the effective target language.  On any chapter
    failure, the first exception is re-raised with ``chapter_progress``
    and ``chapter_summary`` attributes attached for the activity worker
    to surface a partial-failure summary.
    """

    source: SourceAdapter | None = None
    with contextlib.suppress(Exception):
        source = self._source_factory(source_key)
    meta = self.storage.load_metadata(novel_id)
    if not meta:
        raise RuntimeError("Metadata not found; run scrape-metadata first.")
    platform_novel_id = _resolve_platform_novel_id(novel_id, meta)
    glossary_revision = _resolve_glossary_revision(novel_id, platform_novel_id)

    effective_source_language = source_language or self._infer_source_language(source_key, meta)
    effective_target_language = target_language or settings.TRANSLATION_TARGET_LANGUAGE
    # Section 3: ONE authoritative provider identity per run, resolved HERE —
    # before the run manifest, the resume gate, delta retranslation, pipeline
    # execution and stored lineage are created. Precedence is strict: explicit
    # caller values > body-translation workflow profile > global preferred
    # provider/model. The result is never None, so the contract, the executed
    # pipeline call and the stored lineage can never diverge (a version must
    # never record a missing provider identity while the pipeline silently
    # executes the global preferred one).
    effective_provider_key, effective_provider_model = self._resolve_effective_provider_contract(
        step="body_translation",
        metadata=meta,
        provider_key=provider_key,
        provider_model=provider_model,
        contributor_mode=contribution_mode == "contributor",
    )

    # Read workflow defaults from metadata and apply as fallbacks. The
    # effective identity for each output-shaping dimension is symmetric with
    # the validity contract: an explicit caller value is authoritative and an
    # explicit ``False`` (``consistency_mode`` / ``json_output``) is preserved
    # — only an omitted value falls back to the workflow default.
    workflow_defaults = meta.get("translation_defaults") if isinstance(meta, dict) else {}
    if not isinstance(workflow_defaults, dict):
        workflow_defaults = {}
    (
        effective_style_preset,
        effective_consistency_mode,
        effective_json_output,
        effective_honorific_policy,
    ) = _resolve_effective_output_policy(
        style_preset=style_preset,
        consistency_mode=consistency_mode,
        json_output=json_output,
        honorific_policy=honorific_policy,
        workflow_defaults=workflow_defaults,
    )

    resolved = resolve_chapter_selection(meta, chapters)
    _chapter_by_id = {record.chapter_id: record for record in resolved}
    selected_numbers = [record.sequence_number for record in resolved]
    selected_chapter_ids = [record.chapter_id for record in resolved]
    normalized_threshold = max(0.0, min(1.0, confidence_threshold))

    # Incremental glossary preflight runs after chapter selection and before
    # the body preflight/pipeline. Approved terms remain authoritative; new
    # ambiguous terms are persisted as pending and excluded from prompts.
    existing_glossary_entries = self.storage.load_glossary(novel_id)
    preexisting_pending = {
        str(entry.get("source"))
        for entry in existing_glossary_entries
        if isinstance(entry, dict) and str(entry.get("status") or "").lower() == "pending"
    }
    from novelai.services.orchestration.glossary import discover_incremental_glossary_terms

    incremental_glossary = await discover_incremental_glossary_terms(
        self,
        novel_id,
        resolved,
        provider_key=effective_provider_key,
        provider_model=effective_provider_model,
        source_language=str(effective_source_language or "Unknown"),
        existing_entries=existing_glossary_entries,
    )
    meta["_incremental_glossary_preflight"] = incremental_glossary
    incremental_pending_terms = incremental_glossary.get("pending", [])
    if isinstance(incremental_pending_terms, list):
        meta["_incremental_pending_terms"] = incremental_pending_terms
    if isinstance(incremental_glossary.get("discovery_state"), dict):
        meta["incremental_glossary_discovery"] = incremental_glossary["discovery_state"]
    if not preexisting_pending:
        meta["_incremental_glossary_preflight"]["pending_only_new_terms"] = True
    glossary = self.storage.load_glossary(novel_id)
    glossary_revision = _resolve_glossary_revision(novel_id, platform_novel_id)

    preflight_issues = self._preflight_translation(
        novel_id=novel_id,
        source_key=source_key,
        meta=meta,
        selected=resolved,
        force=force,
        source_language=effective_source_language,
        target_language=effective_target_language,
        glossary=glossary,
        skip_glossary_gate=skip_glossary_gate,
    )
    if preflight_issues:
        details = "; ".join(f"{issue.code}: {issue.reason}" for issue in preflight_issues)
        raise RuntimeError(f"Translation preflight failed: {details}")

    # Initialize CheckpointManager for segment-level resume (REQ-2)
    from novelai.services.orchestration.translation_resume import _init_checkpoint_manager

    cp_mgr = _init_checkpoint_manager(
        self,
        novel_id=novel_id,
        selected_chapter_ids=selected_chapter_ids,
        force=force,
    )

    # Section 9: link the run to the active raw generation so every
    # translation version can be traced back to its immutable snapshot.
    raw_generation_id = resolve_active_generation_id(self.storage, novel_id) or ""

    # Section 9: hash the glossary through the canonical serializer
    # (normalized source/target/status/locked/notes, sort_keys, JSON).
    glossary_hash = canonical_glossary_hash(glossary)

    # Section 9: resolve the effective prompt template version from
    # :func:`build_translation_request` instead of a hard-coded literal so the
    # manifest records what the pipeline actually used.
    prompt_template_version = _resolve_effective_prompt_version(self, meta)

    qa_policy_fingerprint = _qa_policy_fingerprint(prompt_template_version=prompt_template_version)

    # Blocker D: derive one run id for the entire run and persist a
    # TranslationRunManifest (initial "running" record).  The same id is
    # stamped into pipeline metadata, cache entries, chunk states and
    # translation outputs, so the manifest is hash-linked evidence of the
    # exact inputs, provider, glossary and prompt used for the run.
    translation_run_id = job_id or activity_id or f"translation_run_{uuid4().hex}"
    manifest = TranslationRunManifest(
        translation_run_id=translation_run_id,
        novel_id=novel_id,
        raw_generation_id=raw_generation_id,
        status="running",
        prompt_version=prompt_template_version,
        prompt_template_version=prompt_template_version,
        qa_policy_version=str(getattr(settings, "LLM_QA_POLICY", "") or ""),
        qa_policy_fingerprint=qa_policy_fingerprint,
        glossary_hash=glossary_hash,
        glossary_revision=glossary_revision,
        provider_key=effective_provider_key,
        provider_model=effective_provider_model,
        source_language=effective_source_language,
        target_language=effective_target_language,
        style_preset=effective_style_preset,
        json_output=effective_json_output,
        consistency_mode=effective_consistency_mode,
        requested_chapters=[record.chapter_id for record in resolved],
        expected_count=len(resolved),
    )
    # Initial manifest persistence is best-effort: a missing record must not
    # abort translation. The failure is logged so CI / operators can see
    # that the committed manifest went missing on the initial write.
    manifest_persistence_warnings: list[str] = []
    try:
        self.storage.save_translation_run_manifest(novel_id, manifest)
    except Exception as exc:
        warning = f"initial_manifest_persistence_failed: {type(exc).__name__}: {exc}"
        manifest_persistence_warnings.append(warning)
        logger.warning(
            "Initial translation run manifest persistence failed for %s/%s: %s",
            novel_id,
            translation_run_id,
            exc,
        )

    # Bounded chapter-level concurrency.  Default 1 preserves the previous
    # sequential behavior.  Each chapter is independent (per-chapter lock,
    # per-chapter storage keys, per-chapter DB rows) so they can run in
    # parallel without colliding.  REQ-1.1..REQ-1.4.
    chapter_concurrency = max(1, int(getattr(settings, "TRANSLATION_CHAPTER_CONCURRENCY", 1) or 1))
    chapter_concurrency = min(chapter_concurrency, max(1, len(selected_numbers)) or 1)
    chapter_semaphore = asyncio.Semaphore(chapter_concurrency)

    async def _run_chapter(record: ResolvedChapterSelection) -> dict[str, Any]:
        async with chapter_semaphore:
            chapter = record.metadata if isinstance(record.metadata, dict) else {}
            chapter_id = record.chapter_id
            _chapter_num = record.sequence_number

            # Load raw bundle up-front so the resume gate can validate the
            # existing translation against the *current* effective contract
            # (source text / structure / image hash). Loading twice (once for
            # the gate, once for translation) would be wasteful and would let
            # the bundle change between calls.
            raw_chapter = self.storage.load_chapter(novel_id, chapter_id)
            current_source_structure_hash = ""
            current_source_image_manifest_hash = ""
            if isinstance(raw_chapter, dict):
                current_source_structure_hash = self.storage._hash_text(
                    json.dumps(
                        raw_chapter.get("source_blocks") or [],
                        ensure_ascii=False,
                        sort_keys=True,
                        default=str,
                    )
                )
                current_source_image_manifest_hash = self.storage._hash_text(
                    json.dumps(
                        raw_chapter.get("images") or [],
                        ensure_ascii=False,
                        sort_keys=True,
                        default=str,
                    )
                )
            # Section 4: the effective source is resolved ONCE (reviewed OCR
            # text wins over raw text) and every downstream consumer — resume
            # gate hash, run-manifest chapter hash, delta and full
            # translation, stored source_hash lineage — uses it. Resolving
            # the media overlay here (before the gate) keeps the gate and the
            # translation path on the same source.
            current_raw_text, current_source_text_hash = _resolve_effective_translation_source(
                self.storage,
                novel_id,
                chapter_id,
                raw_chapter,
            )

            # Resume logic (REQ-3.1): skip when previous translation is still
            # valid against the current effective contract, reset FAILED. The
            # DB ``COMPLETE`` state alone is insufficient evidence — a stale
            # source text / glossary / prompt / QA change must retranslate.
            # Bypassed entirely when force=True (REQ-3.4).
            from novelai.services.orchestration.translation_resume import _check_chapter_resume_state

            skip_result = _check_chapter_resume_state(
                self,
                novel_id=novel_id,
                chapter_id=chapter_id,
                force=force,
                source_text_hash=current_source_text_hash,
                effective_glossary_hash=glossary_hash,
                prompt_template_version=prompt_template_version,
                provider_key=effective_provider_key,
                provider_model=effective_provider_model,
                active_raw_generation_id=raw_generation_id or None,
                source_structure_hash=current_source_structure_hash,
                source_image_manifest_hash=current_source_image_manifest_hash,
                qa_policy_fingerprint=qa_policy_fingerprint,
                source_language=effective_source_language,
                target_language=effective_target_language,
                style_preset=effective_style_preset,
                consistency_mode=effective_consistency_mode,
                json_output=effective_json_output,
                honorific_policy=effective_honorific_policy,
            )
            if skip_result is not None:
                return skip_result

            # Per-chapter lock to serialize same-chapter re-entry (REQ-2.1)
            lock = _get_translation_lock(novel_id, chapter_id)
            if lock.locked():
                raise TranslationInProgressError(f"Translation is already in progress for {novel_id}/{chapter_id}")
            await lock.acquire()

            _update_db_translation_state(novel_id, chapter_id, TranslationState.FETCHING)

            from novelai.services.orchestration.translation_resume import _restore_checkpoint_for_chapter

            prev_state, _checkpoint_restored = _restore_checkpoint_for_chapter(
                self,
                novel_id=novel_id,
                chapter_id=chapter_id,
            )

            try:
                # Section 4: effective source resolved above (before the
                # resume gate); the same text feeds the manifest hash, delta
                # and full translation, and the stored source_hash lineage.
                raw_text = current_raw_text
                raw_images: list[dict[str, Any]] | None = None
                if isinstance(raw_chapter, dict):
                    raw_images = raw_chapter.get("images") if isinstance(raw_chapter.get("images"), list) else None
                if raw_text is not None and raw_text.strip():
                    manifest.chapter_source_hashes[chapter_id] = hash_text(raw_text)
                chapter_url = str(
                    chapter.get("url") or (raw_chapter or {}).get("source_url") or f"import://{novel_id}/{chapter_id}"
                )
                delta_fallback_reason: str | None = None
                delta_result: dict[str, Any] | None = None
                if raw_text is not None and not force:
                    delta_result = await _try_delta_translate_chapter(
                        self,
                        source=source,
                        source_key=source_key,
                        novel_id=novel_id,
                        chapter_id=chapter_id,
                        chapter_url=chapter_url,
                        raw_text=raw_text,
                        provider_key=effective_provider_key,
                        provider_model=effective_provider_model,
                        platform_novel_id=platform_novel_id,
                        source_language=effective_source_language,
                        target_language=effective_target_language,
                        glossary=glossary,
                        style_preset=effective_style_preset,
                        consistency_mode=effective_consistency_mode,
                        translation_run_id=translation_run_id,
                        job_id=job_id,
                        activity_id=activity_id,
                        allow_cross_provider_fallback=allow_cross_provider_fallback,
                        json_output=effective_json_output,
                        honorific_policy=effective_honorific_policy,
                        active_raw_generation_id=raw_generation_id or None,
                        glossary_hash=glossary_hash,
                        prompt_template_version=prompt_template_version,
                        qa_policy_fingerprint=qa_policy_fingerprint,
                        source_structure_hash=current_source_structure_hash or None,
                        source_image_manifest_hash=current_source_image_manifest_hash or None,
                    )
                    if delta_result.get("applied"):
                        if delta_result.get("mode") == "whole_chapter_unchanged":
                            # Section 6: whole-chapter reuse is a TRUE no-op.
                            # No new version is persisted: the stored version's
                            # version_id / translation_run_id / provider /
                            # model / created_at stay untouched, so reuse can
                            # never create false producer lineage. The DB state
                            # was flipped to FETCHING above; restore COMPLETE
                            # and record the reuse (the run manifest carries
                            # it via the summary finalize below).
                            _update_db_translation_state(novel_id, chapter_id, TranslationState.COMPLETE)
                            cp_mgr.delete(chapter_id)
                            return {
                                "chapter_id": chapter_id,
                                "status": "reused",
                                "reason": "whole_chapter_unchanged",
                                "version_id": delta_result.get("version_id"),
                                "translation_run_id": delta_result.get("translation_run_id"),
                                "created_at": delta_result.get("created_at"),
                                "provider_key": delta_result.get("provider_key"),
                                "provider_model": delta_result.get("provider_model"),
                            }
                        translated = str(delta_result.get("text") or "")
                        confidence_score = self._score_translation_confidence(raw_text or "", translated)
                        polish_needed = mark_polish_needed and confidence_score < normalized_threshold
                        auto_activate = (
                            confidence_score is None
                            or confidence_score >= settings.TRANSLATION_LOW_CONFIDENCE_ACTIVATION_THRESHOLD
                        )
                        self.storage.save_translated_chapter(
                            novel_id,
                            chapter_id,
                            translated,
                            provider_key=delta_result.get("provider_key")
                            if isinstance(delta_result.get("provider_key"), str)
                            else effective_provider_key,
                            provider_model=delta_result.get("provider_model")
                            if isinstance(delta_result.get("provider_model"), str)
                            else effective_provider_model,
                            confidence_score=confidence_score,
                            polish_needed=polish_needed,
                            confidence_details={
                                "threshold": normalized_threshold,
                                "source_length": len((raw_text or "").strip()),
                                "translated_length": len(translated.strip()),
                                "style_preset": effective_style_preset,
                                "delta": dict(delta_result.get("provenance") or {}),
                            },
                            glossary_revision=glossary_revision,
                            glossary_injected_term_count=0,
                            auto_activate=auto_activate,
                            **_translation_lineage_kwargs(
                                self.storage,
                                novel_id,
                                chapter_id,
                                raw_text=raw_text or "",
                                translated=translated,
                                translation_run_id=translation_run_id,
                                raw_generation_id=raw_generation_id,
                                source_language=effective_source_language,
                                target_language=effective_target_language,
                                style_preset=effective_style_preset,
                                consistency_mode=effective_consistency_mode,
                                json_output=effective_json_output,
                                qa_policy_fingerprint=qa_policy_fingerprint,
                                auto_activate=auto_activate,
                                honorific_policy=effective_honorific_policy,
                                source_episode_id=record.source_episode_id or chapter_id,
                                glossary_hash=glossary_hash,
                                prompt_template_version=prompt_template_version,
                            ),
                        )
                        safely_refresh_catalog_projection_after_storage_write(
                            novel_id,
                            self.storage,
                            context="translate_delta",
                        )
                        # Invalidate library summary cache after successful storage write
                        best_effort_invalidate(context="translate_delta")
                        self.storage.save_chapter_state(
                            novel_id,
                            chapter_id,
                            _make_state_data(ChapterState.TRANSLATED, previous=prev_state),
                        )
                        self.storage.create_checkpoint(novel_id, chapter_id, "translated")
                        _update_db_translation_state(novel_id, chapter_id, TranslationState.COMPLETE)
                        cp_mgr.save(
                            Checkpoint(
                                chapter_id=chapter_id,
                                state=TranslationState.COMPLETE,
                                completed_stages=["delta_translate"],
                                segments_completed=1,
                                segments_total=1,
                            )
                        )
                        cp_mgr.delete(chapter_id)
                        return {"chapter_id": chapter_id, "status": "succeeded"}
                    delta_fallback_reason = str(delta_result.get("fallback_reason") or "unsafe_delta")
                    fresh_full_required = bool(delta_result.get("fresh_full_required"))
                elif force:
                    delta_fallback_reason = "force_full_translation"
                    fresh_full_required = True
                else:
                    fresh_full_required = False

                # Update DB state + write checkpoint before full pipeline (REQ-1.4, REQ-2.3)
                _update_db_translation_state(novel_id, chapter_id, TranslationState.TRANSLATING)
                cp_mgr.save(
                    Checkpoint(
                        chapter_id=chapter_id,
                        state=TranslationState.TRANSLATING,
                        current_stage="translate",
                    )
                )

                result = await self.translation.translate_chapter(
                    source_adapter=source,
                    chapter_url=chapter_url,
                    translation_run_id=translation_run_id,
                    job_id=job_id,
                    activity_id=activity_id,
                    novel_id=novel_id,
                    chapter_id=chapter_id,
                    source_key=source_key,
                    provider_key=effective_provider_key,
                    provider_model=effective_provider_model,
                    platform_novel_id=platform_novel_id,
                    source_language=effective_source_language,
                    target_language=effective_target_language,
                    glossary=glossary,
                    style_preset=effective_style_preset,
                    consistency_mode=effective_consistency_mode,
                    honorific_policy=effective_honorific_policy,
                    json_output=effective_json_output,
                    allow_cross_provider_fallback=allow_cross_provider_fallback,
                    force_retranslate=force or fresh_full_required,
                    glossary_revision=glossary_revision,
                    raw_text=raw_text,
                    raw_images=raw_images,
                    contribution_mode=contribution_mode,
                    requesting_user_id=requesting_user_id,
                )
                translated = result.final_text
                glossary_injected_term_count = int(result.metadata.get("glossary_injected_term_count", 0) or 0)
                confidence_score = self._score_translation_confidence(raw_text or "", translated)
                polish_needed = mark_polish_needed and confidence_score < normalized_threshold
                auto_activate = (
                    confidence_score is None
                    or confidence_score >= settings.TRANSLATION_LOW_CONFIDENCE_ACTIVATION_THRESHOLD
                )
                scheduler_policy = (
                    result.scheduler_state.get("policy") if isinstance(result.scheduler_state, dict) else None
                )
                # Stored identity is the EFFECTIVE REQUESTED CONTRACT identity the
                # output was requested under — never the pipeline result's report.
                # The production service builds the result from the request, so
                # the two agree; a broken or divergent result must not poison
                # stored lineage, because future reuse decisions compare the
                # stored identity against the current contract. Per-chunk actual
                # execution identity (scheduler model fallbacks) is recorded in
                # chunk_states, not in the version identity.
                if (
                    isinstance(result.provider_key, str)
                    and result.provider_key
                    and result.provider_key != effective_provider_key
                ) or (
                    isinstance(result.provider_model, str)
                    and result.provider_model
                    and result.provider_model != effective_provider_model
                ):
                    logger.warning(
                        "Provider identity divergence for %s/%s: requested %s/%s but result reported %s/%s; "
                        "storing the effective (requested) identity",
                        novel_id,
                        chapter_id,
                        effective_provider_key,
                        effective_provider_model,
                        result.provider_key,
                        result.provider_model,
                    )
                self.storage.save_translated_chapter(
                    novel_id,
                    chapter_id,
                    translated,
                    provider_key=effective_provider_key,
                    provider_model=effective_provider_model,
                    confidence_score=confidence_score,
                    polish_needed=polish_needed,
                    confidence_details={
                        "threshold": normalized_threshold,
                        "source_length": len((raw_text or "").strip()),
                        "translated_length": len(translated.strip()),
                        "style_preset": effective_style_preset,
                        "scheduler_policy": scheduler_policy,
                        "delta": {
                            "delta_retranslation": False,
                            "mode": "full",
                            "fallback_reason": delta_fallback_reason,
                        }
                        if delta_fallback_reason
                        else None,
                    },
                    glossary_revision=glossary_revision,
                    glossary_injected_term_count=glossary_injected_term_count,
                    auto_activate=auto_activate,
                    **_translation_lineage_kwargs(
                        self.storage,
                        novel_id,
                        chapter_id,
                        raw_text=raw_text or "",
                        translated=translated,
                        translation_run_id=translation_run_id,
                        raw_generation_id=raw_generation_id,
                        source_language=effective_source_language,
                        target_language=effective_target_language,
                        style_preset=effective_style_preset,
                        consistency_mode=effective_consistency_mode,
                        json_output=effective_json_output,
                        qa_policy_fingerprint=qa_policy_fingerprint,
                        auto_activate=auto_activate,
                        honorific_policy=effective_honorific_policy,
                        source_episode_id=record.source_episode_id or chapter_id,
                        glossary_hash=glossary_hash,
                        prompt_template_version=prompt_template_version,
                    ),
                )
                safely_refresh_catalog_projection_after_storage_write(
                    novel_id,
                    self.storage,
                    context="translate_full",
                )
                # Invalidate library summary cache after successful storage write
                best_effort_invalidate()
                self.storage.save_chapter_state(
                    novel_id,
                    chapter_id,
                    _make_state_data(ChapterState.TRANSLATED, previous=prev_state),
                )
                self.storage.append_pipeline_events(result.pipeline_events)
                for chunk_state in result.chunk_states.values():
                    self.storage.upsert_chunk_state(chunk_state)
                manifest.chunk_outputs.update(
                    _persist_chunk_qa_results_to_outputs(self.storage, novel_id, result.chunk_states)
                )
                self.storage.create_checkpoint(novel_id, chapter_id, "translated")
                # Mark COMPLETE in DB + write CheckpointManager checkpoint (REQ-2.3, REQ-3.1)
                _update_db_translation_state(novel_id, chapter_id, TranslationState.COMPLETE)
                n_segments = len(result.chunk_states)
                cp_mgr.save(
                    Checkpoint(
                        chapter_id=chapter_id,
                        state=TranslationState.COMPLETE,
                        completed_stages=["fetch", "parse", "segment", "translate", "qa", "post_process"],
                        segments_completed=n_segments,
                        segments_total=n_segments,
                    )
                )
                cp_mgr.delete(chapter_id)
                return {"chapter_id": chapter_id, "status": "succeeded"}
            except Exception as exc:
                logger.error("Failed to translate chapter %s/%s: %s", novel_id, chapter_id, exc)
                failure = getattr(exc, "original", exc)
                provider_code = getattr(getattr(failure, "provider_error_code", None), "value", None)
                qa_status = getattr(failure, "qa_status", None)
                paused_reason = getattr(failure, "paused_reason", None)
                if isinstance(paused_reason, str) and paused_reason.strip():
                    failed_state = ChapterState.TRANSLATED_PARTIAL
                elif qa_status == ChapterState.QA_FAILED.value:
                    failed_state = ChapterState.QA_FAILED
                elif qa_status == ChapterState.NEEDS_REVIEW.value:
                    failed_state = ChapterState.NEEDS_REVIEW
                else:
                    failed_state = ChapterState.NEEDS_RETRY if isinstance(provider_code, str) else ChapterState.FAILED
                self.storage.save_chapter_state(
                    novel_id,
                    chapter_id,
                    _make_state_data(failed_state, error=str(exc), previous=prev_state),
                )
                details = getattr(failure, "details", None)
                failed_chunk_id = details.get("chunk_id") if isinstance(details, dict) else None
                error_code = provider_code or getattr(failure, "error_code", None) or failure.__class__.__name__
                failed_context = _pipeline_context_from_exception(exc)
                failed_events = _pipeline_events_from_exception(exc)
                if failed_events:
                    self.storage.append_pipeline_events(failed_events)
                failed_event_recorded = any(event.get("status_after") == "failed" for event in failed_events)
                chunk_states = getattr(failed_context, "chunk_states", None)
                if isinstance(chunk_states, dict):
                    for chunk_state in chunk_states.values():
                        if isinstance(chunk_state, dict):
                            self.storage.upsert_chunk_state(chunk_state)
                    manifest.chunk_outputs.update(
                        _persist_chunk_qa_results_to_outputs(self.storage, novel_id, chunk_states)
                    )
                if isinstance(failed_chunk_id, str) and failed_chunk_id.strip():
                    self.storage.upsert_chunk_state(
                        {
                            "chunk_id": failed_chunk_id,
                            "novel_id": novel_id,
                            "chapter_ids": [chapter_id],
                            "provider_key": getattr(failure, "provider_key", effective_provider_key),
                            "provider_model": getattr(failure, "provider_model", effective_provider_model),
                            "attempt_number": details.get("attempt_number", 1) if isinstance(details, dict) else 1,
                            "status": failed_state.value,
                            "error_code": str(error_code),
                        }
                    )
                if not failed_event_recorded:
                    self.storage.append_pipeline_event(
                        {
                            "job_id": job_id,
                            "activity_id": activity_id,
                            "novel_id": novel_id,
                            "chapter_id": chapter_id,
                            "source_key": source_key,
                            "provider_key": getattr(failure, "provider_key", effective_provider_key),
                            "provider_model": getattr(failure, "provider_model", effective_provider_model),
                            "chunk_id": failed_chunk_id,
                            "stage_name": _failed_stage_name_from_exception(exc),
                            "status_before": "running",
                            "status_after": failed_state.value,
                            "error_code": str(error_code),
                            "message": str(exc),
                        }
                    )
                self.storage.create_checkpoint(novel_id, chapter_id, "failed")
                _update_db_translation_state(novel_id, chapter_id, TranslationState.FAILED, error=str(exc))
                cp_mgr.save(
                    Checkpoint(
                        chapter_id=chapter_id,
                        state=TranslationState.FAILED,
                        error=str(exc)[:1024],
                    )
                )
                raise
            finally:
                lock.release()

    # Schedule all chapter tasks with bounded concurrency.  Each task is
    # independent (different chapter_id, different storage keys, different
    # DB rows).  Exceptions are captured via return_exceptions=True so a
    # single chapter failure does not abort the rest of the run.
    tasks = [asyncio.create_task(_run_chapter(record)) for record in resolved]
    task_results = await asyncio.gather(*tasks, return_exceptions=True)

    # Aggregate per-chapter progress in source order.  REQ-3.3.

    summary, first_error = _build_chapter_summary(
        resolved=resolved,
        task_results=task_results,
        chapters=chapters,
        force=force,
        target_language=effective_target_language,
    )

    # Finalize the run manifest (Blocker D): succeeded chapter ids in source
    # order, final counts, commit timestamp, and final status.  Best-effort
    # so manifest storage failure never fails the translation run itself.
    review_count = 0
    succeeded_chapter_ids: list[str] = []
    reused_chapter_ids: list[str] = []
    ordered_ids = [record.chapter_id for record in resolved]
    for chapter_id in ordered_ids:
        entry = summary["chapter_progress"].get(chapter_id)
        if not isinstance(entry, dict):
            continue
        status = str(entry.get("status") or "")
        if status == "succeeded":
            succeeded_chapter_ids.append(chapter_id)
        elif status == "reused":
            # Section 6: whole-chapter reuse no-ops are recorded explicitly so
            # the manifest distinguishes reused output from newly generated,
            # skipped, or failed chapters.
            reused_chapter_ids.append(chapter_id)
        elif status == "requires_review" or entry.get("needs_review"):
            review_count += 1

    manifest.chapter_ids = succeeded_chapter_ids
    manifest.completed_count = int(summary.get("succeeded") or 0)
    manifest.skipped_count = int(summary.get("skipped") or 0)
    manifest.failed_count = int(summary.get("failed") or 0)
    manifest.reused_chapter_ids = reused_chapter_ids
    manifest.reused_count = len(reused_chapter_ids)
    manifest.review_count = review_count
    manifest.status = "failed" if first_error is not None else "completed"
    manifest.committed_at = datetime.now(UTC).isoformat().replace("+00:00", "Z")
    # Section 9 surfaces persistence errors instead of swallowing them so
    # CI and operators can see when the final committed manifest goes
    # missing; running translation still tolerates a manifest write
    # failure because the per-chapter storage writes already happened.
    try:
        self.storage.save_translation_run_manifest(novel_id, manifest)
    except Exception as exc:
        warning = f"final_manifest_persistence_failed: {type(exc).__name__}: {exc}"
        manifest_persistence_warnings.append(warning)
        logger.warning("Translation run manifest persistence failed for %s/%s: %s", novel_id, translation_run_id, exc)
    summary["translation_run_id"] = translation_run_id
    if manifest_persistence_warnings:
        summary["manifest_persistence_warnings"] = manifest_persistence_warnings
    if first_error is not None:
        # Attach progress so the activity worker can surface a partial-failure
        # summary (REQ-3.3) while still propagating the underlying error so
        # existing failure routing is preserved.
        first_error.chapter_progress = summary["chapter_progress"]  # type: ignore[attr-defined]
        first_error.chapter_summary = summary  # type: ignore[attr-defined]
        raise first_error
    return summary


async def retranslate_chapter(
    self: Any,
    source_key: str,
    novel_id: str,
    chapter_id: str,
    provider_key: str | None = None,
    provider_model: str | None = None,
    source_language: str | None = None,
    target_language: str | None = None,
    glossary: Any | None = None,
    style_preset: str | None = None,
    consistency_mode: bool = False,
    json_output: bool = False,
    allow_cross_provider_fallback: bool = True,
) -> None:
    """Force retranslation for a single chapter using chapter-scoped selection.

    Section 2: ``chapter_id`` is the stable logical identifier (numeric or
    ``kakuyomu:<episode>``). Validation only ensures the id is non-empty;
    resolution to a chapter must rely on the current source index.
    """
    normalized_chapter_id = str(chapter_id).strip()
    if not normalized_chapter_id:
        raise ValueError("chapter_id must be a non-empty identifier.")

    meta = self.storage.load_metadata(novel_id)
    if not meta:
        raise RuntimeError("Metadata not found; run scrape-metadata first.")
    resolved = resolve_chapter_selection(meta, normalized_chapter_id)
    if not resolved:
        raise ValueError(f"chapter_id {normalized_chapter_id!r} does not match any chapter in the current index.")

    await self.translate_chapters(
        source_key=source_key,
        novel_id=novel_id,
        chapters=normalized_chapter_id,
        provider_key=provider_key,
        provider_model=provider_model,
        force=True,
        source_language=source_language,
        target_language=target_language,
        glossary=glossary,
        style_preset=style_preset,
        consistency_mode=consistency_mode,
        json_output=json_output,
        allow_cross_provider_fallback=allow_cross_provider_fallback,
    )
