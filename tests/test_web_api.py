"""Tests for the FastAPI web API (auth, CORS, rate limiting, endpoints)."""

from __future__ import annotations

import shutil
from collections import defaultdict
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from novelai.runtime.bootstrap import bootstrap
from novelai.config.settings import settings
from novelai.services.job_queue_service import JobQueueService
from novelai.services.job_runner_service import BackgroundJobRunner
from novelai.services.job_worker_service import JobWorkerService
from novelai.services.novel_request_service import NovelRequestService
from novelai.services.storage_service import StorageService
from novelai.interfaces.web.api import create_app
from novelai.interfaces.web.routers.novels import (
    get_job_runner,
    get_job_worker,
    get_jobs,
    get_orchestrator,
    get_requests,
    get_storage,
)

_TMP = Path(__file__).resolve().parent / ".tmp" / "web_api"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _fresh_storage() -> StorageService:
    d = _TMP / "lib"
    d.mkdir(parents=True, exist_ok=True)
    return StorageService(d)


def _seed_novel(storage: StorageService, novel_id: str = "test-n1") -> None:
    storage.save_metadata(novel_id, {
        "novel_id": novel_id,
        "title": "Test Novel",
        "author": "Author",
        "chapters": [{"id": "1", "title": "Ch1"}, {"id": "2", "title": "Ch2"}],
    })
    storage.save_chapter(novel_id, "1", "Raw text ch1", source_key="dummy", source_url="http://example.com/1")
    storage.save_translated_chapter(novel_id, "1", "Translated ch1", provider="dummy", model="dummy")


def _make_app(
    storage: StorageService,
    jobs: JobQueueService | None = None,
    worker: JobWorkerService | None = None,
    runner: BackgroundJobRunner | None = None,
    requests: NovelRequestService | None = None,
) -> TestClient:
    """Create a TestClient with storage dependency overridden."""
    app = create_app()
    app.dependency_overrides[get_storage] = lambda: storage
    if jobs is not None:
        app.dependency_overrides[get_jobs] = lambda: jobs
    if worker is not None:
        app.dependency_overrides[get_job_worker] = lambda: worker
    if runner is not None:
        app.dependency_overrides[get_job_runner] = lambda: runner
    if requests is not None:
        app.dependency_overrides[get_requests] = lambda: requests
    return TestClient(app)


class StubJobOrchestrator:
    def __init__(self, storage: StorageService) -> None:
        self.storage = storage
        self.calls: list[tuple[str, tuple[object, ...], dict[str, object]]] = []

    async def scrape_metadata(self, *args: object, **kwargs: object) -> dict[str, object]:
        self.calls.append(("scrape_metadata", args, kwargs))
        return {"chapters": [{"id": "1"}]}

    async def scrape_chapters(self, *args: object, **kwargs: object) -> None:
        self.calls.append(("scrape_chapters", args, kwargs))

    async def translate_chapters(self, *args: object, **kwargs: object) -> None:
        self.calls.append(("translate_chapters", args, kwargs))


class StubRunner:
    def __init__(self) -> None:
        self.running = False
        self.jobs_processed = 0

    def status(self) -> dict[str, object]:
        return {
            "running": self.running,
            "poll_seconds": 0.05,
            "job_type": None,
            "started_at": "start" if self.running else None,
            "stopped_at": None if self.running else "stop",
            "last_tick_at": None,
            "last_job_id": "job-1" if self.jobs_processed else None,
            "last_error": None,
            "jobs_processed": self.jobs_processed,
            "idle_ticks": 0,
            "error_count": 0,
        }

    async def start(self) -> dict[str, object]:
        self.running = True
        return self.status()

    async def stop(self) -> dict[str, object]:
        self.running = False
        return self.status()

    async def run_once(self) -> dict[str, object]:
        self.jobs_processed += 1
        return {"id": "job-1", "status": "completed"}


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _clean_tmp():
    if _TMP.exists():
        shutil.rmtree(_TMP, ignore_errors=True)
    _TMP.mkdir(parents=True, exist_ok=True)
    yield
    shutil.rmtree(_TMP, ignore_errors=True)


