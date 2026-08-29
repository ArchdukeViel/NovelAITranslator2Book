"""Translation resume/restart logic — extracted from translation.py.

Chapter resume state checks, checkpoint restoration, and checkpoint manager
initialization. These were previously inline in ``translate_chapters``.
"""

from __future__ import annotations

import logging
from typing import Any

from novelai.config.settings import settings
from novelai.core.chapter_state import ChapterState, TranslationState
from novelai.services.orchestration.common import _make_state_data
from novelai.services.orchestration.translation import (
    _load_db_translation_state,
    _update_db_translation_state,
)
from novelai.services.pipeline.checkpoint import CheckpointManager
from novelai.translation.run_manifest import is_translation_valid

logger = logging.getLogger(__name__)


def _check_chapter_resume_state(
    self: Any,
    *,
    novel_id: str,
    chapter_id: str,
    force: bool,
    # Effective translation contract. When any field is None the matching
    # stored value must exist on the existing translation version — the
    # validator fails closed when a required input is missing.
    source_text_hash: str | None = None,
    effective_glossary_hash: str | None = None,
    prompt_template_version: str | None = None,
    provider_key: str | None = None,
    provider_model: str | None = None,
    active_raw_generation_id: str | None = None,
    source_structure_hash: str | None = None,
    source_image_manifest_hash: str | None = None,
    qa_policy_fingerprint: str | None = None,
    source_language: str | None = None,
    target_language: str | None = None,
    # Output-shaping settings participate in the effective contract: a change
    # in style preset, consistency mode, JSON output, or honorific policy
    # alters generated text and must retranslate.
    style_preset: str | None = None,
    consistency_mode: bool | None = None,
    json_output: bool | None = None,
    honorific_policy: str | None = None,
) -> dict[str, str] | None:
    """Check whether a chapter should be skipped or reset before translation.

    Returns a ``{"chapter_id": ..., "status": "skipped", "reason": ...}`` dict
    if the chapter should be skipped, or ``None`` if translation should proceed.

    A DB ``COMPLETE`` state or an existing translation is **not** sufficient
    evidence that the previous translation is still valid against the current
    effective contract. When the stored lineage diverges from the contract —
    changed source text, glossary, prompt template, QA policy, provider /
    model, target language, structure, or image manifest — the resume path
    must retranslate instead of silently serving stale output. The previous
    version is retained in the per-chapter overlay history regardless.

    REQ-3.1: skip when previous translation is still valid, reset FAILED.
    REQ-3.4: force=True bypasses validity and clears prior state.
    """
    db_state = _load_db_translation_state(novel_id, chapter_id)
    if not force:
        if db_state == TranslationState.FAILED.value:
            logger.info("Resetting FAILED chapter %s/%s to PENDING for retry", novel_id, chapter_id)
            _update_db_translation_state(novel_id, chapter_id, TranslationState.PENDING)

    existing = self.storage.load_translated_chapter(novel_id, chapter_id)
    if force:
        return None

    if existing and not settings.TRANSLATION_DELTA_RETRANSLATION_ENABLED:
        # Validate against the *complete* effective contract. ``is_translation_valid``
        # fails closed when a required input has no stored value, so a stale or
        # partially missing lineage cannot silently pass.
        valid = is_translation_valid(
            source_text_hash=source_text_hash or "",
            active_glossary_hash=effective_glossary_hash,
            prompt_version=prompt_template_version,
            provider_key=provider_key,
            provider_model=provider_model,
            record=existing,
            active_raw_generation_id=active_raw_generation_id,
            source_structure_hash=source_structure_hash,
            source_image_manifest_hash=source_image_manifest_hash,
            qa_policy_fingerprint=qa_policy_fingerprint,
            source_language=source_language,
            target_language=target_language,
            style_preset=style_preset,
            consistency_mode=consistency_mode,
            json_output=json_output,
            honorific_policy=honorific_policy,
        )
        if valid:
            # A prior worker may have persisted the artifact successfully and
            # then lost its activity lease before the database state transition
            # was recorded. Reconcile that durable artifact before returning a
            # skip so a retry cannot leave a valid translation permanently
            # reported as failed (and so stale translation_error is cleared).
            _update_db_translation_state(novel_id, chapter_id, TranslationState.COMPLETE)
            logger.info(
                "Skipping already-translated chapter %s/%s (lineage valid)",
                novel_id,
                chapter_id,
            )
            reason = "already_complete" if db_state == TranslationState.COMPLETE.value else "already_translated"
            return {"chapter_id": chapter_id, "status": "skipped", "reason": reason}

        # Existing translation has stale lineage: surface the decision so the
        # caller proceeds with full or delta retranslation. The previous
        # version remains in the overlay history; the DB state is reset so
        # downstream progress accounting treats the chapter as pending.
        logger.info(
            "Existing translation for %s/%s has stale lineage; retranslating (db_state=%s)",
            novel_id,
            chapter_id,
            db_state,
        )
        if db_state == TranslationState.COMPLETE.value:
            _update_db_translation_state(novel_id, chapter_id, TranslationState.PENDING)

    # If there is no existing translation, an old COMPLETE DB state with no
    # lineage evidence must also be treated as stale: the recorded completion
    # is evidence of a past run, not of current validity.
    if existing is None and db_state == TranslationState.COMPLETE.value:
        _update_db_translation_state(novel_id, chapter_id, TranslationState.PENDING)

    return None


