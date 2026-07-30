"""add least-privilege backend runtime role contract

Revision ID: c7d9e1f3a5b2
Revises: f2a4c6e8b0d1
Create Date: 2026-07-30 00:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "c7d9e1f3a5b2"
down_revision: str | Sequence[str] | None = "f2a4c6e8b0d1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'novelai_app') THEN
                CREATE ROLE novelai_app NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS;
            END IF;
        END;
        $$;
        """
    )
    op.execute("DO $$ BEGIN EXECUTE format('GRANT CONNECT ON DATABASE %I TO novelai_app', current_database()); END $$;")
    op.execute("GRANT USAGE ON SCHEMA public, private TO novelai_app")
    op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO novelai_app")
    op.execute("GRANT USAGE, SELECT, UPDATE ON ALL SEQUENCES IN SCHEMA public TO novelai_app")
    op.execute(
        """
        DO $$
        DECLARE
            table_name text;
        BEGIN
            FOR table_name IN
                SELECT tablename FROM pg_tables WHERE schemaname = 'public'
            LOOP
                EXECUTE format('DROP POLICY IF EXISTS novelai_app_runtime_all ON public.%I', table_name);
                EXECUTE format(
                    'CREATE POLICY novelai_app_runtime_all ON public.%I FOR ALL TO novelai_app USING (true) WITH CHECK (true)',
                    table_name
                );
            END LOOP;
        END;
        $$;
        """
    )
    op.execute(
        "ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO novelai_app"
    )
    op.execute("ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT USAGE, SELECT, UPDATE ON SEQUENCES TO novelai_app")
    # Supabase project owners cannot safely ALTER an existing custom role. A
    # separately provisioned LOGIN role inherits this stable privilege contract.


def downgrade() -> None:
    # Keep role, grants, and policies: older application revisions still need runtime access.
    pass
