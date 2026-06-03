from __future__ import annotations

import shutil
from uuid import uuid4

import pytest

from novelai.activity.queue import ActivityQueueService
from novelai.activity.worker import ActivityWorkerService
from novelai.storage.service import StorageService
from tests.conftest import TESTS_TMP_ROOT


class StubOrchestrator:
    def __init__(self, storage: StorageService, *, fail: bool = False) -> None:
        self.storage = storage
        self.fail = fail
        self.calls: list[tuple[str, tuple[object, ...], dict[str, object]]] = []

    async def scrape_metadata(self, *args: object, **kwargs: object) -> dict[str, object]:
        self.calls.append(("scrape_metadata", args, kwargs))
        if self.fail:
            raise RuntimeError("metadata failed")
        return {"chapters": [{"id": "1"}, {"id": "2"}]}

    async def scrape_chapters(self, *args: object, **kwargs: object) -> None:
        self.calls.append(("scrape_chapters", args, kwargs))
        if self.fail:
            raise RuntimeError("chapters failed")

    async def translate_chapters(self, *args: object, **kwargs: object) -> None:
        self.calls.append(("translate_chapters", args, kwargs))
        if self.fail:
            raise RuntimeError("translation failed")


@pytest.fixture
def worker_env():
    TESTS_TMP_ROOT.mkdir(parents=True, exist_ok=True)
    data_dir = TESTS_TMP_ROOT / f"worker_{uuid4().hex}"
    data_dir.mkdir(parents=True, exist_ok=False)
    storage = StorageService(data_dir)
    activity_log = ActivityQueueService(data_dir)
    orchestrator = StubOrchestrator(storage)
    yield storage, activity_log, orchestrator, ActivityWorkerService(activity_log, orchestrator)
    shutil.rmtree(data_dir, ignore_errors=True)


@pytest.mark.asyncio
async def test_run_crawl_metadata_activity(worker_env) -> None:
    _storage, activity_log, orchestrator, worker = worker_env
    activity = activity_log.create_crawl_activity(
        novel_id="novel-1",
        source_key="syosetu_ncode",
        kind="metadata",
        metadata={"max_chapter": 2},
    )

    result = await worker.run_activity(activity["id"])

    assert result is not None
    assert result["status"] == "completed"
    assert result["metadata"]["activity_subtype"] == "crawling"
    assert result["metadata"]["activity_phase"] == "metadata_crawl"
    assert result["metadata"]["result"]["chapter_count"] == 2
    health = activity_log.get_source_health("syosetu_ncode")
    assert health is not None
    assert health["success_count"] == 1
    assert health["failure_count"] == 0
    assert orchestrator.calls[0][0] == "scrape_metadata"
    assert orchestrator.calls[0][1][:2] == ("syosetu_ncode", "novel-1")
    assert orchestrator.calls[0][2]["max_chapter"] == 2


@pytest.mark.asyncio
async def test_run_translation_activity_uses_stored_metadata_source(worker_env) -> None:
    storage, activity_log, orchestrator, worker = worker_env
    storage.save_metadata("novel-1", {"source": "kakuyomu", "chapters": [{"id": "1"}]})
    activity = activity_log.create_translation_activity(novel_id="novel-1", chapters="1", provider="openai", model="gpt-5.4")

    result = await worker.run_activity(activity["id"])

    assert result is not None
    assert result["status"] == "completed"
    assert result["metadata"]["activity_subtype"] == "translating"
    assert result["metadata"]["activity_phase"] == "translate"
    assert orchestrator.calls[0][0] == "translate_chapters"
    assert orchestrator.calls[0][1][:3] == ("kakuyomu", "novel-1", "1")
    assert orchestrator.calls[0][2]["provider_key"] == "openai"


@pytest.mark.asyncio
async def test_run_failed_activity_records_error(worker_env) -> None:
    _storage, activity_log, orchestrator, _worker = worker_env
    failing_worker = ActivityWorkerService(activity_log, StubOrchestrator(orchestrator.storage, fail=True))
    activity = activity_log.create_crawl_activity(novel_id="novel-1", source_key="syosetu_ncode", kind="chapters")

    result = await failing_worker.run_activity(activity["id"])

    assert result is not None
    assert result["status"] == "failed"
    assert result["error"] == "chapters failed"
    assert result["retry_count"] == 1
    assert result["metadata"]["activity_subtype"] == "scraping"
    assert result["metadata"]["activity_phase"] == "chapter_scrape"
    assert result["metadata"]["failure_code"] == "SCRAPE_ACTIVITY_FAILED"
    health = activity_log.get_source_health("syosetu_ncode")
    assert health is not None
    assert health["success_count"] == 0
    assert health["failure_count"] == 1
    assert health["last_error"] == "chapters failed"
