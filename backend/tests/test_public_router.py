"""Tests for the public catalog router (/api/public/).

Uses FastAPI TestClient + temp dir StorageService; no DB or auth required.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.middleware.sessions import SessionMiddleware

from novelai.api.routers.public import router as public_router
from novelai.api.routers.dependencies import get_storage
from novelai.storage.service import StorageService


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def storage(tmp_path: Path) -> StorageService:
    return StorageService(tmp_path)


@pytest.fixture()
def app(storage: StorageService) -> FastAPI:
    _app = FastAPI()
    _app.add_middleware(SessionMiddleware, secret_key="test", https_only=False)
    _app.include_router(public_router)
    _app.dependency_overrides[get_storage] = lambda: storage
    return _app


@pytest.fixture()
def client(app: FastAPI) -> TestClient:
    return TestClient(app, raise_server_exceptions=True)


def _seed_novel(storage: StorageService, novel_id: str, **kwargs) -> None:
    """Seed a novel with metadata in the StorageService."""
    meta = {
        "novel_id": novel_id,
        "title": kwargs.get("title", f"Title {novel_id}"),
        "translated_title": kwargs.get("translated_title"),
        "author": kwargs.get("author", "Test Author"),
        "language": kwargs.get("language", "ja"),
        "status": kwargs.get("status", "ongoing"),
        "chapters": kwargs.get("chapters", [
            {"id": "ch001", "title": "Chapter 1", "num": 1},
            {"id": "ch002", "title": "Chapter 2", "num": 2},
        ]),
    }
    storage.save_metadata(novel_id, meta)


def _seed_translated_chapter(
    storage: StorageService, novel_id: str, chapter_id: str, text: str = "Translated text."
) -> None:
    storage.save_translated_chapter(novel_id, chapter_id, text)


# ---------------------------------------------------------------------------
# Catalog endpoint
# ---------------------------------------------------------------------------

class TestCatalog:
    def test_empty_catalog(self, client: TestClient) -> None:
        resp = client.get("/api/public/catalog")
        assert resp.status_code == 200
        data = resp.json()
        assert data["novels"] == []
        assert data["total"] == 0
        assert data["page"] == 1

    def test_catalog_lists_novels(self, client: TestClient, storage: StorageService) -> None:
        _seed_novel(storage, "novel-001", title="Novel One")
        _seed_novel(storage, "novel-002", title="Novel Two")
        resp = client.get("/api/public/catalog")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 2
        ids = {n["novel_id"] for n in data["novels"]}
        assert "novel-001" in ids
        assert "novel-002" in ids

    def test_catalog_search_by_title(self, client: TestClient, storage: StorageService) -> None:
        _seed_novel(storage, "novel-001", title="Dragon Quest")
        _seed_novel(storage, "novel-002", title="Magic School")
        resp = client.get("/api/public/catalog?q=dragon")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert data["novels"][0]["title"] == "Dragon Quest"

    def test_catalog_search_by_author(self, client: TestClient, storage: StorageService) -> None:
        _seed_novel(storage, "novel-001", author="Tanaka")
        _seed_novel(storage, "novel-002", author="Yamamoto")
        resp = client.get("/api/public/catalog?q=tanaka")
        assert resp.status_code == 200
        assert resp.json()["total"] == 1

    def test_catalog_filter_by_status(self, client: TestClient, storage: StorageService) -> None:
        _seed_novel(storage, "novel-001", status="ongoing")
        _seed_novel(storage, "novel-002", status="completed")
        resp = client.get("/api/public/catalog?status=completed")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert data["novels"][0]["status"] == "completed"

    def test_catalog_filter_by_language(self, client: TestClient, storage: StorageService) -> None:
        _seed_novel(storage, "novel-001", language="ja")
        _seed_novel(storage, "novel-002", language="zh")
        resp = client.get("/api/public/catalog?language=zh")
        assert resp.status_code == 200
        assert resp.json()["total"] == 1

    def test_catalog_pagination(self, client: TestClient, storage: StorageService) -> None:
        for i in range(5):
            _seed_novel(storage, f"novel-{i:03d}", title=f"Novel {i}")
        resp = client.get("/api/public/catalog?page=1&page_size=3")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 5
        assert len(data["novels"]) == 3
        resp2 = client.get("/api/public/catalog?page=2&page_size=3")
        assert resp2.status_code == 200
        assert len(resp2.json()["novels"]) == 2

    def test_catalog_no_auth_required(self, client: TestClient, storage: StorageService) -> None:
        """Public catalog must work without any auth header."""
        _seed_novel(storage, "novel-001")
        resp = client.get("/api/public/catalog")
        assert resp.status_code == 200

    def test_catalog_novel_has_slug_field(self, client: TestClient, storage: StorageService) -> None:
        _seed_novel(storage, "novel-001")
        data = client.get("/api/public/catalog").json()
        assert "slug" in data["novels"][0]
        assert data["novels"][0]["slug"] == "novel-001"


# ---------------------------------------------------------------------------
# Novel detail endpoint
# ---------------------------------------------------------------------------

class TestGetNovel:
    def test_returns_novel_detail(self, client: TestClient, storage: StorageService) -> None:
        _seed_novel(storage, "novel-001", title="My Novel", author="Author A")
        resp = client.get("/api/public/novels/novel-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["novel_id"] == "novel-001"
        assert data["title"] == "My Novel"

    def test_404_for_unknown_novel(self, client: TestClient) -> None:
        resp = client.get("/api/public/novels/does-not-exist")
        assert resp.status_code == 404

    def test_no_auth_required(self, client: TestClient, storage: StorageService) -> None:
        _seed_novel(storage, "novel-001")
        assert client.get("/api/public/novels/novel-001").status_code == 200


# ---------------------------------------------------------------------------
# Chapter list endpoint
# ---------------------------------------------------------------------------

class TestListChapters:
    def test_lists_chapters(self, client: TestClient, storage: StorageService) -> None:
        _seed_novel(storage, "novel-001", chapters=[
            {"id": "ch001", "title": "Ch 1", "num": 1},
            {"id": "ch002", "title": "Ch 2", "num": 2},
        ])
        resp = client.get("/api/public/novels/novel-001/chapters")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2
        assert data[0]["chapter_id"] == "ch001"

    def test_marks_translated_chapters(
        self, client: TestClient, storage: StorageService
    ) -> None:
        _seed_novel(storage, "novel-001", chapters=[
            {"id": "ch001", "title": "Ch 1", "num": 1},
            {"id": "ch002", "title": "Ch 2", "num": 2},
        ])
        _seed_translated_chapter(storage, "novel-001", "ch001", "Translated text.")
        resp = client.get("/api/public/novels/novel-001/chapters")
        assert resp.status_code == 200
        data = resp.json()
        assert data[0]["translated"] is True
        assert data[1]["translated"] is False

    def test_404_for_unknown_novel(self, client: TestClient) -> None:
        assert client.get("/api/public/novels/unknown/chapters").status_code == 404


# ---------------------------------------------------------------------------
# Chapter reader endpoint
# ---------------------------------------------------------------------------

class TestGetChapter:
    def test_returns_translated_chapter(
        self, client: TestClient, storage: StorageService
    ) -> None:
        _seed_novel(storage, "novel-001", chapters=[{"id": "ch001", "title": "Ch 1", "num": 1}])
        _seed_translated_chapter(storage, "novel-001", "ch001", "Hello translated world.")
        resp = client.get("/api/public/novels/novel-001/chapters/ch001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["text"] == "Hello translated world."
        assert data["chapter_id"] == "ch001"
        assert data["novel_id"] == "novel-001"

    def test_returns_prev_next_links(
        self, client: TestClient, storage: StorageService
    ) -> None:
        _seed_novel(storage, "novel-001", chapters=[
            {"id": "ch001", "title": "Ch 1", "num": 1},
            {"id": "ch002", "title": "Ch 2", "num": 2},
            {"id": "ch003", "title": "Ch 3", "num": 3},
        ])
        for ch in ["ch001", "ch002", "ch003"]:
            _seed_translated_chapter(storage, "novel-001", ch, f"Text {ch}")
        resp = client.get("/api/public/novels/novel-001/chapters/ch002")
        assert resp.status_code == 200
        data = resp.json()
        assert data["previous_chapter_id"] == "ch001"
        assert data["next_chapter_id"] == "ch003"

    def test_first_chapter_has_no_prev(
        self, client: TestClient, storage: StorageService
    ) -> None:
        _seed_novel(storage, "novel-001", chapters=[
            {"id": "ch001", "title": "Ch 1", "num": 1},
            {"id": "ch002", "title": "Ch 2", "num": 2},
        ])
        _seed_translated_chapter(storage, "novel-001", "ch001", "Text")
        resp = client.get("/api/public/novels/novel-001/chapters/ch001")
        assert resp.status_code == 200
        assert resp.json()["previous_chapter_id"] is None

    def test_404_for_untranslated_chapter(
        self, client: TestClient, storage: StorageService
    ) -> None:
        _seed_novel(storage, "novel-001", chapters=[{"id": "ch001", "title": "Ch 1", "num": 1}])
        # No translated chapter saved
        assert client.get("/api/public/novels/novel-001/chapters/ch001").status_code == 404

    def test_404_for_unknown_chapter(
        self, client: TestClient, storage: StorageService
    ) -> None:
        _seed_novel(storage, "novel-001")
        assert client.get("/api/public/novels/novel-001/chapters/ch999").status_code == 404

    def test_no_auth_required(
        self, client: TestClient, storage: StorageService
    ) -> None:
        _seed_novel(storage, "novel-001", chapters=[{"id": "ch001", "title": "Ch 1", "num": 1}])
        _seed_translated_chapter(storage, "novel-001", "ch001", "Text")
        assert client.get("/api/public/novels/novel-001/chapters/ch001").status_code == 200
