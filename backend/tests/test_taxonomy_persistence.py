"""Tests for taxonomy persistence — connecting scraped metadata to DB taxonomy schema.

Uses SQLite in-memory; no Postgres required.
"""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from novelai.db.base import Base
from novelai.db.models.genre import Genre, novel_genres
from novelai.db.models.novel import Novel
from novelai.db.models.tag import Tag, novel_tags
from novelai.services.taxonomy_persistence import persist_taxonomy_assignments

_SQLITE = "sqlite:///:memory:"


@pytest.fixture()
def engine():
    eng = create_engine(_SQLITE)
    Base.metadata.create_all(eng)
    yield eng
    Base.metadata.drop_all(eng)


@pytest.fixture()
def session(engine):
    Session = sessionmaker(bind=engine)
    sess = Session()
    yield sess
    sess.close()


def _seed_genres(session) -> None:
    _SEEDS = [
        ("isekai-tensei", "異世界転生", "Isekai (Reincarnation)", False, 1),
        ("fantasy", "ファンタジー", "Fantasy", False, 3),
        ("romance", "恋愛", "Romance", False, 6),
        ("sf", "SF", "Sci-Fi", False, 5),
        ("horror", "ホラー", "Horror", False, 7),
        ("adult-romance", "大人向け恋愛", "Adult Romance", True, 101),
    ]
    for slug, name_ja, name_en, is_adult, order in _SEEDS:
        session.add(Genre(
            slug=slug, name_ja=name_ja, name_en=name_en,
            is_adult=is_adult, display_order=order, is_active=True,
        ))
    session.commit()


def _make_novel(session, slug: str) -> Novel:
    novel = Novel(slug=slug, title=f"Novel {slug}", language="ja", publication_status="ongoing")
    session.add(novel)
    session.flush()
    return novel


# ---------------------------------------------------------------------------
# Genre assignment
# ---------------------------------------------------------------------------

class TestGenreAssignment:
    def test_genre_slug_creates_one_novel_genres_row(self, session) -> None:
        _seed_genres(session)
        novel = _make_novel(session, "g01")

        metadata = {"genre_slug": "fantasy", "source_keywords": [], "source_tags": []}
        persist_taxonomy_assignments(session, novel.id, metadata)
        session.commit()

        count = session.execute(
            text("SELECT COUNT(*) FROM novel_genres WHERE novel_id = :id"),
            {"id": novel.id},
        ).scalar()
        assert count == 1

    def test_genre_slug_assigns_correct_genre(self, session) -> None:
        _seed_genres(session)
        novel = _make_novel(session, "g02")

        metadata = {"genre_slug": "isekai-tensei", "source_keywords": [], "source_tags": []}
        persist_taxonomy_assignments(session, novel.id, metadata)
        session.commit()

        session.refresh(novel)
        assert len(novel.genres) == 1
        assert novel.genres[0].slug == "isekai-tensei"

    def test_unknown_genre_slug_creates_no_assignment(self, session) -> None:
        _seed_genres(session)
        novel = _make_novel(session, "g03")

        metadata = {"genre_slug": "unknown-slug", "source_keywords": [], "source_tags": []}
        persist_taxonomy_assignments(session, novel.id, metadata)
        session.commit()

        count = session.execute(
            text("SELECT COUNT(*) FROM novel_genres WHERE novel_id = :id"),
            {"id": novel.id},
        ).scalar()
        assert count == 0

    def test_null_genre_slug_creates_no_assignment(self, session) -> None:
        _seed_genres(session)
        novel = _make_novel(session, "g04")

        metadata = {"genre_slug": None, "source_keywords": [], "source_tags": []}
        persist_taxonomy_assignments(session, novel.id, metadata)
        session.commit()

        count = session.execute(
            text("SELECT COUNT(*) FROM novel_genres WHERE novel_id = :id"),
            {"id": novel.id},
        ).scalar()
        assert count == 0

    def test_empty_genre_slug_creates_no_assignment(self, session) -> None:
        _seed_genres(session)
        novel = _make_novel(session, "g05")

        metadata = {"genre_slug": "", "source_keywords": [], "source_tags": []}
        persist_taxonomy_assignments(session, novel.id, metadata)
        session.commit()

        count = session.execute(
            text("SELECT COUNT(*) FROM novel_genres WHERE novel_id = :id"),
            {"id": novel.id},
        ).scalar()
        assert count == 0

    def test_inactive_genre_creates_no_assignment(self, session) -> None:
        _seed_genres(session)
        genre = session.query(Genre).filter_by(slug="romance").one()
        genre.is_active = False
        session.commit()

        novel = _make_novel(session, "g06")
        metadata = {"genre_slug": "romance", "source_keywords": [], "source_tags": []}
        persist_taxonomy_assignments(session, novel.id, metadata)
        session.commit()

        count = session.execute(
            text("SELECT COUNT(*) FROM novel_genres WHERE novel_id = :id"),
            {"id": novel.id},
        ).scalar()
        assert count == 0


