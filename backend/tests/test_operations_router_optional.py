"""Optional tests for the operations router request schema."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from pydantic import ValidationError

from novelai.api.routers.operations import RetranslateStaleRequest, TranslateRequest
from novelai.services.orchestration.operations import OperationError, OperationsService


def test_translate_request_defaults_skip_glossary_gate_to_false() -> None:
    request = TranslateRequest.model_validate({"source_key": "kakuyomu"})
    assert request.skip_glossary_gate is False


def test_translate_request_round_trips_skip_glossary_gate_true() -> None:
    request = TranslateRequest.model_validate({"source_key": "kakuyomu", "skip_glossary_gate": True})
    assert request.skip_glossary_gate is True


def test_retranslate_stale_request_rejects_removed_options() -> None:
    with pytest.raises(ValidationError):
        RetranslateStaleRequest.model_validate({"include_legacy_unknown": True, "activate": True})


def _operations_service(
    metadata: dict[str, object],
) -> tuple[OperationsService, MagicMock, MagicMock]:
    storage = MagicMock()
    storage.load_metadata.return_value = metadata
    orchestrator = MagicMock()
    orchestrator.translate_chapters = AsyncMock()
    service = OperationsService(
        orchestrator=orchestrator,
        activity_log=MagicMock(),
        storage=storage,
        export_service=MagicMock(),
    )
    return service, orchestrator, storage


@pytest.mark.asyncio
async def test_retranslate_stale_rejects_legacy_source_metadata() -> None:
    service, orchestrator, _storage = _operations_service({"source": "kakuyomu", "chapters": []})

    with pytest.raises(OperationError, match="Novel has no source_key"):
        await service.retranslate_stale(novel_id="novel-1")

    orchestrator.translate_chapters.assert_not_awaited()


@pytest.mark.asyncio
async def test_retranslate_stale_accepts_canonical_source_key() -> None:
    service, orchestrator, _storage = _operations_service({"source_key": "kakuyomu", "chapters": []})

    result = await service.retranslate_stale(novel_id="novel-1")

    assert result["scheduled_chapter_count"] == 0
    orchestrator.translate_chapters.assert_not_awaited()


@pytest.mark.asyncio
async def test_retranslate_stale_schedules_only_stale_canonical_versions() -> None:
    service, orchestrator, storage = _operations_service(
        {
            "source_key": "kakuyomu",
            "glossary_revision": 2,
            "chapters": [{"id": "1"}, {"id": "2"}],
        }
    )
    storage.load_translated_chapter.side_effect = [
        {"glossary_revision": 1},
        {"glossary_revision": 2},
    ]

    result = await service.retranslate_stale(novel_id="novel-1")

    assert result == {
        "novel_id": "novel-1",
        "stale_chapter_count": 1,
        "scheduled_chapter_count": 1,
        "activity_id": None,
    }
    orchestrator.translate_chapters.assert_awaited_once_with(
        "kakuyomu",
        "novel-1",
        "1",
        provider_key=None,
        provider_model=None,
        force=True,
    )
