"""Add exact R2 artifact references and PostgreSQL generation activation.

Revision ID: f1a7c9e2d4b6
Revises: e5f7a9c1d3b2
Create Date: 2026-08-20 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "f1a7c9e2d4b6"
down_revision: str | Sequence[str] | None = "e5f7a9c1d3b2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("novels", sa.Column("active_generation_id", sa.String(length=255), nullable=True))
    op.add_column("novels", sa.Column("active_generation_storage_key", sa.String(length=512), nullable=True))
    op.add_column("novels", sa.Column("metadata_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'")))
    op.add_column(
        "novels", sa.Column("metadata_history_json", sa.JSON(), nullable=False, server_default=sa.text("'[]'"))
    )
    op.add_column("novels", sa.Column("source_state_json", sa.JSON(), nullable=True))
    op.add_column("chapters", sa.Column("media_storage_key", sa.String(length=512), nullable=True))
    op.add_column("chapters", sa.Column("raw_content_hash", sa.String(length=64), nullable=True))
    op.add_column("chapters", sa.Column("translated_content_hash", sa.String(length=64), nullable=True))
    op.add_column("chapters", sa.Column("media_content_hash", sa.String(length=64), nullable=True))
    op.add_column("chapters", sa.Column("media_state_json", sa.JSON(), nullable=True))
    op.add_column("chapters", sa.Column("translation_versions_json", sa.JSON(), nullable=True))
    op.add_column("chapters", sa.Column("translation_edit_history_json", sa.JSON(), nullable=True))
    op.create_index(
        "ix_novels_active_generation_id",
        "novels",
        ["active_generation_id"],
        unique=False,
    )
    op.create_index(
        "ix_chapters_raw_storage_key",
        "chapters",
        ["raw_storage_key"],
        unique=False,
    )
    op.create_index(
        "ix_chapters_translated_storage_key",
        "chapters",
        ["translated_storage_key"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_chapters_translated_storage_key", table_name="chapters")
    op.drop_index("ix_chapters_raw_storage_key", table_name="chapters")
    op.drop_index("ix_novels_active_generation_id", table_name="novels")
    op.drop_column("chapters", "media_content_hash")
    op.drop_column("chapters", "media_state_json")
    op.drop_column("chapters", "translation_edit_history_json")
    op.drop_column("chapters", "translation_versions_json")
    op.drop_column("chapters", "translated_content_hash")
    op.drop_column("chapters", "raw_content_hash")
    op.drop_column("chapters", "media_storage_key")
    op.drop_column("novels", "active_generation_storage_key")
    op.drop_column("novels", "active_generation_id")
    op.drop_column("novels", "source_state_json")
    op.drop_column("novels", "metadata_history_json")
    op.drop_column("novels", "metadata_json")