# ---------------------------------------------------------------------------
# Tag assignment
# ---------------------------------------------------------------------------

class TestTagAssignment:
    def test_source_keywords_create_tags_and_novel_tags_rows(self, session) -> None:
        _seed_genres(session)
        novel = _make_novel(session, "t01")

        metadata = {
            "genre_slug": None,
            "source_keywords": ["異世界", "魔法", "勇者"],
            "source_tags": [],
        }
        persist_taxonomy_assignments(session, novel.id, metadata, source_key="syosetu_ncode")
        session.commit()

        session.refresh(novel)
        tag_names = {t.name for t in novel.tags}
        assert tag_names == {"異世界", "魔法", "勇者"}

        count = session.execute(
            text("SELECT COUNT(*) FROM novel_tags WHERE novel_id = :id"),
            {"id": novel.id},
        ).scalar()
        assert count == 3

    def test_source_tags_create_tags_and_novel_tags_rows(self, session) -> None:
        _seed_genres(session)
        novel = _make_novel(session, "t02")

        metadata = {
            "genre_slug": None,
            "source_keywords": [],
            "source_tags": ["スローライフ", "魔法使い"],
        }
        persist_taxonomy_assignments(session, novel.id, metadata, source_key="kakuyomu")
        session.commit()

        session.refresh(novel)
        tag_names = {t.name for t in novel.tags}
        assert tag_names == {"スローライフ", "魔法使い"}

    def test_tags_are_upserted_across_novels(self, session) -> None:
        """Same tag name across novels should share one Tag row."""
        _seed_genres(session)
        novel_a = _make_novel(session, "t03a")
        novel_b = _make_novel(session, "t03b")

        meta = {"genre_slug": None, "source_keywords": [], "source_tags": ["魔法"]}
        persist_taxonomy_assignments(session, novel_a.id, meta, source_key="syosetu")
        persist_taxonomy_assignments(session, novel_b.id, meta, source_key="kakuyomu")
        session.commit()

        tag_count = session.query(Tag).filter_by(name="魔法").count()
        assert tag_count == 1

    def test_tag_origin_tracked(self, session) -> None:
        _seed_genres(session)
        novel = _make_novel(session, "t04")

        metadata = {"genre_slug": None, "source_keywords": [], "source_tags": ["魔法"]}
        persist_taxonomy_assignments(session, novel.id, metadata, source_key="syosetu_ncode")
        session.commit()

        row = session.execute(
            text("SELECT origin FROM novel_tags WHERE novel_id = :id"),
            {"id": novel.id},
        ).fetchone()
        assert row is not None
        assert row[0] == "syosetu_ncode"

    def test_metadata_source_key_sets_origin_when_argument_omitted(self, session) -> None:
        _seed_genres(session)
        novel = _make_novel(session, "t05")

        metadata = {
            "genre_slug": None,
            "source_keywords": [],
            "source_tags": ["魔法"],
            "source_key": "syosetu_ncode",
        }
        persist_taxonomy_assignments(session, novel.id, metadata)
        session.commit()

        row = session.execute(
            text("SELECT origin FROM novel_tags WHERE novel_id = :id"),
            {"id": novel.id},
        ).fetchone()
        assert row is not None
        assert row[0] == "syosetu"


# ---------------------------------------------------------------------------
# Idempotency
# ---------------------------------------------------------------------------

