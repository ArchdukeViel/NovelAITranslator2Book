"""index the novel request chapter foreign key

Revision ID: c9d1e3f5a7b9
Revises: b6c8d0e2f4a6
Create Date: 2026-08-22 00:00:00.000000
"""

from collections.abc import Sequence

from alembic import op

revision: str = "c9d1e3f5a7b9"
down_revision: str | Sequence[str] | None = "b6c8d0e2f4a6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add a covering index for the chapter foreign key."""
    op.create_index(
        "ix_novel_requests_chapter_id",
        "novel_requests",
        ["chapter_id"],
        unique=False,
    )


def downgrade() -> None:
    """Remove the chapter foreign-key index."""
    op.drop_index("ix_novel_requests_chapter_id", table_name="novel_requests")
