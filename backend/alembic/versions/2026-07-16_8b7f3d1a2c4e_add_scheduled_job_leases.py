"""add scheduled job leases

Revision ID: 8b7f3d1a2c4e
Revises: 3da9f497264c
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "8b7f3d1a2c4e"
down_revision: str | Sequence[str] | None = "3da9f497264c"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "scheduled_job_leases",
        sa.Column("job_name", sa.String(length=128), nullable=False),
        sa.Column("holder_id", sa.String(length=128), nullable=False),
        sa.Column("acquired_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("heartbeat_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("job_name", name=op.f("pk_scheduled_job_leases")),
    )
    op.create_index(op.f("ix_scheduled_job_leases_expires_at"), "scheduled_job_leases", ["expires_at"])
    op.execute("ALTER TABLE public.scheduled_job_leases ENABLE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY \"Owner has full access to scheduled_job_leases\" "
        "ON public.scheduled_job_leases FOR ALL TO authenticated "
        "USING ((SELECT private.is_owner())) WITH CHECK ((SELECT private.is_owner()))"
    )
    op.execute("REVOKE ALL PRIVILEGES ON TABLE public.scheduled_job_leases FROM anon, authenticated")


def downgrade() -> None:
    op.drop_index(op.f("ix_scheduled_job_leases_expires_at"), table_name="scheduled_job_leases")
    op.drop_table("scheduled_job_leases")