@pytest.fixture()
def _no_api_key(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(settings, "WEB_API_KEY", None)


@pytest.fixture()
def _with_api_key(monkeypatch: pytest.MonkeyPatch):
    from pydantic import SecretStr
    monkeypatch.setattr(settings, "WEB_API_KEY", SecretStr("test-secret"))


@pytest.fixture()
def client(_no_api_key: None) -> TestClient:
    """Unauthenticated client (auth disabled)."""
    bootstrap()
    return _make_app(_fresh_storage())


@pytest.fixture()
def seeded_client(_no_api_key: None) -> TestClient:
    """Client with a pre-seeded novel."""
    bootstrap()
    storage = _fresh_storage()
    _seed_novel(storage)
    return _make_app(storage)


# ---------------------------------------------------------------------------
# Auth tests
# ---------------------------------------------------------------------------


class TestAuth:
    def test_no_key_configured_allows_access(self, seeded_client: TestClient) -> None:
        resp = seeded_client.get("/novels/")
        assert resp.status_code == 200

    def test_key_required_rejects_without_token(self, _with_api_key: None) -> None:
        bootstrap()
        c = _make_app(_fresh_storage())
        resp = c.get("/novels/")
        assert resp.status_code == 403

    def test_key_required_accepts_valid_token(self, _with_api_key: None) -> None:
        bootstrap()
        c = _make_app(_fresh_storage())
        resp = c.get("/novels/", headers={"Authorization": "Bearer test-secret"})
        assert resp.status_code == 200

    def test_key_required_rejects_bad_token(self, _with_api_key: None) -> None:
        bootstrap()
        c = _make_app(_fresh_storage())
        resp = c.get("/novels/", headers={"Authorization": "Bearer wrong"})
        assert resp.status_code == 403


# ---------------------------------------------------------------------------
# List / Detail endpoints
# ---------------------------------------------------------------------------


class TestListDetail:
    def test_api_health(self, client: TestClient) -> None:
        resp = client.get("/api/health")
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}

    def test_api_prefixed_novels_route(self, seeded_client: TestClient) -> None:
        resp = seeded_client.get("/api/novels/")
        assert resp.status_code == 200
        assert resp.json()[0]["novel_id"] == "test-n1"

    def test_list_novels_empty(self, client: TestClient) -> None:
        resp = client.get("/novels/")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_list_novels_with_data(self, seeded_client: TestClient) -> None:
        resp = seeded_client.get("/novels/")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) >= 1
        assert data[0]["novel_id"] == "test-n1"

    def test_get_novel(self, seeded_client: TestClient) -> None:
        resp = seeded_client.get("/novels/test-n1")
        assert resp.status_code == 200
        assert resp.json()["title"] == "Test Novel"

    def test_get_novel_not_found(self, client: TestClient) -> None:
        resp = client.get("/novels/does-not-exist")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Chapter endpoints
# ---------------------------------------------------------------------------


