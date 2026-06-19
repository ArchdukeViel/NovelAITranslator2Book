"""Contract tests for admin novel taxonomy endpoints (TAXONOMY-4B).

Tests cover GET + PUT /api/admin/novels/{novel_id}/taxonomy.
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from starlette.middleware.sessions import SessionMiddleware

from novelai.api.auth.session import SessionUser, get_current_user
from novelai.api.routers.admin_taxonomy import router as admin_taxonomy_router
from novelai.api.routers.auth import router as auth_router
from novelai.api.routers.dependencies import get_db_session
from novelai.config.settings import settings
from novelai.db.base import Base
from novelai.db.models.genre import Genre, novel_genres
from novelai.db.models.novel import Novel
from novelai.db.models.tag import Tag, novel_tags

# Import all models so Base.metadata.create_all picks up every FK target.
import novelai.db.models.chapter  # noqa: F401
import novelai.db.models.jobs  # noqa: F401
import novelai.db.models.system  # noqa: F401
import novelai.db.models.users  # noqa: F401


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def db_engine():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    yield engine
    Base.metadata.drop_all(engine)


@pytest.fixture()
def db_session(db_engine):
    Session = sessionmaker(bind=db_engine, autocommit=False, autoflush=True)
    sess = Session()
    yield sess
    sess.close()


@pytest.fixture()
def app(db_session):
    _app = FastAPI()
    _app.add_middleware(SessionMiddleware, secret_key="test", https_only=False)

    # Mutable state for test-controlled user override
    current: dict = {"user": None}

    def _user_override():
        return current["user"] or SessionUser(user_id=None, email=None, role="guest")

    def _db_override():
        yield db_session
        db_session.commit()

    _app.dependency_overrides[get_db_session] = _db_override
    _app.dependency_overrides[get_current_user] = _user_override
    _app.include_router(auth_router)
    _app.include_router(admin_taxonomy_router, prefix="/api/admin/novels")
    _app.state.current_user = current
    return _app


@pytest.fixture()
def client(app):
    return TestClient(app, raise_server_exceptions=True)


@pytest.fixture()
def owner_client(app):
    """Client pre-authenticated as owner via dependency override."""
    set_user(app, user_id=1, role="owner")
    c = TestClient(app, raise_server_exceptions=True)
    token_resp = c.get("/api/auth/csrf")
    c.headers.update({"X-CSRF-Token": token_resp.json()["csrf_token"]})
    yield c
    set_user(app, user_id=None, role="guest")


def set_user(app: FastAPI, user_id: int | None = None, role: str = "guest") -> None:
    """Set the current user override in the test app."""
    app.state.current_user["user"] = SessionUser(
        user_id=user_id,
        email=f"user{user_id}@test.com" if user_id else None,
        role=role,
    )


# ---------------------------------------------------------------------------
# Seed helpers
# ---------------------------------------------------------------------------


def _seed_novel(db_session, slug: str, title: str = "Test Novel") -> Novel:
    novel = Novel(slug=slug, title=title, language="ja", status="ongoing")
    db_session.add(novel)
    db_session.flush()
    return novel


def _seed_genre(
    db_session, slug: str, name_ja: str,
    display_order: int = 0, is_active: bool = True,
) -> Genre:
    genre = Genre(
        slug=slug, name_ja=name_ja, name_en=slug,
        display_order=display_order, is_active=is_active,
    )
    db_session.add(genre)
    db_session.flush()
    return genre


def _assign_genre_as(
    db_session, novel_id: int, genre_id: int, assigned_by: str = "scraper",
) -> None:
    db_session.execute(
        novel_genres.insert().values(
            novel_id=novel_id,
            genre_id=genre_id,
            assigned_by=assigned_by,
        )
    )
    db_session.commit()


def _seed_tag(db_session, name: str) -> Tag:
    tag = Tag(name=name)
    db_session.add(tag)
    db_session.flush()
    return tag


def _assign_tag_as(
    db_session, novel_id: int, tag_id: int,
    assigned_by: str = "scraper", origin: str = "scraper",
) -> None:
    db_session.execute(
        novel_tags.insert().values(
            novel_id=novel_id,
            tag_id=tag_id,
            assigned_by=assigned_by,
            origin=origin,
        )
    )
    db_session.commit()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestAdminTaxonomyAuth:
    """Auth enforcement tests."""

    def test_get_requires_owner(self, client: TestClient) -> None:
        """Unauthenticated GET returns 401."""
        resp = client.get("/api/admin/novels/n001/taxonomy")
        assert resp.status_code == 401

    def test_put_requires_owner(self, client: TestClient) -> None:
        """Unauthenticated PUT returns 401."""
        resp = client.put("/api/admin/novels/n001/taxonomy", json={})
        assert resp.status_code == 401

    def test_get_with_owner(
        self, owner_client: TestClient, db_session,
    ) -> None:
        """Owner can GET taxonomy (returns 200 or 404 for missing novel)."""
        resp = owner_client.get("/api/admin/novels/n001/taxonomy")
        # n001 doesn't exist, expect 404
        assert resp.status_code == 404


class TestAdminTaxonomyGet:
    """GET endpoint behavior."""

    def test_get_missing_novel(self, owner_client: TestClient) -> None:
        """GET returns 404 for non-existent novel."""
        resp = owner_client.get("/api/admin/novels/nonexistent/taxonomy")
        assert resp.status_code == 404
        assert "not found" in resp.json()["detail"].lower()

    def test_get_empty_taxonomy(
        self, owner_client: TestClient, db_session,
    ) -> None:
        """GET returns empty lists when no genres/tags assigned."""
        _seed_novel(db_session, "n001")
        resp = owner_client.get("/api/admin/novels/n001/taxonomy")
        assert resp.status_code == 200
        data = resp.json()
        assert data["novel_id"] == "n001"
        assert data["genres"] == []
        assert data["tags"] == []

    def test_get_returns_genre_slugs(
        self, owner_client: TestClient, db_session,
    ) -> None:
        """GET returns assigned genre slugs."""
        novel = _seed_novel(db_session, "n001")
        genre = _seed_genre(db_session, "fantasy", "ファンタジー")
        _assign_genre_as(db_session, novel.id, genre.id, assigned_by="scraper")
        resp = owner_client.get("/api/admin/novels/n001/taxonomy")
        assert resp.status_code == 200
        assert resp.json()["genres"] == ["fantasy"]

    def test_get_returns_tag_names(
        self, owner_client: TestClient, db_session,
    ) -> None:
        """GET returns assigned tag names."""
        novel = _seed_novel(db_session, "n001")
        tag = _seed_tag(db_session, "魔法")
        _assign_tag_as(db_session, novel.id, tag.id, assigned_by="scraper")
        resp = owner_client.get("/api/admin/novels/n001/taxonomy")
        assert resp.status_code == 200
        assert resp.json()["tags"] == ["魔法"]

    def test_get_filters_inactive_genres(
        self, owner_client: TestClient, db_session,
    ) -> None:
        """GET excludes inactive genres."""
        novel = _seed_novel(db_session, "n001")
        g1 = _seed_genre(db_session, "active-genre", "アクティブ")
        g2 = _seed_genre(db_session, "inactive-genre", "非アクティブ", is_active=False)
        _assign_genre_as(db_session, novel.id, g1.id, assigned_by="scraper")
        _assign_genre_as(db_session, novel.id, g2.id, assigned_by="scraper")
        resp = owner_client.get("/api/admin/novels/n001/taxonomy")
        assert resp.status_code == 200
        assert resp.json()["genres"] == ["active-genre"]


class TestAdminTaxonomyPut:
    """PUT endpoint behavior."""

    def test_put_missing_novel(self, owner_client: TestClient) -> None:
        """PUT returns 404 for non-existent novel."""
        resp = owner_client.put(
            "/api/admin/novels/nonexistent/taxonomy",
            json={"genre_slugs": [], "tags": []},
        )
        assert resp.status_code == 404
        assert "not found" in resp.json()["detail"].lower()

    def test_put_unknown_genre_slug(
        self, owner_client: TestClient, db_session,
    ) -> None:
        """PUT returns 422 for unknown genre slug."""
        _seed_novel(db_session, "n001")
        resp = owner_client.put(
            "/api/admin/novels/n001/taxonomy",
            json={"genre_slugs": ["nonexistent-slug"], "tags": []},
        )
        assert resp.status_code == 422
        assert "unknown" in resp.json()["detail"].lower()

    def test_put_inactive_genre_slug(
        self, owner_client: TestClient, db_session,
    ) -> None:
        """PUT returns 422 for inactive genre slug."""
        _seed_novel(db_session, "n001")
        _seed_genre(db_session, "dormant", "休眠", is_active=False)
        resp = owner_client.put(
            "/api/admin/novels/n001/taxonomy",
            json={"genre_slugs": ["dormant"], "tags": []},
        )
        assert resp.status_code == 422
        assert "inactive" in resp.json()["detail"].lower()

    def test_put_upserts_new_tag(
        self, owner_client: TestClient, db_session,
    ) -> None:
        """PUT creates tag that doesn't exist yet and assigns it."""
        _seed_novel(db_session, "n001")
        resp = owner_client.put(
            "/api/admin/novels/n001/taxonomy",
            json={"genre_slugs": [], "tags": ["新タグ"]},
        )
        assert resp.status_code == 200
        assert resp.json()["tags"] == ["新タグ"]
        # Verify tag exists in DB
        tag = db_session.query(Tag).filter_by(name="新タグ").one_or_none()
        assert tag is not None

    def test_put_reuses_existing_tag(
        self, owner_client: TestClient, db_session,
    ) -> None:
        """PUT reuses existing tag without creating duplicate."""
        _seed_novel(db_session, "n001")
        _seed_tag(db_session, "existing-tag")
        resp = owner_client.put(
            "/api/admin/novels/n001/taxonomy",
            json={"genre_slugs": [], "tags": ["existing-tag"]},
        )
        assert resp.status_code == 200
        assert resp.json()["tags"] == ["existing-tag"]
        # Only one tag row in DB
        count = db_session.query(Tag).filter_by(name="existing-tag").count()
        assert count == 1

    def test_put_assigns_genres_with_admin_flag(
        self, owner_client: TestClient, db_session,
    ) -> None:
        """PUT assigns genres with assigned_by='admin'."""
        novel = _seed_novel(db_session, "n001")
        _seed_genre(db_session, "fantasy", "ファンタジー")
        owner_client.put(
            "/api/admin/novels/n001/taxonomy",
            json={"genre_slugs": ["fantasy"], "tags": []},
        )
        # Check assigned_by in novel_genres
        row = db_session.execute(
            text("SELECT assigned_by FROM novel_genres WHERE novel_id = :nid"),
            {"nid": novel.id},
        ).one_or_none()
        assert row is not None
        assert row[0] == "admin"

    def test_put_assigns_tags_with_admin_origin(
        self, owner_client: TestClient, db_session,
    ) -> None:
        """PUT assigns tags with assigned_by='admin' and origin='admin'."""
        novel = _seed_novel(db_session, "n001")
        owner_client.put(
            "/api/admin/novels/n001/taxonomy",
            json={"genre_slugs": [], "tags": ["admin-tag"]},
        )
        row = db_session.execute(
            text(
                "SELECT assigned_by, origin FROM novel_tags WHERE novel_id = :nid"
            ),
            {"nid": novel.id},
        ).one_or_none()
        assert row is not None
        assert row[0] == "admin"
        assert row[1] == "admin"

    def test_put_preserves_scraper_assignments(
        self, owner_client: TestClient, db_session,
    ) -> None:
        """PUT does not delete scraper-assigned genres/tags."""
        novel = _seed_novel(db_session, "n001")
        genre = _seed_genre(db_session, "scraper-genre", "スクレイパー")
        tag = _seed_tag(db_session, "scraper-tag")
        _assign_genre_as(db_session, novel.id, genre.id, assigned_by="scraper")
        _assign_tag_as(db_session, novel.id, tag.id, assigned_by="scraper")

        # Admin saves different set
        _seed_genre(db_session, "admin-genre", "管理")
        resp = owner_client.put(
            "/api/admin/novels/n001/taxonomy",
            json={"genre_slugs": ["admin-genre"], "tags": ["admin-tag"]},
        )
        assert resp.status_code == 200
        data = resp.json()
        #scraper-genre should still be present (combined view)
        assert "scraper-genre" in data["genres"]
        assert "scraper-tag" in data["tags"]

    def test_put_promotes_scraper_genre_to_admin(self, owner_client: TestClient, db_session) -> None:
        """When admin selects a genre already assigned by scraper,
        the row is promoted to assigned_by='admin' rather than skipped."""
        novel = _seed_novel(db_session, "n001")
        genre = _seed_genre(db_session, "fantasy", "ファンタジー")
        _assign_genre_as(db_session, novel.id, genre.id, assigned_by="scraper")

        # Verify initial state
        row = db_session.execute(
            text("SELECT assigned_by FROM novel_genres WHERE novel_id = :nid"),
            {"nid": novel.id},
        ).one_or_none()
        assert row is not None
        assert row[0] == "scraper"

        # Admin PUT includes the same genre — should promote it
        resp = owner_client.put(
            "/api/admin/novels/n001/taxonomy",
            json={"genre_slugs": ["fantasy"], "tags": []},
        )
        assert resp.status_code == 200
        assert "fantasy" in resp.json()["genres"]

        # Only one row exists for this novel+genre
        count = db_session.query(novel_genres).filter_by(
            novel_id=novel.id, genre_id=genre.id,
        ).count()
        assert count == 1

        # Row should now be assigned_by="admin" (promoted)
        assigned_by = db_session.execute(
            text("SELECT assigned_by FROM novel_genres WHERE novel_id = :nid"),
            {"nid": novel.id},
        ).scalar()
        assert assigned_by == "admin"

    def test_put_promotes_scraper_tag_to_admin(self, owner_client: TestClient, db_session) -> None:
        """When admin selects a tag already assigned by scraper,
        the row is promoted to assigned_by='admin' and origin='admin'."""
        novel = _seed_novel(db_session, "n001")
        tag = _seed_tag(db_session, "isekai")
        _assign_tag_as(db_session, novel.id, tag.id, assigned_by="scraper", origin="unknown")

        # Verify initial state
        row = db_session.execute(
            text("SELECT assigned_by, origin FROM novel_tags WHERE novel_id = :nid"),
            {"nid": novel.id},
        ).one_or_none()
        assert row is not None
        assert row[0] == "scraper"
        assert row[1] == "unknown"

        # Admin PUT includes the same tag — should promote it
        resp = owner_client.put(
            "/api/admin/novels/n001/taxonomy",
            json={"genre_slugs": [], "tags": ["isekai"]},
        )
        assert resp.status_code == 200
        assert "isekai" in resp.json()["tags"]

        # Only one row exists
        count = db_session.execute(
            text("SELECT COUNT(*) FROM novel_tags WHERE novel_id = :nid"),
            {"nid": novel.id},
        ).scalar()
        assert count == 1

        # Row should now be assigned_by="admin" and origin="admin"
        row2 = db_session.execute(
            text("SELECT assigned_by, origin FROM novel_tags WHERE novel_id = :nid"),
            {"nid": novel.id},
        ).one_or_none()
        assert row2 is not None
        assert row2[0] == "admin"
        assert row2[1] == "admin"

    def test_put_is_idempotent(
        self, owner_client: TestClient, db_session,
    ) -> None:
        """Repeated PUT with same body produces identical result."""
        _seed_novel(db_session, "n001")
        _seed_genre(db_session, "fantasy", "ファンタジー")
        body = {"genre_slugs": ["fantasy"], "tags": ["isekai"]}
        resp1 = owner_client.put("/api/admin/novels/n001/taxonomy", json=body)
        assert resp1.status_code == 200
        resp2 = owner_client.put("/api/admin/novels/n001/taxonomy", json=body)
        assert resp2.status_code == 200
        assert resp1.json() == resp2.json()

    def test_put_replaces_prior_admin_assignments(
        self, owner_client: TestClient, db_session,
    ) -> None:
        """PUT replaces previous admin assignments with new ones."""
        novel = _seed_novel(db_session, "n001")
        _seed_genre(db_session, "fantasy", "ファンタジー")
        _seed_genre(db_session, "romance", "恋愛")

        # First PUT adds fantasy
        owner_client.put(
            "/api/admin/novels/n001/taxonomy",
            json={"genre_slugs": ["fantasy"], "tags": []},
        )
        # Second PUT replaces with romance
        resp2 = owner_client.put(
            "/api/admin/novels/n001/taxonomy",
            json={"genre_slugs": ["romance"], "tags": []},
        )
        assert resp2.status_code == 200
        data = resp2.json()
        assert "fantasy" not in data["genres"]
        assert "romance" in data["genres"]

    def test_put_handles_empty_arrays(
        self, owner_client: TestClient, db_session,
    ) -> None:
        """PUT with empty arrays clears previous admin assignments."""
        novel = _seed_novel(db_session, "n001")
        _seed_genre(db_session, "fantasy", "ファンタジー")

        # First add fantasy
        owner_client.put(
            "/api/admin/novels/n001/taxonomy",
            json={"genre_slugs": ["fantasy"], "tags": []},
        )
        # Then clear
        resp = owner_client.put(
            "/api/admin/novels/n001/taxonomy",
            json={"genre_slugs": [], "tags": []},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["genres"] == []
        assert data["tags"] == []

        # Admin rows should be gone
        admin_rows = db_session.execute(
            novel_genres.select().where(
                novel_genres.c.novel_id == novel.id,
                novel_genres.c.assigned_by == "admin",
            )
        ).all()
        assert len(admin_rows) == 0

    def test_put_normalizes_tags(
        self, owner_client: TestClient, db_session,
    ) -> None:
        """PUT trims whitespace, drops empty strings, deduplicates tags."""
        _seed_novel(db_session, "n001")
        resp = owner_client.put(
            "/api/admin/novels/n001/taxonomy",
            json={
                "genre_slugs": [],
                "tags": ["  spaced  ", "", "dupe", "dupe", "  "],
            },
        )
        assert resp.status_code == 200
        assert resp.json()["tags"] == ["dupe", "spaced"]

    def test_put_returns_combined_scraper_and_admin(
        self, owner_client: TestClient, db_session,
    ) -> None:
        """PUT response includes both scraper and admin assignments."""
        novel = _seed_novel(db_session, "n001")
        g_scraper = _seed_genre(db_session, "action", "アクション")
        t_scraper = _seed_tag(db_session, "adventure")
        _assign_genre_as(db_session, novel.id, g_scraper.id, assigned_by="scraper")
        _assign_tag_as(db_session, novel.id, t_scraper.id, assigned_by="scraper")

        _seed_genre(db_session, "fantasy", "ファンタジー")
        resp = owner_client.put(
            "/api/admin/novels/n001/taxonomy",
            json={"genre_slugs": ["fantasy"], "tags": ["admin-tag"]},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert set(data["genres"]) == {"action", "fantasy"}
        assert set(data["tags"]) == {"adventure", "admin-tag"}


class TestPromotionDurability:
    """Promoted taxonomy items must survive scraper re-scrape."""

    def test_promoted_genre_survives_rescrape(
        self, owner_client: TestClient, db_session,
    ) -> None:
        """Admin promotes a scraper genre, then scraper re-scrape drops that genre.
        The promoted row (assigned_by='admin') must survive."""
        from novelai.services.taxonomy_persistence import persist_taxonomy_assignments

        novel = _seed_novel(db_session, "n001")
        genre = _seed_genre(db_session, "fantasy", "ファンタジー")

        # Scraper initially assigns fantasy
        _assign_genre_as(db_session, novel.id, genre.id, assigned_by="scraper")
        db_session.commit()

        # Admin promotes it
        resp = owner_client.put(
            "/api/admin/novels/n001/taxonomy",
            json={"genre_slugs": ["fantasy"], "tags": []},
        )
        assert resp.status_code == 200

        # Verify promotion
        assigned_by = db_session.execute(
            text("SELECT assigned_by FROM novel_genres WHERE novel_id = :nid"),
            {"nid": novel.id},
        ).scalar()
        assert assigned_by == "admin"

        # Scraper re-scrape: source no longer lists fantasy (empty genre)
        persist_taxonomy_assignments(
            db_session, novel.id,
            {"genre_slug": None, "source_keywords": [], "source_tags": []},
        )
        db_session.commit()

        # Fantasy must still exist (admin row survives)
        count = db_session.execute(
            text("SELECT COUNT(*) FROM novel_genres WHERE novel_id = :nid"),
            {"nid": novel.id},
        ).scalar()
        assert count == 1

        assigned_by_after = db_session.execute(
            text("SELECT assigned_by FROM novel_genres WHERE novel_id = :nid"),
            {"nid": novel.id},
        ).scalar()
        assert assigned_by_after == "admin"

    def test_promoted_tag_survives_rescrape(
        self, owner_client: TestClient, db_session,
    ) -> None:
        """Admin promotes a scraper tag, then scraper re-scrape drops that tag.
        The promoted row must survive."""
        from novelai.services.taxonomy_persistence import persist_taxonomy_assignments

        novel = _seed_novel(db_session, "n001")
        tag = _seed_tag(db_session, "isekai")

        # Scraper initially assigns the tag
        _assign_tag_as(db_session, novel.id, tag.id, assigned_by="scraper", origin="unknown")
        db_session.commit()

        # Admin promotes it
        resp = owner_client.put(
            "/api/admin/novels/n001/taxonomy",
            json={"genre_slugs": [], "tags": ["isekai"]},
        )
        assert resp.status_code == 200

        # Verify promotion
        row = db_session.execute(
            text("SELECT assigned_by, origin FROM novel_tags WHERE novel_id = :nid"),
            {"nid": novel.id},
        ).one_or_none()
        assert row is not None
        assert row[0] == "admin"
        assert row[1] == "admin"

        # Scraper re-scrape: source no longer lists the tag
        persist_taxonomy_assignments(
            db_session, novel.id,
            {"genre_slug": None, "source_keywords": [], "source_tags": []},
        )
        db_session.commit()

        # Tag must still exist (admin row survives)
        count = db_session.execute(
            text("SELECT COUNT(*) FROM novel_tags WHERE novel_id = :nid"),
            {"nid": novel.id},
        ).scalar()
        assert count == 1

        row2 = db_session.execute(
            text("SELECT assigned_by, origin FROM novel_tags WHERE novel_id = :nid"),
            {"nid": novel.id},
        ).one_or_none()
        assert row2 is not None
        assert row2[0] == "admin"
        assert row2[1] == "admin"
