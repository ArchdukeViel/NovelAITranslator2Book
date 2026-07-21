"""drop legacy novel status

Revision ID: 9c2e4a6b8d0f
Revises: 8b7f3d1a2c4e
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "9c2e4a6b8d0f"
down_revision: str | Sequence[str] | None = "8b7f3d1a2c4e"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("novels") as batch_op:
        batch_op.drop_column("status")


def downgrade() -> None:
    with op.batch_alter_table("novels") as batch_op:
        batch_op.add_column(
            sa.Column("status", sa.String(length=64), nullable=False, server_default="unknown")
        )
    op.execute("UPDATE novels SET status = publication_status")
