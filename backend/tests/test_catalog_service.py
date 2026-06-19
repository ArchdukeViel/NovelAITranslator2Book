"""Tests for CatalogService — storage-key bridge.

Uses SQLite in-memory + temp dir StorageService; no Postgres required.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker

from novelai.db.base import Base
from novelai.db.models.chapter import Chapter
from novelai.db.models.novel import Novel
from novelai.services.catalog_service import (
    CATALOG_PROJECTION_FIELDS,
    CatalogService,
    safely_refresh_catalog_projection_after_storage_write,
)
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
            "chapters": [
                {"id": "ch001", "num": 1, "title": "Chapter 1"},
                {"id": "ch002", "num": 2, "title": "Chapter 2"},
            ],
        }
        novel = catalog.get_or_create_novel("new-novel", metadata)
        db_session.commit()
        result = db_session.query(Novel).filter_by(slug="new-novel").one()
        assert result.title == "New Novel"
        assert result.author == "Author A"
        assert result.publication_status == "ongoing"
        assert result.status == "ongoing"
        assert result.chapter_count == 2
        assert result.translated_count == 0

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

    def test_model_accepts_catalog_projection_fields(self, db_session) -> None:
        scraped_at = datetime(2026, 6, 19, 1, 2, 3, tzinfo=timezone.utc)
        novel = Novel(
            slug="projected-novel",
            title="Projected Novel",
            language="ja",
            status="completed",
            publication_status="completed",
            source_updated_at=scraped_at,
            chapter_count=12,
            translated_count=4,
            latest_chapter_id="ch004",
            latest_chapter_number=4,
            latest_chapter_title="Fourth Chapter",
            latest_chapter_updated_at=scraped_at,
        )

        db_session.add(novel)
        db_session.commit()

        result = db_session.query(Novel).filter_by(slug="projected-novel").one()
        assert result.publication_status == "completed"
        assert result.source_updated_at is not None
        assert result.source_updated_at.replace(tzinfo=timezone.utc) == scraped_at
        assert result.chapter_count == 12
        assert result.translated_count == 4
        assert result.latest_chapter_id == "ch004"
        assert result.latest_chapter_number == 4
        assert result.latest_chapter_title == "Fourth Chapter"
        assert result.latest_chapter_updated_at is not None
        assert result.latest_chapter_updated_at.replace(tzinfo=timezone.utc) == scraped_at

    def test_normalizes_publication_status_from_metadata(self, catalog, db_session) -> None:
        catalog.get_or_create_novel(
            "finished-novel",
            {
                "title": "Finished Novel",
                "publication_status": "Finished",
                "updated_at": "2026-06-19T01:02:03+00:00",
            },
        )
        db_session.commit()

        result = db_session.query(Novel).filter_by(slug="finished-novel").one()
        assert result.publication_status == "completed"
        assert result.status == "completed"
        assert result.source_updated_at is not None
        assert result.source_updated_at.replace(tzinfo=timezone.utc) == datetime(
            2026, 6, 19, 1, 2, 3, tzinfo=timezone.utc
        )

    def test_updates_existing_publication_status_when_metadata_provides_it(
        self, catalog, db_session, seeded_novel
    ) -> None:
        catalog.get_or_create_novel(
            "novel-001",
            {"publication_status": "not a known status"},
        )
        db_session.commit()

        result = db_session.query(Novel).filter_by(slug="novel-001").one()
        assert result.id == seeded_novel.id
        assert result.publication_status == "unknown"
        assert result.status == "unknown"

    def test_populates_latest_chapter_fields_from_latest_readable_translation(
        self, catalog, db_session, storage
    ) -> None:
        storage.save_translated_chapter("readable-novel", "ch001", "Translated 1")
        storage.save_translated_chapter("readable-novel", "ch003", "Translated 3")

        catalog.get_or_create_novel(
            "readable-novel",
            {
                "title": "Readable Novel",
                "chapters": [
                    {"id": "ch001", "num": 1, "title": "Raw 1", "translated_title": "Translated Title 1"},
                    {"id": "ch002", "num": 2, "title": "Raw 2"},
                    {"id": "ch003", "num": 3, "title": "Raw 3", "translated_title": "Translated Title 3"},
                ],
            },
        )
        db_session.commit()

        result = db_session.query(Novel).filter_by(slug="readable-novel").one()
        assert result.chapter_count == 3
        assert result.translated_count == 2
        assert result.latest_chapter_id == "ch003"
        assert result.latest_chapter_number == 3
        assert result.latest_chapter_title == "Translated Title 3"
        assert result.latest_chapter_updated_at is not None

    def test_latest_chapter_fields_remain_null_without_readable_translation(
        self, catalog, db_session
    ) -> None:
        catalog.get_or_create_novel(
            "untranslated-novel",
            {
                "title": "Untranslated Novel",
                "chapters": [{"id": "ch001", "num": 1, "title": "Chapter 1"}],
            },
        )
        db_session.commit()

        result = db_session.query(Novel).filter_by(slug="untranslated-novel").one()
        assert result.chapter_count == 1
        assert result.translated_count == 0
        assert result.latest_chapter_id is None
        assert result.latest_chapter_number is None
        assert result.latest_chapter_title is None
        assert result.latest_chapter_updated_at is None

    def test_rescrape_recomputes_changed_chapter_count(self, catalog, db_session) -> None:
        catalog.get_or_create_novel(
            "rescraped-novel",
            {"title": "Rescraped Novel", "chapters": [{"id": "ch001", "num": 1}]},
        )
        db_session.commit()

        catalog.get_or_create_novel(
            "rescraped-novel",
            {
                "title": "Rescraped Novel",
                "chapters": [
                    {"id": "ch001", "num": 1},
                    {"id": "ch002", "num": 2},
                    {"id": "ch003", "num": 3},
                ],
            },
        )
        db_session.commit()

        result = db_session.query(Novel).filter_by(slug="rescraped-novel").one()
        assert result.chapter_count == 3

    def test_missing_metadata_chapter_list_becomes_zero(self, catalog, db_session) -> None:
        catalog.get_or_create_novel("empty-metadata-novel", {"title": "Empty Metadata Novel"})
        db_session.commit()

        result = db_session.query(Novel).filter_by(slug="empty-metadata-novel").one()
        assert result.chapter_count == 0
        assert result.translated_count == 0
        assert result.latest_chapter_id is None


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
        refreshed = db_session.query(Novel).filter_by(slug="novel-001").one()
        assert refreshed.chapter_count == 1

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
        refreshed = db_session.query(Novel).filter_by(slug="novel-001").one()
        assert refreshed.translated_count == 1

    def test_save_translated_chapter_refreshes_latest_projection(
        self, catalog, db_session, seeded_novel, storage
    ) -> None:
        storage.save_metadata(
            "novel-001",
            {
                "title": "Test Novel",
                "chapters": [
                    {"id": "ch001", "num": 1, "title": "Chapter 1"},
                    {"id": "ch002", "num": 2, "title": "Chapter 2"},
                ],
            },
        )
        catalog.save_translated_chapter("novel-001", "ch002", "Translated")
        db_session.commit()

        result = db_session.query(Novel).filter_by(slug="novel-001").one()
        assert result.id == seeded_novel.id
        assert result.chapter_count == 2
        assert result.translated_count == 1
        assert result.latest_chapter_id == "ch002"
        assert result.latest_chapter_number == 2
        assert result.latest_chapter_title == "Chapter 2"
        assert result.latest_chapter_updated_at is not None


def test_reconcile_catalog_projection_updates_stale_counts(storage, db_session, seeded_novel) -> None:
    seeded_novel.chapter_count = 0
    seeded_novel.translated_count = 0
    seeded_novel.publication_status = "unknown"
    seeded_novel.status = "unknown"
    db_session.commit()
    storage.save_metadata(
        "novel-001",
        {
            "title": "Projection Repair",
            "status": "completed",
            "scraped_at": "2026-06-19T01:02:03+00:00",
            "chapters": [
                {"id": "ch001", "num": 1, "title": "Chapter 1"},
                {"id": "ch002", "num": 2, "title": "Chapter 2"},
            ],
        },
    )

    result = CatalogService(storage=storage, session=db_session).reconcile_catalog_projection("novel-001")
    db_session.commit()

    assert result is not None
    assert result.created is False
    assert result.before is not None
    assert result.after["chapter_count"] == 2
    assert result.after["translated_count"] == 0
    assert result.after["publication_status"] == "completed"
    assert "chapter_count" in result.changed_fields
    assert "publication_status" in result.changed_fields
    repaired = db_session.query(Novel).filter_by(slug="novel-001").one()
    assert repaired.chapter_count == 2
    assert repaired.translated_count == 0
    assert repaired.publication_status == "completed"
    assert repaired.source_updated_at is not None
    assert repaired.source_updated_at.replace(tzinfo=timezone.utc) == datetime(
        2026,
        6,
        19,
        1,
        2,
        3,
        tzinfo=timezone.utc,
    )


def test_reconcile_catalog_projection_updates_translated_latest_fields(storage, db_session, seeded_novel) -> None:
    storage.save_metadata(
        "novel-001",
        {
            "title": "Projection Repair",
            "chapters": [
                {"id": "ch001", "num": 1, "title": "Chapter 1"},
                {"id": "ch002", "num": 2, "title": "Chapter 2"},
            ],
        },
    )
    storage.save_translated_chapter("novel-001", "ch002", "Translated chapter two")

    result = CatalogService(storage=storage, session=db_session).reconcile_catalog_projection("novel-001")
    db_session.commit()

    assert result is not None
    assert result.after["translated_count"] == 1
    assert result.after["latest_chapter_id"] == "ch002"
    assert result.after["latest_chapter_number"] == 2
    assert result.after["latest_chapter_title"] == "Chapter 2"
    assert result.after["latest_chapter_updated_at"] is not None
    assert {"translated_count", "latest_chapter_id"}.issubset(result.changed_fields)


def test_reconcile_catalog_projection_creates_db_row_from_storage_metadata(storage, db_session) -> None:
    storage.save_metadata(
        "storage-only",
        {
            "title": "Storage Only",
            "status": "ongoing",
            "chapters": [{"id": "ch001", "num": 1, "title": "Chapter 1"}],
        },
    )

    result = CatalogService(storage=storage, session=db_session).reconcile_catalog_projection("storage-only")
    db_session.commit()

    assert result is not None
    assert result.created is True
    assert result.before is None
    assert result.changed_fields == list(CATALOG_PROJECTION_FIELDS)
    repaired = db_session.query(Novel).filter_by(slug="storage-only").one()
    assert repaired.title == "Storage Only"
    assert repaired.chapter_count == 1
    assert repaired.publication_status == "ongoing"


def test_reconcile_catalog_projection_missing_novel_returns_none(storage, db_session) -> None:
    result = CatalogService(storage=storage, session=db_session).reconcile_catalog_projection("missing")

    assert result is None


def test_catalog_projection_migration_upgrade_backfill_and_downgrade(
    tmp_path, monkeypatch
) -> None:
    repo_root = Path(__file__).resolve().parents[2]
    alembic_cfg = Config(str(repo_root / "alembic.ini"))
    db_path = tmp_path / "catalog_projection.sqlite"
    database_url = f"sqlite:///{db_path.as_posix()}"
    monkeypatch.setenv("DATABASE_URL", database_url)
    alembic_cfg.set_main_option("sqlalchemy.url", database_url)

    command.upgrade(alembic_cfg, "d9b7e2a1c4f6")
    engine = create_engine(f"sqlite:///{db_path.as_posix()}")
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                INSERT INTO novels (slug, title, language, status, is_published)
                VALUES
                    ('completed-novel', 'Completed Novel', 'ja', 'completed', 0),
                    ('invalid-novel', 'Invalid Novel', 'ja', 'strange', 0)
                """
            )
        )
    engine.dispose()

    command.upgrade(alembic_cfg, "head")
    engine = create_engine(f"sqlite:///{db_path.as_posix()}")
    columns = {column["name"] for column in inspect(engine).get_columns("novels")}
    novel_indexes = {index["name"] for index in inspect(engine).get_indexes("novels")}
    chapter_indexes = {index["name"] for index in inspect(engine).get_indexes("chapters")}
    assert {
        "publication_status",
        "source_updated_at",
        "chapter_count",
        "translated_count",
        "latest_chapter_id",
        "latest_chapter_number",
        "latest_chapter_title",
        "latest_chapter_updated_at",
    }.issubset(columns)
    assert {
        "ix_novels_is_published_updated_at",
        "ix_novels_is_published_publication_status",
        "ix_novels_language",
        "ix_novels_source_site",
        "ix_novels_source_updated_at",
        "ix_novels_chapter_count",
        "ix_novels_translated_count",
        "ix_novels_latest_chapter_updated_at",
    }.issubset(novel_indexes)
    assert {
        "ix_chapters_novel_id_chapter_number",
        "ix_chapters_novel_id_translation_status_updated_at",
    }.issubset(chapter_indexes)

    with engine.begin() as conn:
        rows = conn.execute(
            text(
                """
                SELECT slug, publication_status, chapter_count, translated_count
                FROM novels
                ORDER BY slug
                """
            )
        ).mappings().all()
    assert rows == [
        {
            "slug": "completed-novel",
            "publication_status": "completed",
            "chapter_count": 0,
            "translated_count": 0,
        },
        {
            "slug": "invalid-novel",
            "publication_status": "unknown",
            "chapter_count": 0,
            "translated_count": 0,
        },
    ]
    engine.dispose()

    command.downgrade(alembic_cfg, "-1")
    engine = create_engine(f"sqlite:///{db_path.as_posix()}")
    downgraded_indexes = {index["name"] for index in inspect(engine).get_indexes("novels")}
    downgraded_chapter_indexes = {index["name"] for index in inspect(engine).get_indexes("chapters")}
    downgraded_columns = {column["name"] for column in inspect(engine).get_columns("novels")}
    assert "publication_status" in downgraded_columns
    assert "latest_chapter_updated_at" in downgraded_columns
    assert "ix_novels_is_published_updated_at" not in downgraded_indexes
    assert "ix_chapters_novel_id_chapter_number" not in downgraded_chapter_indexes
    engine.dispose()

    command.downgrade(alembic_cfg, "d9b7e2a1c4f6")
    engine = create_engine(f"sqlite:///{db_path.as_posix()}")
    downgraded_columns = {column["name"] for column in inspect(engine).get_columns("novels")}
    assert "publication_status" not in downgraded_columns
    assert "latest_chapter_updated_at" not in downgraded_columns
    engine.dispose()

    command.upgrade(alembic_cfg, "head")


def test_safe_projection_refresh_logs_failure_without_raising(storage) -> None:
    storage.save_metadata("novel-log", {"title": "Novel Log", "chapters": [{"id": "1"}]})

    def broken_session_scope():
        raise RuntimeError("database unavailable")

    with patch("novelai.services.catalog_service.logger.warning") as warning:
        refreshed = safely_refresh_catalog_projection_after_storage_write(
            "novel-log",
            storage,
            context="test_write",
            session_scope_factory=broken_session_scope,
        )

    assert refreshed is False
    warning.assert_called_once()
    assert warning.call_args.args[:3] == (
        "Catalog projection refresh failed after %s for novel_id=%s: %s",
        "test_write",
        "novel-log",
    )


def test_storage_service_has_no_db_or_catalog_dependency() -> None:
    storage_service_source = Path("backend/src/novelai/storage/service.py").read_text(
        encoding="utf-8"
    )

    assert "novelai.db" not in storage_service_source
    assert "CatalogService" not in storage_service_source
