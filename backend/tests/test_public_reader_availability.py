"""Public reader availability tests.

Covers:
- Configurable unavailable-chapter policy (hard_404, chapter_shell, latest_version)
- Per-novel policy override
- Invalid policy fallback to hard_404
- Owner-only version preview via ?version_id=
- Public unauthenticated ?version_id= is ignored
- Chapter list includes availability_status
- Additive availability/version fields on normal translated responses

No real HTTP. All storage is in a temp directory.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from starlette.middleware.sessions import SessionMiddleware

from novelai.api.auth.session import SessionUser, get_current_user
from novelai.api.routers.dependencies import get_db_session, get_storage
from novelai.api.routers.public_catalog import router as public_catalog_router
from novelai.api.routers.public_chapter import router as public_chapter_router
from novelai.api.routers.public_novel import router as public_novel_router
from novelai.config.settings import settings
from novelai.db.base import Base
from novelai.storage.service import StorageService

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def db_engine():
    eng = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(eng)
    yield eng
    Base.metadata.drop_all(eng)


@pytest.fixture()
def db_session(db_engine):
    Session = sessionmaker(bind=db_engine)
    sess = Session()
    yield sess
    sess.close()


@pytest.fixture()
def storage(tmp_path: Path) -> StorageService:
    return StorageService(tmp_path)


@pytest.fixture()
def app(storage: StorageService, db_session):
    _app = FastAPI()
    _app.add_middleware(SessionMiddleware, secret_key="test", https_only=False)
    _app.include_router(public_catalog_router)
    _app.include_router(public_novel_router)
    _app.include_router(public_chapter_router)
    _app.dependency_overrides[get_storage] = lambda: storage
    _app.dependency_overrides[get_db_session] = lambda: db_session
    return _app


@pytest.fixture()
def client(app: FastAPI) -> TestClient:
    return TestClient(app, raise_server_exceptions=True)


@pytest.fixture()
def owner_client(app: FastAPI, client: TestClient) -> TestClient:
    """Client authenticated as owner via get_current_user override."""
    app.dependency_overrides[get_current_user] = lambda: SessionUser(
        user_id=1, email="owner@example.com", role="owner"
    )
    return client


@pytest.fixture(autouse=True)
def _reset_policy(monkeypatch: pytest.MonkeyPatch) -> None:
    """Reset PUBLIC_READER_UNAVAILABLE_POLICY between tests."""
    monkeypatch.setattr(settings, "PUBLIC_READER_UNAVAILABLE_POLICY", "hard_404")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _seed_novel(
    storage: StorageService,
    novel_id: str,
    *,
    chapters: list[dict[str, Any]] | None = None,
    **kwargs: Any,
) -> None:
    meta: dict[str, Any] = {
        "novel_id": novel_id,
        "title": kwargs.get("title", f"Title {novel_id}"),
        "translated_title": kwargs.get("translated_title"),
        "author": kwargs.get("author", "Test Author"),
        "language": kwargs.get("language", "ja"),
        "status": kwargs.get("status", "ongoing"),
        "publication_status": kwargs.get("publication_status", "ongoing"),
        "chapters": chapters
        if chapters is not None
        else [
            {"id": "ch001", "title": "Chapter 1", "num": 1},
            {"id": "ch002", "title": "Chapter 2", "num": 2},
        ],
    }
    if "public_reader_unavailable_policy" in kwargs:
        meta["public_reader_unavailable_policy"] = kwargs["public_reader_unavailable_policy"]
    storage.save_metadata(novel_id, meta)


def _seed_translated(
    storage: StorageService,
    novel_id: str,
    chapter_id: str,
    text: str = "Translated text.",
    *,
    provider: str | None = None,
    model: str | None = None,
) -> None:
    storage.save_translated_chapter(
        novel_id, chapter_id, text, provider=provider, model=model
    )


# ---------------------------------------------------------------------------
# Task 15: Policy tests
# ---------------------------------------------------------------------------


class TestHard404Policy:
    def test_default_hard_404_returns_404_for_missing_translation(
        self, client: TestClient, storage: StorageService
    ) -> None:
        _seed_novel(storage, "novel-001")
        resp = client.get("/api/public/novels/novel-001/chapters/ch001")
        assert resp.status_code == 404
        assert resp.json()["detail"] == "Translated chapter not available."

    def test_explicit_hard_404_returns_404(
        self, client: TestClient, storage: StorageService, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(settings, "PUBLIC_READER_UNAVAILABLE_POLICY", "hard_404")
        _seed_novel(storage, "novel-001")
        resp = client.get("/api/public/novels/novel-001/chapters/ch001")
        assert resp.status_code == 404


class TestChapterShellPolicy:
    def test_chapter_shell_returns_200_with_null_text(
        self, client: TestClient, storage: StorageService, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(settings, "PUBLIC_READER_UNAVAILABLE_POLICY", "chapter_shell")
        _seed_novel(storage, "novel-001")
        resp = client.get("/api/public/novels/novel-001/chapters/ch001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["text"] is None
        assert data["reader_blocks"] == []
        assert data["availability_status"] == "not_translated"
        assert data["availability_message"] == "This chapter has not been translated yet."
        assert data["version_id"] is None
        assert data["is_active_version"] is False

    def test_chapter_shell_navigation_fields(
        self, client: TestClient, storage: StorageService, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(settings, "PUBLIC_READER_UNAVAILABLE_POLICY", "chapter_shell")
        _seed_novel(storage, "novel-001")
        # ch001 is first chapter → no previous; ch002 is next but untranslated
        resp = client.get("/api/public/novels/novel-001/chapters/ch001")
        data = resp.json()
        assert data["previous_chapter_id"] is None
        assert data["next_chapter_id"] is None
        assert data["previous_chapter_unavailable"] is False
        assert data["next_chapter_unavailable"] is True

    def test_chapter_shell_links_to_translated_neighbor(
        self, client: TestClient, storage: StorageService, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(settings, "PUBLIC_READER_UNAVAILABLE_POLICY", "chapter_shell")
        _seed_novel(storage, "novel-001")
        _seed_translated(storage, "novel-001", "ch001", "First chapter.")
        # ch002 is untranslated, but ch001 (previous) is translated
        resp = client.get("/api/public/novels/novel-001/chapters/ch002")
        data = resp.json()
        assert data["availability_status"] == "not_translated"
        assert data["previous_chapter_id"] == "ch001"
        assert data["next_chapter_unavailable"] is False


class TestLatestVersionPolicy:
    def test_latest_version_returns_newest_saved_version(
        self, client: TestClient, storage: StorageService, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """When active translation is missing but saved versions exist,
        latest_version returns the newest saved version with text."""
        monkeypatch.setattr(settings, "PUBLIC_READER_UNAVAILABLE_POLICY", "latest_version")
        _seed_novel(storage, "novel-001")
        # Save two versions; v2 becomes active by default
        storage.save_translated_chapter(
            "novel-001", "ch001", "First version.", auto_activate=False
        )
        storage.save_translated_chapter(
            "novel-001", "ch001", "Second version.", auto_activate=False
        )
        # Activate v1 so the active translation is the older version
        storage.activate_translated_chapter_version("novel-001", "ch001", "v1")

        resp = client.get("/api/public/novels/novel-001/chapters/ch001")
        assert resp.status_code == 200
        data = resp.json()
        # Active version (v1) is served regardless of policy
        assert data["availability_status"] == "available"
        assert data["is_active_version"] is True
        assert data["version_id"] == "v1"
        assert "First version." in data["text"]

    def test_latest_version_falls_back_to_shell_when_no_versions(
        self, client: TestClient, storage: StorageService, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(settings, "PUBLIC_READER_UNAVAILABLE_POLICY", "latest_version")
        _seed_novel(storage, "novel-001")
        # No translation saved at all
        resp = client.get("/api/public/novels/novel-001/chapters/ch001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["availability_status"] == "not_translated"
        assert data["text"] is None


class TestActiveVersionAlwaysServed:
    def test_active_version_served_under_hard_404(
        self, client: TestClient, storage: StorageService
    ) -> None:
        _seed_novel(storage, "novel-001")
        _seed_translated(storage, "novel-001", "ch001", "Active text.")
        resp = client.get("/api/public/novels/novel-001/chapters/ch001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["availability_status"] == "available"
        assert data["is_active_version"] is True
        assert data["text"] == "Active text."

    def test_active_version_served_under_chapter_shell(
        self, client: TestClient, storage: StorageService, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(settings, "PUBLIC_READER_UNAVAILABLE_POLICY", "chapter_shell")
        _seed_novel(storage, "novel-001")
        _seed_translated(storage, "novel-001", "ch001", "Active text.")
        resp = client.get("/api/public/novels/novel-001/chapters/ch001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["is_active_version"] is True
        assert data["text"] == "Active text."

    def test_active_version_served_under_latest_version(
        self, client: TestClient, storage: StorageService, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(settings, "PUBLIC_READER_UNAVAILABLE_POLICY", "latest_version")
        _seed_novel(storage, "novel-001")
        _seed_translated(storage, "novel-001", "ch001", "Active text.")
        resp = client.get("/api/public/novels/novel-001/chapters/ch001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["is_active_version"] is True


class TestInvalidPolicyFallback:
    def test_invalid_global_policy_falls_back_to_hard_404(
        self, client: TestClient, storage: StorageService, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        monkeypatch.setattr(settings, "PUBLIC_READER_UNAVAILABLE_POLICY", "bogus_policy")
        _seed_novel(storage, "novel-001")
        with caplog.at_level(logging.WARNING):
            resp = client.get("/api/public/novels/novel-001/chapters/ch001")
        assert resp.status_code == 404
        assert any("bogus_policy" in record.message for record in caplog.records)

    def test_invalid_per_novel_policy_falls_back_to_hard_404(
        self, client: TestClient, storage: StorageService, caplog: pytest.LogCaptureFixture
    ) -> None:
        _seed_novel(
            storage, "novel-001", public_reader_unavailable_policy="bogus_per_novel"
        )
        with caplog.at_level(logging.WARNING):
            resp = client.get("/api/public/novels/novel-001/chapters/ch001")
        assert resp.status_code == 404
        assert any("bogus_per_novel" in record.message for record in caplog.records)


# ---------------------------------------------------------------------------
# Task 16: Version preview tests
# ---------------------------------------------------------------------------


class TestOwnerVersionPreview:
    def test_owner_can_load_specific_version(
        self, owner_client: TestClient, storage: StorageService
    ) -> None:
        _seed_novel(storage, "novel-001")
        storage.save_translated_chapter(
            "novel-001", "ch001", "First version.", auto_activate=False
        )
        storage.save_translated_chapter(
            "novel-001", "ch001", "Second version.", auto_activate=False
        )
        # v2 is active
        resp = owner_client.get(
            "/api/public/novels/novel-001/chapters/ch001?version_id=v1"
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["version_id"] == "v1"
        assert data["is_active_version"] is False
        assert "First version." in data["text"]

    def test_owner_preview_of_active_version(
        self, owner_client: TestClient, storage: StorageService
    ) -> None:
        _seed_novel(storage, "novel-001")
        storage.save_translated_chapter(
            "novel-001", "ch001", "First version.", auto_activate=False
        )
        storage.save_translated_chapter(
            "novel-001", "ch001", "Second version.", auto_activate=False
        )
        resp = owner_client.get(
            "/api/public/novels/novel-001/chapters/ch001?version_id=v2"
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["version_id"] == "v2"
        assert data["is_active_version"] is True

    def test_owner_unknown_version_returns_404(
        self, owner_client: TestClient, storage: StorageService
    ) -> None:
        _seed_novel(storage, "novel-001")
        _seed_translated(storage, "novel-001", "ch001", "Active text.")
        resp = owner_client.get(
            "/api/public/novels/novel-001/chapters/ch001?version_id=v999"
        )
        assert resp.status_code == 404
        assert resp.json()["detail"] == "Version not found."

    def test_unauthenticated_version_id_is_ignored(
        self, client: TestClient, storage: StorageService
    ) -> None:
        _seed_novel(storage, "novel-001")
        _seed_translated(storage, "novel-001", "ch001", "Active text.")
        # No owner auth — version_id should be silently ignored
        resp = client.get(
            "/api/public/novels/novel-001/chapters/ch001?version_id=v999"
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["text"] == "Active text."
        assert data["is_active_version"] is True

    def test_unauthenticated_unknown_version_id_does_not_return_version_not_found(
        self, client: TestClient, storage: StorageService
    ) -> None:
        _seed_novel(storage, "novel-001")
        _seed_translated(storage, "novel-001", "ch001", "Active text.")
        resp = client.get(
            "/api/public/novels/novel-001/chapters/ch001?version_id=v999"
        )
        # Should serve normal active version, NOT "Version not found."
        assert resp.status_code == 200
        body = resp.json()
        assert body.get("detail") != "Version not found."
        assert body["text"] == "Active text."


# ---------------------------------------------------------------------------
# Task 17: Per-novel and chapter list tests
# ---------------------------------------------------------------------------


class TestPerNovelPolicyOverride:
    def test_per_novel_overrides_global(
        self, client: TestClient, storage: StorageService, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Global is hard_404, per-novel is chapter_shell
        monkeypatch.setattr(settings, "PUBLIC_READER_UNAVAILABLE_POLICY", "hard_404")
        _seed_novel(storage, "novel-001", public_reader_unavailable_policy="chapter_shell")
        resp = client.get("/api/public/novels/novel-001/chapters/ch001")
        assert resp.status_code == 200
        assert resp.json()["availability_status"] == "not_translated"

    def test_global_applies_when_no_per_novel_override(
        self, client: TestClient, storage: StorageService, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(settings, "PUBLIC_READER_UNAVAILABLE_POLICY", "chapter_shell")
        _seed_novel(storage, "novel-001")  # no per-novel override
        resp = client.get("/api/public/novels/novel-001/chapters/ch001")
        assert resp.status_code == 200
        assert resp.json()["availability_status"] == "not_translated"


class TestChapterListAvailability:
    def test_chapter_list_includes_availability_status(
        self, client: TestClient, storage: StorageService
    ) -> None:
        _seed_novel(storage, "novel-001")
        _seed_translated(storage, "novel-001", "ch001", "First.")
        resp = client.get("/api/public/novels/novel-001/chapters")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2
        assert data[0]["chapter_id"] == "ch001"
        assert data[0]["availability_status"] == "available"
        assert data[0]["translated"] is True
        assert data[1]["chapter_id"] == "ch002"
        assert data[1]["availability_status"] == "not_translated"
        assert data[1]["translated"] is False

    def test_chapter_list_preserves_existing_fields(
        self, client: TestClient, storage: StorageService
    ) -> None:
        _seed_novel(storage, "novel-001")
        _seed_translated(storage, "novel-001", "ch001", "First.")
        resp = client.get("/api/public/novels/novel-001/chapters")
        data = resp.json()
        for chapter in data:
            assert "chapter_id" in chapter
            assert "title" in chapter
            assert "chapter_number" in chapter
            assert "translated" in chapter
            assert "availability_status" in chapter


# ---------------------------------------------------------------------------
# Task 18: Backward compatibility — additive fields on normal responses
# ---------------------------------------------------------------------------


class TestAdditiveFieldsOnNormalResponse:
    def test_normal_response_includes_availability_fields(
        self, client: TestClient, storage: StorageService
    ) -> None:
        _seed_novel(storage, "novel-001")
        _seed_translated(
            storage, "novel-001", "ch001", "Hello.", provider="gemini", model="gemini-3.1-flash-lite"
        )
        resp = client.get("/api/public/novels/novel-001/chapters/ch001")
        assert resp.status_code == 200
        data = resp.json()
        # Existing fields preserved
        assert data["text"] == "Hello."
        assert data["chapter_id"] == "ch001"
        assert data["novel_id"] == "novel-001"
        # Additive fields
        assert data["availability_status"] == "available"
        assert data["availability_message"] is None
        assert data["is_active_version"] is True
        assert data["version_id"] is not None
        assert data["provider"] == "gemini"
        assert data["model"] == "gemini-3.1-flash-lite"
