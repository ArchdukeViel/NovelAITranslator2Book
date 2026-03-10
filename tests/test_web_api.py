"""Tests for the FastAPI web API (auth, CORS, rate limiting, endpoints)."""

from __future__ import annotations

import shutil
from collections import defaultdict
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from novelai.app.bootstrap import bootstrap
from novelai.config.settings import settings
from novelai.services.storage_service import StorageService
from novelai.web.api import create_app
from novelai.web.routers.novels import get_orchestrator, get_storage

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


def _make_app(storage: StorageService) -> TestClient:
    """Create a TestClient with storage dependency overridden."""
    app = create_app()
    app.dependency_overrides[get_storage] = lambda: storage
    return TestClient(app)


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

        with patch("novelai.web.routers.novels._hits", defaultdict(list)):
            c = TestClient(app)
            body = {"url": "https://example.com/n1", "source_key": "dummy"}
            for _ in range(5):
                resp = c.post("/novels/test-n1/scrape", json=body)
                assert resp.status_code == 200
            # 6th should be rate-limited
            resp = c.post("/novels/test-n1/scrape", json=body)
            assert resp.status_code == 429
