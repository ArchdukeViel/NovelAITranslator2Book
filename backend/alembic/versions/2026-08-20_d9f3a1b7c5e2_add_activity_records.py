"""Add the durable activity queue records table.

Revision ID: d9f3a1b7c5e2
Revises: c8d2e4f6a1b3
Create Date: 2026-08-20 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "d9f3a1b7c5e2"
down_revision: str | Sequence[str] | None = "c8d2e4f6a1b3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "activity_records",
        sa.Column("activity_id", sa.String(length=128), nullable=False),
        sa.Column("type", sa.String(length=32), nullable=False),
        sa.Column("kind", sa.String(length=64), nullable=False),
        sa.Column("novel_id", sa.String(length=255), nullable=False),
        sa.Column("source_key", sa.String(length=128), nullable=True),
        sa.Column("chapters", sa.Text(), nullable=True),
        sa.Column("source_url", sa.Text(), nullable=True),
        sa.Column("provider_key", sa.String(length=128), nullable=True),
        sa.Column("provider_model", sa.String(length=255), nullable=True),
        sa.Column("status", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("claimed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_heartbeat_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("lease_id", sa.String(length=128), nullable=True),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("retry_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("idempotency_key", sa.String(length=255), nullable=True),
        sa.Column("metadata_json", sa.Text(), nullable=True),
        sa.UniqueConstraint("idempotency_key", name="uq_activity_records_idempotency_key"),
        sa.PrimaryKeyConstraint("activity_id", name="pk_activity_records"),
    )
    op.create_index("ix_activity_records_type", "activity_records", ["type"], unique=False)
    op.create_index("ix_activity_records_novel_id", "activity_records", ["novel_id"], unique=False)
    op.create_index("ix_activity_records_status", "activity_records", ["status"], unique=False)
    op.create_index(
        "ix_activity_records_status_type_created",
        "activity_records",
        ["status", "type", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_activity_records_novel_status_created",
        "activity_records",
        ["novel_id", "status", "created_at"],
        unique=False,
    )
    op.create_index("ix_activity_records_lease_expires", "activity_records", ["lease_expires_at"], unique=False)
    op.create_index(
        "ix_activity_records_idempotency_status",
        "activity_records",
        ["idempotency_key", "status"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_activity_records_idempotency_status", table_name="activity_records")
    op.drop_index("ix_activity_records_lease_expires", table_name="activity_records")
    op.drop_index("ix_activity_records_novel_status_created", table_name="activity_records")
    op.drop_index("ix_activity_records_status_type_created", table_name="activity_records")
    op.drop_index("ix_activity_records_status", table_name="activity_records")
    op.drop_index("ix_activity_records_novel_id", table_name="activity_records")
    op.drop_index("ix_activity_records_type", table_name="activity_records")
    op.drop_table("activity_records")
