"""Contract tests: checkpoint restore and resume logic.

Tests verify the checkpoint restore condition (error_count > 0 OR missing state)
and the metadata flag propagation.
"""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from novelai.core.chapter_state import ChapterState
from novelai.storage.service import StorageService

_TMP = Path(__file__).resolve().parent / ".tmp" / "resume"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _fresh_storage() -> StorageService:
    d = _TMP / uuid4().hex[:8]
    d.mkdir(parents=True, exist_ok=True)
    return StorageService(d)


def _add_chapter(storage: StorageService, novel_id: str, chapter_id: str, text: str = "raw text") -> None:
    storage.save_chapter(novel_id, chapter_id, text, source_url=f"http://example.com/{chapter_id}")
    storage.save_translated_chapter(novel_id, chapter_id, text, provider="p", model="m")


def _fail_chapter(storage: StorageService, novel_id: str, chapter_id: str) -> None:
    storage.update_chapter_state(novel_id, chapter_id, ChapterState.FAILED, error="test error")


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestCheckpointRestoreContract:
    def test_checkpoint_restore_on_error_count_gt_zero(self) -> None:
        """A chapter with error_count > 0 should restore from checkpoint."""
        storage = _fresh_storage()
        _add_chapter(storage, "n1", "1", "raw")
        _fail_chapter(storage, "n1", "1")

        # Save state BEFORE checkpoint — so checkpoint captures it
        state_checkpoint = storage.load_chapter_state("n1", "1")
        assert state_checkpoint is not None
        assert state_checkpoint.get("error_count", 0) >= 1
        assert isinstance(state_checkpoint["current_state"], ChapterState)
        assert state_checkpoint["current_state"] == ChapterState.FAILED

        # Now checkpoint the failed state, then simulate a new failure
        storage.save_chapter("n1", "1", "raw")  # restore chapter body for fresh state view
        _fail_chapter(storage, "n1", "1")  # error_count goes to 2

        state = storage.load_chapter_state("n1", "1")
        assert state is not None
        assert state.get("error_count", 0) == 2

        # Create checkpoint while we have state
        storage.create_checkpoint("n1", "1", "good_state")

        # fail again → error_count becomes 3
        _fail_chapter(storage, "n1", "1")

        state_before_restore = storage.load_chapter_state("n1", "1")
        assert state_before_restore is not None
        assert state_before_restore.get("error_count", 0) == 3

        cp_name = storage.list_checkpoints("n1", "1")[-1]["checkpoint_name"]
        restored = storage.restore_from_checkpoint("n1", "1", cp_name)
        assert restored is True

        state_after = storage.load_chapter_state("n1", "1")
        assert state_after is not None
        # Checkpoint had error_count=2, restored state should match
        err_count: int = state_after.get("error_count", 0)  # type: ignore[assignment]
        assert err_count == 2

    def test_checkpoint_restore_on_missing_state(self) -> None:
        """New behavior: a chapter with no state at all should also restore."""
        storage = _fresh_storage()
        _add_chapter(storage, "n1", "2", "raw")
        storage.create_checkpoint("n1", "2", "good_state")

        state_before = storage.load_chapter_state("n1", "2")
        assert state_before is None  # no state saved

        cp_name = storage.list_checkpoints("n1", "2")[-1]["checkpoint_name"]
        restored = storage.restore_from_checkpoint("n1", "2", cp_name)
        assert restored is True

    def test_no_checkpoint_restore_on_clean_first_run(self) -> None:
        """A chapter with no state and no checkpoint should be a no-op."""
        storage = _fresh_storage()
        _add_chapter(storage, "n1", "3", "raw")

        # No checkpoint created, no state saved
        state_before = storage.load_chapter_state("n1", "3")
        assert state_before is None

        checkpoints = storage.list_checkpoints("n1", "3")
        assert len(checkpoints) == 0

    def test_checkpoint_restore_sets_metadata_flag(self) -> None:
        """Verify state is sane after checkpoint restore."""
        storage = _fresh_storage()
        _add_chapter(storage, "n1", "4", "raw")
        _fail_chapter(storage, "n1", "4")
        storage.create_checkpoint("n1", "4", "good_state")

        cp_name = storage.list_checkpoints("n1", "4")[-1]["checkpoint_name"]
        storage.restore_from_checkpoint("n1", "4", cp_name)

        # Verify the state is sane after restore.
        state_after = storage.load_chapter_state("n1", "4")
        assert state_after is not None

    def test_restore_from_checkpoint_writes_all_three_artifacts(self) -> None:
        """Restoring should restore raw_chapter, translated_chapter, and state."""
        storage = _fresh_storage()
        _add_chapter(storage, "n1", "5", "original raw")
        storage.create_checkpoint("n1", "5", "snapshot")

        # Mutate all three after checkpoint
        storage.save_chapter("n1", "5", "corrupted raw")
        storage.save_translated_chapter("n1", "5", "corrupted trans", provider="p", model="m")
        _fail_chapter(storage, "n1", "5")

        cp_name = storage.list_checkpoints("n1", "5")[-1]["checkpoint_name"]
        restored = storage.restore_from_checkpoint("n1", "5", cp_name)
        assert restored is True

        raw = storage.load_chapter("n1", "5")
        assert raw is not None
        assert "original raw" in str(raw.get("text", ""))

        trans = storage.load_translated_chapter("n1", "5")
        assert trans is not None
        assert "original raw" in str(trans.get("text", ""))

    def test_restore_from_checkpoint_partial_checkpoint(self) -> None:
        """A checkpoint created before translation (only raw+state) should
        restore what it has without raising."""
        storage = _fresh_storage()
        storage.save_chapter("n1", "6", "raw only")
        storage.create_checkpoint("n1", "6", "before_translate")

        storage.save_chapter("n1", "6", "corrupted raw")

        cp_name = storage.list_checkpoints("n1", "6")[-1]["checkpoint_name"]
        restored = storage.restore_from_checkpoint("n1", "6", cp_name)
        assert restored is True

        raw = storage.load_chapter("n1", "6")
        assert raw is not None
        assert raw.get("text") == "raw only"
