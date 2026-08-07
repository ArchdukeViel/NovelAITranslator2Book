"""add stable chapter identity columns

Revision ID: c7a8b9d0e1f2
Revises: c3a7e9f5b1d2
Create Date: 2026-08-06 00:00:00.000000

Section 2 contract: chapters gain stable ``logical_chapter_id``,
``source_episode_id``, and ``sequence_number`` columns so Kakuyomu
(``kakuyomu:<episode>``) and Syosetu numeric ids share one
chapter_id-keyed pipeline. ``chapter_number`` is retained as a
presentation/sequence compatibility field.

The canonical identity invariant is:

    UNIQUE(novel_id, logical_chapter_id)

``logical_chapter_id`` is NOT NULL: every existing row is backfilled from
``chapter_number`` (duplicates are de-duplicated deterministically), so the
unique index is meaningful and the ORM/migration contracts agree.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c7a8b9d0e1f2"
down_revision: str | Sequence[str] | None = "c3a7e9f5b1d2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add stable chapter identity columns and per-novel uniqueness index."""
    with op.batch_alter_table("chapters") as batch_op:
        batch_op.add_column(
            sa.Column(
                "logical_chapter_id",
                sa.String(length=512),
                nullable=True,
                comment="Stable logical chapter id used everywhere downstream (e.g. kakuyomu:<episode_id>).",
            )
        )
        batch_op.add_column(
            sa.Column(
                "source_episode_id",
                sa.String(length=128),
                nullable=True,
                comment="Source-native chapter identifier exposed by adapters (Kakuyomu episode_id, Syosetu num).",
            )
        )
        batch_op.add_column(
            sa.Column(
                "sequence_number",
                sa.Integer(),
                nullable=True,
                comment="Mutable display position within the source index; not a stable identity.",
            )
        )

    # Safe backfill: the first row per (novel_id, chapter_number) inherits the
    # numeric id; any remaining NULLs (duplicate chapter_number or NULL
    # chapter_number) get a deterministic id derived from the row's primary
    # key so the NOT NULL + UNIQUE(novel_id, logical_chapter_id) invariant
    # holds on existing data without data loss.
    op.execute(
        "UPDATE chapters SET logical_chapter_id = CAST(chapter_number AS VARCHAR(32)) "
        "WHERE logical_chapter_id IS NULL AND id IN ("
        "  SELECT MIN(id) FROM chapters "
        "  WHERE logical_chapter_id IS NULL AND chapter_number IS NOT NULL "
        "  GROUP BY novel_id, chapter_number)"
    )
    op.execute(
        "UPDATE chapters SET logical_chapter_id = 'legacy-' || CAST(id AS VARCHAR(32)) WHERE logical_chapter_id IS NULL"
    )

    with op.batch_alter_table("chapters") as batch_op:
        batch_op.alter_column("logical_chapter_id", existing_type=sa.String(length=512), nullable=False)

    op.create_index(
        op.f("ix_chapters_novel_id_logical_chapter_id"),
        "chapters",
        ["novel_id", "logical_chapter_id"],
        unique=True,
    )
    op.create_index(
        op.f("ix_chapters_novel_id_source_episode_id"),
        "chapters",
        ["novel_id", "source_episode_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_chapters_novel_id_sequence_number"),
        "chapters",
        ["novel_id", "sequence_number"],
        unique=False,
    )


def downgrade() -> None:
    """Drop stable chapter identity columns and indexes."""
    op.drop_index(op.f("ix_chapters_novel_id_sequence_number"), table_name="chapters")
    op.drop_index(op.f("ix_chapters_novel_id_source_episode_id"), table_name="chapters")
    op.drop_index(op.f("ix_chapters_novel_id_logical_chapter_id"), table_name="chapters")
    with op.batch_alter_table("chapters") as batch_op:
        batch_op.drop_column("sequence_number")
        batch_op.drop_column("source_episode_id")
        batch_op.drop_column("logical_chapter_id")
