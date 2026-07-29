"""add admin user-management fields (disabled_at, disabled_reason, disabled_by_user_id, session_revoked_at)

Revision ID: b7d1e3f5a2c4
Revises: e5f7a2d1c4b6
Create Date: 2026-07-26 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b7d1e3f5a2c4"
down_revision: str | Sequence[str] | None = "e5f7a2d1c4b6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add admin user-management columns to the users table."""
    op.add_column(
        "users",
        sa.Column("disabled_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "users",
        sa.Column("disabled_reason", sa.Text(), nullable=True),
    )
    op.add_column(
        "users",
        sa.Column("disabled_by_user_id", sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        "fk_users_disabled_by_user_id_users",
        "users",
        "users",
        ["disabled_by_user_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.add_column(
        "users",
        sa.Column("session_revoked_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    """Remove admin user-management columns from the users table."""
    op.drop_constraint("fk_users_disabled_by_user_id_users", "users", type_="foreignkey")
    op.drop_column("users", "session_revoked_at")
    op.drop_column("users", "disabled_by_user_id")
    op.drop_column("users", "disabled_reason")
    op.drop_column("users", "disabled_at")
