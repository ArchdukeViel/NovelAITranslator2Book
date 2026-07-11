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

logger = logging.getLogger(__name__)


def _check_chapter_resume_state(
    self: Any,
    *,
    novel_id: str,
    chapter_id: str,
    force: bool,
) -> dict[str, str] | None:
    """Check whether a chapter should be skipped or reset before translation.

    Returns a ``{"chapter_id": ..., "status": "skipped", "reason": ...}`` dict
    if the chapter should be skipped, or ``None`` if translation should proceed.

    REQ-3.1: skip COMPLETE, reset FAILED. Bypassed when force=True (REQ-3.4).
    """
    if not force:
        db_state = _load_db_translation_state(novel_id, chapter_id)
        if db_state == TranslationState.COMPLETE.value:
            logger.info("Skipping already-complete chapter %s/%s", novel_id, chapter_id)
            return {"chapter_id": chapter_id, "status": "skipped", "reason": "already_complete"}
        if db_state == TranslationState.FAILED.value:
            logger.info("Resetting FAILED chapter %s/%s to PENDING for retry", novel_id, chapter_id)
            _update_db_translation_state(novel_id, chapter_id, TranslationState.PENDING)

    existing = self.storage.load_translated_chapter(novel_id, chapter_id)
    if existing and not force and not settings.TRANSLATION_DELTA_RETRANSLATION_ENABLED:
        return {"chapter_id": chapter_id, "status": "skipped", "reason": "already_translated"}

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
    selected_numbers: list[int],
    force: bool,
) -> CheckpointManager:
    """Initialize CheckpointManager for segment-level resume (REQ-2).

    When ``force`` is True, resets all selected chapters to PENDING and
    deletes existing checkpoints (REQ-3.4, Task 5.2).
    """
    cp_mgr = CheckpointManager(self.storage._get_checkpoints_dir(novel_id))

    if force:
        for cn in selected_numbers:
            _update_db_translation_state(novel_id, str(cn), TranslationState.PENDING)
            cp_mgr.delete(str(cn))
        logger.info("Force mode: reset %d chapters to PENDING", len(selected_numbers))

    return cp_mgr
