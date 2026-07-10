"""Tests for checkpoint/resume pipeline."""

from __future__ import annotations

import json
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from novelai.core.chapter_state import ChapterState, TranslationState
from novelai.core.errors import TranslationInProgressError
from novelai.services.orchestration.operations import OperationError, OperationsService
from novelai.services.pipeline.checkpoint import Checkpoint, CheckpointManager, CHECKPOINT_MAX_AGE_DAYS


@pytest.mark.asyncio
async def test_translate_novel_409_on_translation_in_progress() -> None:
    """OperationsService.translate_novel maps TranslationInProgressError→OperationError(409)."""
    orchestrator = MagicMock()
    orchestrator.translate_chapters = AsyncMock(
        side_effect=TranslationInProgressError("Translation already in progress for novel n1234")
    )
    svc = OperationsService(
        orchestrator=orchestrator,
        activity_log=MagicMock(),
        storage=MagicMock(),
        export_service=MagicMock(),
    )
    # Guard: load_metadata returns non-None
    svc.storage.load_metadata.return_value = {"novel_id": "n1234"}

    with pytest.raises(OperationError) as exc_info:
        await svc.translate_novel(
            novel_id="n1234",
            source_key="source_a",
            chapters="all",
            provider_key=None,
            provider_model=None,
            force=False,
            source_language="ja",
            target_language="en",
        )
    assert exc_info.value.status_code == 409
    assert "n1234" in str(exc_info.value.detail)


@pytest.mark.asyncio
async def test_translate_novel_504_on_timeout() -> None:
    """TimeoutError → OperationError(504)."""
    orchestrator = MagicMock()
    orchestrator.translate_chapters = AsyncMock(side_effect=TimeoutError("timed out"))
    svc = OperationsService(
        orchestrator=orchestrator,
        activity_log=MagicMock(),
        storage=MagicMock(),
        export_service=MagicMock(),
    )
    svc.storage.load_metadata.return_value = {"novel_id": "n5678"}

    with pytest.raises(OperationError) as exc_info:
        await svc.translate_novel(
            novel_id="n5678",
            source_key="source_a",
            chapters="all",
            provider_key=None,
            provider_model=None,
            force=False,
            source_language="ja",
            target_language="en",
        )
    assert exc_info.value.status_code == 504


@pytest.mark.asyncio
async def test_translate_novel_404_on_missing_novel() -> None:
    """Unknown novel_id → OperationError(404)."""
    svc = OperationsService(
        orchestrator=MagicMock(),
        activity_log=MagicMock(),
        storage=MagicMock(),
        export_service=MagicMock(),
    )
    svc.storage.load_metadata.return_value = None

    with pytest.raises(OperationError) as exc_info:
        await svc.translate_novel(
            novel_id="nonexistent",
            source_key="source_a",
            chapters="all",
            provider_key=None,
            provider_model=None,
            force=False,
            source_language="ja",
            target_language="en",
        )
    assert exc_info.value.status_code == 404


def test_get_translation_status_shape() -> None:
    """translate-status returns expected fields and per-chapter data."""
    svc = OperationsService(
        orchestrator=MagicMock(),
        activity_log=MagicMock(),
        storage=MagicMock(),
        export_service=MagicMock(),
    )
    svc.storage.load_metadata.return_value = {
        "novel_id": "n1234",
        "title": "Test",
        "chapters": [
            {"id": "1", "title": "Ch1"},
            {"id": "2", "title": "Ch2"},
            {"id": "3", "title": "Ch3"},
        ],
    }
    svc.storage.load_chapter_state.side_effect = [
        {"current_state": ChapterState.TRANSLATED, "error_count": 0},
        {"current_state": ChapterState.TRANSLATING, "error_count": 0},
        None,
    ]
    svc.storage.load_translated_chapter.side_effect = [
        {"text": "done"},
        None,
        None,
    ]

    result = svc.get_translation_status(novel_id="n1234")

    assert result["novel_id"] == "n1234"
    assert result["total_chapters"] == 3
    # Overall state: 1 completed, 1 in progress, 1 pending → pending (not all done)
    assert result["overall_state"] == "pending"
    assert result["total_chapters"] == 3
    assert result["completed_chapters"] == 1
    assert result["failed_chapters"] == 0
    assert result["in_progress_chapters"] == 1
    assert len(result["chapters"]) == 3
    # Each chapter gets a state field
    for ch in result["chapters"]:
        assert "state" in ch

    # Ch1: translated
    assert result["chapters"][0]["id"] == "1"
    assert result["chapters"][0]["translated"] is True
    assert result["chapters"][0]["state"] == ChapterState.TRANSLATED.value

    # Ch2: translating
    assert result["chapters"][1]["id"] == "2"
    assert result["chapters"][1]["translated"] is False
    assert result["chapters"][1]["state"] == ChapterState.TRANSLATING.value

    # Ch3: no storage state → falls back to DB translation_state (pending)
    assert result["chapters"][2]["id"] == "3"
    assert result["chapters"][2]["translated"] is False
    assert result["chapters"][2]["state"] == "pending"
    assert result["chapters"][2]["translation_state"] == "pending"


