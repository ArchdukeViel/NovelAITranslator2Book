"""PR-41 Section 7: stable DB chapter identity.

Covers the UNIQUE(novel_id, logical_chapter_id) invariant end to end:

- same-title chapters remain distinct rows;
- Kakuyomu stable ids insert once;
- A,B,C -> A,X,B,C keeps stable row ids for B/C;
- reorder updates sequence_number without a new row;
- migration clean upgrade, existing-data upgrade, downgrade;
- ORM metadata matches the migration constraints.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from novelai.db.base import Base
from novelai.db.models.chapter import Chapter
from novelai.db.models.novel import Novel
from novelai.services.catalog_service import CatalogService
from novelai.storage.service import StorageService

_SQLITE = "sqlite:///:memory:"
_MIGRATION_PATH = (
    Path(__file__).resolve().parents[1]
    / "alembic"
    / "versions"
    / "2026-08-06_c7a8b9d0e1f2_add_stable_chapter_identity.py"
)

KAKUYOMU_A = "kakuyomu:16818093075570329555"
KAKUYOMU_B = "kakuyomu:16818093075570329556"
KAKUYOMU_C = "kakuyomu:16818093075570329557"
KAKUYOMU_X = "kakuyomu:16818093075570329560"


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
    novel = Novel(slug="novel-stable", title="Stable Novel", language="ja", publication_status="ongoing")
    db_session.add(novel)
    db_session.commit()
    return novel


def _rows_by_logical(db_session, novel_db_id: int) -> dict[str, Chapter]:
    rows = db_session.query(Chapter).filter_by(novel_id=novel_db_id).all()
    return {row.logical_chapter_id: row for row in rows}


# ---------------------------------------------------------------------------
# ORM / CatalogService behavior
# ---------------------------------------------------------------------------


def test_two_chapters_with_identical_titles_are_distinct_rows(catalog, db_session, seeded_novel) -> None:
    """Same-title chapters must remain distinct DB rows (no title lookup)."""
    first = catalog._get_or_create_chapter(seeded_novel.id, "1", chapter_number=1, title="Same Title")
    db_session.add(first)
    db_session.flush()
    second = catalog._get_or_create_chapter(seeded_novel.id, "2", chapter_number=2, title="Same Title")
    db_session.add(second)
    db_session.flush()

    rows = _rows_by_logical(db_session, seeded_novel.id)
    assert len(rows) == 2
    assert rows["1"].id != rows["2"].id
    assert rows["1"].title == rows["2"].title == "Same Title"


def test_kakuyomu_stable_id_insertion_keeps_single_row(catalog, db_session, seeded_novel) -> None:
    chapter = catalog._get_or_create_chapter(
        seeded_novel.id,
        KAKUYOMU_A,
        chapter_number=1,
        title="A",
        source_episode_id=KAKUYOMU_A.split(":", 1)[1],
        sequence_number=1,
    )
    db_session.add(chapter)
    db_session.flush()
    again = catalog._get_or_create_chapter(
        seeded_novel.id,
        KAKUYOMU_A,
        chapter_number=1,
        title="A",
        source_episode_id=KAKUYOMU_A.split(":", 1)[1],
        sequence_number=1,
    )
    db_session.add(again)
    db_session.flush()
    assert _rows_by_logical(db_session, seeded_novel.id)[KAKUYOMU_A].id == chapter.id


def test_a_b_c_to_a_x_b_c_preserves_stable_row_ids(catalog, db_session, seeded_novel) -> None:
    """Insertion of X between A and B/C must not recreate B/C rows."""
    ids: dict[str, int] = {}
    for chapter_id, num in ((KAKUYOMU_A, 1), (KAKUYOMU_B, 2), (KAKUYOMU_C, 3)):
        row = catalog._get_or_create_chapter(
            seeded_novel.id,
            chapter_id,
            chapter_number=num,
            title=chapter_id,
            source_episode_id=chapter_id.split(":", 1)[1],
            sequence_number=num,
        )
        db_session.add(row)
        db_session.flush()
        ids[chapter_id] = row.id

    # Reorder: A, X, B, C — B and C keep their stable row ids.
    for chapter_id, num in ((KAKUYOMU_A, 1), (KAKUYOMU_X, 2), (KAKUYOMU_B, 3), (KAKUYOMU_C, 4)):
        row = catalog._get_or_create_chapter(
            seeded_novel.id,
            chapter_id,
            chapter_number=num,
            title=chapter_id,
            source_episode_id=chapter_id.split(":", 1)[1],
            sequence_number=num,
        )
        db_session.add(row)
        db_session.flush()

    rows = _rows_by_logical(db_session, seeded_novel.id)
    assert len(rows) == 4
    assert rows[KAKUYOMU_B].id == ids[KAKUYOMU_B]
    assert rows[KAKUYOMU_C].id == ids[KAKUYOMU_C]
    assert rows[KAKUYOMU_X].sequence_number == 2


def test_reorder_updates_sequence_number_without_new_row(catalog, db_session, seeded_novel) -> None:
    row = catalog._get_or_create_chapter(seeded_novel.id, "1", chapter_number=1, title="Chapter 1", sequence_number=1)
    db_session.add(row)
    db_session.flush()
    row_id = row.id

    updated = catalog._get_or_create_chapter(
        seeded_novel.id, "1", chapter_number=5, title="Chapter 1", sequence_number=5
    )
    db_session.add(updated)
    db_session.flush()
    assert updated.id == row_id
    rows = db_session.query(Chapter).filter_by(novel_id=seeded_novel.id).all()
    assert len(rows) == 1
    assert rows[0].sequence_number == 5
    assert rows[0].chapter_number == 5


def test_duplicate_logical_chapter_id_rejected_by_unique_constraint(db_session, seeded_novel) -> None:
    db_session.add(Chapter(novel_id=seeded_novel.id, logical_chapter_id="dup", chapter_number=1))
    db_session.flush()
    db_session.add(Chapter(novel_id=seeded_novel.id, logical_chapter_id="dup", chapter_number=2))
    with pytest.raises(IntegrityError):
        db_session.flush()


# ---------------------------------------------------------------------------
# Migration behavior (isolated run of the stable-identity migration)
# ---------------------------------------------------------------------------


def _load_migration_module() -> Any:
    import importlib.util

    spec = importlib.util.spec_from_file_location("stable_identity_migration", _MIGRATION_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load migration module from {_MIGRATION_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _pre_migration_schema(engine) -> None:
    """Schema of ``chapters`` immediately before the stable-identity migration."""
    with engine.begin() as conn:
        conn.execute(
            text(
                "CREATE TABLE chapters ("
                "  id INTEGER NOT NULL PRIMARY KEY,"
                "  novel_id INTEGER NOT NULL,"
                "  chapter_number INTEGER NOT NULL,"
                "  title VARCHAR(512)"
                ")"
            )
        )


def _run_migration(engine, fn) -> None:
    module = _load_migration_module()
    with engine.begin() as conn:
        ctx = MigrationContext.configure(conn)
        module.op = Operations(ctx)
        fn(module)


def test_migration_existing_data_upgrade_backfills_and_enforces_unique() -> None:
    engine = create_engine("sqlite://")
    _pre_migration_schema(engine)
    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO chapters (id, novel_id, chapter_number, title) VALUES "
                "(1, 10, 1, 'A'), (2, 10, 2, 'B'), (3, 10, 2, 'B-dup'), "
                "(4, 20, 1, 'C'), (5, 20, 2, 'D')"
            )
        )

    def _upgrade(mod: Any) -> None:
        mod.upgrade()

    _run_migration(engine, _upgrade)

    with engine.connect() as conn:
        rows = conn.execute(text("SELECT id, novel_id, logical_chapter_id FROM chapters ORDER BY id")).mappings().all()
        by_id = {row["id"]: row for row in rows}
        assert by_id[1]["logical_chapter_id"] == "1"
        assert by_id[2]["logical_chapter_id"] == "2"
        # Duplicate chapter_number row gets a deterministic legacy id.
        assert by_id[3]["logical_chapter_id"] == "legacy-3"
        assert by_id[4]["logical_chapter_id"] == "1"
        assert all(row["logical_chapter_id"] for row in rows)

        # NOT NULL enforced.
        with pytest.raises(IntegrityError):
            conn.execute(text("INSERT INTO chapters (novel_id, chapter_number) VALUES (10, 99)"))
        # UNIQUE(novel_id, logical_chapter_id) enforced.
        with pytest.raises(IntegrityError):
            conn.execute(
                text("INSERT INTO chapters (novel_id, logical_chapter_id, chapter_number) VALUES (10, '1', 99)")
            )

        indexes = {idx["name"] for idx in inspect(engine).get_indexes("chapters")}
        assert "ix_chapters_novel_id_logical_chapter_id" in indexes
        assert "ix_chapters_novel_id_source_episode_id" in indexes
        assert "ix_chapters_novel_id_sequence_number" in indexes
    engine.dispose()


def test_migration_clean_upgrade_and_downgrade() -> None:
    engine = create_engine("sqlite://")
    _pre_migration_schema(engine)

    def _upgrade(mod: Any) -> None:
        mod.upgrade()

    _run_migration(engine, _upgrade)
    columns = {col["name"] for col in inspect(engine).get_columns("chapters")}
    assert {"logical_chapter_id", "source_episode_id", "sequence_number"}.issubset(columns)
    logical = next(col for col in inspect(engine).get_columns("chapters") if col["name"] == "logical_chapter_id")
    assert logical["nullable"] is False

    def _downgrade(mod: Any) -> None:
        mod.downgrade()

    _run_migration(engine, _downgrade)
    columns = {col["name"] for col in inspect(engine).get_columns("chapters")}
    assert not {"logical_chapter_id", "source_episode_id", "sequence_number"} & columns
    indexes = {idx["name"] for idx in inspect(engine).get_indexes("chapters")}
    assert "ix_chapters_novel_id_logical_chapter_id" not in indexes
    engine.dispose()


def test_orm_metadata_matches_migration_constraints() -> None:
    """The ORM model and the migration agree on uniqueness, nullability,
    index names, and lengths."""
    source = _MIGRATION_PATH.read_text(encoding="utf-8")
    assert "unique=True" in source
    assert "nullable=False" in source
    assert "String(length=512)" in source
    assert "String(length=128)" in source
    assert "sa.Integer()" in source

    table = Base.metadata.tables["chapters"]
    logical = table.c.logical_chapter_id
    assert logical.nullable is False
    assert getattr(logical.type, "length", None) == 512
    source_ep = table.c.source_episode_id
    assert source_ep.nullable is True
    assert getattr(source_ep.type, "length", None) == 128
    assert table.c.sequence_number.nullable is True

    unique_indexes = [idx for idx in table.indexes if idx.unique]
    assert any(idx.name == "ix_chapters_novel_id_logical_chapter_id" for idx in unique_indexes)
    names = {idx.name for idx in table.indexes}
    assert {
        "ix_chapters_novel_id_logical_chapter_id",
        "ix_chapters_novel_id_source_episode_id",
        "ix_chapters_novel_id_sequence_number",
    }.issubset(names)