class TestChapters:
    def test_list_chapters(self, seeded_client: TestClient) -> None:
        resp = seeded_client.get("/novels/test-n1/chapters")
        assert resp.status_code == 200
        chapters = resp.json()
        assert len(chapters) == 2
        assert chapters[0]["id"] == "1"

    def test_get_chapter(self, seeded_client: TestClient) -> None:
        resp = seeded_client.get("/novels/test-n1/chapters/1")
        assert resp.status_code == 200
        assert "text" in resp.json()

    def test_get_chapter_not_found(self, seeded_client: TestClient) -> None:
        resp = seeded_client.get("/novels/test-n1/chapters/999")
        assert resp.status_code == 404

    def test_get_translated_chapter(self, seeded_client: TestClient) -> None:
        resp = seeded_client.get("/novels/test-n1/chapters/1/translated")
        assert resp.status_code == 200
        assert resp.json()["chapter_id"] == "1"

    def test_get_translated_chapter_not_found(self, seeded_client: TestClient) -> None:
        resp = seeded_client.get("/novels/test-n1/chapters/2/translated")
        assert resp.status_code == 404

    def test_list_translated_chapter_versions(self, seeded_client: TestClient) -> None:
        resp = seeded_client.get("/novels/test-n1/chapters/1/translated/versions")
        assert resp.status_code == 200
        data = resp.json()
        assert data["chapter_id"] == "1"
        assert len(data["versions"]) == 1
        assert data["versions"][0]["text"] == "Translated ch1"
        assert data["versions"][0]["active"] is True

    def test_update_translated_chapter_creates_edit_history(self, seeded_client: TestClient) -> None:
        resp = seeded_client.put(
            "/novels/test-n1/chapters/1/translated",
            json={"text": "Edited ch1", "editor": "admin", "note": "line edit"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["text"] == "Edited ch1"
        assert data["version_kind"] == "manual_edit"

        history_resp = seeded_client.get("/novels/test-n1/chapters/1/translated/edit-history")
        assert history_resp.status_code == 200
        history = history_resp.json()["history"]
        assert len(history) == 1
        assert history[0]["action"] == "manual_edit"
        assert history[0]["editor"] == "admin"

    def test_rollback_translated_chapter_version(self, seeded_client: TestClient) -> None:
        edit_resp = seeded_client.put(
            "/novels/test-n1/chapters/1/translated",
            json={"text": "Edited ch1", "editor": "admin"},
        )
        assert edit_resp.status_code == 200

        rollback_resp = seeded_client.post(
            "/novels/test-n1/chapters/1/translated/rollback",
            json={"version_id": "v1", "editor": "admin", "note": "restore original"},
        )
        assert rollback_resp.status_code == 200
        assert rollback_resp.json()["text"] == "Translated ch1"
        assert rollback_resp.json()["version_id"] == "v1"

        history_resp = seeded_client.get("/novels/test-n1/chapters/1/translated/edit-history")
        history = history_resp.json()["history"]
        assert history[-1]["action"] == "rollback"
        assert history[-1]["previous_version_id"] == "v2"


# ---------------------------------------------------------------------------
# Reader endpoints
# ---------------------------------------------------------------------------


class TestReader:
    def test_get_reader_novel(self, seeded_client: TestClient) -> None:
        resp = seeded_client.get("/novels/test-n1/reader")

        assert resp.status_code == 200
        data = resp.json()
        assert data["novel_id"] == "test-n1"
        assert data["title"] == "Test Novel"
        assert data["chapter_count"] == 2
        assert data["translated_count"] == 1
        assert data["chapters"][0]["translated"] is True
        assert data["chapters"][1]["translated"] is False

    def test_get_reader_chapter(self, seeded_client: TestClient) -> None:
        resp = seeded_client.get("/novels/test-n1/reader/chapters/1")

        assert resp.status_code == 200
        data = resp.json()
        assert data["chapter_id"] == "1"
        assert data["title"] == "Ch1"
        assert data["text"] == "Translated ch1"
        assert data["previous_chapter_id"] is None
        assert data["next_chapter_id"] == "2"

    def test_get_reader_chapter_requires_translation(self, seeded_client: TestClient) -> None:
        resp = seeded_client.get("/novels/test-n1/reader/chapters/2")

        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Delete endpoint
# ---------------------------------------------------------------------------


class TestDelete:
    def test_delete_novel(self, seeded_client: TestClient) -> None:
        resp = seeded_client.delete("/novels/test-n1")
        assert resp.status_code == 204
        # Verify gone
        resp2 = seeded_client.get("/novels/test-n1")
        assert resp2.status_code == 404

    def test_delete_novel_not_found(self, client: TestClient) -> None:
        resp = client.delete("/novels/does-not-exist")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Progress endpoint
# ---------------------------------------------------------------------------


class TestProgress:
    def test_progress(self, seeded_client: TestClient) -> None:
        resp = seeded_client.get("/novels/test-n1/progress")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 2
        assert data["scraped"] >= 1

    def test_progress_not_found(self, client: TestClient) -> None:
        resp = client.get("/novels/does-not-exist/progress")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Sources endpoint
# ---------------------------------------------------------------------------


class TestSources:
    def test_list_sources(self, client: TestClient) -> None:
        resp = client.get("/novels/sources")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)


# ---------------------------------------------------------------------------
# Admin endpoints
# ---------------------------------------------------------------------------


class TestAdmin:
    def test_admin_dashboard_html(self, _no_api_key: None) -> None:
        bootstrap()
        storage = _fresh_storage()
        runner = StubRunner()
        c = _make_app(storage, runner=runner)  # type: ignore[arg-type]

        resp = c.get("/novels/admin")

        assert resp.status_code == 200
        assert "Novel AI Admin" in resp.text
        assert "worker-status" in resp.text

    def test_admin_worker_controls(self, _no_api_key: None) -> None:
        bootstrap()
        storage = _fresh_storage()
        runner = StubRunner()
        c = _make_app(storage, runner=runner)  # type: ignore[arg-type]

        status_resp = c.get("/novels/admin/worker")
        assert status_resp.status_code == 200
        assert status_resp.json()["running"] is False

        start_resp = c.post("/novels/admin/worker/start")
        assert start_resp.status_code == 200
        assert start_resp.json()["running"] is True

        run_once_resp = c.post("/novels/admin/worker/run-once")
        assert run_once_resp.status_code == 200
        assert run_once_resp.json()["job"]["id"] == "job-1"
        assert run_once_resp.json()["worker"]["jobs_processed"] == 1

        stop_resp = c.post("/novels/admin/worker/stop")
        assert stop_resp.status_code == 200
        assert stop_resp.json()["running"] is False


# ---------------------------------------------------------------------------
# Job queue endpoints
# ---------------------------------------------------------------------------


class TestJobs:
    def test_create_and_list_crawl_jobs(self, _no_api_key: None) -> None:
        bootstrap()
        storage = _fresh_storage()
        jobs = JobQueueService(_TMP / "jobs")
        c = _make_app(storage, jobs)

        create_resp = c.post(
            "/novels/jobs/crawl",
            json={
                "novel_id": "test-n1",
                "source_key": "syosetu_ncode",
                "kind": "metadata",
                "source_url": "https://ncode.syosetu.com/n1234ab/",
            },
        )
        assert create_resp.status_code == 200
        created = create_resp.json()
        assert created["type"] == "crawl"
        assert created["status"] == "pending"

        list_resp = c.get("/novels/jobs", params={"job_type": "crawl", "status": "pending"})
        assert list_resp.status_code == 200
        listed = list_resp.json()["jobs"]
        assert len(listed) == 1
        assert listed[0]["id"] == created["id"]

    def test_create_update_and_get_translation_job(self, _no_api_key: None) -> None:
        bootstrap()
        storage = _fresh_storage()
        jobs = JobQueueService(_TMP / "jobs")
        c = _make_app(storage, jobs)

        create_resp = c.post(
            "/novels/jobs/translation",
            json={"novel_id": "test-n1", "chapters": "1-2", "provider": "openai", "model": "gpt-5.4"},
        )
        assert create_resp.status_code == 200
        job_id = create_resp.json()["id"]

        update_resp = c.patch(
            f"/novels/jobs/{job_id}",
            json={"status": "running", "metadata": {"worker": "local"}},
        )
        assert update_resp.status_code == 200
        assert update_resp.json()["status"] == "running"
        assert update_resp.json()["started_at"] is not None

        get_resp = c.get(f"/novels/jobs/{job_id}")
        assert get_resp.status_code == 200
        assert get_resp.json()["metadata"]["worker"] == "local"

    def test_invalid_job_kind_returns_400(self, _no_api_key: None) -> None:
        bootstrap()
        storage = _fresh_storage()
        jobs = JobQueueService(_TMP / "jobs")
        c = _make_app(storage, jobs)

        resp = c.post(
            "/novels/jobs/crawl",
            json={"novel_id": "test-n1", "source_key": "syosetu_ncode", "kind": "unknown"},
        )
        assert resp.status_code == 400

    def test_run_next_job_executes_pending_job(self, _no_api_key: None) -> None:
        bootstrap()
        storage = _fresh_storage()
        jobs = JobQueueService(_TMP / "jobs")
        orchestrator = StubJobOrchestrator(storage)
        worker = JobWorkerService(jobs, orchestrator)  # type: ignore[arg-type]
        c = _make_app(storage, jobs, worker)

        jobs.create_crawl_job(novel_id="test-n1", source_key="syosetu_ncode", kind="chapters", chapters="1")

        resp = c.post("/novels/jobs/run-next", params={"job_type": "crawl"})

        assert resp.status_code == 200
        assert resp.json()["status"] == "completed"
        assert resp.json()["metadata"]["result"]["chapters"] == "1"
        assert orchestrator.calls[0][0] == "scrape_chapters"

        health_resp = c.get("/novels/jobs/source-health/syosetu_ncode")
        assert health_resp.status_code == 200
        assert health_resp.json()["success_count"] == 1

        list_health_resp = c.get("/novels/jobs/source-health")
        assert list_health_resp.status_code == 200
        assert list_health_resp.json()["sources"][0]["source_key"] == "syosetu_ncode"

    def test_run_job_not_found(self, _no_api_key: None) -> None:
        bootstrap()
        storage = _fresh_storage()
        jobs = JobQueueService(_TMP / "jobs")
        worker = JobWorkerService(jobs, StubJobOrchestrator(storage))  # type: ignore[arg-type]
        c = _make_app(storage, jobs, worker)

        resp = c.post("/novels/jobs/missing/run")

        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Novel request endpoints
# ---------------------------------------------------------------------------


class TestNovelRequests:
    def test_create_vote_and_list_request(self, _no_api_key: None) -> None:
        bootstrap()
        storage = _fresh_storage()
        requests = NovelRequestService(_TMP / "requests")
        c = _make_app(storage, requests=requests)

        create_resp = c.post(
            "/novels/requests",
            json={
                "title": "Requested Novel",
                "source_key": "syosetu_ncode",
                "source_url": "https://ncode.syosetu.com/n1234ab/",
                "requested_by": "reader-1",
            },
        )
        assert create_resp.status_code == 200
        request_id = create_resp.json()["id"]

        vote_resp = c.post(f"/novels/requests/{request_id}/vote", json={"voter": "reader-2"})
        assert vote_resp.status_code == 200
        assert vote_resp.json()["vote_count"] == 1

        list_resp = c.get("/novels/requests", params={"status": "pending"})
        assert list_resp.status_code == 200
        listed = list_resp.json()["requests"]
        assert len(listed) == 1
        assert listed[0]["id"] == request_id
        assert listed[0]["source_candidates"][0]["source_key"] == "syosetu_ncode"

    def test_update_request_status_and_add_source_candidate(self, _no_api_key: None) -> None:
        bootstrap()
        storage = _fresh_storage()
        requests = NovelRequestService(_TMP / "requests")
        c = _make_app(storage, requests=requests)
        request_id = c.post("/novels/requests", json={"title": "Requested Novel"}).json()["id"]

        status_resp = c.patch(
            f"/novels/requests/{request_id}",
            json={"status": "approved", "reviewed_by": "admin"},
        )
        assert status_resp.status_code == 200
        assert status_resp.json()["status"] == "approved"

        candidate_resp = c.post(
            f"/novels/requests/{request_id}/source-candidates",
            json={"source_key": "kakuyomu", "source_url": "https://kakuyomu.jp/works/123"},
        )
        assert candidate_resp.status_code == 200
        assert candidate_resp.json()["source_key"] == "kakuyomu"

        get_resp = c.get(f"/novels/requests/{request_id}")
        assert get_resp.status_code == 200
        assert len(get_resp.json()["source_candidates"]) == 1

    def test_invalid_request_status_returns_400(self, _no_api_key: None) -> None:
        bootstrap()
        storage = _fresh_storage()
        requests = NovelRequestService(_TMP / "requests")
        c = _make_app(storage, requests=requests)
        request_id = c.post("/novels/requests", json={"title": "Requested Novel"}).json()["id"]

        resp = c.patch(f"/novels/requests/{request_id}", json={"status": "not-real"})

        assert resp.status_code == 400


# ---------------------------------------------------------------------------
# Rate limiting
# ---------------------------------------------------------------------------


class TestRateLimit:
    def test_scrape_rate_limit(self, _no_api_key: None) -> None:
        """Scrape endpoint should reject after exceeding rate limit."""
        bootstrap()
        storage = _fresh_storage()
        _seed_novel(storage)
        app = create_app()
        app.dependency_overrides[get_storage] = lambda: storage

        mock_orch = AsyncMock()
        mock_orch.scrape_metadata = AsyncMock(return_value={"chapters": []})
        mock_orch.scrape_chapters = AsyncMock()
        app.dependency_overrides[get_orchestrator] = lambda: mock_orch

        with patch("novelai.interfaces.web.routers.novels._hits", defaultdict(list)):
            c = TestClient(app)
            body = {"url": "https://example.com/n1", "source_key": "dummy"}
            for _ in range(5):
                resp = c.post("/novels/test-n1/scrape", json=body)
                assert resp.status_code == 200
            # 6th should be rate-limited
            resp = c.post("/novels/test-n1/scrape", json=body)
            assert resp.status_code == 429
