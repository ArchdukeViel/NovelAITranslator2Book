"""add review moderation fields

Revision ID: c3a7e9f5b1d2
Revises: c7d9e1f3a5b2
Create Date: 2026-08-02 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c3a7e9f5b1d2"
down_revision: str | Sequence[str] | None = "c7d9e1f3a5b2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add moderation columns to reviews: status, updated_at, moderated_at, reviewer_notes, reviewed_by_user_id."""
    with op.batch_alter_table("reviews") as batch_op:
        batch_op.add_column(
            sa.Column(
                "status",
                sa.String(length=20),
                nullable=False,
                server_default="pending",
                comment="pending | published | rejected",
            )
        )
        batch_op.add_column(sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column("moderated_at", sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column("reviewer_notes", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("reviewed_by_user_id", sa.Integer(), nullable=True))

    op.execute("UPDATE reviews SET updated_at = created_at WHERE updated_at IS NULL")

    with op.batch_alter_table("reviews") as batch_op:
        batch_op.alter_column(
            "updated_at",
            existing_type=sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
        )

    op.create_index(op.f("ix_reviews_status"), "reviews", ["status"])
    op.create_index(op.f("ix_reviews_novel_id_status"), "reviews", ["novel_id", "status"])


def downgrade() -> None:
    """Remove review moderation fields."""
    op.drop_index(op.f("ix_reviews_novel_id_status"), table_name="reviews")
    op.drop_index(op.f("ix_reviews_status"), table_name="reviews")
    with op.batch_alter_table("reviews") as batch_op:
        batch_op.drop_column("reviewed_by_user_id")
        batch_op.drop_column("reviewer_notes")
        batch_op.drop_column("moderated_at")
        batch_op.drop_column("updated_at")
        batch_op.drop_column("status")
