from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from novelai.activity.queue import ActivityQueueService
from novelai.services.orchestration.operations import OperationsService
from novelai.storage.service import StorageService


@pytest.mark.asyncio
async def test_scrape_novel_enqueues_durable_activity_instead_of_waiting(tmp_path) -> None:
    storage = StorageService(tmp_path / "storage")
    activity_log = ActivityQueueService(tmp_path / "jobs")
    orchestrator = MagicMock()
    orchestrator.scrape_metadata = AsyncMock()
    orchestrator.scrape_chapters = AsyncMock()
    service = OperationsService(orchestrator=orchestrator, activity_log=activity_log, storage=storage)

    result = await service.scrape_novel(
        novel_id="novel-1",
        source_key="syosetu_ncode",
        url="https://example.test/novel-1",
        chapters="all",
        mode="update",
        max_chapter=12,
    )

    assert result["status"] == "pending"
    activity_id = str(result["activity_id"])
    queued = activity_log.get_activity(activity_id)
    assert queued is not None
    assert queued["kind"] == "scrape"
    assert queued["source_url"] == "https://example.test/novel-1"
    assert queued["metadata"]["max_chapter"] == 12
    orchestrator.scrape_metadata.assert_not_awaited()
    orchestrator.scrape_chapters.assert_not_awaited()


@pytest.mark.asyncio
async def test_resume_onboarding_returns_queued_activity(tmp_path) -> None:
    storage = StorageService(tmp_path / "storage")
    storage.save_metadata(
        "novel-1",
        {
            "source_key": "syosetu_ncode",
            "source_url": "https://example.test/novel-1",
            "onboarding_status": "chapters_pending",
            "chapters": [{"id": "1"}],
        },
    )
    activity_log = ActivityQueueService(tmp_path / "jobs")
    orchestrator = MagicMock()
    orchestrator.scrape_chapters = AsyncMock()
    service = OperationsService(orchestrator=orchestrator, activity_log=activity_log, storage=storage)

    result = await service.resume_onboarding(novel_id="novel-1", chapters="all")

    assert result["onboarding_status"] == "chapters_pending"
    assert result["status"] == "pending"
    queued = activity_log.get_activity(str(result["activity_id"]))
    assert queued is not None
    assert queued["kind"] == "chapters"
    orchestrator.scrape_chapters.assert_not_awaited()
