"""Tests for CatalogService — storage-key bridge.

Uses SQLite in-memory + temp dir StorageService; no Postgres required.
"""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from novelai.db.base import Base
from novelai.db.models.chapter import Chapter
from novelai.db.models.novel import Novel
from novelai.services.catalog_service import CatalogService
from novelai.storage.service import StorageService

_SQLITE = "sqlite:///:memory:"


@pytest.fixture()
def db_session():
    engine = create_engine(_SQLITE)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    sess = Session()
    yield sess
    sess.close()
    Base.metadata.drop_all(engine)


@pytest.fixture()
def storage(tmp_path):
    return StorageService(tmp_path)


@pytest.fixture()
def catalog(storage, db_session):
    return CatalogService(storage=storage, session=db_session)


@pytest.fixture()
def seeded_novel(db_session):
    """A Novel row already in the DB."""
    novel = Novel(slug="novel-001", title="Test Novel", language="ja", status="ongoing")
    db_session.add(novel)
    db_session.commit()
    return novel


class TestGetOrCreateNovel:
    def test_creates_novel_when_absent(self, catalog, db_session) -> None:
        metadata = {
            "title": "New Novel",
            "author": "Author A",
            "language": "ja",
            "status": "ongoing",
        }
        novel = catalog.get_or_create_novel("new-novel", metadata)
        db_session.commit()
        result = db_session.query(Novel).filter_by(slug="new-novel").one()
        assert result.title == "New Novel"
        assert result.author == "Author A"

    def test_returns_existing_novel(self, catalog, db_session, seeded_novel) -> None:
        novel = catalog.get_or_create_novel("novel-001", {"title": "Different Title"})
        db_session.commit()
        # Should return the existing row, not create a duplicate
        count = db_session.query(Novel).filter_by(slug="novel-001").count()
        assert count == 1
        assert novel.id == seeded_novel.id

    def test_sets_source_fields(self, catalog, db_session) -> None:
        metadata = {
            "title": "Sourced Novel",
            "source_key": "syosetu",
            "source_url": "https://ncode.syosetu.com/n1234",
            "language": "ja",
            "status": "completed",
        }
        catalog.get_or_create_novel("sourced-novel", metadata)
        db_session.commit()
        result = db_session.query(Novel).filter_by(slug="sourced-novel").one()
        assert result.source_site == "syosetu"
        assert result.source_url == "https://ncode.syosetu.com/n1234"


class TestSaveRawChapter:
    def test_saves_to_file_storage(self, catalog, db_session, seeded_novel, storage) -> None:
        catalog.save_raw_chapter(
            "novel-001", "ch001", "Chapter content here",
            title="Chapter 1", chapter_number=1
        )
        db_session.commit()
        # File should exist in StorageService
        raw = storage.load_chapter("novel-001", "ch001")
        assert raw is not None

    def test_persists_storage_key_in_db(self, catalog, db_session, seeded_novel) -> None:
        catalog.save_raw_chapter(
            "novel-001", "ch001", "Chapter content",
            title="Chapter 1", chapter_number=1
        )
        db_session.commit()
        chapter = db_session.query(Chapter).filter_by(novel_id=seeded_novel.id).one()
        assert chapter.raw_storage_key is not None
        assert "novel-001" in chapter.raw_storage_key

    def test_sets_raw_status_fetched(self, catalog, db_session, seeded_novel) -> None:
        catalog.save_raw_chapter("novel-001", "ch001", "Content", chapter_number=1)
        db_session.commit()
        chapter = db_session.query(Chapter).filter_by(novel_id=seeded_novel.id).one()
        assert chapter.raw_status == "fetched"

    def test_storage_key_includes_checksum_prefix(self, catalog, db_session, seeded_novel) -> None:
        catalog.save_raw_chapter("novel-001", "ch001", "Deterministic content", chapter_number=1)
        db_session.commit()
        chapter = db_session.query(Chapter).filter_by(novel_id=seeded_novel.id).one()
        # Key format: "novel_id/chapter_id/raw:<8-char-checksum>"
        assert ":" in chapter.raw_storage_key


class TestSaveTranslatedChapter:
    def test_saves_translated_to_file_storage(
        self, catalog, db_session, seeded_novel, storage
    ) -> None:
        # Save raw first so the chapter exists in file storage
        catalog.save_raw_chapter("novel-001", "ch001", "Raw content", chapter_number=1)
        db_session.commit()
        catalog.save_translated_chapter("novel-001", "ch001", "Translated content")
        db_session.commit()
        translated = storage.load_translated_chapter("novel-001", "ch001")
        assert translated is not None

    def test_persists_translated_key_in_db(self, catalog, db_session, seeded_novel) -> None:
        catalog.save_raw_chapter("novel-001", "ch001", "Raw", chapter_number=1)
        db_session.commit()
        catalog.save_translated_chapter("novel-001", "ch001", "Translated")
        db_session.commit()
        chapter = db_session.query(Chapter).filter_by(novel_id=seeded_novel.id).one()
        assert chapter.translated_storage_key is not None
        assert "translated" in chapter.translated_storage_key

    def test_sets_translation_status(self, catalog, db_session, seeded_novel) -> None:
        catalog.save_raw_chapter("novel-001", "ch001", "Raw", chapter_number=1)
        db_session.commit()
        catalog.save_translated_chapter("novel-001", "ch001", "Translated")
        db_session.commit()
        chapter = db_session.query(Chapter).filter_by(novel_id=seeded_novel.id).one()
        assert chapter.translation_status == "translated"
