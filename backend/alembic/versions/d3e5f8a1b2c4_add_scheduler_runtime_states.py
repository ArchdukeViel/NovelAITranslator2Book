"""add scheduler_runtime_states table

Revision ID: d3e5f8a1b2c4
Revises: b5c8f7e2d1a3
Create Date: 2026-07-14 00:00:00.000000

Durable scheduler runtime state for cooldown, failure, exhausted, heartbeat,
and next-eligible tracking (DEBT-036). State survives process restarts.
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "d3e5f8a1b2c4"
down_revision: str | Sequence[str] | None = "b5c8f7e2d1a3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create scheduler_runtime_states table."""
    op.create_table(
        "scheduler_runtime_states",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("scheduler_key", sa.String(64), nullable=False),
        sa.Column("scope_type", sa.String(32), nullable=False),
        sa.Column("scope_key", sa.String(128), nullable=False),
        sa.Column("state", sa.String(32), nullable=False, server_default="idle"),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("error_category", sa.String(64), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("failure_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("consecutive_failures", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_attempt_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_success_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_failure_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cooldown_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("exhausted_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("next_eligible_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("heartbeat_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("locked_by", sa.String(128), nullable=True),
        sa.Column("metadata_json", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_scheduler_runtime_states")),
        sa.UniqueConstraint(
            "scheduler_key",
            "scope_type",
            "scope_key",
            name="uq_scheduler_runtime_states_scope",
        ),
    )
    op.create_index("ix_scheduler_runtime_states_scheduler_key", "scheduler_runtime_states", ["scheduler_key"])
    op.create_index("ix_scheduler_runtime_states_scope_type", "scheduler_runtime_states", ["scope_type"])
    op.create_index("ix_scheduler_runtime_states_state", "scheduler_runtime_states", ["state"])


def downgrade() -> None:
    """Drop scheduler_runtime_states table."""
    op.drop_index("ix_scheduler_runtime_states_state", table_name="scheduler_runtime_states")
    op.drop_index("ix_scheduler_runtime_states_scope_type", table_name="scheduler_runtime_states")
    op.drop_index("ix_scheduler_runtime_states_scheduler_key", table_name="scheduler_runtime_states")
    op.drop_table("scheduler_runtime_states")
