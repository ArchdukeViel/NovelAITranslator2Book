"""add public read projection fields

Revision ID: b7c1e2d3f4a5
Revises: a8c4e2f7b901
Create Date: 2026-08-20 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "b7c1e2d3f4a5"
down_revision: str | Sequence[str] | None = "a8c4e2f7b901"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("novels", sa.Column("public_slug", sa.String(length=255), nullable=True))
    op.create_index("ix_novels_public_slug", "novels", ["public_slug"])
    op.execute(sa.text("UPDATE novels SET public_slug = slug WHERE public_slug IS NULL"))

    op.add_column("chapters", sa.Column("translated_section_title", sa.String(length=512), nullable=True))
    op.add_column("chapters", sa.Column("section_title", sa.String(length=512), nullable=True))
    op.add_column("chapters", sa.Column("section_source_id", sa.String(length=255), nullable=True))
    op.add_column("chapters", sa.Column("section_ordinal", sa.Integer(), nullable=True))
    op.add_column("chapters", sa.Column("section_level", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("chapters", "section_level")
    op.drop_column("chapters", "section_ordinal")
    op.drop_column("chapters", "section_source_id")
    op.drop_column("chapters", "section_title")
    op.drop_column("chapters", "translated_section_title")
    op.drop_index("ix_novels_public_slug", table_name="novels")
    op.drop_column("novels", "public_slug")
