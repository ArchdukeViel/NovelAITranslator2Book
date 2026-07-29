"""secure backend-internal tables against Supabase Data API access

Revision ID: b9e0f1a2c3d4
Revises: a4d8b6c2f1e3
Create Date: 2026-07-29 00:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "b9e0f1a2c3d4"
down_revision: str | Sequence[str] | None = "a4d8b6c2f1e3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

INTERNAL_TABLES: tuple[str, ...] = (
    "analytics_events",
    "notifications",
    "notification_preferences",
    "notification_deliveries",
)


def _quote_identifier(value: str) -> str:
    return f'"{value.replace(chr(34), chr(34) * 2)}"'


def _enable_rls_and_drop_policies(table_name: str) -> None:
    """Make one backend-internal table deny all Data API roles."""
    op.execute(f"ALTER TABLE IF EXISTS public.{_quote_identifier(table_name)} ENABLE ROW LEVEL SECURITY")
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
        END;
        $$;
        """
    )


def _revoke_table_and_sequence(table_names: tuple[str, ...]) -> None:
    """Revoke Data API roles on named tables and sequences when present."""
    table_names_in = ", ".join(f"'{name}'" for name in table_names)
    op.execute(
        f"""
        DO $$
        DECLARE
            role_list text;
            table_list text;
            seq_list text;
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
              AND tablename IN ({table_names_in});
            IF table_list IS NOT NULL THEN
                EXECUTE format('REVOKE ALL PRIVILEGES ON TABLE %s FROM %s', table_list, role_list);
            END IF;

            SELECT string_agg(pg_get_serial_sequence(format('%I.%I', schemaname, tablename), 'id'), ', ')
            INTO seq_list
            FROM pg_tables
            WHERE schemaname = 'public'
              AND tablename IN ({table_names_in})
              AND pg_get_serial_sequence(format('%I.%I', schemaname, tablename), 'id') IS NOT NULL;
            IF seq_list IS NOT NULL THEN
                EXECUTE format('REVOKE ALL PRIVILEGES ON SEQUENCE %s FROM %s', seq_list, role_list);
            END IF;
        END;
        $$;
        """
    )


def upgrade() -> None:
    for table_name in INTERNAL_TABLES:
        _enable_rls_and_drop_policies(table_name)
    _revoke_table_and_sequence((*INTERNAL_TABLES, "scheduled_cron_log"))


def downgrade() -> None:
    # Security-safe downgrade: keep RLS enabled and never broaden Data API access.
    _revoke_table_and_sequence((*INTERNAL_TABLES, "scheduled_cron_log"))