class TestIdempotency:
    def test_genre_idempotent(self, session) -> None:
        _seed_genres(session)
        novel = _make_novel(session, "id01")

        metadata = {"genre_slug": "fantasy", "source_keywords": [], "source_tags": []}
        persist_taxonomy_assignments(session, novel.id, metadata)
        persist_taxonomy_assignments(session, novel.id, metadata)
        session.commit()

        count = session.execute(
            text("SELECT COUNT(*) FROM novel_genres WHERE novel_id = :id"),
            {"id": novel.id},
        ).scalar()
        assert count == 1

    def test_tag_idempotent(self, session) -> None:
        _seed_genres(session)
        novel = _make_novel(session, "id02")

        metadata = {"genre_slug": None, "source_keywords": [], "source_tags": ["魔法"]}
        persist_taxonomy_assignments(session, novel.id, metadata)
        persist_taxonomy_assignments(session, novel.id, metadata)
        session.commit()

        tag_count = session.query(Tag).filter_by(name="魔法").count()
        assert tag_count == 1

        count = session.execute(
            text("SELECT COUNT(*) FROM novel_tags WHERE novel_id = :id"),
            {"id": novel.id},
        ).scalar()
        assert count == 1

    def test_existing_genre_replaced_when_scraper_reruns_without_genre(self, session) -> None:
        _seed_genres(session)
        novel = _make_novel(session, "id03")

        # First pass: assign fantasy
        metadata = {"genre_slug": "fantasy", "source_keywords": [], "source_tags": []}
        persist_taxonomy_assignments(session, novel.id, metadata)
        session.commit()

        # Second pass: no genre_slug (simulating a re-scrape that dropped genre info)
        metadata2 = {"genre_slug": None, "source_keywords": [], "source_tags": []}
        persist_taxonomy_assignments(session, novel.id, metadata2)
        session.commit()

        # Fantasy should be gone — old scraper rows are cleaned on re-scrape
        count = session.execute(
            text("SELECT COUNT(*) FROM novel_genres WHERE novel_id = :id"),
            {"id": novel.id},
        ).scalar()
        assert count == 0

    def test_existing_tags_replaced_when_scraper_reruns_with_new_tags(self, session) -> None:
        _seed_genres(session)
        novel = _make_novel(session, "id04")

        # First pass: assign tags
        metadata = {"genre_slug": None, "source_keywords": ["魔法"], "source_tags": []}
        persist_taxonomy_assignments(session, novel.id, metadata)
        session.commit()

        # Second pass: different tags — re-scrape replaces, not accumulates
        metadata2 = {"genre_slug": None, "source_keywords": ["勇者"], "source_tags": []}
        persist_taxonomy_assignments(session, novel.id, metadata2)
        session.commit()

        session.refresh(novel)
        tag_names = {t.name for t in novel.tags}
        # Old tag "魔法" should be gone; only "勇者" should remain
        assert "魔法" not in tag_names
        assert "勇者" in tag_names


# ---------------------------------------------------------------------------
# Combined genre + tags
# ---------------------------------------------------------------------------

class TestCombinedAssignment:
    def test_genre_and_keywords_together(self, session) -> None:
        _seed_genres(session)
        novel = _make_novel(session, "c01")

        metadata = {
            "genre_slug": "fantasy",
            "source_keywords": ["異世界", "魔法"],
            "source_tags": [],
        }
        persist_taxonomy_assignments(session, novel.id, metadata, source_key="syosetu_ncode")
        session.commit()

        session.refresh(novel)
        assert len(novel.genres) == 1
        assert novel.genres[0].slug == "fantasy"
        tag_names = {t.name for t in novel.tags}
        assert tag_names == {"異世界", "魔法"}


# ---------------------------------------------------------------------------
# CatalogService integration
# ---------------------------------------------------------------------------

