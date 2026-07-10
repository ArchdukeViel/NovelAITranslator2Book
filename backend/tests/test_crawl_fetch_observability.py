"""Crawl and fetch observability tests.

Covers:
- `metadata.crawl_result` persistence after non-fatal crawl completion
- Per-chapter failure enrichment (`error_category`, `http_status_code`, `retry_attempts`)
- Running crawl progress under `metadata.progress`
- Image download failure counting (affected-chapter semantics)
- Source-health enrichment from stored crawl results
- Source-health cache invalidation on activity mutation
- Retry callback contract (1-indexed, before backoff, swallowed exceptions)

No real HTTP. All sources are fake adapters.
"""

from __future__ import annotations

import shutil
from collections.abc import Mapping
from typing import Any
from uuid import uuid4

import pytest

from novelai.activity.queue import ActivityQueueService
from novelai.activity.worker import ActivityWorkerService
from novelai.core.errors import SourceError
from novelai.services.novel_orchestration_service import NovelOrchestrationService
from novelai.services.preferences_service import PreferencesService
from novelai.services.translation_cache import TranslationCache
from novelai.services.usage_service import UsageService
from novelai.sources.base import SourceAdapter
from novelai.storage.service import StorageService
from novelai.infrastructure.http.retry import Retrier, RetryConfig, RetryError
from tests.conftest import TESTS_TMP_ROOT

# ---------------------------------------------------------------------------
# Fake source adapter
# ---------------------------------------------------------------------------


class FakeSource(SourceAdapter):
    """Configurable fake source for observability tests."""

    def __init__(
        self,
        *,
        source_key: str = "test_source",
        chapter_payloads: dict[str, dict[str, Any]] | None = None,
        fetch_errors: dict[str, Exception] | None = None,
        retry_callbacks: list[tuple[int, Exception]] | None = None,
    ) -> None:
        self._source_key = source_key
        self._chapter_payloads = chapter_payloads or {}
        self._fetch_errors = fetch_errors or {}
        self._retry_callbacks = retry_callbacks or []
        self.fetch_count = 0

    @property
    def key(self) -> str:
        return self._source_key

    async def fetch_metadata(self, url: str, *, max_chapter: int | None = None) -> dict[str, Any]:
        novel_id = url
        return {
            "novel_id": novel_id,
            "title": f"Test Novel {novel_id}",
            "author": "Test Author",
            "source": self._source_key,
            "chapters": [
                {"id": str(i), "num": i, "title": f"Chapter {i}", "url": f"http://example.test/{novel_id}/{i}"}
                for i in range(1, 4)
            ],
        }

    async def fetch_chapter(self, url: str) -> str:
        self.fetch_count += 1
        if url in self._fetch_errors:
            raise self._fetch_errors[url]
        return self._chapter_payloads.get(url, {}).get("text", f"Content for {url}")

    async def fetch_chapter_payload(
        self, url: str, *, on_retry: Any = None
    ) -> Mapping[str, Any]:
        self.fetch_count += 1
        if url in self._fetch_errors:
            raise self._fetch_errors[url]
        payload = self._chapter_payloads.get(url, {})
        return {
            "text": payload.get("text", f"Content for {url}"),
            "images": payload.get("images", []),
        }

    async def fetch_asset(self, url: str, *, referer: str | None = None) -> Mapping[str, Any]:
        """Stub asset fetch — returns empty bytes to avoid real HTTP."""
        return {"url": url, "content": b"", "content_type": "image/png"}


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_tmp_dir() -> Any:
    TESTS_TMP_ROOT.mkdir(parents=True, exist_ok=True)
    data_dir = TESTS_TMP_ROOT / f"observability_{uuid4().hex}"
    data_dir.mkdir(parents=True, exist_ok=False)
    return data_dir


@pytest.fixture
def activity_log() -> Any:  # type: ignore[reportInvalidTypeForm]
    data_dir = _make_tmp_dir()
    service = ActivityQueueService(data_dir)
    yield service
    shutil.rmtree(data_dir, ignore_errors=True)


@pytest.fixture
def storage() -> Any:  # type: ignore[reportInvalidTypeForm]
    data_dir = _make_tmp_dir()
    service = StorageService(data_dir)
    yield service
    shutil.rmtree(data_dir, ignore_errors=True)


@pytest.fixture(autouse=True)
def _stub_catalog_projection(monkeypatch: pytest.MonkeyPatch) -> None:
    """Stub catalog projection refresh to avoid DB connection in unit tests."""
    from novelai.services import catalog_service
    from novelai.services.orchestration import crawler as crawler_module

    def _noop(
        novel_id: str,
        storage: Any,
        *,
        context: str,
        session: Any = None,
        session_scope_factory: Any = None,
    ) -> bool:
        return False

    monkeypatch.setattr(
        catalog_service, "safely_refresh_catalog_projection_after_storage_write", _noop
    )
    monkeypatch.setattr(
        crawler_module, "safely_refresh_catalog_projection_after_storage_write", _noop
    )


def _make_orchestrator(
    storage: StorageService,
    source: SourceAdapter,
) -> NovelOrchestrationService:
    return NovelOrchestrationService(
        storage=storage,
        translation=_NoopTranslationService(),  # type: ignore[arg-type]
        source_factory=lambda _key: source,
        settings_service=PreferencesService(),
        translation_cache=TranslationCache(storage.base_dir),
        usage_service=UsageService(storage.base_dir),
    )


