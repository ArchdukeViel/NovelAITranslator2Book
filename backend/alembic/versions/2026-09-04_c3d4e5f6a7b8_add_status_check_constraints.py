"""add check constraints for status columns

Ensure publication_status, raw_status, and translation_status
only accept valid domain enum values:
- novels.publication_status IN ('ongoing', 'completed', 'hiatus', 'cancelled', 'unknown')
- chapters.raw_status IN ('pending', 'fetched', 'crawled', 'failed', 'ready')
- chapters.translation_status IN ('pending', 'in_progress', 'translated', 'completed', 'failed', 'approved')
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "c3d4e5f6a7b8"
down_revision: str | Sequence[str] | None = "b2c3d4e5f6a7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_check_constraint(
        "ck_chapters_raw_status",
        "chapters",
        "raw_status IN ('pending', 'fetched', 'crawled', 'failed', 'ready')",
    )
    op.create_check_constraint(
        "ck_chapters_translation_status",
        "chapters",
        "translation_status IN ('pending', 'in_progress', 'translated', 'completed', 'failed', 'approved')",
    )


def downgrade() -> None:
    op.drop_constraint("ck_chapters_translation_status", "chapters", type_="check")
    op.drop_constraint("ck_chapters_raw_status", "chapters", type_="check")
