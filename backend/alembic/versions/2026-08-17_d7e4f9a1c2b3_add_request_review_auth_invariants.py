"""add request, review, and case-insensitive email invariants

Revision ID: d7e4f9a1c2b3
Revises: 4f7c2a9d1e6b
Create Date: 2026-08-17 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "d7e4f9a1c2b3"
down_revision: str | Sequence[str] | None = "4f7c2a9d1e6b"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _assert_unique_data() -> None:
    """Fail closed instead of silently deleting conflicting production rows."""
    connection = op.get_bind()
    duplicate_email = connection.execute(
        sa.text("SELECT 1 FROM users GROUP BY lower(email) HAVING COUNT(*) > 1 LIMIT 1")
    ).first()
    if duplicate_email is not None:
        raise RuntimeError("Cannot enforce case-insensitive user email uniqueness until duplicate rows are resolved.")

    duplicate_review = connection.execute(
        sa.text("SELECT 1 FROM reviews GROUP BY user_id, novel_id HAVING COUNT(*) > 1 LIMIT 1")
    ).first()
    if duplicate_review is not None:
        raise RuntimeError("Cannot enforce one review per user and novel until duplicate rows are resolved.")


def upgrade() -> None:
    """Persist chapter request identity and enforce auth/review uniqueness."""
    _assert_unique_data()

    with op.batch_alter_table("novel_requests") as batch_op:
        batch_op.add_column(sa.Column("chapter_id", sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            "fk_novel_requests_chapter_id_chapters",
            "chapters",
            ["chapter_id"],
            ["id"],
            ondelete="SET NULL",
        )

    with op.batch_alter_table("reviews") as batch_op:
        batch_op.create_unique_constraint("uq_reviews_user_novel", ["user_id", "novel_id"])

    op.create_index(
        "ix_users_email_lower",
        "users",
        [sa.text("lower(email)")],
        unique=True,
    )


def downgrade() -> None:
    """Remove the request, review, and email uniqueness invariants."""
    op.drop_index("ix_users_email_lower", table_name="users")

    with op.batch_alter_table("reviews") as batch_op:
        batch_op.drop_constraint("uq_reviews_user_novel", type_="unique")

    with op.batch_alter_table("novel_requests") as batch_op:
        batch_op.drop_constraint("fk_novel_requests_chapter_id_chapters", type_="foreignkey")
        batch_op.drop_column("chapter_id")
