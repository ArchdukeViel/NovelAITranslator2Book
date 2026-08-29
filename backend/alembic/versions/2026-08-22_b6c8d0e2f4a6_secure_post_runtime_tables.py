"""secure tables created after the backend runtime-role migration

Revision ID: b6c8d0e2f4a6
Revises: f1a7c9e2d4b6
Create Date: 2026-08-22 00:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "b6c8d0e2f4a6"
down_revision: str | Sequence[str] | None = "f1a7c9e2d4b6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SECURE_BACKEND_TABLES: tuple[str, ...] = (
    "activity_records",
    "contributor_credentials",
    "contributor_usage_ledger",
)


def _quote_identifier(value: str) -> str:
    return f'"{value.replace(chr(34), chr(34) * 2)}"'


def _enable_runtime_policy(table_name: str) -> None:
    """Deny Data API roles while retaining access for the backend role."""
    table = _quote_identifier(table_name)
    op.execute(f"ALTER TABLE IF EXISTS public.{table} ENABLE ROW LEVEL SECURITY")
    op.execute(
        f"""
        DO $$
        DECLARE
            policy_name text;
        BEGIN
            FOR policy_name IN
                SELECT policyname
                FROM pg_policies
                WHERE schemaname = 'public' AND tablename = '{table_name}'
            LOOP
                EXECUTE format('DROP POLICY %I ON public.%I', policy_name, '{table_name}');
            END LOOP;
            EXECUTE 'CREATE POLICY novelai_app_runtime_all ON public.{table} '
                || 'FOR ALL TO novelai_app USING (true) WITH CHECK (true)';
        END;
        $$;
        """
    )
    op.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE public.{table} TO novelai_app")


def _revoke_data_api_roles() -> None:
    """Remove direct Supabase Data API privileges when those roles exist."""
    table_names = ", ".join(f"'{name}'" for name in SECURE_BACKEND_TABLES)
    op.execute(
        f"""
        DO $$
        DECLARE
            role_list text;
            table_list text;
            sequence_name text;
        BEGIN
            SELECT string_agg(quote_ident(rolname), ', ' ORDER BY rolname)
            INTO role_list
            FROM pg_roles
            WHERE rolname IN ('anon', 'authenticated');

            IF role_list IS NULL THEN
                RETURN;
            END IF;

            SELECT string_agg(quote_ident(schemaname) || '.' || quote_ident(tablename), ', ')
            INTO table_list
            FROM pg_tables
            WHERE schemaname = 'public'
              AND tablename IN ({table_names});
            IF table_list IS NOT NULL THEN
                EXECUTE format('REVOKE ALL PRIVILEGES ON TABLE %s FROM %s', table_list, role_list);
            END IF;

            FOR sequence_name IN
                SELECT pg_get_serial_sequence(format('%I.%I', table_schema, table_name), 'id')
                FROM information_schema.tables
                WHERE table_schema = 'public'
                  AND table_name IN ({table_names})
                  AND EXISTS (
                      SELECT 1
                      FROM information_schema.columns
                      WHERE table_schema = 'public'
                        AND table_name = information_schema.tables.table_name
                        AND column_name = 'id'
                  )
            LOOP
                IF sequence_name IS NOT NULL THEN
                    EXECUTE format('REVOKE ALL PRIVILEGES ON SEQUENCE %s FROM %s', sequence_name, role_list);
                END IF;
            END LOOP;
        END;
        $$;
        """
    )


def upgrade() -> None:
    for table_name in SECURE_BACKEND_TABLES:
        _enable_runtime_policy(table_name)
    _revoke_data_api_roles()


def downgrade() -> None:
    # Keep RLS enabled and Data API privileges revoked on downgrade.
    _revoke_data_api_roles()
