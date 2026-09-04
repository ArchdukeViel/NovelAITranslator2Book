"""add composite performance indexes for public novel listing and chapter TOC ordering

Optimizes:
- novels(is_published, created_at) for new release ordering
- chapters(novel_id, sequence_number, chapter_number, id) for Table of Contents resolution
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "b2c3d4e5f6a7"
down_revision: str | Sequence[str] | None = "a1b2c3d4e5f6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_index(
        "ix_novels_is_published_created_at",
        "novels",
        ["is_published", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_chapters_novel_toc_ordering",
        "chapters",
        ["novel_id", "sequence_number", "chapter_number", "id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_chapters_novel_toc_ordering", table_name="chapters")
    op.drop_index("ix_novels_is_published_created_at", table_name="novels")
