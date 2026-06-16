"""Tests for the public catalog router (/api/public/).

Uses FastAPI TestClient + temp dir StorageService; DB session via SQLAlchemy.
"""

from __future__ import annotations

import json
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
        import json
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
        import json
        from pathlib import Path
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
    def _seed_genre(self, db_session, slug: str, name_ja: str, display_order: int = 0) -> None:
        from novelai.db.models.genre import Genre
        genre = Genre(slug=slug, name_ja=name_ja, name_en=slug, display_order=display_order, is_active=True)
        db_session.add(genre)
        db_session.commit()

    def _assign_genre(self, db_session, novel_slug: str, genre_slug: str) -> None:
        from sqlalchemy import text
        novel = db_session.query(Novel).filter_by(slug=novel_slug).one_or_none()
        if novel is None:
            novel = Novel(slug=novel_slug, title="Temp", language="ja", status="ongoing")
            db_session.add(novel)
            db_session.flush()
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
            novel = Novel(slug=novel_slug, title="Temp", language="ja", status="ongoing")
            db_session.add(novel)
            db_session.flush()
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
