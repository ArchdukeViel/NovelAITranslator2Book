"""Tests for the CheckpointManager."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest

from novelai.core.chapter_state import ChapterState
from novelai.services.checkpoint_manager import CheckpointManager, CheckpointMetadata
from novelai.services.storage_service import StorageService

_TMP = Path(__file__).resolve().parent / ".tmp" / "checkpoints"


@pytest.fixture()
def storage(request: pytest.FixtureRequest) -> StorageService:
    d = _TMP / uuid4().hex[:8]
    d.mkdir(parents=True, exist_ok=True)
    return StorageService(base_dir=d)


@pytest.fixture()
def mgr(storage: StorageService) -> CheckpointManager:
    return CheckpointManager(storage)


class TestCheckpointManager:
    @pytest.mark.asyncio
    async def test_create_checkpoint(self, mgr: CheckpointManager) -> None:
        cp = await mgr.create_checkpoint("n1", "ch1", ChapterState.PARSED)
        assert isinstance(cp, CheckpointMetadata)
        assert cp.novel_id == "n1"
        assert cp.state == "parsed"
        assert cp.error is None

    @pytest.mark.asyncio
    async def test_create_checkpoint_with_error(self, mgr: CheckpointManager) -> None:
        cp = await mgr.create_checkpoint("n1", "ch1", ChapterState.TRANSLATED, error="timeout")
        assert cp.error == "timeout"

    def test_get_checkpoint_id(self, mgr: CheckpointManager) -> None:
        assert mgr._get_checkpoint_id("novel1", "ch2") == "novel1_ch2"

    def test_get_checkpoint_history_empty(self, mgr: CheckpointManager) -> None:
        history = mgr.get_checkpoint_history("n1", "ch1")
        assert history == []

    @pytest.mark.asyncio
    async def test_get_checkpoint_history_returns_created(self, mgr: CheckpointManager) -> None:
        await mgr.create_checkpoint("n1", "ch1", ChapterState.SCRAPED)
        history = mgr.get_checkpoint_history("n1", "ch1")
        assert len(history) >= 1
