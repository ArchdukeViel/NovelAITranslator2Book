"""add composite indexes for public ranking aggregation

Revision ID: c8d2e4f6a1b3
Revises: b7c1e2d3f4a5
Create Date: 2026-08-20 00:00:00.000000
"""

from collections.abc import Sequence

from alembic import op

revision: str = "c8d2e4f6a1b3"
down_revision: str | Sequence[str] | None = "b7c1e2d3f4a5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Support the public_novel.view time-window and viewer predicates."""
    op.create_index(
        "ix_analytics_events_rank_event_time_novel_user",
        "analytics_events",
        ["event_name", "created_at", "novel_id", "user_id"],
        unique=False,
    )
    op.create_index(
        "ix_analytics_events_rank_event_time_novel_session",
        "analytics_events",
        ["event_name", "created_at", "novel_id", "session_id"],
        unique=False,
    )


def downgrade() -> None:
    """Remove public ranking aggregation indexes."""
    op.drop_index("ix_analytics_events_rank_event_time_novel_session", table_name="analytics_events")
    op.drop_index("ix_analytics_events_rank_event_time_novel_user", table_name="analytics_events")
