"""Translation orchestration — core functions + re-exports.

This module holds the core orchestration functions:
- DB state helpers, exception helpers, platform/glossary resolution
- Preflight checks, polish phase, phased pipeline
- Main ``translate_chapters`` and ``retranslate_chapter``

Metadata translation and request estimation are in ``translation_metadata.py``.
Paragraph lineage and delta retranslation are in ``translation_lineage.py``.
Both are re-exported here for backward compatibility.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
from typing import Any

from novelai.config.settings import settings
from novelai.core.chapter_state import ChapterState, TranslationState
from novelai.core.errors import TranslationInProgressError
from novelai.db.engine import session_scope
from novelai.db.models.chapter import Chapter
from novelai.db.models.novel import Novel
from novelai.glossary import glossary_status_counts, normalize_glossary_entries
from novelai.services.catalog_service import safely_refresh_catalog_projection_after_storage_write
from novelai.services.library_summary_service import invalidate_library_summary_cache
from novelai.services.orchestration.common import PreflightIssue, _make_state_data
from novelai.services.pipeline.checkpoint import Checkpoint
from novelai.sources.base import SourceAdapter

logger = logging.getLogger(__name__)

# Per-chapter lock to prevent concurrent translation of the same chapter
_translation_locks: dict[str, asyncio.Lock] = {}


def _get_translation_lock(novel_id: str, chapter_id: str) -> asyncio.Lock:
    key = f"{novel_id}:{chapter_id}"
    if key not in _translation_locks:
        _translation_locks[key] = asyncio.Lock()
    return _translation_locks[key]


def _update_db_translation_state(
    novel_id: str,
    chapter_id: str,
    state: TranslationState,
    error: str | None = None,
) -> None:
    """Update ``translation_state`` and ``translation_error`` on Chapter row.

    REQ-1.4: State must be updated before/after each pipeline stage.
    """
    try:
        with session_scope() as session:
            novel = session.query(Novel).filter_by(slug=novel_id).one_or_none()
            if novel is None:
                return
            chapter_num = int(chapter_id) if chapter_id.isdigit() else -1
            row = (
                session.query(Chapter)
                .filter(
                    Chapter.novel_id == novel.id,
                    Chapter.chapter_number == chapter_num,
                )
                .one_or_none()
            )
            if row is not None:
                row.translation_state = state.value  # type: ignore[assignment]
                if error is not None:
                    row.translation_error = error[:1024] if len(error) > 1024 else error
                session.commit()
    except Exception:
        logger.warning("Failed to update DB translation state %s/%s", novel_id, chapter_id, exc_info=True)


def _load_db_translation_state(novel_id: str, chapter_id: str) -> str:
    """Read ``translation_state`` from the Chapter row (REQ-3.1)."""
    try:
        with session_scope() as session:
            novel = session.query(Novel).filter_by(slug=novel_id).one_or_none()
            if novel is None:
                return TranslationState.PENDING.value
            chapter_num = int(chapter_id) if chapter_id.isdigit() else -1
            row = (
                session.query(Chapter.translation_state)
                .filter(
                    Chapter.novel_id == novel.id,
                    Chapter.chapter_number == chapter_num,
                )
                .one_or_none()
            )
            if row is not None:
                return row[0] or TranslationState.PENDING.value
    except Exception:
        logger.warning("Failed to load DB translation state %s/%s", novel_id, chapter_id, exc_info=True)
    return TranslationState.PENDING.value


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


def _persist_chunk_qa_results_to_outputs(storage: Any, novel_id: str, chunk_states: dict[str, Any]) -> None:
    if not isinstance(novel_id, str) or not novel_id.strip():
        return
    for chunk_id, state in chunk_states.items():
        if not isinstance(chunk_id, str) or not chunk_id.strip() or not isinstance(state, dict):
            continue
        outputs = storage.read_translation_output(
            novel_id,
            chunk_id=chunk_id,
            translation_run_id=state.get("translation_run_id") if isinstance(state.get("translation_run_id"), str) else None,
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


def _preflight_translation(
    self: Any,
    *,
    novel_id: str,
    source_key: str,
    meta: dict[str, Any],
    selected_numbers: list[int],
    force: bool,
    source_language: str | None,
    target_language: str | None,
    glossary: Any | None,
    skip_glossary_gate: bool = False,
) -> list[PreflightIssue]:

    issues: list[PreflightIssue] = []

    if not selected_numbers:
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
                reason=(
                    f"Novel onboarding is {onboarding_status!r}; "
                    "complete chapter scraping before translation."
                ),
                details={"onboarding_status": onboarding_status},
            )
        )

    chapter_map = {
        int(chapter["id"]): chapter
        for chapter in meta.get("chapters", [])
        if isinstance(chapter, dict) and str(chapter.get("id", "")).isdigit()
    }

    missing_chapters = [number for number in selected_numbers if number not in chapter_map]
    if missing_chapters:
        issues.append(
            PreflightIssue(
                code="metadata_mismatch",
                reason=(
                    "Selected chapters are missing from metadata: "
                    + ", ".join(str(number) for number in missing_chapters)
                ),
            )
        )

    unresolved_urls: list[int] = []
    for number in selected_numbers:
        chapter = chapter_map.get(number)
        if chapter is None:
            continue
        chapter_id = str(number)
        raw_chapter = self.storage.load_chapter(novel_id, chapter_id)
        if chapter.get("url") or (raw_chapter and isinstance(raw_chapter.get("text"), str)):
            continue
        unresolved_urls.append(number)
    if unresolved_urls:
        issues.append(
            PreflightIssue(
                code="missing_chapter_url",
                reason=(
                    "Some selected chapters have no source URL: "
                    + ", ".join(str(number) for number in unresolved_urls)
                ),
            )
        )

    effective_source_language = source_language or self._infer_source_language(source_key, meta)
    if not effective_source_language:
        for number in selected_numbers:
            raw_chapter = self.storage.load_chapter(novel_id, str(number))
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
                reason=(
                    "Source language is unknown. Provide source_language explicitly or include it in metadata."
                ),
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

    pending_terms = [entry.source for entry in normalized_glossary if entry.status == "pending"]
    if pending_terms:
        preview = ", ".join(pending_terms[:5])
        if len(pending_terms) > 5:
            preview += f", +{len(pending_terms) - 5} more"
        issues.append(
            PreflightIssue(
                code="pending_glossary_terms",
                reason=(
                    "Review glossary terms before translation. "
                    f"Pending terms: {preview}."
                ),
            )
        )

    # --- Glossary gate ---
    if not skip_glossary_gate:
        _novel_is_pending = False
        with session_scope() as session:
            _novel = session.query(Novel).filter_by(slug=novel_id).one_or_none()
            if _novel is not None:
                _novel_is_pending = _novel.glossary_status == "glossary_pending"
        if _novel_is_pending:
            pending_count = _count_pending_glossary_entries(novel_id)
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
    for number in selected_numbers:
        chapter_id = str(number)
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
        for number in selected_numbers:
            if number not in chapter_map:
                continue
            chapter_id = str(number)
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
    profile_provider, profile_model = self._resolve_workflow_profile("polish", meta)
    effective_provider = provider_key or profile_provider
    effective_model = provider_model or profile_model

    chapter_map = {
        int(chapter["id"]): chapter
        for chapter in meta.get("chapters", [])
        if isinstance(chapter, dict) and str(chapter.get("id", "")).isdigit()
    }
    selected_numbers = self._selected_chapter_numbers(meta, chapters)
    low_confidence_ids: list[str] = []
    normalized_threshold = max(0.0, min(1.0, confidence_threshold))

    for number in selected_numbers:
        chapter_id = str(number)
        if number not in chapter_map:
            continue
        raw = self.storage.load_chapter(novel_id, chapter_id) or {}
        translated = self.storage.load_translated_chapter(novel_id, chapter_id) or {}

        raw_text = raw.get("text")
        translated_raw_text = translated.get("text")
        source_text = raw_text if isinstance(raw_text, str) else ""
        translated_text = translated_raw_text if isinstance(translated_raw_text, str) else ""
        stored_score = translated.get("confidence_score") if isinstance(translated.get("confidence_score"), float) else None
        polish_needed_flag = translated.get("polish_needed") if isinstance(translated.get("polish_needed"), bool) else None

        if low_confidence_only and isinstance(polish_needed_flag, bool):
            if polish_needed_flag:
                low_confidence_ids.append(chapter_id)
            continue

        confidence_score = stored_score if isinstance(stored_score, float) else self._score_translation_confidence(source_text, translated_text)

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
        if isinstance(entry, dict) and str(entry.get("status") or "pending").strip().lower() in {"approved", "translated"}
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
    consistency_mode: bool = False,
    json_output: bool = False,
    allow_cross_provider_fallback: bool = True,
    skip_glossary_gate: bool = False,
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
    profile_provider, profile_model = self._resolve_workflow_profile("body_translation", meta)
    effective_provider_key = provider_key or profile_provider
    effective_provider_model = provider_model or profile_model

    # Read workflow defaults from metadata and apply as fallbacks.
    workflow_defaults = meta.get("translation_defaults") if isinstance(meta, dict) else {}
    if not isinstance(workflow_defaults, dict):
        workflow_defaults = {}
    effective_style_preset = style_preset if style_preset is not None else workflow_defaults.get("style_preset")
    effective_consistency_mode = consistency_mode if consistency_mode else bool(workflow_defaults.get("consistency_mode", False))
    effective_honorific_policy = workflow_defaults.get("honorific_policy")

    # Auto-load stored glossary when none was explicitly provided.
    if glossary is None:
        stored_entries = self.storage.load_glossary(novel_id)
        if stored_entries:
            glossary = stored_entries

    chapter_map = {int(c["id"]): c for c in meta.get("chapters", [])}
    selected_numbers = self._selected_chapter_numbers(meta, chapters)
    normalized_threshold = max(0.0, min(1.0, confidence_threshold))

    preflight_issues = self._preflight_translation(
        novel_id=novel_id,
        source_key=source_key,
        meta=meta,
        selected_numbers=selected_numbers,
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

    cp_mgr = _init_checkpoint_manager(
        self,
        novel_id=novel_id,
        selected_numbers=selected_numbers,
        force=force,
    )

    # Bounded chapter-level concurrency.  Default 1 preserves the previous
    # sequential behavior.  Each chapter is independent (per-chapter lock,
    # per-chapter storage keys, per-chapter DB rows) so they can run in
    # parallel without colliding.  REQ-1.1..REQ-1.4.
    chapter_concurrency = max(1, int(getattr(settings, "TRANSLATION_CHAPTER_CONCURRENCY", 1) or 1))
    chapter_concurrency = min(chapter_concurrency, max(1, len(selected_numbers)) or 1)
    chapter_semaphore = asyncio.Semaphore(chapter_concurrency)

    async def _run_chapter(chapter_num: int) -> dict[str, str]:
        async with chapter_semaphore:
            chapter = chapter_map.get(chapter_num)
            if not chapter:
                return {"chapter_id": str(chapter_num), "status": "skipped", "reason": "missing_metadata"}

            chapter_id = str(chapter_num)

            # Resume logic (REQ-3.1): skip COMPLETE, reset FAILED - bypassed when force=True (REQ-3.4)
            from novelai.services.orchestration.translation_resume import _check_chapter_resume_state

            skip_result = _check_chapter_resume_state(
                self,
                novel_id=novel_id,
                chapter_id=chapter_id,
                force=force,
            )
            if skip_result is not None:
                return skip_result

            # Per-chapter lock to serialize same-chapter re-entry (REQ-2.1)
            lock = _get_translation_lock(novel_id, chapter_id)
            if lock.locked():
                raise TranslationInProgressError(
                    f"Translation is already in progress for {novel_id}/{chapter_id}"
                )
            await lock.acquire()

            _update_db_translation_state(novel_id, chapter_id, TranslationState.FETCHING)

            from novelai.services.orchestration.translation_resume import _restore_checkpoint_for_chapter

            prev_state, _checkpoint_restored = _restore_checkpoint_for_chapter(
                self,
                novel_id=novel_id,
                chapter_id=chapter_id,
            )

            try:
                raw_chapter = self.storage.load_chapter(novel_id, chapter_id)
                media_state = self.storage.load_chapter_media_state(novel_id, chapter_id) or {}
                raw_text = None
                raw_images: list[dict[str, Any]] | None = None
                if raw_chapter is not None:
                    reviewed_ocr_text = media_state.get("ocr_text")
                    if (
                        bool(media_state.get("ocr_required", False))
                        and str(media_state.get("ocr_status") or "").strip().lower() == "reviewed"
                        and isinstance(reviewed_ocr_text, str)
                        and reviewed_ocr_text.strip()
                    ):
                        raw_text = reviewed_ocr_text
                    else:
                        raw_text = raw_chapter.get("text") if isinstance(raw_chapter.get("text"), str) else None
                    raw_images = raw_chapter.get("images") if isinstance(raw_chapter.get("images"), list) else None
                chapter_url = str(chapter.get("url") or (raw_chapter or {}).get("source_url") or f"import://{novel_id}/{chapter_id}")
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
                        job_id=job_id,
                        activity_id=activity_id,
                        allow_cross_provider_fallback=allow_cross_provider_fallback,
                    )
                    if delta_result.get("applied"):
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
                            provider=delta_result.get("provider") if isinstance(delta_result.get("provider"), str) else effective_provider_key,
                            model=delta_result.get("model") if isinstance(delta_result.get("model"), str) else effective_provider_model,
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
                        )
                        safely_refresh_catalog_projection_after_storage_write(
                            novel_id,
                            self.storage,
                            context="translate_delta",
                        )
                        # Invalidate library summary cache after successful storage write
                        try:
                            invalidate_library_summary_cache()
                        except Exception:
                            logger.debug("Library summary cache invalidation failed (non-fatal)", exc_info=True)
                        self.storage.save_chapter_state(
                            novel_id,
                            chapter_id,
                            _make_state_data(ChapterState.TRANSLATED, previous=prev_state),
                        )
                        self.storage.create_checkpoint(novel_id, chapter_id, "translated")
                        _update_db_translation_state(novel_id, chapter_id, TranslationState.COMPLETE)
                        cp_mgr.save(Checkpoint(
                            chapter_id=chapter_id,
                            state=TranslationState.COMPLETE,
                            completed_stages=["delta_translate"],
                            segments_completed=1,
                            segments_total=1,
                        ))
                        cp_mgr.delete(chapter_id)
                        return {"chapter_id": chapter_id, "status": "succeeded"}
                    delta_fallback_reason = str(delta_result.get("fallback_reason") or "unsafe_delta")
                elif force:
                    delta_fallback_reason = "force_full_translation"

                # Update DB state + write checkpoint before full pipeline (REQ-1.4, REQ-2.3)
                _update_db_translation_state(novel_id, chapter_id, TranslationState.TRANSLATING)
                cp_mgr.save(Checkpoint(
                    chapter_id=chapter_id,
                    state=TranslationState.TRANSLATING,
                    current_stage="translate",
                ))

                result = await self.translation.translate_chapter(
                    source_adapter=source,
                    chapter_url=chapter_url,
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
                    json_output=json_output,
                    allow_cross_provider_fallback=allow_cross_provider_fallback,
                    force_retranslate=force,
                    glossary_revision=glossary_revision,
                    raw_text=raw_text,
                    raw_images=raw_images,
                )
                translated = result.final_text
                glossary_injected_term_count = int(result.metadata.get("glossary_injected_term_count", 0) or 0)
                confidence_score = self._score_translation_confidence(raw_text or "", translated)
                polish_needed = mark_polish_needed and confidence_score < normalized_threshold
                auto_activate = (
                    confidence_score is None
                    or confidence_score >= settings.TRANSLATION_LOW_CONFIDENCE_ACTIVATION_THRESHOLD
                )
                scheduler_policy = result.scheduler_state.get("policy") if isinstance(result.scheduler_state, dict) else None
                self.storage.save_translated_chapter(
                    novel_id,
                    chapter_id,
                    translated,
                    provider=result.provider_key,
                    model=result.provider_model,
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
                        } if delta_fallback_reason else None,
                    },
                    glossary_revision=glossary_revision,
                    glossary_injected_term_count=glossary_injected_term_count,
                    auto_activate=auto_activate,
                )
                safely_refresh_catalog_projection_after_storage_write(
                    novel_id,
                    self.storage,
                    context="translate_full",
                )
                # Invalidate library summary cache after successful storage write
                try:
                    invalidate_library_summary_cache()
                except Exception:
                    logger.debug("Library summary cache invalidation failed (non-fatal)", exc_info=True)
                self.storage.save_chapter_state(
                    novel_id, chapter_id,
                    _make_state_data(ChapterState.TRANSLATED, previous=prev_state),
                )
                self.storage.append_pipeline_events(result.pipeline_events)
                for chunk_state in result.chunk_states.values():
                    self.storage.upsert_chunk_state(chunk_state)
                _persist_chunk_qa_results_to_outputs(self.storage, novel_id, result.chunk_states)
                self.storage.create_checkpoint(novel_id, chapter_id, "translated")
                # Mark COMPLETE in DB + write CheckpointManager checkpoint (REQ-2.3, REQ-3.1)
                _update_db_translation_state(novel_id, chapter_id, TranslationState.COMPLETE)
                n_segments = len(result.chunk_states)
                cp_mgr.save(Checkpoint(
                    chapter_id=chapter_id,
                    state=TranslationState.COMPLETE,
                    completed_stages=["fetch", "parse", "segment", "translate", "qa", "post_process"],
                    segments_completed=n_segments,
                    segments_total=n_segments,
                ))
                cp_mgr.delete(chapter_id)
                return {"chapter_id": chapter_id, "status": "succeeded"}
            except Exception as exc:
                logger.error("Failed to translate chapter %s/%s: %s", novel_id, chapter_id, exc)
                provider_code = getattr(getattr(exc, "provider_error_code", None), "value", None)
                qa_status = getattr(exc, "qa_status", None)
                paused_reason = getattr(exc, "paused_reason", None)
                if isinstance(paused_reason, str) and paused_reason.strip():
                    failed_state = ChapterState.TRANSLATED_PARTIAL
                elif qa_status == ChapterState.QA_FAILED.value:
                    failed_state = ChapterState.QA_FAILED
                elif qa_status == ChapterState.NEEDS_REVIEW.value:
                    failed_state = ChapterState.NEEDS_REVIEW
                else:
                    failed_state = ChapterState.NEEDS_RETRY if isinstance(provider_code, str) else ChapterState.FAILED
                self.storage.save_chapter_state(
                    novel_id, chapter_id,
                    _make_state_data(failed_state, error=str(exc), previous=prev_state),
                )
                details = getattr(exc, "details", None)
                failed_chunk_id = details.get("chunk_id") if isinstance(details, dict) else None
                error_code = provider_code or getattr(exc, "error_code", None) or exc.__class__.__name__
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
                    _persist_chunk_qa_results_to_outputs(self.storage, novel_id, chunk_states)
                if isinstance(failed_chunk_id, str) and failed_chunk_id.strip():
                    self.storage.upsert_chunk_state(
                        {
                            "chunk_id": failed_chunk_id,
                            "novel_id": novel_id,
                            "chapter_ids": [chapter_id],
                            "provider_key": getattr(exc, "provider_key", effective_provider_key),
                            "provider_model": getattr(exc, "provider_model", effective_provider_model),
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
                            "provider_key": getattr(exc, "provider_key", effective_provider_key),
                            "provider_model": getattr(exc, "provider_model", effective_provider_model),
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
                cp_mgr.save(Checkpoint(
                    chapter_id=chapter_id,
                    state=TranslationState.FAILED,
                    error=str(exc)[:1024],
                ))
                raise
            finally:
                lock.release()

    # Schedule all chapter tasks with bounded concurrency.  Each task is
    # independent (different chapter_id, different storage keys, different
    # DB rows).  Exceptions are captured via return_exceptions=True so a
    # single chapter failure does not abort the rest of the run.
    tasks = [asyncio.create_task(_run_chapter(cn)) for cn in selected_numbers]
    task_results = await asyncio.gather(*tasks, return_exceptions=True)

    # Aggregate per-chapter progress in source order.  REQ-3.3.

    summary, first_error = _build_chapter_summary(
        selected_numbers=selected_numbers,
        task_results=task_results,
        chapters=chapters,
        force=force,
        target_language=effective_target_language,
    )
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
    """Force retranslation for a single chapter using chapter-scoped selection."""
    normalized_chapter_id = str(chapter_id).strip()
    if not normalized_chapter_id.isdigit():
        raise ValueError("chapter_id must be a numeric chapter identifier.")

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


# ---------------------------------------------------------------------------
# Re-exports — backward compatibility for novel_orchestration_service.py
# ---------------------------------------------------------------------------

from novelai.services.orchestration.translation_lineage import (  # noqa: E402
    _compare_lineage,
    _count_pending_glossary_entries,
    _estimate_delta_requests,
    _lineage_from_paragraphs,
    _lineage_signature,
    _old_lineage_by_chapter,
    _try_delta_translate_chapter,
)
from novelai.services.orchestration.translation_metadata import (  # noqa: E402
    _translate_metadata_batch,
    _translate_metadata_fields,
    _translate_metadata_items,
    _translate_text,
    estimate_translation_requests,
)
from novelai.services.orchestration.translation_progress import (  # noqa: E402
    _build_chapter_summary,
)
from novelai.services.orchestration.translation_resume import (  # noqa: E402
    _check_chapter_resume_state,
    _init_checkpoint_manager,
    _restore_checkpoint_for_chapter,
)

__all__ = [
    "_build_chapter_summary",
    "_check_chapter_resume_state",
    "_compare_lineage",
    "_count_pending_glossary_entries",
    "_estimate_delta_requests",
    "_init_checkpoint_manager",
    "_lineage_from_paragraphs",
    "_lineage_signature",
    "_old_lineage_by_chapter",
    "_restore_checkpoint_for_chapter",
    "_translate_metadata_batch",
    "_translate_metadata_fields",
    "_translate_metadata_items",
    "_translate_text",
    "_try_delta_translate_chapter",
    "estimate_translation_requests",
]
