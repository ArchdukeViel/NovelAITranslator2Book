"""Optional tests for the operations router request schema."""

from __future__ import annotations

from typing import Any, cast
from unittest.mock import AsyncMock, MagicMock

import pytest
from pydantic import ValidationError

from novelai.api.routers.operations import ImportRequest, RetranslateStaleRequest, TranslateRequest
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


def test_import_request_accepts_only_source_urls() -> None:
    request = ImportRequest.model_validate({"source_url": "https://example.com/story", "max_units": 3})

    assert str(request.source_url) == "https://example.com/story"
    assert request.max_units == 3

    for payload in (
        {"source_url": "C:/books/story.txt"},
        {"source_url": "story.epub"},
        {"adapter_key": "web", "source_key": "https://example.com/story"},
    ):
        with pytest.raises(ValidationError):
            ImportRequest.model_validate(payload)


def _operations_service(
    metadata: dict[str, object],
) -> tuple[OperationsService, MagicMock, MagicMock]:
    storage = MagicMock()
    storage.load_metadata.return_value = metadata
    orchestrator = MagicMock()
    orchestrator.translate_chapters = AsyncMock()
    activity_log = MagicMock()
    activity_log.create_translation_activity.return_value = {
        "activity_id": "translation-test",
        "status": "pending",
    }
    service = OperationsService(
        orchestrator=orchestrator,
        activity_log=activity_log,
        storage=storage,
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
        "activity_id": "translation-test",
        "status": "pending",
    }
    orchestrator.translate_chapters.assert_not_awaited()
    create_kwargs = cast(Any, service.activity_log.create_translation_activity).call_args.kwargs
    assert create_kwargs["kind"] == "batch_retranslate"
    assert create_kwargs["chapters"] == "1"
