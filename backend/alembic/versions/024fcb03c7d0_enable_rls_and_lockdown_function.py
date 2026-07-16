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
    op.execute(
        """
        CREATE SCHEMA IF NOT EXISTS private;
        REVOKE ALL ON SCHEMA private FROM PUBLIC;

        CREATE TABLE IF NOT EXISTS public.scheduled_cron_log (
            id BIGSERIAL PRIMARY KEY,
            job_name TEXT NOT NULL,
            started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            status TEXT NOT NULL,
            rows_affected INTEGER DEFAULT 0,
            error_message TEXT
        );
        """
    )
    op.execute(
        """
        CREATE OR REPLACE FUNCTION private.cleanup_expired_scheduler_states()
        RETURNS void
        LANGUAGE plpgsql
        SECURITY DEFINER
        SET search_path = ''
        AS $$
        DECLARE
            deleted_count INTEGER;
        BEGIN
            DELETE FROM public.scheduler_runtime_states
            WHERE state NOT IN ('running', 'cooldown', 'failed', 'disabled')
              AND updated_at < NOW() - INTERVAL '14 days';
            GET DIAGNOSTICS deleted_count = ROW_COUNT;
            INSERT INTO public.scheduled_cron_log (job_name, status, rows_affected)
            VALUES ('cleanup_expired_scheduler_states', 'succeeded', deleted_count);
        EXCEPTION WHEN OTHERS THEN
            INSERT INTO public.scheduled_cron_log (job_name, status, rows_affected, error_message)
            VALUES ('cleanup_expired_scheduler_states', 'failed', 0, SQLERRM);
        END;
        $$;
        """
    )

    op.execute("ALTER TABLE public.scheduled_cron_log ENABLE ROW LEVEL SECURITY;")
    op.execute("REVOKE ALL ON FUNCTION private.cleanup_expired_scheduler_states() FROM PUBLIC;")
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'service_role') THEN
                GRANT USAGE ON SCHEMA private TO service_role;
                GRANT EXECUTE ON FUNCTION private.cleanup_expired_scheduler_states() TO service_role;
            END IF;
        END;
        $$;
        """
    )
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'pg_cron') THEN
                PERFORM cron.schedule(
                    'cleanup-scheduler-states',
                    '30 3 * * *',
                    'SELECT private.cleanup_expired_scheduler_states();'
                );
            END IF;
        END;
        $$;
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'pg_cron') THEN
                PERFORM cron.unschedule('cleanup-scheduler-states');
            END IF;
        END;
        $$;
        """
    )
    op.execute("ALTER TABLE public.scheduled_cron_log DISABLE ROW LEVEL SECURITY;")
    op.execute("DROP FUNCTION IF EXISTS private.cleanup_expired_scheduler_states()")
    op.execute("DROP TABLE IF EXISTS public.scheduled_cron_log")
