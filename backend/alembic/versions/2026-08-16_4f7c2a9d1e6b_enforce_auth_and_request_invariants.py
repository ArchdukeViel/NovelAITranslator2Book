"""enforce persisted role and novel-request status invariants

Revision ID: 4f7c2a9d1e6b
Revises: c7a8b9d0e1f2
Create Date: 2026-08-16 00:00:00.000000
"""

from collections.abc import Sequence

from alembic import op
from sqlalchemy import text

revision: str = "4f7c2a9d1e6b"
down_revision: str | Sequence[str] | None = "c7a8b9d0e1f2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Reject invalid persisted roles/statuses and permit at most one owner."""

    op.create_check_constraint(
        "ck_users_role_valid",
        "users",
        "role IN ('guest', 'user', 'owner')",
    )
    op.create_check_constraint(
        "ck_novel_requests_status_valid",
        "novel_requests",
        "status IN ('pending', 'approved', 'rejected', 'released')",
    )
    op.create_index(
        "uq_users_single_owner",
        "users",
        ["role"],
        unique=True,
        postgresql_where=text("role = 'owner'"),
    )


def downgrade() -> None:
    """Remove the persisted role/status invariants."""

    op.drop_index("uq_users_single_owner", table_name="users")
    op.drop_constraint("ck_novel_requests_status_valid", "novel_requests", type_="check")
    op.drop_constraint("ck_users_role_valid", "users", type_="check")