class _NoopTranslationService:
    """Minimal translation service stub — not used by crawl tests."""

    async def translate_chapters(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
        return {"status": "noop"}


def _seed_metadata(storage: StorageService, novel_id: str, chapters: int = 3) -> dict[str, Any]:
    meta = {
        "novel_id": novel_id,
        "title": f"Test Novel {novel_id}",
        "author": "Test Author",
        "source": "test_source",
        "chapters": [
            {"id": str(i), "num": i, "title": f"Chapter {i}", "url": f"http://example.test/{novel_id}/{i}"}
            for i in range(1, chapters + 1)
        ],
    }
    storage.save_metadata(novel_id, meta)
    return meta


def _make_crawl_activity(
    activity_log: ActivityQueueService,
    *,
    novel_id: str = "novel-1",
    source_key: str = "test_source",
    kind: str = "chapters",
    chapters: str = "all",
) -> dict[str, Any]:
    return activity_log.create_crawl_activity(
        novel_id=novel_id,
        source_key=source_key,
        kind=kind,
        chapters=chapters,
    )


# ---------------------------------------------------------------------------
# Task 15: Crawl Result Tests
# ---------------------------------------------------------------------------


class TestCrawlResultPersistence:
    """metadata.crawl_result is persisted after non-fatal crawl completion."""

    @pytest.mark.asyncio
    async def test_crawl_result_persisted_in_activity(self, storage: StorageService) -> None:
        _seed_metadata(storage, "novel-1", chapters=3)
        source = FakeSource(
            chapter_payloads={
                "http://example.test/novel-1/1": {"text": "Chapter 1 content"},
                "http://example.test/novel-1/2": {"text": "Chapter 2 content"},
                "http://example.test/novel-1/3": {"text": "Chapter 3 content"},
            }
        )
        orchestrator = _make_orchestrator(storage, source)  # type: ignore[arg-type]
        data_dir = _make_tmp_dir()
        try:
            activity_log = ActivityQueueService(data_dir)
            activity = _make_crawl_activity(activity_log)
            worker = ActivityWorkerService(activity_log, orchestrator)  # type: ignore[arg-type]

            await worker.run_activity(activity["id"])

            loaded = activity_log.get_activity(activity["id"])
            assert loaded is not None
            crawl_result = loaded.get("metadata", {}).get("crawl_result")
            assert isinstance(crawl_result, dict)
            assert crawl_result["succeeded"] == 3
            assert crawl_result["skipped"] == 0
            assert crawl_result["failed"] == 0
            assert crawl_result["failures"] == []
            assert crawl_result["image_download_failures"] == 0
        finally:
            shutil.rmtree(data_dir, ignore_errors=True)

    @pytest.mark.asyncio
    async def test_crawl_result_includes_all_required_fields(self, storage: StorageService) -> None:
        _seed_metadata(storage, "novel-1", chapters=2)
        source = FakeSource(
            fetch_errors={"http://example.test/novel-1/2": SourceError("HTTP 429 Too Many Requests")}
        )
        orchestrator = _make_orchestrator(storage, source)  # type: ignore[arg-type]
        data_dir = _make_tmp_dir()
        try:
            activity_log = ActivityQueueService(data_dir)
            activity = _make_crawl_activity(activity_log)
            worker = ActivityWorkerService(activity_log, orchestrator)  # type: ignore[arg-type]

            await worker.run_activity(activity["id"])

            loaded = activity_log.get_activity(activity["id"])
            assert loaded is not None
            crawl_result = loaded["metadata"]["crawl_result"]
            for key in ("succeeded", "skipped", "failed", "failures", "image_download_failures"):
                assert key in crawl_result, f"crawl_result missing {key}"
            assert crawl_result["succeeded"] == 1
            assert crawl_result["failed"] == 1
            assert len(crawl_result["failures"]) == 1
        finally:
            shutil.rmtree(data_dir, ignore_errors=True)

    @pytest.mark.asyncio
    async def test_failure_records_preserve_existing_fields(self, storage: StorageService) -> None:
        _seed_metadata(storage, "novel-1", chapters=1)
        source = FakeSource(
            fetch_errors={"http://example.test/novel-1/1": SourceError("timeout")}
        )
        orchestrator = _make_orchestrator(storage, source)  # type: ignore[arg-type]
        data_dir = _make_tmp_dir()
        try:
            activity_log = ActivityQueueService(data_dir)
            activity = _make_crawl_activity(activity_log)
            worker = ActivityWorkerService(activity_log, orchestrator)  # type: ignore[arg-type]

            await worker.run_activity(activity["id"])

            loaded = activity_log.get_activity(activity["id"])
            assert loaded is not None
            failure = loaded["metadata"]["crawl_result"]["failures"][0]
            for field in ("chapter_id", "chapter_number", "title", "source_url", "error_type", "error_message"):
                assert field in failure, f"failure record missing {field}"
        finally:
            shutil.rmtree(data_dir, ignore_errors=True)

    @pytest.mark.asyncio
    async def test_fatal_crawl_error_leaves_crawl_result_absent(self, storage: StorageService) -> None:
        _seed_metadata(storage, "novel-1", chapters=2)

        class _FailingOrchestrator:
            def __init__(self, storage: StorageService) -> None:
                self.storage = storage

            async def scrape_chapters(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
                raise RuntimeError("fatal crawl failure")

        data_dir = _make_tmp_dir()
        try:
            activity_log = ActivityQueueService(data_dir)
            activity = _make_crawl_activity(activity_log)
            worker = ActivityWorkerService(activity_log, _FailingOrchestrator(storage))  # type: ignore[arg-type]

            await worker.run_activity(activity["id"])

            loaded = activity_log.get_activity(activity["id"])
            assert loaded is not None
            assert loaded["status"] == "failed"
            assert "crawl_result" not in loaded.get("metadata", {})
        finally:
            shutil.rmtree(data_dir, ignore_errors=True)

    @pytest.mark.asyncio
    async def test_fatal_crawl_error_sets_top_level_activity_error(self, storage: StorageService) -> None:
        _seed_metadata(storage, "novel-1", chapters=2)

        class _FailingOrchestrator:
            def __init__(self, storage: StorageService) -> None:
                self.storage = storage

            async def scrape_chapters(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
                raise RuntimeError("fatal crawl failure")

        data_dir = _make_tmp_dir()
        try:
            activity_log = ActivityQueueService(data_dir)
            activity = _make_crawl_activity(activity_log)
            worker = ActivityWorkerService(activity_log, _FailingOrchestrator(storage))  # type: ignore[arg-type]

            await worker.run_activity(activity["id"])

            loaded = activity_log.get_activity(activity["id"])
            assert loaded is not None
            assert loaded["error"] == "fatal crawl failure"
        finally:
            shutil.rmtree(data_dir, ignore_errors=True)

    @pytest.mark.asyncio
    async def test_final_crawl_result_preserves_progress(self, storage: StorageService) -> None:
        _seed_metadata(storage, "novel-1", chapters=2)
        source = FakeSource(
            chapter_payloads={
                "http://example.test/novel-1/1": {"text": "Chapter 1"},
                "http://example.test/novel-1/2": {"text": "Chapter 2"},
            }
        )
        orchestrator = _make_orchestrator(storage, source)  # type: ignore[arg-type]
        data_dir = _make_tmp_dir()
        try:
            activity_log = ActivityQueueService(data_dir)
            activity = _make_crawl_activity(activity_log)
            worker = ActivityWorkerService(activity_log, orchestrator)  # type: ignore[arg-type]

            await worker.run_activity(activity["id"])

            loaded = activity_log.get_activity(activity["id"])
            assert loaded is not None
            metadata = loaded["metadata"]
            assert "progress" in metadata
            assert "crawl_result" in metadata
            assert metadata["progress"]["total"] == 2
        finally:
            shutil.rmtree(data_dir, ignore_errors=True)


# ---------------------------------------------------------------------------
# Task 16: Failure Telemetry Tests
# ---------------------------------------------------------------------------


class TestFailureClassification:
    """_classify_error and _extract_http_status produce correct categories."""

    def test_rate_limited_from_http_status(self) -> None:
        from novelai.services.orchestration.crawler import _classify_error

        assert _classify_error(SourceError("rate limit"), "rate limit", 429) == "rate_limited"

    def test_rate_limited_from_text(self) -> None:
        from novelai.services.orchestration.crawler import _classify_error

        assert _classify_error(Exception("Too Many Requests - rate limited"), "rate limited", None) == "rate_limited"

    def test_not_found_from_http_status(self) -> None:
        from novelai.services.orchestration.crawler import _classify_error

        assert _classify_error(SourceError("not found"), "not found", 404) == "not_found"

    def test_not_found_from_text(self) -> None:
        from novelai.services.orchestration.crawler import _classify_error

        assert _classify_error(Exception("page not found"), "page not found", None) == "not_found"

    def test_timeout_from_text(self) -> None:
        from novelai.services.orchestration.crawler import _classify_error

        assert _classify_error(Exception("connection timeout"), "connection timeout", None) == "timeout"

    def test_server_error_from_http_status(self) -> None:
        from novelai.services.orchestration.crawler import _classify_error

        assert _classify_error(Exception("server error"), "server error", 503) == "server_error"

    def test_server_error_500_range(self) -> None:
        from novelai.services.orchestration.crawler import _classify_error

        assert _classify_error(Exception("500"), "500", 500) == "server_error"
        assert _classify_error(Exception("599"), "599", 599) == "server_error"

    def test_quality_gate_classification(self) -> None:
        from novelai.services.orchestration.crawler import _classify_error

        exc = SourceError("Chapter quality gate failed for test/novel-1/1: empty content")
        assert _classify_error(exc, str(exc), None) == "quality_gate"

    def test_fetch_error_for_source_error(self) -> None:
        from novelai.services.orchestration.crawler import _classify_error

        assert _classify_error(SourceError("generic fetch fail"), "generic fetch fail", None) == "fetch_error"

    def test_unknown_for_unrecognized(self) -> None:
        from novelai.services.orchestration.crawler import _classify_error

        assert _classify_error(ValueError("weird"), "weird", None) == "unknown"


class TestExtractHttpStatus:
    """_extract_http_status parses status from exceptions and messages."""

    def test_status_from_response_attribute(self) -> None:
        from novelai.services.orchestration.crawler import _extract_http_status

        class _FakeResponse:
            status_code = 503

        class _FakeExc(Exception):
            response = _FakeResponse()

        assert _extract_http_status(_FakeExc()) == 503

    def test_status_from_status_code_attribute(self) -> None:
        from novelai.services.orchestration.crawler import _extract_http_status

        class _FakeExc(Exception):
            status_code = 429

        assert _extract_http_status(_FakeExc()) == 429

    def test_status_from_message_status_equals(self) -> None:
        from novelai.services.orchestration.crawler import _extract_http_status

        assert _extract_http_status(Exception("error status=503 occurred")) == 503

    def test_status_from_message_status_code_equals(self) -> None:
        from novelai.services.orchestration.crawler import _extract_http_status

        assert _extract_http_status(Exception("error status_code=503 occurred")) == 503

    def test_status_from_message_http_prefix(self) -> None:
        from novelai.services.orchestration.crawler import _extract_http_status

        assert _extract_http_status(Exception("HTTP 503 Service Unavailable")) == 503

    def test_status_from_message_standalone_429(self) -> None:
        from novelai.services.orchestration.crawler import _extract_http_status

        assert _extract_http_status(Exception("got 429 from server")) == 429

    def test_status_from_message_standalone_404(self) -> None:
        from novelai.services.orchestration.crawler import _extract_http_status

        assert _extract_http_status(Exception("returned 404")) == 404

    def test_status_returns_none_when_unparseable(self) -> None:
        from novelai.services.orchestration.crawler import _extract_http_status

        assert _extract_http_status(Exception("unknown error")) is None


class TestRetryCallback:
    """Retrier.execute_async on_retry contract."""

    @pytest.mark.asyncio
    async def test_three_attempt_exhausted_records_retry_attempts_2(self) -> None:
        calls: list[tuple[int, Exception]] = []

        def _on_retry(retry_number: int, exc: Exception) -> None:
            calls.append((retry_number, exc))

        config = RetryConfig(max_attempts=3, initial_delay=0.01, jitter=False)
        retrier = Retrier(config)

        async def always_fail() -> None:
            raise RuntimeError("fail")

        with pytest.raises(RetryError):
            await retrier.execute_async(always_fail, on_retry=_on_retry)

        assert len(calls) == 2
        assert calls[0][0] == 1
        assert calls[1][0] == 2

    @pytest.mark.asyncio
    async def test_on_retry_not_called_on_initial_attempt(self) -> None:
        calls: list[tuple[int, Exception]] = []

        def _on_retry(retry_number: int, exc: Exception) -> None:
            calls.append((retry_number, exc))

        config = RetryConfig(max_attempts=3, initial_delay=0.01, jitter=False)
        retrier = Retrier(config)

        async def succeed_first_time() -> str:
            return "ok"

        result = await retrier.execute_async(succeed_first_time, on_retry=_on_retry)
        assert result == "ok"
        assert calls == []

    @pytest.mark.asyncio
    async def test_on_retry_not_called_after_final_attempt(self) -> None:
        calls: list[tuple[int, Exception]] = []

        def _on_retry(retry_number: int, exc: Exception) -> None:
            calls.append((retry_number, exc))

        config = RetryConfig(max_attempts=2, initial_delay=0.01, jitter=False)
        retrier = Retrier(config)

        async def always_fail() -> None:
            raise RuntimeError("fail")

        with pytest.raises(RetryError):
            await retrier.execute_async(always_fail, on_retry=_on_retry)

        # Only 1 retry callback (before 2nd attempt), not after final exhaustion
        assert len(calls) == 1
        assert calls[0][0] == 1

    @pytest.mark.asyncio
    async def test_on_retry_exception_does_not_break_retry(self) -> None:
        config = RetryConfig(max_attempts=3, initial_delay=0.01, jitter=False)
        retrier = Retrier(config)
        call_count = [0]

        def bad_callback(retry_number: int, exc: Exception) -> None:
            call_count[0] += 1
            raise RuntimeError("callback itself failed")

        async def fail_twice_then_succeed() -> str:
            if call_count[0] < 2:
                raise RuntimeError("transient")
            return "recovered"

        result = await retrier.execute_async(fail_twice_then_succeed, on_retry=bad_callback)
        assert result == "recovered"
        assert call_count[0] == 2

    @pytest.mark.asyncio
    async def test_no_on_retry_preserves_behavior(self) -> None:
        config = RetryConfig(max_attempts=2, initial_delay=0.01, jitter=False)
        retrier = Retrier(config)

        async def always_fail() -> None:
            raise RuntimeError("fail")

        with pytest.raises(RetryError):
            await retrier.execute_async(always_fail)


# ---------------------------------------------------------------------------
# Task 17: Progress Tests
# ---------------------------------------------------------------------------


class TestProgressMetadata:
    """metadata.progress is updated during crawl."""

    @pytest.mark.asyncio
    async def test_progress_callback_updates_activity_metadata(self, storage: StorageService) -> None:
        _seed_metadata(storage, "novel-1", chapters=3)
        source = FakeSource(
            chapter_payloads={
                f"http://example.test/novel-1/{i}": {"text": f"Chapter {i}"}
                for i in range(1, 4)
            }
        )
        orchestrator = _make_orchestrator(storage, source)  # type: ignore[arg-type]
        data_dir = _make_tmp_dir()
        try:
            activity_log = ActivityQueueService(data_dir)
            activity = _make_crawl_activity(activity_log)
            worker = ActivityWorkerService(activity_log, orchestrator)  # type: ignore[arg-type]

            await worker.run_activity(activity["id"])

            loaded = activity_log.get_activity(activity["id"])
            assert loaded is not None
            progress = loaded["metadata"]["progress"]
            assert "completed" in progress
            assert "total" in progress
            assert "current_label" in progress
        finally:
            shutil.rmtree(data_dir, ignore_errors=True)

    @pytest.mark.asyncio
    async def test_progress_stored_under_metadata_progress(self, storage: StorageService) -> None:
        _seed_metadata(storage, "novel-1", chapters=2)
        source = FakeSource(
            chapter_payloads={
                "http://example.test/novel-1/1": {"text": "Chapter 1"},
                "http://example.test/novel-1/2": {"text": "Chapter 2"},
            }
        )
        orchestrator = _make_orchestrator(storage, source)  # type: ignore[arg-type]
        data_dir = _make_tmp_dir()
        try:
            activity_log = ActivityQueueService(data_dir)
            activity = _make_crawl_activity(activity_log)
            worker = ActivityWorkerService(activity_log, orchestrator)  # type: ignore[arg-type]

            await worker.run_activity(activity["id"])

            loaded = activity_log.get_activity(activity["id"])
            assert loaded is not None
            metadata = loaded["metadata"]
            assert isinstance(metadata.get("progress"), dict)
            assert metadata["progress"]["total"] == 2
        finally:
            shutil.rmtree(data_dir, ignore_errors=True)

    @pytest.mark.asyncio
    async def test_progress_increments_after_success(self, storage: StorageService) -> None:
        _seed_metadata(storage, "novel-1", chapters=3)
        source = FakeSource(
            chapter_payloads={
                f"http://example.test/novel-1/{i}": {"text": f"Chapter {i}"}
                for i in range(1, 4)
            }
        )
        orchestrator = _make_orchestrator(storage, source)  # type: ignore[arg-type]
        data_dir = _make_tmp_dir()
        try:
            activity_log = ActivityQueueService(data_dir)
            activity = _make_crawl_activity(activity_log)
            worker = ActivityWorkerService(activity_log, orchestrator)  # type: ignore[arg-type]

            await worker.run_activity(activity["id"])

            loaded = activity_log.get_activity(activity["id"])
            assert loaded is not None
            progress = loaded["metadata"]["progress"]
            # completed is a positive integer that increases as the crawl progresses
            assert isinstance(progress["completed"], int)
            assert progress["completed"] > 0
        finally:
            shutil.rmtree(data_dir, ignore_errors=True)

    @pytest.mark.asyncio
    async def test_progress_increments_after_per_chapter_failure(self, storage: StorageService) -> None:
        _seed_metadata(storage, "novel-1", chapters=2)
        source = FakeSource(
            fetch_errors={"http://example.test/novel-1/1": SourceError("fetch failed")}
        )
        orchestrator = _make_orchestrator(storage, source)  # type: ignore[arg-type]
        data_dir = _make_tmp_dir()
        try:
            activity_log = ActivityQueueService(data_dir)
            activity = _make_crawl_activity(activity_log)
            worker = ActivityWorkerService(activity_log, orchestrator)  # type: ignore[arg-type]

            await worker.run_activity(activity["id"])

            loaded = activity_log.get_activity(activity["id"])
            assert loaded is not None
            progress = loaded["metadata"]["progress"]
            # completed is a positive integer that increases even when chapters fail
            assert isinstance(progress["completed"], int)
            assert progress["completed"] > 0
        finally:
            shutil.rmtree(data_dir, ignore_errors=True)


# ---------------------------------------------------------------------------
# Task 18: Image Failure Tests
# ---------------------------------------------------------------------------


class TestImageDownloadFailures:
    """image_download_failures counts affected chapters."""

    @pytest.mark.asyncio
    async def test_one_image_error_counts_as_one(self, storage: StorageService) -> None:
        _seed_metadata(storage, "novel-1", chapters=1)
        source = FakeSource(
            chapter_payloads={
                "http://example.test/novel-1/1": {
                    "text": "Chapter 1",
                    "images": [{"original_url": "http://example.test/img1.png", "index": 0}],
                }
            }
        )
        orchestrator = _make_orchestrator(storage, source)  # type: ignore[arg-type]
        data_dir = _make_tmp_dir()
        try:
            activity_log = ActivityQueueService(data_dir)
            activity = _make_crawl_activity(activity_log)
            worker = ActivityWorkerService(activity_log, orchestrator)  # type: ignore[arg-type]

            await worker.run_activity(activity["id"])

            loaded = activity_log.get_activity(activity["id"])
            assert loaded is not None
            crawl_result = loaded["metadata"]["crawl_result"]
            # Image fetch will fail (no real HTTP), so image_download_failures == 1
            assert crawl_result["image_download_failures"] == 1
        finally:
            shutil.rmtree(data_dir, ignore_errors=True)

    @pytest.mark.asyncio
    async def test_multiple_image_errors_in_one_chapter_count_as_one(self, storage: StorageService) -> None:
        _seed_metadata(storage, "novel-1", chapters=1)
        source = FakeSource(
            chapter_payloads={
                "http://example.test/novel-1/1": {
                    "text": "Chapter 1",
                    "images": [
                        {"original_url": "http://example.test/img1.png", "index": 0},
                        {"original_url": "http://example.test/img2.png", "index": 1},
                        {"original_url": "http://example.test/img3.png", "index": 2},
                    ],
                }
            }
        )
        orchestrator = _make_orchestrator(storage, source)  # type: ignore[arg-type]
        data_dir = _make_tmp_dir()
        try:
            activity_log = ActivityQueueService(data_dir)
            activity = _make_crawl_activity(activity_log)
            worker = ActivityWorkerService(activity_log, orchestrator)  # type: ignore[arg-type]

            await worker.run_activity(activity["id"])

            loaded = activity_log.get_activity(activity["id"])
            assert loaded is not None
            crawl_result = loaded["metadata"]["crawl_result"]
            assert crawl_result["image_download_failures"] == 1
        finally:
            shutil.rmtree(data_dir, ignore_errors=True)

    @pytest.mark.asyncio
    async def test_multiple_affected_chapters_count_separately(self, storage: StorageService) -> None:
        _seed_metadata(storage, "novel-1", chapters=2)
        source = FakeSource(
            chapter_payloads={
                "http://example.test/novel-1/1": {
                    "text": "Chapter 1",
                    "images": [{"original_url": "http://example.test/img1.png", "index": 0}],
                },
                "http://example.test/novel-1/2": {
                    "text": "Chapter 2",
                    "images": [{"original_url": "http://example.test/img2.png", "index": 0}],
                },
            }
        )
        orchestrator = _make_orchestrator(storage, source)  # type: ignore[arg-type]
        data_dir = _make_tmp_dir()
        try:
            activity_log = ActivityQueueService(data_dir)
            activity = _make_crawl_activity(activity_log)
            worker = ActivityWorkerService(activity_log, orchestrator)  # type: ignore[arg-type]

            await worker.run_activity(activity["id"])

            loaded = activity_log.get_activity(activity["id"])
            assert loaded is not None
            crawl_result = loaded["metadata"]["crawl_result"]
            assert crawl_result["image_download_failures"] == 2
        finally:
            shutil.rmtree(data_dir, ignore_errors=True)

    @pytest.mark.asyncio
    async def test_failed_chapter_fetch_without_payload_does_not_increase_count(
        self, storage: StorageService
    ) -> None:
        _seed_metadata(storage, "novel-1", chapters=2)
        source = FakeSource(
            fetch_errors={"http://example.test/novel-1/1": SourceError("fetch failed")},
            chapter_payloads={
                "http://example.test/novel-1/2": {"text": "Chapter 2"},
            },
        )
        orchestrator = _make_orchestrator(storage, source)  # type: ignore[arg-type]
        data_dir = _make_tmp_dir()
        try:
            activity_log = ActivityQueueService(data_dir)
            activity = _make_crawl_activity(activity_log)
            worker = ActivityWorkerService(activity_log, orchestrator)  # type: ignore[arg-type]

            await worker.run_activity(activity["id"])

            loaded = activity_log.get_activity(activity["id"])
            assert loaded is not None
            crawl_result = loaded["metadata"]["crawl_result"]
            # Chapter 1 failed fetch (no payload saved), Chapter 2 succeeded with no images
            assert crawl_result["image_download_failures"] == 0
        finally:
            shutil.rmtree(data_dir, ignore_errors=True)


# ---------------------------------------------------------------------------
# Task 19: Source Health Tests
# ---------------------------------------------------------------------------


class TestSourceHealthEnrichment:
    """Source health aggregates crawl_result data from activities."""

    def test_source_health_includes_enriched_fields(self, activity_log: ActivityQueueService) -> None:
        activity_log._persist_activity(
            [
                {
                    "id": "crawl-1",
                    "type": "crawl",
                    "kind": "chapters",
                    "novel_id": "novel-1",
                    "source_key": "test_source",
                    "status": "completed",
                    "created_at": "2026-07-01T00:00:00Z",
                    "started_at": "2026-07-01T00:00:00Z",
                    "finished_at": "2026-07-01T00:01:00Z",
                    "metadata": {
                        "crawl_result": {
                            "succeeded": 10,
                            "skipped": 2,
                            "failed": 3,
                            "failures": [
                                {"error_category": "rate_limited", "http_status_code": 429},
                                {"error_category": "timeout", "http_status_code": None},
                                {"error_category": "rate_limited", "http_status_code": 429},
                            ],
                            "image_download_failures": 1,
                        }
                    },
                }
            ]
        )

        health = activity_log.get_source_health("test_source")
        assert health is not None
        assert health["total_chapters_attempted"] == 15
        assert health["total_chapters_succeeded"] == 10
        assert health["total_chapters_failed"] == 3
        assert health["error_category_counts"] == {"rate_limited": 2, "timeout": 1}
        assert health["http_status_counts"] == {"429": 2}
        assert health["last_crawl_at"] == "2026-07-01T00:01:00Z"

    def test_source_health_ignores_activities_without_crawl_result(
        self, activity_log: ActivityQueueService
    ) -> None:
        activity_log._persist_activity(
            [
                {
                    "id": "crawl-1",
                    "type": "crawl",
                    "kind": "chapters",
                    "novel_id": "novel-1",
                    "source_key": "test_source",
                    "status": "completed",
                    "metadata": {},
                }
            ]
        )

        health = activity_log.get_source_health("test_source")
        # No crawl_result, no legacy health → None
        assert health is None

    def test_source_health_ignores_non_dict_crawl_result(self, activity_log: ActivityQueueService) -> None:
        activity_log._persist_activity(
            [
                {
                    "id": "crawl-1",
                    "type": "crawl",
                    "source_key": "test_source",
                    "status": "completed",
                    "metadata": {"crawl_result": "not a dict"},
                }
            ]
        )

        health = activity_log.get_source_health("test_source")
        assert health is None

    def test_list_source_health_groups_by_source_key(self, activity_log: ActivityQueueService) -> None:
        activity_log._persist_activity(
            [
                {
                    "id": "crawl-1",
                    "type": "crawl",
                    "source_key": "source_a",
                    "status": "completed",
                    "finished_at": "2026-07-01T00:00:00Z",
                    "metadata": {
                        "crawl_result": {
                            "succeeded": 5,
                            "skipped": 0,
                            "failed": 1,
                            "failures": [{"error_category": "not_found", "http_status_code": 404}],
                            "image_download_failures": 0,
                        }
                    },
                },
                {
                    "id": "crawl-2",
                    "type": "crawl",
                    "source_key": "source_b",
                    "status": "completed",
                    "finished_at": "2026-07-02T00:00:00Z",
                    "metadata": {
                        "crawl_result": {
                            "succeeded": 3,
                            "skipped": 1,
                            "failed": 0,
                            "failures": [],
                            "image_download_failures": 0,
                        }
                    },
                },
            ]
        )

        all_health = activity_log.list_source_health()
        sources = {h["source_key"] for h in all_health}
        assert sources == {"source_a", "source_b"}

        source_a = next(h for h in all_health if h["source_key"] == "source_a")
        assert source_a["total_chapters_succeeded"] == 5
        assert source_a["total_chapters_failed"] == 1
        assert source_a["error_category_counts"] == {"not_found": 1}

    def test_list_source_health_aggregates_multiple_activities(
        self, activity_log: ActivityQueueService
    ) -> None:
        activity_log._persist_activity(
            [
                {
                    "id": "crawl-1",
                    "type": "crawl",
                    "source_key": "test_source",
                    "status": "completed",
                    "finished_at": "2026-07-01T00:00:00Z",
                    "metadata": {
                        "crawl_result": {
                            "succeeded": 5,
                            "skipped": 0,
                            "failed": 1,
                            "failures": [{"error_category": "rate_limited", "http_status_code": 429}],
                            "image_download_failures": 0,
                        }
                    },
                },
                {
                    "id": "crawl-2",
                    "type": "crawl",
                    "source_key": "test_source",
                    "status": "completed",
                    "finished_at": "2026-07-02T00:00:00Z",
                    "metadata": {
                        "crawl_result": {
                            "succeeded": 3,
                            "skipped": 0,
                            "failed": 2,
                            "failures": [
                                {"error_category": "timeout", "http_status_code": None},
                                {"error_category": "rate_limited", "http_status_code": 429},
                            ],
                            "image_download_failures": 0,
                        }
                    },
                },
            ]
        )

        health = activity_log.get_source_health("test_source")
        assert health is not None
        assert health["total_chapters_succeeded"] == 8
        assert health["total_chapters_failed"] == 3
        assert health["error_category_counts"] == {"rate_limited": 2, "timeout": 1}
        assert health["http_status_counts"] == {"429": 2}
        assert health["last_crawl_at"] == "2026-07-02T00:00:00Z"


class TestSourceHealthCache:
    """Source-health cache invalidates on activity mutation."""

    def test_cache_invalidates_after_update_activity_metadata(
        self, activity_log: ActivityQueueService
    ) -> None:
        activity_log._persist_activity(
            [
                {
                    "id": "crawl-1",
                    "type": "crawl",
                    "source_key": "test_source",
                    "status": "running",
                    "metadata": {},
                }
            ]
        )

        # Prime cache
        health_before = activity_log.get_source_health("test_source")
        assert health_before is None

        # Mutate metadata with crawl_result
        activity_log.update_activity_metadata(
            "crawl-1",
            {
                "crawl_result": {
                    "succeeded": 1,
                    "skipped": 0,
                    "failed": 0,
                    "failures": [],
                    "image_download_failures": 0,
                }
            },
        )

        # Cache should be invalidated — new query sees the crawl_result
        health_after = activity_log.get_source_health("test_source")
        assert health_after is not None
        assert health_after["total_chapters_succeeded"] == 1

    def test_cache_invalidates_after_update_activity_status(
        self, activity_log: ActivityQueueService
    ) -> None:
        activity_log._persist_activity(
            [
                {
                    "id": "crawl-1",
                    "type": "crawl",
                    "source_key": "test_source",
                    "status": "running",
                    "started_at": "2026-07-01T00:00:00Z",
                    "metadata": {
                        "crawl_result": {
                            "succeeded": 2,
                            "skipped": 0,
                            "failed": 0,
                            "failures": [],
                            "image_download_failures": 0,
                        }
                    },
                }
            ]
        )

        # Prime cache — last_crawl_at falls back to started_at
        health_before = activity_log.get_source_health("test_source")
        assert health_before is not None
        assert health_before["total_chapters_succeeded"] == 2
        assert health_before["last_crawl_at"] == "2026-07-01T00:00:00Z"

        # Mutate status (adds finished_at which is later than started_at)
        activity_log.update_activity_status("crawl-1", "completed")

        # Cache invalidated — last_crawl_at should now be the finished_at timestamp
        health_after = activity_log.get_source_health("test_source")
        assert health_after is not None
        assert health_after["last_crawl_at"] is not None
        # finished_at is later than started_at, so last_crawl_at should update
        assert health_after["last_crawl_at"] != "2026-07-01T00:00:00Z"

    def test_cache_returns_same_object_within_ttl(self, activity_log: ActivityQueueService) -> None:
        activity_log._persist_activity(
            [
                {
                    "id": "crawl-1",
                    "type": "crawl",
                    "source_key": "test_source",
                    "status": "completed",
                    "finished_at": "2026-07-01T00:00:00Z",
                    "metadata": {
                        "crawl_result": {
                            "succeeded": 1,
                            "skipped": 0,
                            "failed": 0,
                            "failures": [],
                            "image_download_failures": 0,
                        }
                    },
                }
            ]
        )

        first = activity_log.list_source_health()
        second = activity_log.list_source_health()
        # Within TTL, same cached object reference
        assert first is second


# ---------------------------------------------------------------------------
# Task 15.5 / 16.10: Integration — failure record enrichment via worker
# ---------------------------------------------------------------------------


class TestFailureRecordEnrichmentIntegration:
    """End-to-end failure enrichment through the worker."""

    @pytest.mark.asyncio
    async def test_http_429_failure_records_rate_limited_and_status(self, storage: StorageService) -> None:
        _seed_metadata(storage, "novel-1", chapters=1)

        class _429Error(Exception):
            status_code = 429

            def __str__(self) -> str:
                return "HTTP 429 Too Many Requests"

        source = FakeSource(fetch_errors={"http://example.test/novel-1/1": _429Error()})
        orchestrator = _make_orchestrator(storage, source)  # type: ignore[arg-type]
        data_dir = _make_tmp_dir()
        try:
            activity_log = ActivityQueueService(data_dir)
            activity = _make_crawl_activity(activity_log)
            worker = ActivityWorkerService(activity_log, orchestrator)  # type: ignore[arg-type]

            await worker.run_activity(activity["id"])

            loaded = activity_log.get_activity(activity["id"])
            assert loaded is not None
            failure = loaded["metadata"]["crawl_result"]["failures"][0]
            assert failure["error_category"] == "rate_limited"
            assert failure["http_status_code"] == 429
        finally:
            shutil.rmtree(data_dir, ignore_errors=True)

    @pytest.mark.asyncio
    async def test_quality_gate_failure_records_quality_gate_category(
        self, storage: StorageService
    ) -> None:
        _seed_metadata(storage, "novel-1", chapters=1)
        source = FakeSource(
            fetch_errors={
                "http://example.test/novel-1/1": SourceError(
                    "Chapter quality gate failed for test_source/novel-1/1: empty content"
                )
            }
        )
        orchestrator = _make_orchestrator(storage, source)  # type: ignore[arg-type]
        data_dir = _make_tmp_dir()
        try:
            activity_log = ActivityQueueService(data_dir)
            activity = _make_crawl_activity(activity_log)
            worker = ActivityWorkerService(activity_log, orchestrator)  # type: ignore[arg-type]

            await worker.run_activity(activity["id"])

            loaded = activity_log.get_activity(activity["id"])
            assert loaded is not None
            failure = loaded["metadata"]["crawl_result"]["failures"][0]
            assert failure["error_category"] == "quality_gate"
        finally:
            shutil.rmtree(data_dir, ignore_errors=True)

    @pytest.mark.asyncio
    async def test_failure_record_includes_retry_attempts(self, storage: StorageService) -> None:
        _seed_metadata(storage, "novel-1", chapters=1)
        source = FakeSource(
            fetch_errors={"http://example.test/novel-1/1": SourceError("fetch failed")}
        )
        orchestrator = _make_orchestrator(storage, source)  # type: ignore[arg-type]
        data_dir = _make_tmp_dir()
        try:
            activity_log = ActivityQueueService(data_dir)
            activity = _make_crawl_activity(activity_log)
            worker = ActivityWorkerService(activity_log, orchestrator)  # type: ignore[arg-type]

            await worker.run_activity(activity["id"])

            loaded = activity_log.get_activity(activity["id"])
            assert loaded is not None
            failure = loaded["metadata"]["crawl_result"]["failures"][0]
            assert "retry_attempts" in failure
            assert isinstance(failure["retry_attempts"], int)
        finally:
            shutil.rmtree(data_dir, ignore_errors=True)