def _restore_checkpoint_for_chapter(
    self: Any,
    *,
    novel_id: str,
    chapter_id: str,
) -> tuple[dict[str, Any] | None, bool]:
    """Restore latest checkpoint and mark chapter as in-progress.

    Returns ``(prev_state, checkpoint_restored)``. The caller must use
    ``prev_state`` for subsequent ``save_chapter_state`` calls and error
    handling within the chapter's try/except block.
    """
    state_before = self.storage.load_chapter_state(novel_id, chapter_id)
    checkpoint_restored = False
    if state_before is None or state_before.get("error_count", 0) > 0:
        checkpoint_restored = self._restore_latest_checkpoint_for_resume(novel_id, chapter_id)

    # Persist an explicit resume point before making changes.
    self.storage.create_checkpoint(novel_id, chapter_id, "before_translate")

    # Checkpoint: mark chapter as in-progress
    prev_state = self.storage.load_chapter_state(novel_id, chapter_id)
    state_data = _make_state_data(ChapterState.TRANSLATING, previous=prev_state)
    state_data["metadata"] = dict(state_data.get("metadata") or {})
    state_data["metadata"]["checkpoint_restored"] = checkpoint_restored
    self.storage.save_chapter_state(
        novel_id,
        chapter_id,
        state_data,
    )

    return prev_state, checkpoint_restored


def _init_checkpoint_manager(
    self: Any,
    *,
    novel_id: str,
    selected_chapter_ids: list[str],
    force: bool,
) -> CheckpointManager:
    """Initialize CheckpointManager for segment-level resume (REQ-2).

    When ``force`` is True, resets all selected chapters to PENDING and
    deletes existing checkpoints (REQ-3.4, Task 5.2).

    ``selected_chapter_ids`` must be the *stable* chapter ids (never
    positional sequence numbers): checkpoint files and DB state rows are
    keyed by chapter id, so deleting by sequence number would miss the
    actual checkpoints for non-numeric ids (e.g. Kakuyomu).
    """
    cp_mgr = CheckpointManager(self.storage._get_checkpoints_dir(novel_id))

    if force:
        for chapter_id in selected_chapter_ids:
            _update_db_translation_state(novel_id, chapter_id, TranslationState.PENDING)
            cp_mgr.delete(chapter_id)
        logger.info("Force mode: reset %d chapters to PENDING", len(selected_chapter_ids))

    return cp_mgr
