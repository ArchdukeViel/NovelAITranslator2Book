"""index users.disabled_by_user_id foreign key

Revision ID: f2a4c6e8b0d1
Revises: b9e0f1a2c3d4
Create Date: 2026-07-30 00:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "f2a4c6e8b0d1"
down_revision: str | Sequence[str] | None = "b9e0f1a2c3d4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_index(
        "ix_users_disabled_by_user_id",
        "users",
        ["disabled_by_user_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_users_disabled_by_user_id", table_name="users")
