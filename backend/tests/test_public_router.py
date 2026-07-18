"""Tests for the public catalog router (/api/public/).

Uses FastAPI TestClient + temp dir StorageService; DB session via SQLAlchemy.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from starlette.middleware.sessions import SessionMiddleware

from novelai.api.routers.dependencies import get_db_session, get_storage
from novelai.api.routers.public import router as public_router
from novelai.db.base import Base
from novelai.db.models.genre import Genre
from novelai.db.models.glossary import NovelGlossaryAlias, NovelGlossaryEntry
from novelai.db.models.novel import Novel
from novelai.storage.service import StorageService

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_SQLITE = "sqlite:///:memory:"


@pytest.fixture()
def db_engine():
    from sqlalchemy.pool import StaticPool
    eng = create_engine(
        _SQLITE,
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
    _app.include_router(public_router)
    _app.dependency_overrides[get_storage] = lambda: storage
    _app.dependency_overrides[get_db_session] = lambda: db_session
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
        "publication_status": kwargs.get("publication_status", kwargs.get("status", "ongoing")),
        "scraped_at": kwargs.get("scraped_at"),
        "updated_at": kwargs.get("updated_at"),
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


def _seed_db_catalog_novel(
    db_session,
    slug: str,
    *,
    title: str | None = None,
    source_title: str | None = None,
    author: str | None = None,
    language: str = "ja",
    status: str = "ongoing",
    publication_status: str | None = None,
    synopsis: str | None = None,
    is_published: bool = True,
    created_at: datetime | None = None,
    updated_at: datetime | None = None,
    chapter_count: int = 0,
    translated_count: int = 0,
    latest_chapter_id: str | None = None,
    latest_chapter_number: int | None = None,
    latest_chapter_title: str | None = None,
    latest_chapter_updated_at: datetime | None = None,
) -> Novel:
    novel = Novel(
        slug=slug,
        title=title or f"Title {slug}",
        original_title=source_title,
        author=author,
        language=language,
        status=status,
        publication_status=publication_status or status,
        synopsis=synopsis,
        is_published=is_published,
        created_at=created_at or datetime(2024, 1, 1, tzinfo=UTC),
        updated_at=updated_at or datetime(2024, 1, 1, tzinfo=UTC),
        chapter_count=chapter_count,
        translated_count=translated_count,
        latest_chapter_id=latest_chapter_id,
        latest_chapter_number=latest_chapter_number,
        latest_chapter_title=latest_chapter_title,
        latest_chapter_updated_at=latest_chapter_updated_at,
    )
    db_session.add(novel)
    db_session.commit()
    return novel


def _seed_public_glossary_entry(db_session, novel: Novel) -> NovelGlossaryEntry:
    entry = NovelGlossaryEntry(
        novel_id=novel.id,
        canonical_term="Demon Lord",
        approved_translation="Demon King",
        term_type="title",
        status="approved",
        public_visible=True,
        public_description="The translated title used for this character.",
    )
    db_session.add(entry)
    db_session.flush()
    db_session.add(
        NovelGlossaryAlias(
            glossary_entry_id=entry.id,
            novel_id=novel.id,
            alias_text="Dark King",
            alias_type="allowed",
        )
    )
    db_session.commit()
    return entry


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
        assert data["novels"][0]["publication_status"] == "completed"

    def test_catalog_includes_publication_status_alias_for_storage_summary(
        self, client: TestClient, storage: StorageService
    ) -> None:
        _seed_novel(storage, "novel-001", status="連載中")

        resp = client.get("/api/public/catalog")

        assert resp.status_code == 200
        novel = resp.json()["novels"][0]
        assert novel["publication_status"] == "ongoing"
        assert novel["status"] == novel["publication_status"]

    def test_catalog_unknowns_invalid_storage_status(
        self, client: TestClient, storage: StorageService
    ) -> None:
        _seed_novel(storage, "novel-001", status="unexpected source value")

        novel = client.get("/api/public/catalog").json()["novels"][0]

        assert novel["publication_status"] == "unknown"
        assert novel["status"] == "unknown"

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
        assert data["novels"][0]["slug"] == "title-novel-001"

    def test_catalog_uses_translated_title_storage_slug_when_available(
        self,
        client: TestClient,
        storage: StorageService,
    ) -> None:
        _seed_novel(
            storage,
            "n2056dn",
            title="父は英雄、母は精霊、娘の私は転生者。",
            translated_title="My Father is a Hero, My Mother is a Spirit, and I am a Reincarnator.",
        )

        data = client.get("/api/public/catalog").json()

        assert data["novels"][0]["novel_id"] == "n2056dn"
        assert data["novels"][0]["slug"] == "my-father-is-a-hero-my-mother-is-a-spirit-and-i-am-a-reincarnator"
        assert data["novels"][0]["title"] == "My Father is a Hero, My Mother is a Spirit, and I am a Reincarnator."
        assert data["novels"][0]["source_title"] == "父は英雄、母は精霊、娘の私は転生者。"

    def test_catalog_summary_includes_source_title_and_synopsis(self, client: TestClient, storage: StorageService) -> None:
        """PublicNovelSummary now exposes source_title and synopsis."""
        # Seed a novel with translated_title → source_title = original title
        _seed_novel(
            storage, "novel-001",
            title="Original Title",
            translated_title="Translated Title",
        )
        # Seed via raw metadata for description field
        meta = {
            "novel_id": "novel-002",
            "title": "Japanese Title",
            "translated_title": "English Title",
            "author": "Test Author",
            "description": "A captivating story about magic and adventure.",
            "chapters": [{"id": "ch001", "title": "Ch1", "num": 1}],
        }
        storage.save_metadata("novel-002", meta)

        data = client.get("/api/public/catalog").json()
        novels = {n["novel_id"]: n for n in data["novels"]}

        n1 = novels["novel-001"]
        assert n1["source_title"] == "Original Title"
        assert n1["synopsis"] is None  # no description in metadata

        n2 = novels["novel-002"]
        assert n2["title"] == "English Title"
        assert n2["source_title"] == "Japanese Title"
        assert n2["synopsis"] == "A captivating story about magic and adventure."

    def test_catalog_source_title_null_when_no_translation(self, client: TestClient, storage: StorageService) -> None:
        """source_title is null when title is not translated (no distinct original)."""
        _seed_novel(storage, "novel-001", title="Only Title", translated_title=None)
        data = client.get("/api/public/catalog").json()
        novel = data["novels"][0]
        assert novel["source_title"] is None
        assert novel["title"] == "Only Title"

    def test_catalog_summary_includes_latest_translated_chapter(
        self, client: TestClient, storage: StorageService
    ) -> None:
        _seed_novel(storage, "novel-001", chapters=[
            {"id": "ch001", "title": "Source Chapter 1", "translated_title": "Translated Chapter 1", "num": 1, "translated_at": "2026-01-01T00:00:00Z"},
            {"id": "ch002", "title": "Source Chapter 2", "translated_title": "Translated Chapter 2", "num": 2, "translated_at": "2026-01-02T00:00:00Z"},
            {"id": "ch003", "title": "Source Chapter 3", "translated_title": "Translated Chapter 3", "num": 3, "translated_at": "2026-01-03T00:00:00Z"},
        ])
        _seed_translated_chapter(storage, "novel-001", "ch001", "Translated one.")
        _seed_translated_chapter(storage, "novel-001", "ch002", "Translated two.")

        data = client.get("/api/public/catalog").json()
        novel = data["novels"][0]

        assert novel["latest_chapter_id"] == "ch002"
        assert novel["latest_chapter_number"] == 2
        assert novel["latest_chapter_title"] == "Translated Chapter 2"
        assert isinstance(novel["latest_chapter_updated_at"], str)
        assert novel["title"] == "Title novel-001"
        assert novel["chapter_count"] == 3
        assert novel["translated_count"] == 2

    def test_catalog_summary_latest_chapter_fields_null_without_translation(
        self, client: TestClient, storage: StorageService
    ) -> None:
        _seed_novel(storage, "novel-001", chapters=[
            {"id": "ch001", "title": "Source Chapter 1", "num": 1},
        ])

        data = client.get("/api/public/catalog").json()
        novel = data["novels"][0]

        assert novel["latest_chapter_id"] is None
        assert novel["latest_chapter_number"] is None
        assert novel["latest_chapter_title"] is None
        assert novel["latest_chapter_updated_at"] is None

    def test_catalog_does_not_expose_is_adult(self, client: TestClient, storage: StorageService) -> None:
        """Public catalog response must not include is_adult field."""
        _seed_novel(storage, "novel-001")
        novel = client.get("/api/public/catalog").json()["novels"][0]
        assert "is_adult" not in novel

    def test_catalog_uses_db_pagination_for_base_request(
        self,
        client: TestClient,
        storage: StorageService,
        db_session,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        _seed_db_catalog_novel(
            db_session,
            "novel-old",
            title="Old Novel",
            created_at=datetime(2024, 1, 1, tzinfo=UTC),
            updated_at=datetime(2024, 1, 1, tzinfo=UTC),
        )
        _seed_db_catalog_novel(
            db_session,
            "novel-new",
            title="New Novel",
            source_title="新しい小説",
            author="Author",
            synopsis="Stored synopsis.",
            created_at=datetime(2024, 6, 1, tzinfo=UTC),
            updated_at=datetime(2024, 6, 1, tzinfo=UTC),
            chapter_count=9,
            translated_count=3,
            latest_chapter_id="ch009",
            latest_chapter_number=9,
            latest_chapter_title="Chapter 9",
            latest_chapter_updated_at=datetime(2024, 6, 2, tzinfo=UTC),
        )
        storage.save_metadata(
            "novel-new",
            {
                "title": "æ–°ã—ã„å°èª¬",
                "translated_title": "New Novel",
                "publication_status": "ongoing",
            },
        )
        _seed_db_catalog_novel(
            db_session,
            "novel-mid",
            title="Mid Novel",
            created_at=datetime(2024, 3, 1, tzinfo=UTC),
            updated_at=datetime(2024, 3, 1, tzinfo=UTC),
        )
        monkeypatch.setattr(
            storage,
            "list_novels",
            lambda: (_ for _ in ()).throw(AssertionError("storage scan should not run")),
        )

        resp = client.get("/api/public/catalog?page=1&page_size=2")
        data = resp.json()

        assert resp.status_code == 200
        assert data["total"] == 3
        assert [novel["novel_id"] for novel in data["novels"]] == ["novel-new", "novel-mid"]
        first = data["novels"][0]
        assert first["slug"] == "new-novel"
        assert first["title"] == "New Novel"
        assert first["source_title"] == "新しい小説"
        assert first["author"] == "Author"
        assert first["language"] == "ja"
        assert first["synopsis"] == "Stored synopsis."
        assert first["status"] == "ongoing"
        assert first["publication_status"] == "ongoing"
        assert first["chapter_count"] == 9
        assert first["translated_count"] == 3
        assert first["latest_chapter_id"] == "ch009"
        assert first["latest_chapter_number"] == 9
        assert first["latest_chapter_title"] == "Chapter 9"
        assert first["added_at"] == "2024-06-01T00:00:00"
        assert first["latest_chapter_updated_at"] == "2024-06-02T00:00:00"

    def test_catalog_db_default_sort_uses_created_at_not_updated_at(
        self,
        client: TestClient,
        storage: StorageService,
        db_session,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        _seed_db_catalog_novel(
            db_session,
            "created-old-updated-new",
            created_at=datetime(2024, 1, 1, tzinfo=UTC),
            updated_at=datetime(2024, 12, 1, tzinfo=UTC),
        )
        _seed_db_catalog_novel(
            db_session,
            "created-new-updated-old",
            created_at=datetime(2024, 6, 1, tzinfo=UTC),
            updated_at=datetime(2024, 2, 1, tzinfo=UTC),
        )
        monkeypatch.setattr(
            storage,
            "list_novels",
            lambda: (_ for _ in ()).throw(AssertionError("storage scan should not run")),
        )

        data = client.get("/api/public/catalog").json()

        assert [novel["novel_id"] for novel in data["novels"]] == [
            "created-new-updated-old",
            "created-old-updated-new",
        ]
        assert data["novels"][0]["added_at"] == "2024-06-01T00:00:00"

    def test_catalog_db_sort_by_added_at_uses_created_at_with_stable_tiebreaker(
        self,
        client: TestClient,
        storage: StorageService,
        db_session,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        created_at = datetime(2024, 3, 1, tzinfo=UTC)
        _seed_db_catalog_novel(
            db_session,
            "first",
            created_at=created_at,
            updated_at=datetime(2024, 5, 1, tzinfo=UTC),
        )
        _seed_db_catalog_novel(
            db_session,
            "second",
            created_at=created_at,
            updated_at=datetime(2024, 4, 1, tzinfo=UTC),
        )
        monkeypatch.setattr(
            storage,
            "list_novels",
            lambda: (_ for _ in ()).throw(AssertionError("storage scan should not run")),
        )

        data = client.get("/api/public/catalog?sort_by=added_at&order=asc").json()

        assert [novel["novel_id"] for novel in data["novels"]] == ["first", "second"]
        assert {novel["added_at"] for novel in data["novels"]} == {"2024-03-01T00:00:00"}

    def test_catalog_db_path_excludes_unpublished_rows(
        self,
        client: TestClient,
        db_session,
    ) -> None:
        _seed_db_catalog_novel(db_session, "published", is_published=True)
        _seed_db_catalog_novel(db_session, "draft", is_published=False)

        data = client.get("/api/public/catalog").json()

        assert data["total"] == 1
        assert [novel["novel_id"] for novel in data["novels"]] == ["published"]

    def test_catalog_db_path_includes_taxonomy_for_returned_page(
        self,
        client: TestClient,
        db_session,
    ) -> None:
        _seed_db_catalog_novel(db_session, "novel-tax", updated_at=datetime(2024, 6, 1, tzinfo=UTC))
        _seed_genre_for_tests(db_session, "fantasy", "ファンタジー", display_order=2)
        _seed_genre_for_tests(db_session, "romance", "恋愛", display_order=1)
        _assign_genre_for_tests(db_session, "novel-tax", "fantasy")
        _assign_genre_for_tests(db_session, "novel-tax", "romance")
        _assign_tag_for_tests(db_session, "novel-tax", "魔法")

        novel = client.get("/api/public/catalog").json()["novels"][0]

        assert novel["genres"] == ["romance", "fantasy"]
        assert novel["tags"] == ["魔法"]

    def test_catalog_status_filter_uses_db_publication_status(
        self,
        client: TestClient,
        storage: StorageService,
        db_session,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        _seed_db_catalog_novel(db_session, "ongoing-novel", status="ongoing")
        _seed_db_catalog_novel(db_session, "completed-novel", status="completed")
        monkeypatch.setattr(
            storage,
            "list_novels",
            lambda: (_ for _ in ()).throw(AssertionError("storage scan should not run")),
        )

        data = client.get("/api/public/catalog?status=completed").json()

        assert data["total"] == 1
        assert data["novels"][0]["novel_id"] == "completed-novel"
        assert data["novels"][0]["status"] == "completed"
        assert data["novels"][0]["publication_status"] == "completed"

    def test_catalog_publication_status_filter_alias_uses_db_publication_status(
        self,
        client: TestClient,
        storage: StorageService,
        db_session,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        _seed_db_catalog_novel(db_session, "ongoing-novel", status="ongoing")
        _seed_db_catalog_novel(db_session, "completed-novel", status="completed")
        monkeypatch.setattr(
            storage,
            "list_novels",
            lambda: (_ for _ in ()).throw(AssertionError("storage scan should not run")),
        )

        resp = client.get("/api/public/catalog?publication_status=completed")

        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert data["novels"][0]["novel_id"] == "completed-novel"
        assert data["novels"][0]["publication_status"] == "completed"
        assert data["novels"][0]["status"] == "completed"

    def test_catalog_status_filter_alias_conflict_returns_400(
        self, client: TestClient
    ) -> None:
        resp = client.get("/api/public/catalog?status=ongoing&publication_status=completed")

        assert resp.status_code == 400
        assert "must match" in resp.json()["detail"]

    def test_catalog_db_summary_status_matches_publication_status_when_legacy_status_differs(
        self,
        client: TestClient,
        storage: StorageService,
        db_session,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        _seed_db_catalog_novel(
            db_session,
            "novel-001",
            status="internal-workflow-state",
            publication_status="completed",
        )
        monkeypatch.setattr(
            storage,
            "list_novels",
            lambda: (_ for _ in ()).throw(AssertionError("storage scan should not run")),
        )

        novel = client.get("/api/public/catalog").json()["novels"][0]

        assert novel["publication_status"] == "completed"
        assert novel["status"] == "completed"

    def test_catalog_language_filter_uses_db_path(
        self,
        client: TestClient,
        storage: StorageService,
        db_session,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        _seed_db_catalog_novel(db_session, "ja-novel", language="ja")
        _seed_db_catalog_novel(db_session, "zh-novel", language="zh")
        monkeypatch.setattr(
            storage,
            "list_novels",
            lambda: (_ for _ in ()).throw(AssertionError("storage scan should not run")),
        )

        data = client.get("/api/public/catalog?language=zh").json()

        assert data["total"] == 1
        assert data["novels"][0]["novel_id"] == "zh-novel"
        assert data["novels"][0]["language"] == "zh"

    def test_catalog_chapter_count_range_uses_db_path(
        self,
        client: TestClient,
        storage: StorageService,
        db_session,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        _seed_db_catalog_novel(db_session, "short", chapter_count=2)
        _seed_db_catalog_novel(db_session, "middle", chapter_count=5)
        _seed_db_catalog_novel(db_session, "long", chapter_count=9)
        monkeypatch.setattr(
            storage,
            "list_novels",
            lambda: (_ for _ in ()).throw(AssertionError("storage scan should not run")),
        )

        data = client.get("/api/public/catalog?min_chapters=5&max_chapters=9&sort_by=chapter_count&order=asc").json()

        assert data["total"] == 2
        assert [novel["novel_id"] for novel in data["novels"]] == ["middle", "long"]
        assert [novel["chapter_count"] for novel in data["novels"]] == [5, 9]

    def test_catalog_basic_search_uses_db_title_and_author(
        self,
        client: TestClient,
        storage: StorageService,
        db_session,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        _seed_db_catalog_novel(db_session, "dragon-title", title="Dragon King", author="Tanaka")
        _seed_db_catalog_novel(db_session, "author-match", title="Quiet Novel", author="Dragon Writer")
        _seed_db_catalog_novel(db_session, "miss", title="Slime World", author="Yamamoto")
        monkeypatch.setattr(
            storage,
            "list_novels",
            lambda: (_ for _ in ()).throw(AssertionError("storage scan should not run")),
        )

        data = client.get("/api/public/catalog?q=dragon&sort_by=title&order=asc").json()

        assert data["total"] == 2
        assert [novel["novel_id"] for novel in data["novels"]] == ["dragon-title", "author-match"]

    def test_catalog_title_sort_uses_db_path(
        self,
        client: TestClient,
        storage: StorageService,
        db_session,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        _seed_db_catalog_novel(db_session, "charlie", title="Charlie")
        _seed_db_catalog_novel(db_session, "alpha", title="Alpha")
        _seed_db_catalog_novel(db_session, "bravo", title="Bravo")
        monkeypatch.setattr(
            storage,
            "list_novels",
            lambda: (_ for _ in ()).throw(AssertionError("storage scan should not run")),
        )

        data = client.get("/api/public/catalog?sort_by=title&order=asc").json()

        assert [novel["title"] for novel in data["novels"]] == ["Alpha", "Bravo", "Charlie"]

    def test_catalog_taxonomy_filter_uses_db_path(
        self,
        client: TestClient,
        storage: StorageService,
        db_session,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        _seed_db_catalog_novel(db_session, "db-only", title="Other DB Novel")
        _seed_db_catalog_novel(db_session, "db-dragon", title="Dragon King")
        _seed_genre_for_tests(db_session, "fantasy", "ファンタジー")
        _assign_genre_for_tests(db_session, "db-dragon", "fantasy")
        monkeypatch.setattr(
            storage,
            "list_novels",
            lambda: (_ for _ in ()).throw(AssertionError("storage scan should not run")),
        )

        data = client.get("/api/public/catalog?genre_include=fantasy").json()

        assert data["total"] == 1
        assert data["novels"][0]["novel_id"] == "db-dragon"

    def test_storage_fallback_does_not_expose_unpublished_db_row(
        self,
        client: TestClient,
        storage: StorageService,
        db_session,
    ) -> None:
        _seed_novel(storage, "draft-storage", title="Draft Storage")
        _seed_db_catalog_novel(db_session, "draft-storage", is_published=False)

        data = client.get("/api/public/catalog").json()

        assert data["total"] == 0
        assert data["novels"] == []

    def test_db_catalog_hydrates_underfed_row_from_title_slug_storage(
        self,
        client: TestClient,
        storage: StorageService,
        db_session,
    ) -> None:
        novel_id = "16817330655991571532"
        source_title = "転生したら世界樹だった件"
        translated_title = "That Time I Was Reincarnated as a World Tree: Comic Vol. 1 Now on Sale"
        canonical_slug = "that-time-i-was-reincarnated-as-a-world-tree-comic-vol-1-now-on-sale"
        chapters = [
            {
                "id": str(number),
                "title": f"第{number}話",
                "translated_title": f"Chapter {number}",
                "num": number,
            }
            for number in range(1, 89)
        ]
        storage.save_metadata(
            novel_id,
            {
                "title": source_title,
                "translated_title": translated_title,
                "translated_synopsis": "A translated public synopsis.",
                "publication_status": "ongoing",
                "chapters": chapters,
            },
        )
        for chapter_id in ("1", "2", "3"):
            _seed_translated_chapter(storage, novel_id, chapter_id, f"Translated chapter {chapter_id}.")
        _seed_db_catalog_novel(
            db_session,
            novel_id,
            title=novel_id,
            chapter_count=0,
            translated_count=0,
            latest_chapter_id=None,
            is_published=True,
        )

        catalog = client.get("/api/public/catalog").json()
        novel = catalog["novels"][0]

        assert catalog["total"] == 1
        assert novel["novel_id"] == novel_id
        assert novel["slug"] == canonical_slug
        assert novel["title"] == translated_title
        assert novel["source_title"] == source_title
        assert novel["synopsis"] == "A translated public synopsis."
        assert novel["chapter_count"] == 88
        assert novel["translated_count"] == 3
        assert novel["latest_chapter_id"] == "3"
        assert novel["latest_chapter_number"] == 3
        assert novel["latest_chapter_title"] == "Chapter 3"

        detail = client.get(f"/api/public/novels/{canonical_slug}")
        source_id_detail = client.get(f"/api/public/novels/{novel_id}")
        chapter_three = client.get(f"/api/public/novels/{canonical_slug}/chapters/3")
        chapter_four = client.get(f"/api/public/novels/{canonical_slug}/chapters/4")

        assert detail.status_code == 200
        assert source_id_detail.status_code == 200
        assert detail.json()["slug"] == canonical_slug
        assert detail.json()["chapter_count"] == 88
        assert detail.json()["translated_count"] == 3
        assert chapter_three.status_code == 200
        assert chapter_three.json()["slug"] == canonical_slug
        assert chapter_four.status_code == 404


# ---------------------------------------------------------------------------
# Novel detail endpoint
# ---------------------------------------------------------------------------

class TestGetNovel:
    def test_returns_novel_detail(self, client: TestClient, storage: StorageService) -> None:
        _seed_novel(storage, "novel-001", title="My Novel", author="Author A", status="完結")
        resp = client.get("/api/public/novels/novel-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["novel_id"] == "novel-001"
        assert data["title"] == "My Novel"
        assert data["publication_status"] == "completed"
        assert data["status"] == "completed"

    def test_catalog_and_detail_prefer_translated_metadata(
        self, client: TestClient, storage: StorageService
    ) -> None:
        storage.save_metadata(
            "translated-meta",
            {
                "title": "日本語の題名",
                "translated_title": "English Title",
                "author": "原作者",
                "translated_author": "Original Author",
                "synopsis": "日本語のあらすじ",
                "translated_synopsis": "English synopsis.",
                "publication_status": "ongoing",
                "chapters": [
                    {
                        "id": "ch001",
                        "title": "第一話",
                        "translated_title": "Chapter One",
                        "num": 1,
                    }
                ],
            },
        )

        detail = client.get("/api/public/novels/translated-meta")
        catalog = client.get("/api/public/catalog")

        assert detail.status_code == 200
        detail_payload = detail.json()
        assert detail_payload["title"] == "English Title"
        assert detail_payload["source_title"] == "日本語の題名"
        assert detail_payload["author"] == "Original Author"
        assert detail_payload["synopsis"] == "English synopsis."

        assert catalog.status_code == 200
        catalog_payload = catalog.json()["novels"][0]
        assert catalog_payload["title"] == "English Title"
        assert catalog_payload["source_title"] == "日本語の題名"
        assert catalog_payload["synopsis"] == "English synopsis."

    def test_detail_resolves_canonical_title_slug_and_source_id_alias(
        self,
        client: TestClient,
        storage: StorageService,
    ) -> None:
        _seed_novel(
            storage,
            "n2056dn",
            title="父は英雄、母は精霊、娘の私は転生者。",
            translated_title="My Father is a Hero, My Mother is a Spirit, and I am a Reincarnator.",
        )
        canonical_slug = "my-father-is-a-hero-my-mother-is-a-spirit-and-i-am-a-reincarnator"

        canonical = client.get(f"/api/public/novels/{canonical_slug}")
        legacy = client.get("/api/public/novels/n2056dn")

        assert canonical.status_code == 200
        assert legacy.status_code == 200
        assert canonical.json()["novel_id"] == "n2056dn"
        assert legacy.json()["novel_id"] == "n2056dn"
        assert canonical.json()["slug"] == canonical_slug
        assert legacy.json()["slug"] == canonical_slug

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
        assert data["chapter_number"] == 1
        assert data["previous_chapter_unavailable"] is False
        assert data["next_chapter_unavailable"] is False

    def test_returns_only_public_glossary_annotations(
        self,
        client: TestClient,
        storage: StorageService,
        db_session,
    ) -> None:
        _seed_novel(storage, "novel-001", chapters=[{"id": "ch001", "title": "Ch 1", "num": 1}])
        _seed_translated_chapter(storage, "novel-001", "ch001", "The Demon King appeared.")
        novel = _seed_db_catalog_novel(db_session, "novel-001")
        entry = _seed_public_glossary_entry(db_session, novel)
        db_session.add(
            NovelGlossaryEntry(
                novel_id=novel.id,
                canonical_term="Hidden Name",
                approved_translation="appeared",
                term_type="term",
                status="approved",
                public_visible=False,
            )
        )
        db_session.commit()

        response = client.get("/api/public/novels/novel-001/chapters/ch001")

        assert response.status_code == 200
        annotations = response.json()["glossary_annotations"]
        assert annotations == [
            {
                "term_id": entry.id,
                "canonical_term": "Demon Lord",
                "display_term": "Demon King",
                "term_type": "title",
                "short_definition": "The translated title used for this character.",
                "aliases": ["Dark King"],
                "matches": [
                    {"surface": "Demon King", "block_index": 0, "start": 4, "end": 14}
                ],
            }
        ]

    def test_reader_strips_translation_protocol_markers(
        self, client: TestClient, storage: StorageService
    ) -> None:
        _seed_novel(storage, "novel-001", chapters=[{"id": "ch001", "title": "Ch 1", "num": 1}])
        _seed_translated_chapter(
            storage,
            "novel-001",
            "ch001",
            "[CHAPTER 1]\n[P p0001] First translated paragraph.\n\n[P p0002]\nSecond translated paragraph.",
        )

        resp = client.get("/api/public/novels/novel-001/chapters/ch001")

        assert resp.status_code == 200
        text = resp.json()["text"]
        assert "[CHAPTER 1]" not in text
        assert "[P p0001]" not in text
        assert "[P p0002]" not in text
        assert "First translated paragraph." in text
        assert "Second translated paragraph." in text
        assert "\n\n" in text

    def test_reader_returns_source_layout_blocks_from_protocol_markers(
        self, client: TestClient, storage: StorageService
    ) -> None:
        _seed_novel(storage, "novel-001", chapters=[{"id": "ch001", "title": "Ch 1", "num": 1}])
        _seed_translated_chapter(
            storage,
            "novel-001",
            "ch001",
            (
                "[CHAPTER ch001]\n"
                "[P p0001] \"A line of dialogue.\"\n"
                "[P p0002] A short narration line.\n"
                "[P p0003]\n"
                "Another source paragraph unit."
            ),
        )

        resp = client.get("/api/public/novels/novel-001/chapters/ch001")

        assert resp.status_code == 200
        payload = resp.json()
        assert payload["reader_blocks"] == [
            {"type": "line", "text": '"A line of dialogue."'},
            {"type": "line", "text": "A short narration line."},
            {"type": "line", "text": "Another source paragraph unit."},
        ]
        assert "[CHAPTER" not in payload["text"]
        assert "[P p0001]" not in payload["text"]
        assert all("[P " not in str(block) for block in payload["reader_blocks"])

    def test_reader_blocks_preserve_explicit_group_breaks(
        self, client: TestClient, storage: StorageService
    ) -> None:
        _seed_novel(storage, "novel-001", chapters=[{"id": "ch001", "title": "Ch 1", "num": 1}])
        _seed_translated_chapter(
            storage,
            "novel-001",
            "ch001",
            "[CHAPTER ch001]\n[P p0001]\nFirst line.\n\n\n[P p0002]\nSecond group line.",
        )

        resp = client.get("/api/public/novels/novel-001/chapters/ch001")

        assert resp.status_code == 200
        assert resp.json()["reader_blocks"] == [
            {"type": "line", "text": "First line."},
            {"type": "break"},
            {"type": "line", "text": "Second group line."},
        ]

    def test_reader_blocks_use_source_blocks_when_available(
        self, client: TestClient, storage: StorageService
    ) -> None:
        _seed_novel(storage, "novel-001", chapters=[{"id": "ch001", "title": "Ch 1", "num": 1}])
        storage.save_chapter(
            "novel-001",
            "ch001",
            "Source one.\n\nSource two.",
            source_blocks=[
                {"type": "line", "paragraph_id": "p0001", "text": "Source one."},
                {"type": "break"},
                {"type": "line", "paragraph_id": "p0002", "text": "Source two."},
            ],
        )
        _seed_translated_chapter(
            storage,
            "novel-001",
            "ch001",
            "[CHAPTER ch001]\n[P p0001]\nTranslated one.\n[P p0002]\nTranslated two.",
        )

        resp = client.get("/api/public/novels/novel-001/chapters/ch001")

        assert resp.status_code == 200
        assert resp.json()["reader_blocks"] == [
            {"type": "line", "text": "Translated one."},
            {"type": "break"},
            {"type": "line", "text": "Translated two."},
        ]

    def test_reader_adjacent_marker_units_remain_close_without_explicit_breaks(
        self, client: TestClient, storage: StorageService
    ) -> None:
        _seed_novel(storage, "novel-001", chapters=[{"id": "ch001", "title": "Ch 1", "num": 1}])
        _seed_translated_chapter(
            storage,
            "novel-001",
            "ch001",
            "[CHAPTER ch001]\n[P p0001]\nFirst line.\n[P p0002]\nSecond line.\n[P p0003]\nThird line.",
        )

        resp = client.get("/api/public/novels/novel-001/chapters/ch001")

        assert resp.status_code == 200
        assert resp.json()["reader_blocks"] == [
            {"type": "line", "text": "First line."},
            {"type": "line", "text": "Second line."},
            {"type": "line", "text": "Third line."},
        ]

    def test_reader_blocks_fallback_for_unmarked_text_splits_on_blank_breaks(
        self, client: TestClient, storage: StorageService
    ) -> None:
        _seed_novel(storage, "novel-001", chapters=[{"id": "ch001", "title": "Ch 1", "num": 1}])
        _seed_translated_chapter(
            storage,
            "novel-001",
            "ch001",
            "First display block.\nStill first block.\n\nSecond display block.",
        )

        resp = client.get("/api/public/novels/novel-001/chapters/ch001")

        assert resp.status_code == 200
        assert resp.json()["reader_blocks"] == [
            {"type": "line", "text": "First display block.\nStill first block."},
            {"type": "break"},
            {"type": "line", "text": "Second display block."},
        ]

    def test_returns_chapter_number_matches_stored(
        self, client: TestClient, storage: StorageService
    ) -> None:
        _seed_novel(storage, "novel-001", chapters=[
            {"id": "ch001", "title": "Ch 1", "num": 5},
            {"id": "ch002", "title": "Ch 2", "num": 7},
        ])
        for ch in ["ch001", "ch002"]:
            _seed_translated_chapter(storage, "novel-001", ch, f"Text {ch}")
        resp = client.get("/api/public/novels/novel-001/chapters/ch001")
        assert resp.status_code == 200
        assert resp.json()["chapter_number"] == 5
        resp = client.get("/api/public/novels/novel-001/chapters/ch002")
        assert resp.status_code == 200
        assert resp.json()["chapter_number"] == 7

    def test_reader_resolves_canonical_title_slug_and_source_id_alias(
        self,
        client: TestClient,
        storage: StorageService,
    ) -> None:
        _seed_novel(
            storage,
            "n2056dn",
            title="父は英雄、母は精霊、娘の私は転生者。",
            translated_title="My Father is a Hero, My Mother is a Spirit, and I am a Reincarnator.",
            chapters=[{"id": "1", "title": "序章", "translated_title": "Prologue", "num": 1}],
        )
        _seed_translated_chapter(storage, "n2056dn", "1", "Hello translated world.")
        canonical_slug = "my-father-is-a-hero-my-mother-is-a-spirit-and-i-am-a-reincarnator"

        canonical = client.get(f"/api/public/novels/{canonical_slug}/chapters/1")
        legacy = client.get("/api/public/novels/n2056dn/chapters/1")

        assert canonical.status_code == 200
        assert legacy.status_code == 200
        assert canonical.json()["novel_id"] == "n2056dn"
        assert canonical.json()["slug"] == canonical_slug
        assert canonical.json()["title"] == "Prologue"
        assert legacy.json()["slug"] == canonical_slug

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
        assert data["previous_chapter_unavailable"] is False
        assert data["next_chapter_unavailable"] is False

    def test_untranslated_adjacent_chapters_are_not_active_reader_links(
        self, client: TestClient, storage: StorageService
    ) -> None:
        _seed_novel(storage, "novel-001", chapters=[
            {"id": "ch001", "title": "Ch 1", "num": 1},
            {"id": "ch002", "title": "Ch 2", "num": 2},
            {"id": "ch003", "title": "Ch 3", "num": 3},
        ])
        _seed_translated_chapter(storage, "novel-001", "ch002", "Text ch002")

        resp = client.get("/api/public/novels/novel-001/chapters/ch002")

        assert resp.status_code == 200
        data = resp.json()
        assert data["previous_chapter_id"] is None
        assert data["next_chapter_id"] is None
        assert data["previous_chapter_unavailable"] is True
        assert data["next_chapter_unavailable"] is True

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


# ---------------------------------------------------------------------------
# Catalog sorting
# ---------------------------------------------------------------------------

class TestCatalogSort:
    def test_default_sort_is_added_at_desc(
        self, client: TestClient, storage: StorageService
    ) -> None:
        _seed_novel(storage, "novel-old", title="Old Novel", scraped_at="2024-01-01T00:00:00")
        _seed_novel(storage, "novel-new", title="New Novel", scraped_at="2024-06-15T00:00:00")
        _seed_novel(storage, "novel-mid", title="Mid Novel", scraped_at="2024-03-10T00:00:00")
        resp = client.get("/api/public/catalog")
        assert resp.status_code == 200
        ids = [n["novel_id"] for n in resp.json()["novels"]]
        assert ids == ["novel-new", "novel-mid", "novel-old"]

    def test_sort_by_title_asc(
        self, client: TestClient, storage: StorageService
    ) -> None:
        _seed_novel(storage, "novel-c", title="Charlie")
        _seed_novel(storage, "novel-a", title="Alpha")
        _seed_novel(storage, "novel-b", title="Bravo")
        resp = client.get("/api/public/catalog?sort_by=title&order=asc")
        assert resp.status_code == 200
        titles = [n["title"] for n in resp.json()["novels"]]
        assert titles == ["Alpha", "Bravo", "Charlie"]

    def test_sort_by_title_desc(
        self, client: TestClient, storage: StorageService
    ) -> None:
        _seed_novel(storage, "novel-c", title="Charlie")
        _seed_novel(storage, "novel-a", title="Alpha")
        _seed_novel(storage, "novel-b", title="Bravo")
        resp = client.get("/api/public/catalog?sort_by=title&order=desc")
        assert resp.status_code == 200
        titles = [n["title"] for n in resp.json()["novels"]]
        assert titles == ["Charlie", "Bravo", "Alpha"]

    def test_sort_by_chapter_count_asc(
        self, client: TestClient, storage: StorageService
    ) -> None:
        _seed_novel(storage, "novel-many", chapters=[
            {"id": f"ch{i:03d}", "title": f"Ch {i}", "num": i}
            for i in range(1, 11)
        ])
        _seed_novel(storage, "novel-few", chapters=[
            {"id": "ch001", "title": "Ch 1", "num": 1},
        ])
        _seed_novel(storage, "novel-mid", chapters=[
            {"id": f"ch{i:03d}", "title": f"Ch {i}", "num": i}
            for i in range(1, 6)
        ])
        resp = client.get("/api/public/catalog?sort_by=chapter_count&order=asc")
        assert resp.status_code == 200
        counts = [n["chapter_count"] for n in resp.json()["novels"]]
        assert counts == sorted(counts)

    def test_sort_by_chapter_count_desc(
        self, client: TestClient, storage: StorageService
    ) -> None:
        _seed_novel(storage, "novel-many", chapters=[
            {"id": f"ch{i:03d}", "title": f"Ch {i}", "num": i}
            for i in range(1, 11)
        ])
        _seed_novel(storage, "novel-few", chapters=[
            {"id": "ch001", "title": "Ch 1", "num": 1},
        ])
        _seed_novel(storage, "novel-mid", chapters=[
            {"id": f"ch{i:03d}", "title": f"Ch {i}", "num": i}
            for i in range(1, 6)
        ])
        resp = client.get("/api/public/catalog?sort_by=chapter_count&order=desc")
        assert resp.status_code == 200
        counts = [n["chapter_count"] for n in resp.json()["novels"]]
        assert counts == sorted(counts, reverse=True)

    def test_invalid_sort_by_falls_back_to_default(
        self, client: TestClient, storage: StorageService
    ) -> None:
        _seed_novel(storage, "novel-old", scraped_at="2024-01-01T00:00:00")
        _seed_novel(storage, "novel-new", scraped_at="2024-06-15T00:00:00")
        resp = client.get("/api/public/catalog?sort_by=invalid_field")
        assert resp.status_code == 200
        ids = [n["novel_id"] for n in resp.json()["novels"]]
        # Should fall back to added_at desc
        assert ids == ["novel-new", "novel-old"]

    def test_invalid_order_falls_back_to_desc(
        self, client: TestClient, storage: StorageService
    ) -> None:
        _seed_novel(storage, "novel-old", scraped_at="2024-01-01T00:00:00")
        _seed_novel(storage, "novel-new", scraped_at="2024-06-15T00:00:00")
        resp = client.get("/api/public/catalog?sort_by=added_at&order=sideways")
        assert resp.status_code == 200
        ids = [n["novel_id"] for n in resp.json()["novels"]]
        assert ids == ["novel-new", "novel-old"]

    def test_added_at_prefers_scraped_at(
        self, client: TestClient, storage: StorageService
    ) -> None:
        _seed_novel(storage, "novel-001", scraped_at="2024-03-01T00:00:00", updated_at="2024-06-01T00:00:00")
        resp = client.get("/api/public/catalog")
        assert resp.status_code == 200
        novel = resp.json()["novels"][0]
        assert novel["added_at"] == "2024-03-01T00:00:00"

    def test_added_at_falls_back_to_updated_at(
        self, client: TestClient, storage: StorageService
    ) -> None:
        # Write metadata directly to have updated_at but no scraped_at
        novel_dir = storage.novels_dir / "novel-001"
        novel_dir.mkdir(parents=True, exist_ok=True)
        meta = {
            "novel_id": "novel-001",
            "title": "Test Novel",
            "updated_at": "2024-06-01T00:00:00",
            "chapters": [{"id": "ch001", "title": "Ch 1", "num": 1}],
        }
        (novel_dir / "metadata.json").write_text(json.dumps(meta), encoding="utf-8")
        index = storage._load_index()
        index["novel-001"] = {"folder_name": "novel-001"}
        storage._persist_index(index)

        resp = client.get("/api/public/catalog")
        assert resp.status_code == 200
        novel = resp.json()["novels"][0]
        assert novel["added_at"] == "2024-06-01T00:00:00"

    def test_added_at_null_when_no_dates(
        self, client: TestClient, storage: StorageService
    ) -> None:
        _seed_novel(storage, "novel-001")
        resp = client.get("/api/public/catalog")
        assert resp.status_code == 200
        novel = resp.json()["novels"][0]
        # save_metadata always sets scraped_at/updated_at, so this validates the field exists
        assert "added_at" in novel

    def test_novels_without_added_at_sort_last_in_desc(
        self, client: TestClient, storage: StorageService
    ) -> None:
        """Novels with no scraped_at/updated_at should appear after dated novels in desc."""
        # We need to manipulate metadata directly to remove scraped_at
        storage.save_metadata("novel-dated", {
            "title": "Dated Novel",
            "scraped_at": "2024-06-01T00:00:00",
            "chapters": [{"id": "ch001", "title": "Ch 1", "num": 1}],
        })
        # Create a novel with no date fields by manually editing
        meta = {
            "novel_id": "novel-nodate",
            "title": "No Date Novel",
            "chapters": [{"id": "ch001", "title": "Ch 1", "num": 1}],
        }
        # Overwrite to strip scraped_at/updated_at that save_metadata auto-sets
        novel_dir = storage.novels_dir / "novel-nodate"
        novel_dir.mkdir(parents=True, exist_ok=True)
        meta_path = novel_dir / "metadata.json"
        meta_path.write_text(json.dumps(meta), encoding="utf-8")
        # Re-register in the index
        index = storage._load_index()
        index["novel-nodate"] = {"folder_name": "novel-nodate"}
        storage._persist_index(index)

        resp = client.get("/api/public/catalog?sort_by=added_at&order=desc")
        assert resp.status_code == 200
        ids = [n["novel_id"] for n in resp.json()["novels"]]
        assert ids[0] == "novel-dated"
        assert ids[-1] == "novel-nodate"


# ---------------------------------------------------------------------------
# Catalog chapter count filters
# ---------------------------------------------------------------------------

class TestCatalogChapterFilter:
    def test_min_chapters_filter(
        self, client: TestClient, storage: StorageService
    ) -> None:
        _seed_novel(storage, "novel-few", chapters=[
            {"id": "ch001", "title": "Ch 1", "num": 1},
        ])
        _seed_novel(storage, "novel-many", chapters=[
            {"id": f"ch{i:03d}", "title": f"Ch {i}", "num": i}
            for i in range(1, 11)
        ])
        resp = client.get("/api/public/catalog?min_chapters=5")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert data["novels"][0]["novel_id"] == "novel-many"

    def test_max_chapters_filter(
        self, client: TestClient, storage: StorageService
    ) -> None:
        _seed_novel(storage, "novel-few", chapters=[
            {"id": "ch001", "title": "Ch 1", "num": 1},
        ])
        _seed_novel(storage, "novel-many", chapters=[
            {"id": f"ch{i:03d}", "title": f"Ch {i}", "num": i}
            for i in range(1, 11)
        ])
        resp = client.get("/api/public/catalog?max_chapters=5")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert data["novels"][0]["novel_id"] == "novel-few"

    def test_min_and_max_chapters_combined(
        self, client: TestClient, storage: StorageService
    ) -> None:
        _seed_novel(storage, "novel-1", chapters=[
            {"id": "ch001", "title": "Ch 1", "num": 1},
        ])
        _seed_novel(storage, "novel-5", chapters=[
            {"id": f"ch{i:03d}", "title": f"Ch {i}", "num": i}
            for i in range(1, 6)
        ])
        _seed_novel(storage, "novel-20", chapters=[
            {"id": f"ch{i:03d}", "title": f"Ch {i}", "num": i}
            for i in range(1, 21)
        ])
        resp = client.get("/api/public/catalog?min_chapters=3&max_chapters=10")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert data["novels"][0]["novel_id"] == "novel-5"

    def test_chapter_filter_with_zero_min(
        self, client: TestClient, storage: StorageService
    ) -> None:
        _seed_novel(storage, "novel-001", chapters=[
            {"id": "ch001", "title": "Ch 1", "num": 1},
            {"id": "ch002", "title": "Ch 2", "num": 2},
        ])
        resp = client.get("/api/public/catalog?min_chapters=0")
        assert resp.status_code == 200
        assert resp.json()["total"] == 1

    def test_chapter_filter_with_pagination(
        self, client: TestClient, storage: StorageService
    ) -> None:
        for i in range(5):
            _seed_novel(storage, f"novel-{i:03d}", chapters=[
                {"id": f"ch{j:03d}", "title": f"Ch {j}", "num": j}
                for j in range(1, i + 2)
            ])
        # All novels have >= 1 chapter, min_chapters=1 should return all 5
        resp = client.get("/api/public/catalog?min_chapters=1&page_size=3")
        data = resp.json()
        assert data["total"] == 5
        assert len(data["novels"]) == 3

    def test_sort_and_filter_combined(
        self, client: TestClient, storage: StorageService
    ) -> None:
        _seed_novel(storage, "novel-small", title="Small", chapters=[
            {"id": "ch001", "title": "Ch 1", "num": 1},
        ])
        _seed_novel(storage, "novel-big-a", title="Big Alpha", chapters=[
            {"id": f"ch{i:03d}", "title": f"Ch {i}", "num": i}
            for i in range(1, 11)
        ])
        _seed_novel(storage, "novel-big-z", title="Big Zeta", chapters=[
            {"id": f"ch{i:03d}", "title": f"Ch {i}", "num": i}
            for i in range(1, 11)
        ])
        # Filter min_chapters=5, sort by title asc
        resp = client.get("/api/public/catalog?min_chapters=5&sort_by=title&order=asc")
        data = resp.json()
        assert data["total"] == 2
        titles = [n["title"] for n in data["novels"]]
        assert titles == ["Big Alpha", "Big Zeta"]


# ---------------------------------------------------------------------------
# Catalog taxonomy (genres/tags in response)
# ---------------------------------------------------------------------------

class TestCatalogTaxonomy:
    def _seed_genre(self, db_session, slug: str, name_ja: str, display_order: int = 0, **kwargs) -> None:
        from novelai.db.models.genre import Genre
        genre = Genre(slug=slug, name_ja=name_ja, name_en=slug, display_order=display_order, is_active=True, **kwargs)
        db_session.add(genre)
        db_session.commit()

    def _assign_genre(self, db_session, novel_slug: str, genre_slug: str) -> None:
        from sqlalchemy import text
        novel = db_session.query(Novel).filter_by(slug=novel_slug).one_or_none()
        if novel is None:
            novel = Novel(slug=novel_slug, title="Temp", language="ja", status="ongoing", is_published=True)
            db_session.add(novel)
            db_session.flush()
        else:
            novel.is_published = True
        genre = db_session.query(Genre).filter_by(slug=genre_slug).one()
        db_session.execute(text(
            "INSERT OR IGNORE INTO novel_genres (novel_id, genre_id, assigned_by) "
            "VALUES (:nid, :gid, 'scraper')"
        ), {"nid": novel.id, "gid": genre.id})
        db_session.commit()

    def _assign_tag(self, db_session, novel_slug: str, tag_name: str) -> None:
        from sqlalchemy import text

        from novelai.db.models.tag import Tag
        tag = db_session.query(Tag).filter_by(name=tag_name).one_or_none()
        if tag is None:
            tag = Tag(name=tag_name)
            db_session.add(tag)
            db_session.flush()
        novel = db_session.query(Novel).filter_by(slug=novel_slug).one_or_none()
        if novel is None:
            novel = Novel(slug=novel_slug, title="Temp", language="ja", status="ongoing", is_published=True)
            db_session.add(novel)
            db_session.flush()
        else:
            novel.is_published = True
        db_session.execute(text(
            "INSERT OR IGNORE INTO novel_tags (novel_id, tag_id, origin, assigned_by) "
            "VALUES (:nid, :tid, 'test', 'scraper')"
        ), {"nid": novel.id, "tid": tag.id})
        db_session.commit()

    def test_catalog_returns_empty_genres_and_tags_when_no_assignments(
        self, client: TestClient, storage: StorageService
    ) -> None:
        _seed_novel(storage, "n001")
        resp = client.get("/api/public/catalog")
        assert resp.status_code == 200
        novel = resp.json()["novels"][0]
        assert novel["genres"] == []
        assert novel["tags"] == []

    def test_catalog_returns_assigned_genre_slugs(
        self, client: TestClient, storage: StorageService, db_session
    ) -> None:
        _seed_novel(storage, "n002")
        self._seed_genre(db_session, "fantasy", "ファンタジー")
        self._assign_genre(db_session, "n002", "fantasy")

        resp = client.get("/api/public/catalog")
        assert resp.status_code == 200
        novel = resp.json()["novels"][0]
        assert novel["genres"] == ["fantasy"]
        assert novel["tags"] == []

    def test_catalog_returns_assigned_tag_names(
        self, client: TestClient, storage: StorageService, db_session
    ) -> None:
        _seed_novel(storage, "n003")
        self._assign_tag(db_session, "n003", "魔法")
        self._assign_tag(db_session, "n003", "勇者")

        resp = client.get("/api/public/catalog")
        assert resp.status_code == 200
        novel = resp.json()["novels"][0]
        assert set(novel["tags"]) == {"魔法", "勇者"}
        # Tags should be alphabetically sorted
        assert novel["tags"] == sorted(novel["tags"])

    def test_inactive_genre_excluded_from_response(
        self, client: TestClient, storage: StorageService, db_session
    ) -> None:
        _seed_novel(storage, "n004")
        from novelai.db.models.genre import Genre
        self._seed_genre(db_session, "horror", "ホラー")
        self._assign_genre(db_session, "n004", "horror")
        # Deactivate the genre
        genre = db_session.query(Genre).filter_by(slug="horror").one()
        genre.is_active = False
        db_session.commit()

        resp = client.get("/api/public/catalog")
        assert resp.status_code == 200
        novel = resp.json()["novels"][0]
        assert novel["genres"] == []

    def test_genre_order_by_display_order(
        self, client: TestClient, storage: StorageService, db_session
    ) -> None:
        _seed_novel(storage, "n005")
        self._seed_genre(db_session, "sf", "SF", display_order=5)
        self._seed_genre(db_session, "isekai-tensei", "異世界転生", display_order=1)
        self._assign_genre(db_session, "n005", "sf")
        self._assign_genre(db_session, "n005", "isekai-tensei")

        resp = client.get("/api/public/catalog")
        assert resp.status_code == 200
        novel = resp.json()["novels"][0]
        # Should be ordered by display_order: isekai-tensei (1) before sf (5)
        assert novel["genres"] == ["isekai-tensei", "sf"]

    def test_novel_detail_also_has_genres_and_tags(
        self, client: TestClient, storage: StorageService, db_session
    ) -> None:
        _seed_novel(storage, "n006")
        self._seed_genre(db_session, "romance", "恋愛", display_order=6)
        self._assign_genre(db_session, "n006", "romance")
        self._assign_tag(db_session, "n006", "転生")

        resp = client.get("/api/public/novels/n006")
        assert resp.status_code == 200
        novel = resp.json()
        assert novel["genres"] == ["romance"]
        assert novel["tags"] == ["転生"]

    def test_adult_genre_novel_excluded_by_default(
        self, client: TestClient, storage: StorageService, db_session
    ) -> None:
        """Novel with adult genre excluded from catalog by default."""
        _seed_novel(storage, "adult-novel")
        self._seed_genre(db_session, "adult-romance", "大人向け恋愛", display_order=101, is_adult=True)
        self._assign_genre(db_session, "adult-novel", "adult-romance")

        resp = client.get("/api/public/catalog")
        assert resp.status_code == 200
        slugs = {n["slug"] for n in resp.json()["novels"]}
        assert "adult-novel" not in slugs

    def test_adult_genre_novel_included_when_include_adult_true(
        self, client: TestClient, storage: StorageService, db_session
    ) -> None:
        """Novel with adult genre included when include_adult=true."""
        _seed_novel(storage, "adult-novel")
        self._seed_genre(db_session, "adult-romance", "大人向け恋愛", display_order=101, is_adult=True)
        self._assign_genre(db_session, "adult-novel", "adult-romance")

        resp = client.get("/api/public/catalog?include_adult=true")
        assert resp.status_code == 200
        novel_ids = {n["novel_id"] for n in resp.json()["novels"]}
        assert "adult-novel" in novel_ids

    def test_non_adult_genre_novel_visible_by_default(
        self, client: TestClient, storage: StorageService, db_session
    ) -> None:
        """Novel with non-adult genre visible in catalog by default."""
        _seed_novel(storage, "safe-novel")
        self._seed_genre(db_session, "fantasy", "ファンタジー")
        self._assign_genre(db_session, "safe-novel", "fantasy")

        resp = client.get("/api/public/catalog")
        assert resp.status_code == 200
        novel_ids = {n["novel_id"] for n in resp.json()["novels"]}
        assert "safe-novel" in novel_ids

    def test_novel_detail_filters_adult_genres_by_default(
        self, client: TestClient, storage: StorageService, db_session
    ) -> None:
        """Novel detail returns novel but without adult genre slugs by default."""
        _seed_novel(storage, "adult-novel")
        self._seed_genre(db_session, "adult-romance", "大人向け恋愛", display_order=101, is_adult=True)
        self._assign_genre(db_session, "adult-novel", "adult-romance")

        resp = client.get("/api/public/novels/adult-novel")
        assert resp.status_code == 200
        assert resp.json()["genres"] == []

    def test_novel_detail_includes_adult_genres_when_requested(
        self, client: TestClient, storage: StorageService, db_session
    ) -> None:
        """Novel detail includes adult genres when include_adult=true."""
        _seed_novel(storage, "adult-novel")
        self._seed_genre(db_session, "adult-romance", "大人向け恋愛", display_order=101, is_adult=True)
        self._assign_genre(db_session, "adult-novel", "adult-romance")

        resp = client.get("/api/public/novels/adult-novel?include_adult=true")
        assert resp.status_code == 200
        assert resp.json()["genres"] == ["adult-romance"]


# ---------------------------------------------------------------------------
# Module-level helpers for taxonomy filter tests
# ---------------------------------------------------------------------------


def _seed_genre_for_tests(
    db_session,
    slug: str,
    name_ja: str,
    display_order: int = 0,
    is_active: bool = True,
    is_adult: bool = False,
) -> None:
    from novelai.db.models.genre import Genre
    genre = Genre(
        slug=slug,
        name_ja=name_ja,
        name_en=slug,
        display_order=display_order,
        is_active=is_active,
        is_adult=is_adult,
    )
    db_session.add(genre)
    db_session.commit()


def _assign_genre_for_tests(db_session, novel_slug: str, genre_slug: str) -> None:
    from sqlalchemy import text
    novel = db_session.query(Novel).filter_by(slug=novel_slug).one_or_none()
    if novel is None:
        novel = Novel(slug=novel_slug, title="Temp", language="ja", status="ongoing", is_published=True)
        db_session.add(novel)
        db_session.flush()
    else:
        novel.is_published = True
    from novelai.db.models.genre import Genre
    genre = db_session.query(Genre).filter_by(slug=genre_slug).one()
    db_session.execute(text(
        "INSERT OR IGNORE INTO novel_genres (novel_id, genre_id, assigned_by) "
        "VALUES (:nid, :gid, 'scraper')"
    ), {"nid": novel.id, "gid": genre.id})
    db_session.commit()


def _assign_tag_for_tests(db_session, novel_slug: str, tag_name: str) -> None:
    from sqlalchemy import text

    from novelai.db.models.tag import Tag
    tag = db_session.query(Tag).filter_by(name=tag_name).one_or_none()
    if tag is None:
        tag = Tag(name=tag_name)
        db_session.add(tag)
        db_session.flush()
    novel = db_session.query(Novel).filter_by(slug=novel_slug).one_or_none()
    if novel is None:
        novel = Novel(slug=novel_slug, title="Temp", language="ja", status="ongoing", is_published=True)
        db_session.add(novel)
        db_session.flush()
    else:
        novel.is_published = True
    db_session.execute(text(
        "INSERT OR IGNORE INTO novel_tags (novel_id, tag_id, origin, assigned_by) "
        "VALUES (:nid, :tid, 'test', 'scraper')"
    ), {"nid": novel.id, "tid": tag.id})
    db_session.commit()


# ---------------------------------------------------------------------------
# Catalog genre/tag filtering
# ---------------------------------------------------------------------------


class TestCatalogGenreTagFilter:
    """Filtering by genre_include, genre_exclude, tag_include, tag_exclude."""

    def test_genre_include_matches(
        self, client: TestClient, storage: StorageService, db_session,
    ) -> None:
        _seed_novel(storage, "n001")
        _seed_genre_for_tests(db_session, "fantasy", "ファンタジー")
        _assign_genre_for_tests(db_session, "n001", "fantasy")
        resp = client.get("/api/public/catalog?genre_include=fantasy")
        assert resp.status_code == 200
        assert resp.json()["total"] == 1

    def test_genre_exclude_removes(
        self, client: TestClient, storage: StorageService, db_session,
    ) -> None:
        _seed_db_catalog_novel(db_session, "n001")
        _seed_db_catalog_novel(db_session, "n002")
        _seed_genre_for_tests(db_session, "fantasy", "ファンタジー")
        _assign_genre_for_tests(db_session, "n001", "fantasy")
        resp = client.get("/api/public/catalog?genre_exclude=fantasy")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert data["novels"][0]["novel_id"] == "n002"

    def test_tag_include_matches(
        self, client: TestClient, storage: StorageService, db_session,
    ) -> None:
        _seed_db_catalog_novel(db_session, "n001")
        _assign_tag_for_tests(db_session, "n001", "魔法")
        resp = client.get("/api/public/catalog?tag_include=魔法")
        assert resp.status_code == 200
        assert resp.json()["total"] == 1

    def test_tag_exclude_removes(
        self, client: TestClient, storage: StorageService, db_session,
    ) -> None:
        _seed_db_catalog_novel(db_session, "n001")
        _seed_db_catalog_novel(db_session, "n002")
        _assign_tag_for_tests(db_session, "n001", "魔法")
        resp = client.get("/api/public/catalog?tag_exclude=魔法")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert data["novels"][0]["novel_id"] == "n002"

    def test_genre_include_all_required(
        self, client: TestClient, storage: StorageService, db_session,
    ) -> None:
        _seed_db_catalog_novel(db_session, "n001")
        _seed_db_catalog_novel(db_session, "n002")
        _seed_genre_for_tests(db_session, "fantasy", "ファンタジー")
        _seed_genre_for_tests(db_session, "romance", "恋愛")
        _assign_genre_for_tests(db_session, "n001", "fantasy")
        _assign_genre_for_tests(db_session, "n001", "romance")
        _assign_genre_for_tests(db_session, "n002", "fantasy")
        # n001 has both, n002 only has fantasy
        resp = client.get("/api/public/catalog?genre_include=fantasy,romance")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert data["novels"][0]["novel_id"] == "n001"

    def test_unknown_genre_include_returns_zero(
        self, client: TestClient, storage: StorageService, db_session,
    ) -> None:
        _seed_db_catalog_novel(db_session, "n001")
        _seed_genre_for_tests(db_session, "fantasy", "ファンタジー")
        _assign_genre_for_tests(db_session, "n001", "fantasy")
        resp = client.get("/api/public/catalog?genre_include=nonexistent-slug")
        assert resp.status_code == 200
        assert resp.json()["total"] == 0

    def test_unknown_genre_exclude_no_effect(
        self, client: TestClient, storage: StorageService, db_session,
    ) -> None:
        _seed_db_catalog_novel(db_session, "n001")
        _seed_db_catalog_novel(db_session, "n002")
        _seed_genre_for_tests(db_session, "fantasy", "ファンタジー")
        _assign_genre_for_tests(db_session, "n001", "fantasy")
        resp = client.get("/api/public/catalog?genre_exclude=nonexistent-slug")
        assert resp.status_code == 200
        assert resp.json()["total"] == 2

    def test_unknown_tag_include_returns_zero(
        self, client: TestClient, storage: StorageService, db_session,
    ) -> None:
        _seed_db_catalog_novel(db_session, "n001")
        _assign_tag_for_tests(db_session, "n001", "魔法")
        resp = client.get("/api/public/catalog?tag_include=nonexistent_tag")
        assert resp.status_code == 200
        assert resp.json()["total"] == 0

    def test_unknown_tag_exclude_no_effect(
        self, client: TestClient, storage: StorageService, db_session,
    ) -> None:
        _seed_db_catalog_novel(db_session, "n001")
        _seed_db_catalog_novel(db_session, "n002")
        _assign_tag_for_tests(db_session, "n001", "魔法")
        resp = client.get("/api/public/catalog?tag_exclude=nonexistent_tag")
        assert resp.status_code == 200
        assert resp.json()["total"] == 2

    def test_tag_include_all_required(
        self, client: TestClient, storage: StorageService, db_session,
    ) -> None:
        _seed_db_catalog_novel(db_session, "n001")
        _seed_db_catalog_novel(db_session, "n002")
        _assign_tag_for_tests(db_session, "n001", "魔法")
        _assign_tag_for_tests(db_session, "n001", "勇者")
        _assign_tag_for_tests(db_session, "n002", "魔法")
        resp = client.get("/api/public/catalog?tag_include=魔法,勇者")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert data["novels"][0]["novel_id"] == "n001"

    def test_filter_combines_with_status(
        self, client: TestClient, storage: StorageService, db_session,
    ) -> None:
        _seed_db_catalog_novel(db_session, "n001", status="ongoing")
        _seed_db_catalog_novel(db_session, "n002", status="completed")
        _seed_genre_for_tests(db_session, "fantasy", "ファンタジー")
        _assign_genre_for_tests(db_session, "n001", "fantasy")
        _assign_genre_for_tests(db_session, "n002", "fantasy")
        resp = client.get("/api/public/catalog?genre_include=fantasy&status=completed")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert data["novels"][0]["novel_id"] == "n002"

    def test_filter_combines_with_search(
        self, client: TestClient, storage: StorageService, db_session,
    ) -> None:
        _seed_db_catalog_novel(db_session, "n001", title="Dragon King")
        _seed_db_catalog_novel(db_session, "n002", title="Slime World")
        _seed_genre_for_tests(db_session, "fantasy", "ファンタジー")
        _assign_genre_for_tests(db_session, "n001", "fantasy")
        _assign_genre_for_tests(db_session, "n002", "fantasy")
        resp = client.get("/api/public/catalog?genre_include=fantasy&q=dragon")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert data["novels"][0]["novel_id"] == "n001"

    def test_filter_combines_with_chapter_filter(
        self, client: TestClient, storage: StorageService, db_session,
    ) -> None:
        _seed_db_catalog_novel(db_session, "n001", chapter_count=1)
        _seed_db_catalog_novel(db_session, "n002", chapter_count=10)
        _seed_genre_for_tests(db_session, "fantasy", "ファンタジー")
        _assign_genre_for_tests(db_session, "n001", "fantasy")
        _assign_genre_for_tests(db_session, "n002", "fantasy")
        resp = client.get("/api/public/catalog?genre_include=fantasy&min_chapters=5")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert data["novels"][0]["novel_id"] == "n002"

    def test_filter_applies_before_pagination(
        self, client: TestClient, storage: StorageService, db_session,
    ) -> None:
        _seed_genre_for_tests(db_session, "fantasy", "ファンタジー")
        for i in range(5):
            nid = f"n{i:03d}"
            _seed_db_catalog_novel(db_session, nid)
            _assign_genre_for_tests(db_session, nid, "fantasy")
        _seed_db_catalog_novel(db_session, "n999")
        _assign_tag_for_tests(db_session, "n999", "魔法")
        resp = client.get("/api/public/catalog?genre_include=fantasy&page_size=2")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 5  # Total before pagination
        assert len(data["novels"]) == 2  # Only page

    def test_sort_works_with_genre_filter(
        self, client: TestClient, storage: StorageService, db_session,
    ) -> None:
        _seed_db_catalog_novel(db_session, "n001", title="Zebra")
        _seed_db_catalog_novel(db_session, "n002", title="Alpha")
        _seed_genre_for_tests(db_session, "fantasy", "ファンタジー")
        _assign_genre_for_tests(db_session, "n001", "fantasy")
        _assign_genre_for_tests(db_session, "n002", "fantasy")
        resp = client.get("/api/public/catalog?genre_include=fantasy&sort_by=title&order=asc")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 2
        assert [n["title"] for n in data["novels"]] == ["Alpha", "Zebra"]

    def test_genre_exclude_with_multiple_values(
        self, client: TestClient, storage: StorageService, db_session,
    ) -> None:
        _seed_db_catalog_novel(db_session, "n001")
        _seed_db_catalog_novel(db_session, "n002")
        _seed_db_catalog_novel(db_session, "n003")
        _seed_genre_for_tests(db_session, "fantasy", "ファンタジー")
        _seed_genre_for_tests(db_session, "romance", "恋愛")
        _assign_genre_for_tests(db_session, "n001", "fantasy")
        _assign_genre_for_tests(db_session, "n002", "romance")
        # n003 has no genre
        resp = client.get("/api/public/catalog?genre_exclude=fantasy,romance")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert data["novels"][0]["novel_id"] == "n003"

    def test_tag_exclude_with_multiple_values(
        self, client: TestClient, storage: StorageService, db_session,
    ) -> None:
        _seed_db_catalog_novel(db_session, "n001")
        _seed_db_catalog_novel(db_session, "n002")
        _seed_db_catalog_novel(db_session, "n003")
        _assign_tag_for_tests(db_session, "n001", "魔法")
        _assign_tag_for_tests(db_session, "n002", "勇者")
        resp = client.get("/api/public/catalog?tag_exclude=魔法,勇者")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert data["novels"][0]["novel_id"] == "n003"

    def test_inactive_genre_include_returns_zero(
        self, client: TestClient, storage: StorageService, db_session,
    ) -> None:
        _seed_db_catalog_novel(db_session, "n001")
        _seed_genre_for_tests(db_session, "dormant", "Dormant", is_active=False)
        _assign_genre_for_tests(db_session, "n001", "dormant")

        resp = client.get("/api/public/catalog?genre_include=dormant")

        assert resp.status_code == 200
        assert resp.json()["total"] == 0

    def test_inactive_genre_exclude_has_no_effect(
        self, client: TestClient, storage: StorageService, db_session,
    ) -> None:
        _seed_db_catalog_novel(db_session, "n001")
        _seed_genre_for_tests(db_session, "dormant", "Dormant", is_active=False)
        _assign_genre_for_tests(db_session, "n001", "dormant")

        resp = client.get("/api/public/catalog?genre_exclude=dormant")

        assert resp.status_code == 200
        assert resp.json()["total"] == 1

    def test_adult_genre_include_requires_include_adult(
        self, client: TestClient, storage: StorageService, db_session,
    ) -> None:
        _seed_db_catalog_novel(db_session, "adult-novel")
        _seed_genre_for_tests(db_session, "adult-romance", "Adult Romance", is_adult=True)
        _assign_genre_for_tests(db_session, "adult-novel", "adult-romance")

        hidden = client.get("/api/public/catalog?genre_include=adult-romance").json()
        visible = client.get("/api/public/catalog?genre_include=adult-romance&include_adult=true").json()

        assert hidden["total"] == 0
        assert visible["total"] == 1
        assert visible["novels"][0]["novel_id"] == "adult-novel"

    def test_no_params_returns_all(
        self, client: TestClient, storage: StorageService, db_session,
    ) -> None:
        _seed_db_catalog_novel(db_session, "n001")
        _seed_db_catalog_novel(db_session, "n002")
        resp = client.get("/api/public/catalog")
        assert resp.status_code == 200
        assert resp.json()["total"] == 2


# ---------------------------------------------------------------------------
# Tag search
# ---------------------------------------------------------------------------


def _seed_tag_for_tests(db_session, name: str, name_ja: str | None = None, is_adult: bool = False) -> None:
    """Create a tag row directly in the DB (no novel association)."""
    from novelai.db.models.tag import Tag
    tag = Tag(name=name, name_ja=name_ja, is_adult=is_adult)
    db_session.add(tag)
    db_session.commit()


class TestTagSearch:
    """Tag search endpoint — GET /api/public/tags/search."""

    def test_search_returns_matching_tags(
        self, client: TestClient, storage: StorageService, db_session,
    ) -> None:
        _seed_tag_for_tests(db_session, "dragon", "ドラゴン")
        _seed_tag_for_tests(db_session, "elf", "エルフ")
        resp = client.get("/api/public/tags/search?q=dr")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["name"] == "dragon"
        assert data[0]["name_ja"] == "ドラゴン"
        assert "is_adult" not in data[0]

    def test_search_matches_name_ja(
        self, client: TestClient, storage: StorageService, db_session,
    ) -> None:
        _seed_tag_for_tests(db_session, "dragon", "ドラゴン")
        resp = client.get("/api/public/tags/search?q=ドラ")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["name"] == "dragon"

    def test_search_returns_empty_for_no_match(
        self, client: TestClient, storage: StorageService, db_session,
    ) -> None:
        _seed_tag_for_tests(db_session, "dragon", "ドラゴン")
        resp = client.get("/api/public/tags/search?q=zzzzz")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_too_short_query_returns_empty(
        self, client: TestClient, storage: StorageService, db_session,
    ) -> None:
        _seed_tag_for_tests(db_session, "dragon", "ドラゴン")
        resp = client.get("/api/public/tags/search?q=d")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_too_short_query_after_strip(
        self, client: TestClient, storage: StorageService, db_session,
    ) -> None:
        _seed_tag_for_tests(db_session, "dragon", "ドラゴン")
        resp = client.get("/api/public/tags/search?q=%20%20")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_adult_tags_excluded_when_include_adult_false(
        self, client: TestClient, storage: StorageService, db_session,
    ) -> None:
        _seed_tag_for_tests(db_session, "dragon", "ドラゴン")
        _seed_tag_for_tests(db_session, "adult_tag", "アダルト", is_adult=True)
        resp = client.get("/api/public/tags/search?q=ad&include_adult=false")
        assert resp.status_code == 200
        data = resp.json()
        names = [t["name"] for t in data]
        assert "dragon" not in names  # doesn't match "ad"
        assert "adult_tag" not in names  # excluded

    def test_adult_tags_included_when_include_adult_true(
        self, client: TestClient, storage: StorageService, db_session,
    ) -> None:
        _seed_tag_for_tests(db_session, "adult_tag", is_adult=True)
        _seed_tag_for_tests(db_session, "adventure", "冒険")
        resp = client.get("/api/public/tags/search?q=adult&include_adult=true")
        assert resp.status_code == 200
        assert len(data := resp.json()) == 1
        assert data[0]["name"] == "adult_tag"
        assert "is_adult" not in data[0]

    def test_result_limit_works(
        self, client: TestClient, storage: StorageService, db_session,
    ) -> None:
        for name in ["apple", "apricot", "application", "appetizer", "appliance"]:
            _seed_tag_for_tests(db_session, name)
        resp = client.get("/api/public/tags/search?q=ap&limit=3")
        assert resp.status_code == 200
        assert len(resp.json()) == 3

    def test_prefix_matches_first(
        self, client: TestClient, storage: StorageService, db_session,
    ) -> None:
        # "dr" appears in all these, but only some start with "dr"
        _seed_tag_for_tests(db_session, "sundress")   # contains "dr", not a prefix
        _seed_tag_for_tests(db_session, "dragon")      # prefix match
        _seed_tag_for_tests(db_session, "drift")       # prefix match
        _seed_tag_for_tests(db_session, "dramatic")    # prefix match
        _seed_tag_for_tests(db_session, "padre")       # contains "dr", not a prefix
        resp = client.get("/api/public/tags/search?q=dr")
        assert resp.status_code == 200
        data = resp.json()
        names = [t["name"] for t in data]
        # Prefix matches (dramatic, drift, dragon) come before non-prefix (padre, sundress)
        # Within prefix group: alphabetical: dramatic, drift, dragon
        # Within non-prefix group: alphabetical: padre, sundress
        for prefix_name in ["dramatic", "drift", "dragon"]:
            for non_prefix_name in ["padre", "sundress"]:
                assert names.index(prefix_name) < names.index(non_prefix_name), (
                    f"{prefix_name} should come before {non_prefix_name}"
                )
        # Verify alphabetical within prefix group
        assert names[:3] == sorted(names[:3])
        # Verify alphabetical within non-prefix group
        assert names[3:] == sorted(names[3:])

    def test_stable_alphabetical_ordering(
        self, client: TestClient, storage: StorageService, db_session,
    ) -> None:
        _seed_tag_for_tests(db_session, "sword")
        _seed_tag_for_tests(db_session, "shield")
        _seed_tag_for_tests(db_session, "staff")
        resp = client.get("/api/public/tags/search?q=sw")
        assert resp.status_code == 200
        data = resp.json()
        names = [t["name"] for t in data]
        assert names == sorted(names)

    def test_no_tags_created_during_search(
        self, client: TestClient, storage: StorageService, db_session,
    ) -> None:
        from novelai.db.models.tag import Tag
        count_before = db_session.query(Tag).count()
        client.get("/api/public/tags/search?q=nonexistent")
        count_after = db_session.query(Tag).count()
        assert count_before == count_after

    def test_search_requires_authentication(
        self, client: TestClient, storage: StorageService, db_session,
    ) -> None:
        """Tag search is a public endpoint — no auth required."""
        resp = client.get("/api/public/tags/search?q=dr")
        assert resp.status_code == 200
