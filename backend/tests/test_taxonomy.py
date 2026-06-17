"""Tests for taxonomy schema, genre seed data, and the public genre endpoint.

Uses SQLite in-memory; no Postgres required.
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from novelai.db.base import Base
from novelai.db.models.genre import Genre, novel_genres
from novelai.db.models.novel import Novel
from novelai.db.models.tag import Tag, novel_tags

_SQLITE = "sqlite:///:memory:"

# The curated genre seed list from the migration
_GENRE_SEEDS = [
    ("isekai-tensei", "異世界転生", "Isekai (Reincarnation)", False, 1),
    ("isekai-tenni", "異世界転移", "Isekai (Transfer)", False, 2),
    ("fantasy", "ファンタジー", "Fantasy", False, 3),
    ("modern-fantasy", "現代ファンタジー", "Modern Fantasy", False, 4),
    ("sf", "SF", "Sci-Fi", False, 5),
    ("romance", "恋愛", "Romance", False, 6),
    ("horror", "ホラー", "Horror", False, 7),
    ("mystery", "ミステリー", "Mystery", False, 8),
    ("action", "アクション", "Action", False, 9),
    ("comedy", "コメディ", "Comedy", False, 10),
    ("drama", "ドラマ", "Drama", False, 11),
    ("slice-of-life", "日常", "Slice of Life", False, 12),
    ("historical", "歴史", "Historical", False, 13),
    ("poetry", "詩", "Poetry", False, 14),
    ("essay", "エッセイ", "Essay", False, 15),
    ("other", "その他", "Other", False, 16),
    ("adult-romance", "大人向け恋愛", "Adult Romance", True, 101),
    ("adult-fantasy", "大人向けファンタジー", "Adult Fantasy", True, 102),
    ("adult-sf", "大人向けSF", "Adult Sci-Fi", True, 103),
    ("adult-other", "大人向けその他", "Adult Other", True, 104),
]


@pytest.fixture()
def session():
    engine = create_engine(_SQLITE)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    sess = Session()
    yield sess
    sess.close()
    Base.metadata.drop_all(engine)


def _seed_genres(session) -> None:
    """Insert the curated genre seed list."""
    for slug, name_ja, name_en, is_adult, display_order in _GENRE_SEEDS:
        session.add(Genre(
            slug=slug,
            name_ja=name_ja,
            name_en=name_en,
            is_adult=is_adult,
            display_order=display_order,
            is_active=True,
        ))
    session.commit()


# ---------------------------------------------------------------------------
# Schema tests
# ---------------------------------------------------------------------------

class TestTaxonomySchema:
    def test_genres_table_exists(self, session) -> None:
        inspector = inspect(session.bind)
        assert "genres" in inspector.get_table_names()

    def test_tags_table_exists(self, session) -> None:
        inspector = inspect(session.bind)
        assert "tags" in inspector.get_table_names()

    def test_novel_genres_table_exists(self, session) -> None:
        inspector = inspect(session.bind)
        assert "novel_genres" in inspector.get_table_names()

    def test_novel_tags_table_exists(self, session) -> None:
        inspector = inspect(session.bind)
        assert "novel_tags" in inspector.get_table_names()

    def test_genres_columns(self, session) -> None:
        inspector = inspect(session.bind)
        columns = {col["name"] for col in inspector.get_columns("genres")}
        expected = {"id", "slug", "name_ja", "name_en", "is_adult", "display_order", "is_active", "created_at"}
        assert expected.issubset(columns)

    def test_tags_columns(self, session) -> None:
        inspector = inspect(session.bind)
        columns = {col["name"] for col in inspector.get_columns("tags")}
        expected = {"id", "name", "name_ja", "is_adult", "created_at", "updated_at"}
        assert expected.issubset(columns)

    def test_novel_genres_columns(self, session) -> None:
        inspector = inspect(session.bind)
        columns = {col["name"] for col in inspector.get_columns("novel_genres")}
        expected = {"novel_id", "genre_id", "assigned_by", "assigned_at"}
        assert expected.issubset(columns)

    def test_novel_tags_columns(self, session) -> None:
        inspector = inspect(session.bind)
        columns = {col["name"] for col in inspector.get_columns("novel_tags")}
        expected = {"novel_id", "tag_id", "origin", "assigned_by", "assigned_at"}
        assert expected.issubset(columns)


# ---------------------------------------------------------------------------
# Genre model tests
# ---------------------------------------------------------------------------

class TestGenreModel:
    def test_create_genre(self, session) -> None:
        genre = Genre(slug="test-genre", name_ja="テスト", name_en="Test", is_adult=False)
        session.add(genre)
        session.commit()
        result = session.query(Genre).filter_by(slug="test-genre").one()
        assert result.name_ja == "テスト"
        assert result.name_en == "Test"
        assert result.is_adult is False
        assert result.is_active is True
        assert result.display_order == 0

    def test_slug_unique_constraint(self, session) -> None:
        session.add(Genre(slug="dup", name_ja="A"))
        session.commit()
        session.add(Genre(slug="dup", name_ja="B"))
        with pytest.raises(IntegrityError):
            session.commit()

    def test_is_adult_defaults_false(self, session) -> None:
        session.add(Genre(slug="safe", name_ja="Safe"))
        session.commit()
        result = session.query(Genre).filter_by(slug="safe").one()
        assert result.is_adult is False

    def test_is_active_defaults_true(self, session) -> None:
        session.add(Genre(slug="active-test", name_ja="Active"))
        session.commit()
        result = session.query(Genre).filter_by(slug="active-test").one()
        assert result.is_active is True

    def test_name_en_nullable(self, session) -> None:
        session.add(Genre(slug="ja-only", name_ja="日本語のみ"))
        session.commit()
        result = session.query(Genre).filter_by(slug="ja-only").one()
        assert result.name_en is None


# ---------------------------------------------------------------------------
# Genre seed data tests
# ---------------------------------------------------------------------------

class TestGenreSeedData:
    def test_seed_count(self, session) -> None:
        _seed_genres(session)
        count = session.query(Genre).count()
        assert count == 20

    def test_all_slugs_unique(self, session) -> None:
        _seed_genres(session)
        slugs = [g.slug for g in session.query(Genre).all()]
        assert len(slugs) == len(set(slugs))

    def test_adult_genre_count(self, session) -> None:
        _seed_genres(session)
        adult_count = session.query(Genre).filter_by(is_adult=True).count()
        assert adult_count == 4

    def test_non_adult_genre_count(self, session) -> None:
        _seed_genres(session)
        non_adult = session.query(Genre).filter_by(is_adult=False).count()
        assert non_adult == 16

    def test_all_seeded_genres_active(self, session) -> None:
        _seed_genres(session)
        inactive = session.query(Genre).filter_by(is_active=False).count()
        assert inactive == 0

    def test_isekai_tensei_present(self, session) -> None:
        _seed_genres(session)
        genre = session.query(Genre).filter_by(slug="isekai-tensei").one()
        assert genre.name_ja == "異世界転生"
        assert genre.name_en == "Isekai (Reincarnation)"
        assert genre.is_adult is False

    def test_adult_romance_present(self, session) -> None:
        _seed_genres(session)
        genre = session.query(Genre).filter_by(slug="adult-romance").one()
        assert genre.name_ja == "大人向け恋愛"
        assert genre.is_adult is True

    def test_display_order_set(self, session) -> None:
        _seed_genres(session)
        fantasy = session.query(Genre).filter_by(slug="fantasy").one()
        assert fantasy.display_order == 3
        adult_other = session.query(Genre).filter_by(slug="adult-other").one()
        assert adult_other.display_order == 104


# ---------------------------------------------------------------------------
# Tag model tests
# ---------------------------------------------------------------------------

class TestTagModel:
    def test_tags_table_starts_empty(self, session) -> None:
        count = session.query(Tag).count()
        assert count == 0

    def test_create_tag(self, session) -> None:
        tag = Tag(name="isekai", name_ja="異世界")
        session.add(tag)
        session.commit()
        result = session.query(Tag).filter_by(name="isekai").one()
        assert result.name_ja == "異世界"
        assert result.is_adult is False

    def test_tag_name_unique(self, session) -> None:
        session.add(Tag(name="dup"))
        session.commit()
        session.add(Tag(name="dup"))
        with pytest.raises(IntegrityError):
            session.commit()


# ---------------------------------------------------------------------------
# Junction table tests
# ---------------------------------------------------------------------------

class TestJunctionTables:
    def test_novel_genre_assignment(self, session) -> None:
        _seed_genres(session)
        novel = Novel(slug="test-novel", title="Test", language="ja", status="ongoing")
        session.add(novel)
        session.commit()

        fantasy = session.query(Genre).filter_by(slug="fantasy").one()
        session.execute(novel_genres.insert().values(
            novel_id=novel.id, genre_id=fantasy.id, assigned_by="test",
        ))
        session.commit()

        # Verify through relationship
        session.refresh(novel)
        assert len(novel.genres) == 1
        assert novel.genres[0].slug == "fantasy"

    def test_novel_genre_duplicate_prevented(self, session) -> None:
        _seed_genres(session)
        novel = Novel(slug="dup-test", title="Dup", language="ja", status="ongoing")
        session.add(novel)
        session.commit()

        fantasy = session.query(Genre).filter_by(slug="fantasy").one()
        session.execute(novel_genres.insert().values(
            novel_id=novel.id, genre_id=fantasy.id, assigned_by="test",
        ))
        session.commit()

        # Attempting duplicate should raise
        with pytest.raises(IntegrityError):
            session.execute(novel_genres.insert().values(
                novel_id=novel.id, genre_id=fantasy.id, assigned_by="test",
            ))
            session.commit()

    def test_novel_tag_assignment(self, session) -> None:
        novel = Novel(slug="tag-test", title="Tag Test", language="ja", status="ongoing")
        session.add(novel)
        tag = Tag(name="magic")
        session.add(tag)
        session.commit()

        session.execute(novel_tags.insert().values(
            novel_id=novel.id, tag_id=tag.id, origin="test", assigned_by="test",
        ))
        session.commit()

        session.refresh(novel)
        assert len(novel.tags) == 1
        assert novel.tags[0].name == "magic"

    def test_novel_tag_duplicate_prevented(self, session) -> None:
        novel = Novel(slug="tag-dup", title="Tag Dup", language="ja", status="ongoing")
        session.add(novel)
        tag = Tag(name="dragons")
        session.add(tag)
        session.commit()

        session.execute(novel_tags.insert().values(
            novel_id=novel.id, tag_id=tag.id, origin="test", assigned_by="test",
        ))
        session.commit()

        with pytest.raises(IntegrityError):
            session.execute(novel_tags.insert().values(
                novel_id=novel.id, tag_id=tag.id, origin="test", assigned_by="test",
            ))
            session.commit()

    def test_cascade_delete_novel_removes_genre_assignment(self, session) -> None:
        _seed_genres(session)
        novel = Novel(slug="cascade-test", title="Cascade", language="ja", status="ongoing")
        session.add(novel)
        session.commit()

        fantasy = session.query(Genre).filter_by(slug="fantasy").one()
        session.execute(novel_genres.insert().values(
            novel_id=novel.id, genre_id=fantasy.id, assigned_by="test",
        ))
        session.commit()

        # Count assignments before delete
        count_before = session.execute(
            text("SELECT COUNT(*) FROM novel_genres WHERE genre_id = :gid"),
            {"gid": fantasy.id},
        ).scalar()
        assert count_before == 1

        session.delete(novel)
        session.commit()

        count_after = session.execute(
            text("SELECT COUNT(*) FROM novel_genres WHERE genre_id = :gid"),
            {"gid": fantasy.id},
        ).scalar()
        assert count_after == 0


# ---------------------------------------------------------------------------
# GET /api/public/genres endpoint tests
# ---------------------------------------------------------------------------

class TestPublicGenreEndpoint:
    @pytest.fixture()
    def client(self):
        from starlette.middleware.sessions import SessionMiddleware
        from sqlalchemy.pool import StaticPool

        from novelai.api.routers.public import router as public_router
        from novelai.api.routers.dependencies import get_db_session

        engine = create_engine(
            _SQLITE,
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(engine)
        Session = sessionmaker(bind=engine)
        sess = Session()
        _seed_genres(sess)

        app = FastAPI()
        app.add_middleware(SessionMiddleware, secret_key="test", https_only=False)
        app.include_router(public_router)

        def _override_db():
            yield sess

        app.dependency_overrides[get_db_session] = _override_db
        test_client = TestClient(app, raise_server_exceptions=True)
        yield test_client, sess
        sess.close()
        Base.metadata.drop_all(engine)
        engine.dispose()

    def test_returns_all_active_genres(self, client) -> None:
        c, _ = client
        resp = c.get("/api/public/genres?include_adult=true")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 20

    def test_response_shape(self, client) -> None:
        c, _ = client
        resp = c.get("/api/public/genres")
        data = resp.json()
        first = data[0]
        assert "slug" in first
        assert "name_ja" in first
        assert "name_en" in first
        assert "is_adult" not in first

    def test_exclude_adult_genres(self, client) -> None:
        c, _ = client
        resp = c.get("/api/public/genres?include_adult=false")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 16
        slugs = {g["slug"] for g in data}
        adult_slugs = {"adult-romance", "adult-fantasy", "adult-sf", "adult-other"}
        assert adult_slugs.isdisjoint(slugs)

    def test_exclude_adult_by_default(self, client) -> None:
        c, _ = client
        resp = c.get("/api/public/genres")
        data = resp.json()
        slugs = {g["slug"] for g in data}
        adult_slugs = {"adult-romance", "adult-fantasy", "adult-sf", "adult-other"}
        assert adult_slugs.isdisjoint(slugs)

    def test_adult_genres_included_when_include_adult_true(self, client) -> None:
        c, _ = client
        resp = c.get("/api/public/genres?include_adult=true")
        data = resp.json()
        slugs = {g["slug"] for g in data}
        adult_slugs = {"adult-romance", "adult-fantasy", "adult-sf", "adult-other"}
        assert adult_slugs.issubset(slugs)

    def test_ordered_by_display_order(self, client) -> None:
        c, _ = client
        resp = c.get("/api/public/genres?include_adult=true")
        data = resp.json()
        slugs = [g["slug"] for g in data]
        assert slugs.index("isekai-tensei") < slugs.index("adult-romance")
        assert slugs.index("fantasy") < slugs.index("adult-fantasy")

    def test_inactive_genres_excluded(self, client) -> None:
        c, sess = client
        genre = sess.query(Genre).filter_by(slug="poetry").one()
        genre.is_active = False
        sess.commit()

        resp = c.get("/api/public/genres?include_adult=true")
        data = resp.json()
        slugs = [g["slug"] for g in data]
        assert "poetry" not in slugs
        assert len(data) == 19

    def test_no_auth_required(self, client) -> None:
        c, _ = client
        resp = c.get("/api/public/genres")
        assert resp.status_code == 200