class TestCatalogServiceIntegration:
    def test_get_or_create_novel_calls_persist_taxonomy(self, session) -> None:
        _seed_genres(session)
        from pathlib import Path

        from novelai.services.catalog_service import CatalogService
        from novelai.storage.service import StorageService

        catalog = CatalogService(StorageService(Path.cwd()), session)
        metadata = {
            "title": "Integration Test",
            "genre_slug": "fantasy",
            "source_keywords": ["魔法"],
            "source_tags": [],
            "source_key": "test",
            "chapters": [],
        }
        novel = catalog.get_or_create_novel("int-test", metadata)
        session.commit()

        assert novel is not None
        assert novel.slug == "int-test"
        session.refresh(novel)
        assert len(novel.genres) == 1
        assert novel.genres[0].slug == "fantasy"
        tag_names = {t.name for t in novel.tags}
        assert "魔法" in tag_names

    def test_get_or_create_existing_novel_replaces_scraper_assignments(self, session) -> None:
        _seed_genres(session)
        from pathlib import Path

        from novelai.services.catalog_service import CatalogService
        from novelai.storage.service import StorageService

        catalog = CatalogService(StorageService(Path.cwd()), session)

        # First call: creates novel + assigns genre + tag
        metadata1 = {
            "title": "Reuse Test",
            "genre_slug": "fantasy",
            "source_keywords": ["魔法"],
            "source_tags": [],
            "source_key": "test",
            "chapters": [],
        }
        catalog.get_or_create_novel("reuse-test", metadata1)
        session.commit()

        # Second call: reuses existing novel, replaces scraper tags with new ones
        metadata2 = {
            "title": "Reuse Test",
            "genre_slug": "fantasy",
            "source_keywords": ["勇者"],
            "source_tags": [],
            "source_key": "test",
            "chapters": [],
        }
        novel = catalog.get_or_create_novel("reuse-test", metadata2)
        session.commit()

        session.refresh(novel)
        # Still has exactly one genre (fantasy was re-inserted)
        assert len(novel.genres) == 1
        # Old scraper tag "魔法" replaced by "勇者"
        tag_names = {t.name for t in novel.tags}
        assert "魔法" not in tag_names
        assert "勇者" in tag_names


# ---------------------------------------------------------------------------
# Data honesty
# ---------------------------------------------------------------------------

class TestDataHonesty:
    def test_no_fake_tags_invented(self, session) -> None:
        _seed_genres(session)
        novel = _make_novel(session, "h01")

        metadata = {"genre_slug": None, "source_keywords": [], "source_tags": []}
        persist_taxonomy_assignments(session, novel.id, metadata)
        session.commit()

        count = session.execute(
            text("SELECT COUNT(*) FROM novel_tags WHERE novel_id = :id"),
            {"id": novel.id},
        ).scalar()
        assert count == 0

    def test_no_auto_genre_creation(self, session) -> None:
        """Unknown genre text should never create a new genre row."""
        _seed_genres(session)
        novel = _make_novel(session, "h02")

        metadata = {"genre_slug": "brand-new-unknown-genre", "source_keywords": [], "source_tags": []}
        persist_taxonomy_assignments(session, novel.id, metadata)
        session.commit()

        # No new genre should have been created
        genre = session.query(Genre).filter_by(slug="brand-new-unknown-genre").one_or_none()
        assert genre is None

    def test_empty_metadata_is_safe(self, session) -> None:
        _seed_genres(session)
        novel = _make_novel(session, "h03")

        # Completely empty metadata — should not crash
        metadata: dict = {}
        persist_taxonomy_assignments(session, novel.id, metadata)
        session.commit()

        genre_count = session.execute(
            text("SELECT COUNT(*) FROM novel_genres WHERE novel_id = :id"),
            {"id": novel.id},
        ).scalar()
        tag_count = session.execute(
            text("SELECT COUNT(*) FROM novel_tags WHERE novel_id = :id"),
            {"id": novel.id},
        ).scalar()
        assert genre_count == 0
        assert tag_count == 0


# ---------------------------------------------------------------------------
# Admin preservation during re-scrape (TAXONOMY-4D)
# ---------------------------------------------------------------------------