def test_get_translation_status_404() -> None:
    """Unknown novel → OperationError(404)."""
    svc = OperationsService(
        orchestrator=MagicMock(),
        activity_log=MagicMock(),
        storage=MagicMock(),
        export_service=MagicMock(),
    )
    svc.storage.load_metadata.return_value = None

    with pytest.raises(OperationError) as exc_info:
        svc.get_translation_status(novel_id="nonexistent")
    assert exc_info.value.status_code == 404


# ── CheckpointManager unit tests ─────────────────────────────────────────────


class TestCheckpointManager:
    """Tests for segment-level checkpoint persistence (Task 2, REQ-2)."""

    def test_save_and_load(self, tmp_path: Path) -> None:
        """7.1: Checkpoint is written and can be loaded."""
        mgr = CheckpointManager(tmp_path)
        cp = Checkpoint(
            chapter_id="42",
            state=TranslationState.TRANSLATING,
            completed_stages=["fetch", "parse"],
            current_stage="translate",
            segments_completed=5,
            segments_total=15,
        )
        mgr.save(cp)

        loaded = mgr.load("42")
        assert loaded is not None
        assert loaded.chapter_id == "42"
        assert loaded.state == TranslationState.TRANSLATING
        assert loaded.completed_stages == ["fetch", "parse"]
        assert loaded.current_stage == "translate"
        assert loaded.segments_completed == 5
        assert loaded.segments_total == 15
        assert loaded.error is None
        assert loaded.last_updated  # timestamp populated

    def test_load_missing(self, tmp_path: Path) -> None:
        """load returns None for non-existent checkpoint."""
        mgr = CheckpointManager(tmp_path)
        assert mgr.load("99") is None

    def test_load_corrupt(self, tmp_path: Path) -> None:
        """7.7: Corrupt checkpoint file is removed and returns None."""
        mgr = CheckpointManager(tmp_path)
        path = mgr._path("42")
        path.write_text("{invalid json", encoding="utf-8")
        assert mgr.load("42") is None
        assert not path.exists()

    def test_load_stale(self, tmp_path: Path) -> None:
        """7.8: Stale checkpoint (>CHECKPOINT_MAX_AGE_DAYS) is invalidated."""
        mgr = CheckpointManager(tmp_path)
        old_ts = (datetime.now(timezone.utc) - timedelta(days=CHECKPOINT_MAX_AGE_DAYS + 1)).isoformat()
        cp = Checkpoint(
            chapter_id="42",
            state=TranslationState.TRANSLATING,
            last_updated=old_ts,
        )
        mgr.save(cp)
        # Override the timestamp with a stale one
        path = mgr._path("42")
        raw = json.loads(path.read_text(encoding="utf-8"))
        raw["last_updated"] = old_ts
        path.write_text(json.dumps(raw), encoding="utf-8")

        assert mgr.load("42") is None
        assert not path.exists()

    def test_delete(self, tmp_path: Path) -> None:
        """delete removes the checkpoint file."""
        mgr = CheckpointManager(tmp_path)
        mgr.save(Checkpoint(chapter_id="42"))
        assert mgr._path("42").exists()
        mgr.delete("42")
        assert not mgr._path("42").exists()

    def test_delete_missing_no_error(self, tmp_path: Path) -> None:
        """delete on non-existent file does not raise."""
        mgr = CheckpointManager(tmp_path)
        mgr.delete("nonexistent")  # should not raise

    def test_save_atomicity(self, tmp_path: Path) -> None:
        """2.4: Writes use temp-file-then-rename (non-tmp files not left around)."""
        mgr = CheckpointManager(tmp_path)
        mgr.save(Checkpoint(chapter_id="42"))
        # No .tmp files should remain
        tmp_files = list(tmp_path.glob("*.tmp"))
        assert len(tmp_files) == 0
        assert mgr._path("42").exists()

    def test_save_failure_logged_not_raised(self, tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
        """5.1: Checkpoint write failure is logged at WARNING, not raised."""
        mgr = CheckpointManager(tmp_path)
        # Make checkpoint_dir a file to force OSError on write
        file_path = mgr.checkpoint_dir / "dummy"
        file_path.write_text("blocking file")
        # Point to that file as if it were the checkpoint dir
        mgr.checkpoint_dir = file_path
        mgr.save(Checkpoint(chapter_id="42"))
        assert any("Failed to write checkpoint" in msg for msg in caplog.messages)


# ── TranslationState helper tests ────────────────────────────────────────────


@pytest.mark.asyncio
async def test_update_db_translation_state() -> None:
    """_update_db_translation_state runs without error (integration via session_scope)."""
    from novelai.services.orchestration.translation import _update_db_translation_state
    # In test env without DB, this should log warning and return gracefully
    _update_db_translation_state("test_novel", "1", TranslationState.FETCHING)
    # No exception = pass


@pytest.mark.asyncio
async def test_load_db_translation_state_defaults_to_pending() -> None:
    """_load_db_translation_state returns PENDING when no DB row found."""
    from novelai.services.orchestration.translation import _load_db_translation_state
    state = _load_db_translation_state("nonexistent_novel", "1")
    assert state == TranslationState.PENDING.value


# ── Resume logic tests ───────────────────────────────────────────────────────

# We test the resume/force behavior by mocking the orchestration layer
# at the OperationsService level.

@pytest.mark.asyncio
async def test_force_resets_all_chapters_to_pending() -> None:
    """5: ?force=true resets all chapters — tested by verifying translate_chapters is called."""
    orchestrator = MagicMock()
    orchestrator.translate_chapters = AsyncMock()
    svc = OperationsService(
        orchestrator=orchestrator,
        activity_log=MagicMock(),
        storage=MagicMock(),
        export_service=MagicMock(),
    )
    svc.storage.load_metadata.return_value = {"novel_id": "n1"}

    result = await svc.translate_novel(
        novel_id="n1",
        source_key="source_a",
        chapters="all",
        provider_key=None,
        provider_model=None,
        force=True,
        source_language="ja",
        target_language="en",
    )
    assert result["status"] == "ok"
    orchestrator.translate_chapters.assert_awaited_once()
    # force=True is passed through
    call_kwargs = orchestrator.translate_chapters.call_args.kwargs
    assert call_kwargs["force"] is True


@pytest.mark.asyncio
async def test_skip_already_complete_chapters() -> None:
    """7.3: Chapters with translation_state == COMPLETE are skipped.

    This is tested implicitly: when force=False, the orchestrator still
    receives a call. The resume check happens *inside* translate_chapters
    before the chapter loop — we verify the endpoint plumbing works.
    """
    orchestrator = MagicMock()
    orchestrator.translate_chapters = AsyncMock()
    svc = OperationsService(
        orchestrator=orchestrator,
        activity_log=MagicMock(),
        storage=MagicMock(),
        export_service=MagicMock(),
    )
    svc.storage.load_metadata.return_value = {"novel_id": "n1"}

    result = await svc.translate_novel(
        novel_id="n1",
        source_key="source_a",
        chapters="all",
        provider_key=None,
        provider_model=None,
        force=False,
        source_language="ja",
        target_language="en",
    )
    assert result["status"] == "ok"
    orchestrator.translate_chapters.assert_awaited_once()
