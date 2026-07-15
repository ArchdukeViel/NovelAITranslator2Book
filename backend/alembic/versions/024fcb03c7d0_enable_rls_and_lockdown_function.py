"""enable RLS on scheduled_cron_log and lock down cleanup function

Enables Row-Level Security on the scheduled_cron_log tracking table
(which had RLS disabled, exposing internal scheduler data via PostgREST).
Also revokes public/anon/authenticated EXECUTE on cleanup_expired_scheduler_states()
which is a SECURITY DEFINER function intended only for the service role.

Revision ID: 024fcb03c7d0
Revises: d3e5f8a1b2c4
Create Date: 2026-07-15 00:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "024fcb03c7d0"
down_revision: str | Sequence[str] | None = "d3e5f8a1b2c4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. Enable RLS on scheduled_cron_log
    op.execute("ALTER TABLE public.scheduled_cron_log ENABLE ROW LEVEL SECURITY;")
    # No policies are created; only service_role (which bypasses RLS) can access.

    # 2. Revoke SECURITY DEFINER function EXECUTE from public/anonymous/authenticated
    op.execute("REVOKE EXECUTE ON FUNCTION public.cleanup_expired_scheduler_states() FROM PUBLIC;")
    op.execute("REVOKE EXECUTE ON FUNCTION public.cleanup_expired_scheduler_states() FROM anon;")
    op.execute("REVOKE EXECUTE ON FUNCTION public.cleanup_expired_scheduler_states() FROM authenticated;")
    # service_role already has implicit execute via superuser status.
    # Drop the old cron job that called it via anon and recreate it.
    op.execute("SELECT cron.schedule('cleanup-scheduler-states', '30 3 * * *', 'SELECT public.cleanup_expired_scheduler_states();');")


def downgrade() -> None:
    op.execute("ALTER TABLE public.scheduled_cron_log DISABLE ROW LEVEL SECURITY;")
    op.execute("GRANT EXECUTE ON FUNCTION public.cleanup_expired_scheduler_states() TO PUBLIC;")
    op.execute("GRANT EXECUTE ON FUNCTION public.cleanup_expired_scheduler_states() TO anon;")
    op.execute("GRANT EXECUTE ON FUNCTION public.cleanup_expired_scheduler_states() TO authenticated;")
