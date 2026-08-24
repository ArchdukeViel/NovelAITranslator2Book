"""secure the unified credential registry from Supabase Data API roles

Revision ID: e7f1a9c3b5d2
Revises: d4e6f8a2b1c3
Create Date: 2026-08-22 00:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "e7f1a9c3b5d2"
down_revision: str | Sequence[str] | None = "d4e6f8a2b1c3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("ALTER TABLE IF EXISTS public.provider_credentials ENABLE ROW LEVEL SECURITY")
    op.execute(
        """
        DO $$
        BEGIN
            DROP POLICY IF EXISTS novelai_app_runtime_all ON public.provider_credentials;
            CREATE POLICY novelai_app_runtime_all ON public.provider_credentials
                FOR ALL TO novelai_app USING (true) WITH CHECK (true);
        END;
        $$;
        """
    )
    op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE public.provider_credentials TO novelai_app")
    op.execute("REVOKE ALL PRIVILEGES ON TABLE public.provider_credentials FROM anon, authenticated")
    op.execute(
        """
        DO $$
        DECLARE
            sequence_name text;
        BEGIN
            SELECT pg_get_serial_sequence('public.provider_credentials', 'id') INTO sequence_name;
            IF sequence_name IS NOT NULL THEN
                EXECUTE format('REVOKE ALL PRIVILEGES ON SEQUENCE %s FROM anon, authenticated', sequence_name);
            END IF;
        END;
        $$;
        """
    )


def downgrade() -> None:
    # Keep the credential table protected if this migration is rolled back.
    op.execute("REVOKE ALL PRIVILEGES ON TABLE public.provider_credentials FROM anon, authenticated")
