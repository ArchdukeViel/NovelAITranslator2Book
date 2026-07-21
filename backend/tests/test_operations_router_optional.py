"""Optional tests for the operations router request schema."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from novelai.api.routers.operations import TranslateRequest
from novelai.services.orchestration.operations import OperationError, OperationsService


def test_translate_request_defaults_skip_glossary_gate_to_false() -> None:
    request = TranslateRequest.model_validate({"source_key": "kakuyomu"})
    assert request.skip_glossary_gate is False


def test_translate_request_round_trips_skip_glossary_gate_true() -> None:
    request = TranslateRequest.model_validate({"source_key": "kakuyomu", "skip_glossary_gate": True})
    assert request.skip_glossary_gate is True


def _operations_service(metadata: dict[str, object]) -> tuple[OperationsService, MagicMock]:
    storage = MagicMock()
    storage.load_metadata.return_value = metadata
    orchestrator = MagicMock()
    orchestrator.translate_chapters = AsyncMock()
    return (
        OperationsService(
            orchestrator=orchestrator,
            activity_log=MagicMock(),
            storage=storage,
            export_service=MagicMock(),
        ),
        orchestrator,
    )


@pytest.mark.asyncio
async def test_retranslate_stale_rejects_legacy_source_metadata() -> None:
    service, orchestrator = _operations_service({"source": "kakuyomu", "chapters": []})

    with pytest.raises(OperationError, match="Novel has no source_key"):
        await service.retranslate_stale(novel_id="novel-1")

    orchestrator.translate_chapters.assert_not_awaited()


@pytest.mark.asyncio
async def test_retranslate_stale_accepts_canonical_source_key() -> None:
    service, orchestrator = _operations_service({"source_key": "kakuyomu", "chapters": []})

    result = await service.retranslate_stale(novel_id="novel-1")

    assert result["scheduled_chapter_count"] == 0
    orchestrator.translate_chapters.assert_not_awaited()