class TestAdminPersistenceDuringReScrape:
    """Admin-managed assignments must survive scraper persistence."""

    def test_admin_genre_survives_re_scrape(self, session) -> None:
        _seed_genres(session)
        novel = _make_novel(session, "ad01")

        # Admin assigns genre "fantasy"
        genre = session.query(Genre).filter_by(slug="fantasy").one()
        session.execute(
            novel_genres.insert().values(
                novel_id=novel.id, genre_id=genre.id,
                assigned_by="admin",
            )
        )
        session.commit()

        # Scraper re-scrape assigns different genre "romance"
        metadata = {"genre_slug": "romance", "source_keywords": [], "source_tags": []}
        persist_taxonomy_assignments(session, novel.id, metadata)
        session.commit()

        session.refresh(novel)
        genre_slugs = {g.slug for g in novel.genres}
        # Admin-assigned "fantasy" must survive
        assert "fantasy" in genre_slugs
        # Scraper "romance" also present
        assert "romance" in genre_slugs

    def test_admin_tag_survives_re_scrape(self, session) -> None:
        _seed_genres(session)
        novel = _make_novel(session, "ad02")

        # Admin assigns tag "admin-tag"
        tag = Tag(name="admin-tag")
        session.add(tag)
        session.flush()
        session.execute(
            novel_tags.insert().values(
                novel_id=novel.id, tag_id=tag.id,
                origin="admin", assigned_by="admin",
            )
        )
        session.commit()

        # Scraper re-scrape assigns tag "scraper-tag"
        metadata = {"genre_slug": None, "source_keywords": [], "source_tags": ["scraper-tag"]}
        persist_taxonomy_assignments(session, novel.id, metadata)
        session.commit()

        session.refresh(novel)
        tag_names = {t.name for t in novel.tags}
        # Admin-assigned "admin-tag" must survive
        assert "admin-tag" in tag_names
        # Scraper "scraper-tag" also present
        assert "scraper-tag" in tag_names

    def test_admin_genre_not_overwritten_by_scraper_duplicate(self, session) -> None:
        """When admin already assigned a genre, scraper trying to assign the
        same genre skips the insert (composite PK prevents dual rows)."""
        _seed_genres(session)
        novel = _make_novel(session, "ad03")

        # Admin assigns "fantasy"
        genre = session.query(Genre).filter_by(slug="fantasy").one()
        session.execute(
            novel_genres.insert().values(
                novel_id=novel.id, genre_id=genre.id,
                assigned_by="admin",
            )
        )
        session.commit()

        # Scraper re-scrape also lists "fantasy"
        metadata = {"genre_slug": "fantasy", "source_keywords": [], "source_tags": []}
        persist_taxonomy_assignments(session, novel.id, metadata)
        session.commit()

        session.refresh(novel)
        genre_slugs = {g.slug for g in novel.genres}
        assert "fantasy" in genre_slugs
        # Only one row — composite PK prevented duplicate
        count = session.execute(
            text("SELECT COUNT(*) FROM novel_genres WHERE novel_id = :id AND genre_id = :gid"),
            {"id": novel.id, "gid": genre.id},
        ).scalar()
        assert count == 1
        # Row should still be assigned_by="admin" (scraper skip preserves original)
        assigned_by = session.execute(
            text("SELECT assigned_by FROM novel_genres WHERE novel_id = :id AND genre_id = :gid"),
            {"id": novel.id, "gid": genre.id},
        ).scalar()
        assert assigned_by == "admin"

    def test_admin_tag_not_overwritten_by_scraper_duplicate(self, session) -> None:
        """When admin already assigned a tag, scraper trying to assign the
        same tag skips the insert (composite PK prevents dual rows)."""
        _seed_genres(session)
        novel = _make_novel(session, "ad04")

        # Admin assigns "shared-tag"
        tag = Tag(name="shared-tag")
        session.add(tag)
        session.flush()
        session.execute(
            novel_tags.insert().values(
                novel_id=novel.id, tag_id=tag.id,
                origin="admin", assigned_by="admin",
            )
        )
        session.commit()

        # Scraper re-scrape also lists "shared-tag"
        metadata = {"genre_slug": None, "source_keywords": [], "source_tags": ["shared-tag"]}
        persist_taxonomy_assignments(session, novel.id, metadata)
        session.commit()

        session.refresh(novel)
        tag_names = {t.name for t in novel.tags}
        assert "shared-tag" in tag_names
        # Only one row
        count = session.execute(
            text("SELECT COUNT(*) FROM novel_tags WHERE novel_id = :id"),
            {"id": novel.id},
        ).scalar()
        assert count == 1
        # Row should still be assigned_by="admin"
        assigned_by = session.execute(
            text("SELECT assigned_by FROM novel_tags WHERE novel_id = :id"),
            {"id": novel.id},
        ).scalar()
        assert assigned_by == "admin"
