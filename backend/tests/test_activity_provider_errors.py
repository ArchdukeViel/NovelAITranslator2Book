from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from novelai.activity.queue import ActivityQueueService
from novelai.activity.worker import ActivityWorkerService
from novelai.core.errors import ProviderError, ProviderErrorCode

_TMP = Path(__file__).resolve().parent / ".tmp" / "activity_provider_errors"


class _ProviderFailingOrchestrator:
    async def translate_chapters(
        self,
        source_key: str,
        novel_id: str,
        chapters: str,
        **kwargs: object,
    ) -> None:
        raise ProviderError(
            ProviderErrorCode.RATE_LIMITED,
            provider_key="gemini",
            provider_model="gemini-2.5-flash",
            message="Provider rate limit reached",
            retry_after_seconds=13,
            cooldown_until="2026-06-04T12:00:13Z",
            details={"chunk_id": "c0002", "attempt_number": 1, "raw_message": "429 RESOURCE_EXHAUSTED"},
        )


@pytest.mark.asyncio
async def test_activity_worker_records_structured_provider_failure() -> None:
    shutil.rmtree(_TMP, ignore_errors=True)
    queue = ActivityQueueService(_TMP)
    activity = queue.create_translation_activity(
        novel_id="novel1",
        source_key="kakuyomu",
        chapters="chapter_001",
        provider="gemini",
        model="gemini-2.5-flash",
        metadata={"chapter_id": "chapter_001"},
    )
    worker = ActivityWorkerService(queue, _ProviderFailingOrchestrator())  # type: ignore[arg-type]

    failed = await worker.run_activity(str(activity["id"]))

    assert failed is not None
    assert failed["status"] == "failed"
    metadata = failed["metadata"]
    assert metadata["provider_key"] == "gemini"
    assert metadata["provider_model"] == "gemini-2.5-flash"
    assert metadata["provider_error_code"] == "provider_rate_limited"
    assert metadata["retry_after_seconds"] == 13
    assert metadata["cooldown_until"] == "2026-06-04T12:00:13Z"
    provider_error = metadata["provider_error"]
    assert provider_error["activity_id"] == activity["id"]
    assert provider_error["job_id"] == activity["id"]
    assert provider_error["novel_id"] == "novel1"
    assert provider_error["chapter_id"] == "chapter_001"
    assert provider_error["chunk_id"] == "c0002"
    assert provider_error["attempt_number"] == 1
    assert provider_error["provider_error_details"]["raw_message"] == "429 RESOURCE_EXHAUSTED"
    shutil.rmtree(_TMP, ignore_errors=True)
