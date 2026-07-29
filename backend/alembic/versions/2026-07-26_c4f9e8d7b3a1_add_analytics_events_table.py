"""add analytics_events table (DEBT-009)

Revision ID: c4f9e8d7b3a1
Revises: b7d1e3f5a2c4
Create Date: 2026-07-26 12:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c4f9e8d7b3a1"
down_revision: str | Sequence[str] | None = "b7d1e3f5a2c4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create the analytics_events table."""
    op.create_table(
        "analytics_events",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("event_name", sa.String(128), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("session_id", sa.String(255), nullable=True),
        sa.Column("novel_id", sa.String(255), nullable=True),
        sa.Column("chapter_id", sa.String(255), nullable=True),
        sa.Column("metadata_json", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_analytics_events")),
    )
    op.create_index(
        op.f("ix_analytics_events_event_name"),
        "analytics_events",
        ["event_name"],
    )
    op.create_index(
        op.f("ix_analytics_events_user_id"),
        "analytics_events",
        ["user_id"],
    )
    op.create_index(
        op.f("ix_analytics_events_novel_id"),
        "analytics_events",
        ["novel_id"],
    )
    op.create_index(
        op.f("ix_analytics_events_chapter_id"),
        "analytics_events",
        ["chapter_id"],
    )
    op.create_index(
        op.f("ix_analytics_events_created_at"),
        "analytics_events",
        ["created_at"],
    )


def downgrade() -> None:
    """Drop the analytics_events table."""
    op.drop_index(op.f("ix_analytics_events_created_at"), table_name="analytics_events")
    op.drop_index(op.f("ix_analytics_events_chapter_id"), table_name="analytics_events")
    op.drop_index(op.f("ix_analytics_events_novel_id"), table_name="analytics_events")
    op.drop_index(op.f("ix_analytics_events_user_id"), table_name="analytics_events")
    op.drop_index(op.f("ix_analytics_events_event_name"), table_name="analytics_events")
    op.drop_table("analytics_events")
