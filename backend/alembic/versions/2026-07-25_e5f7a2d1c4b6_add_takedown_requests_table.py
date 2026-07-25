"""add takedown_requests table for DMCA intake

Revision ID: e5f7a2d1c4b6
Revises: 9c2e4a6b8d0f
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "e5f7a2d1c4b6"
down_revision: str | Sequence[str] | None = "9c2e4a6b8d0f"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "takedown_requests",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("complainant_name", sa.String(length=255), nullable=False),
        sa.Column("complainant_email", sa.String(length=255), nullable=False),
        sa.Column("complainant_phone", sa.String(length=64), nullable=True),
        sa.Column("infringing_url", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("original_work_url", sa.Text(), nullable=True),
        sa.Column("original_work_description", sa.Text(), nullable=True),
        sa.Column(
            "status",
            sa.String(length=32),
            nullable=False,
            server_default="pending",
            comment="pending | reviewing | approved | rejected | expired",
        ),
        sa.Column("reviewer_notes", sa.Text(), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reviewed_by_user_id", sa.Integer(), nullable=True),
        sa.Column("signature", sa.Text(), nullable=False, comment="Digital signature or typed legal name."),
        sa.Column("ip_address", sa.String(length=64), nullable=True),
        sa.Column("user_agent", sa.String(length=512), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_takedown_requests")),
    )
    op.create_index(op.f("ix_takedown_requests_status"), "takedown_requests", ["status"])
    op.execute("ALTER TABLE public.takedown_requests ENABLE ROW LEVEL SECURITY")
    op.execute(
        'CREATE POLICY "Owner full access to takedown_requests" '
        "ON public.takedown_requests FOR ALL TO authenticated "
        "USING ((SELECT private.is_owner())) WITH CHECK ((SELECT private.is_owner()))"
    )
    op.execute("REVOKE ALL PRIVILEGES ON TABLE public.takedown_requests FROM anon, authenticated")


def downgrade() -> None:
    op.execute('DROP POLICY IF EXISTS "Owner full access to takedown_requests" ON public.takedown_requests')
    op.drop_index(op.f("ix_takedown_requests_status"), table_name="takedown_requests")
    op.drop_table("takedown_requests")
