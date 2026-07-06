"""add glossary scope and make novel_id nullable

Revision ID: b5c8f7e2d1a3
Revises: cea7d090afbc
Create Date: 2026-07-04 00:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "b5c8f7e2d1a3"
down_revision: str | Sequence[str] | None = "cea7d090afbc"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add scope column, make novel_id nullable for global entries."""
    with op.batch_alter_table("novel_glossary_entries") as batch_op:
        batch_op.add_column(
            sa.Column("scope", sa.String(32), nullable=False, server_default="novel")
        )
        batch_op.alter_column("novel_id", existing_type=sa.Integer(), nullable=True)
        batch_op.create_index("ix_novel_glossary_entries_scope", ["scope"])
        batch_op.create_index("ix_novel_glossary_entries_novel_id_scope", ["novel_id", "scope"])


def downgrade() -> None:
    """Revert scope column and nullable novel_id."""
    with op.batch_alter_table("novel_glossary_entries") as batch_op:
        batch_op.drop_index("ix_novel_glossary_entries_novel_id_scope")
        batch_op.drop_index("ix_novel_glossary_entries_scope")
        batch_op.drop_column("scope")
        batch_op.alter_column("novel_id", existing_type=sa.Integer(), nullable=False)
