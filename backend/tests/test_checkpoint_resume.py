"""Tests for checkpoint/resume pipeline: concurrency guard, 409 mapping, status endpoint."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from novelai.core.chapter_state import ChapterState
from novelai.core.errors import TranslationInProgressError
from novelai.services.orchestration.operations import OperationError, OperationsService


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
    assert result["translated_chapters"] == 1
    assert len(result["chapters"]) == 3

    # Ch1: translated
    assert result["chapters"][0]["id"] == "1"
    assert result["chapters"][0]["translated"] is True
    assert result["chapters"][0]["state"] == ChapterState.TRANSLATED.value

    # Ch2: translating
    assert result["chapters"][1]["id"] == "2"
    assert result["chapters"][1]["translated"] is False
    assert result["chapters"][1]["state"] == ChapterState.TRANSLATING.value

    # Ch3: no state → unknown
    assert result["chapters"][2]["id"] == "3"
    assert result["chapters"][2]["translated"] is False
    assert result["chapters"][2]["state"] == "unknown"


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
