from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType
from unittest.mock import patch

MIGRATIONS_DIR = Path(__file__).parents[1] / "alembic" / "versions"
SQL_DIR = Path(__file__).parents[1] / "sql"


def _load_migration(filename: str, module_name: str) -> ModuleType:
    path = MIGRATIONS_DIR / filename
    spec = importlib.util.spec_from_file_location(module_name, path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_prerequisite_migration_owns_cron_objects() -> None:
    source = (MIGRATIONS_DIR / "024fcb03c7d0_enable_rls_and_lockdown_function.py").read_text(encoding="utf-8")

    assert "CREATE TABLE IF NOT EXISTS public.scheduled_cron_log" in source
    assert "CREATE OR REPLACE FUNCTION private.cleanup_expired_scheduler_states()" in source
    assert "IF EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'pg_cron')" in source
    assert "SELECT private.cleanup_expired_scheduler_states();" in source


def test_security_migration_covers_every_public_application_table() -> None:
    migration = _load_migration(
        "2026-07-16_3da9f497264c_remove_pg_net_and_reconcile_rls_policies.py",
        "security_migration",
    )

    policies = migration._policies()
    assert set(policies) == set(migration.ALL_TABLES)
    assert policies["scheduled_cron_log"] == []


def test_security_migration_has_one_policy_per_command() -> None:
    migration = _load_migration(
        "2026-07-16_3da9f497264c_remove_pg_net_and_reconcile_rls_policies.py",
        "security_migration_commands",
    )

    for table_name, policies in migration._policies().items():
        commands = [policy[1] for policy in policies]
        assert len(commands) == len(set(commands)), table_name
        assert not ("ALL" in commands and len(commands) > 1), table_name


def test_security_migration_handles_missing_supabase_roles() -> None:
    source = (MIGRATIONS_DIR / "2026-07-16_3da9f497264c_remove_pg_net_and_reconcile_rls_policies.py").read_text(
        encoding="utf-8"
    )

    assert "SELECT rolname FROM pg_roles WHERE rolname = ANY(:role_names)" in source
    assert "if available_roles is None:" in source


def test_ci_auth_compatibility_shim_is_minimal_and_fail_closed() -> None:
    source = (SQL_DIR / "ci_vanilla_postgres_auth_compat.sql").read_text(encoding="utf-8")
    normalized = " ".join(source.upper().split())

    assert "CI-ONLY COMPATIBILITY SHIM" in source
    assert "CREATE SCHEMA IF NOT EXISTS AUTH" in normalized
    assert "CREATE OR REPLACE FUNCTION AUTH.UID()" in normalized
    assert "SELECT NULL::UUID" in normalized
    assert "REVOKE ALL ON SCHEMA AUTH FROM PUBLIC" in normalized
    assert "REVOKE ALL ON FUNCTION AUTH.UID() FROM PUBLIC" in normalized
    assert normalized.count("CREATE ROLE") == 2
    assert "CREATE ROLE ANON NOLOGIN" in normalized
    assert "CREATE ROLE AUTHENTICATED NOLOGIN" in normalized
    assert "SUPERUSER" not in normalized
    assert "CREATEDB" not in normalized
    assert "CREATEROLE" not in normalized
    assert "PASSWORD" not in normalized
    assert "CREATE TABLE" not in normalized
    assert "GRANT " not in normalized


def test_security_migration_removes_pg_net_and_cron_table_grants() -> None:
    source = (MIGRATIONS_DIR / "2026-07-16_3da9f497264c_remove_pg_net_and_reconcile_rls_policies.py").read_text(
        encoding="utf-8"
    )

    assert "DROP EXTENSION IF EXISTS pg_net" in source
    assert "REVOKE ALL PRIVILEGES ON TABLE public.scheduled_cron_log FROM {data_api_roles}" in source
    assert '_existing_roles("anon, authenticated")' in source
    assert "SET search_path = ''" in source
    assert "CREATE OR REPLACE FUNCTION private.current_user_id()" in source
    assert "CREATE OR REPLACE FUNCTION private.is_owner()" in source
    assert "DROP FUNCTION IF EXISTS public.current_user_id()" in source


# ---------------------------------------------------------------------------
# Migration b9e0f1a2c3d4 — secure internal tables with RLS and revoke
# ---------------------------------------------------------------------------

INTERNAL_MIGRATION = "2026-07-29_b9e0f1a2c3d4_secure_internal_tables_with_rls_revoke.py"


def test_internal_table_migration_identity() -> None:
    """Verify revision chain and table inventory."""
    migration = _load_migration(INTERNAL_MIGRATION, "internal_tables")

    assert migration.revision == "b9e0f1a2c3d4"
    assert migration.down_revision == "a4d8b6c2f1e3"
    assert migration.INTERNAL_TABLES == (
        "analytics_events",
        "notifications",
        "notification_preferences",
        "notification_deliveries",
    )


def test_internal_table_migration_enables_rls_and_drops_policies() -> None:
    """Each internal table gets RLS enabled and all policies dropped."""
    source = (MIGRATIONS_DIR / INTERNAL_MIGRATION).read_text(encoding="utf-8")

    assert "ALTER TABLE IF EXISTS public.{_quote_identifier(table_name)} ENABLE ROW LEVEL SECURITY" in source
    assert "SELECT policyname" in source
    assert "FROM pg_policies" in source
    assert "DROP POLICY %I ON public.%I" in source


def test_internal_table_migration_revokes_table_from_anon_authenticated() -> None:
    """Table-level REVOKE ALL for anon/authenticated when roles exist."""
    source = (MIGRATIONS_DIR / INTERNAL_MIGRATION).read_text(encoding="utf-8")

    assert "REVOKE ALL PRIVILEGES ON TABLE %s FROM %s" in source
    assert "WHERE rolname IN ('anon', 'authenticated')" in source
    assert "FROM pg_tables" in source


def test_internal_table_migration_revokes_sequences_from_anon_authenticated() -> None:
    """Sequence-level REVOKE ALL for anon/authenticated autoincrement sequences."""
    source = (MIGRATIONS_DIR / INTERNAL_MIGRATION).read_text(encoding="utf-8")

    assert "pg_get_serial_sequence" in source
    assert "FROM pg_tables" in source
    assert "REVOKE ALL PRIVILEGES ON SEQUENCE" in source


def test_internal_table_migration_has_no_policies() -> None:
    """Zero policies created — backend SQLAlchemy is the only access path."""
    migration = _load_migration(INTERNAL_MIGRATION, "internal_tables_no_policies")

    assert not hasattr(migration, "_policies") or "analytics_events" not in migration._policies()
    # Verify no policy-creation helpers are called in upgrade
    source = (MIGRATIONS_DIR / INTERNAL_MIGRATION).read_text(encoding="utf-8")
    assert "CREATE POLICY" not in source


def test_internal_table_migration_uses_existing_roles_pattern() -> None:
    """Role-safe guard for vanilla PostgreSQL without Supabase roles."""
    source = (MIGRATIONS_DIR / INTERNAL_MIGRATION).read_text(encoding="utf-8")

    assert "FROM pg_roles" in source
    assert "WHERE rolname IN ('anon', 'authenticated')" in source
    assert "IF role_list IS NULL" in source


def test_internal_table_migration_reasserts_scheduled_cron_log_revoke() -> None:
    """scheduled_cron_log zero-policy/revoke contract is reasserted."""
    source = (MIGRATIONS_DIR / INTERNAL_MIGRATION).read_text(encoding="utf-8")

    assert "scheduled_cron_log" in source
    assert '(*INTERNAL_TABLES, "scheduled_cron_log")' in source


def test_internal_table_migration_downgrade_is_security_safe() -> None:
    """Downgrade repeats REVOKE (idempotent) rather than GRANT."""
    source = (MIGRATIONS_DIR / INTERNAL_MIGRATION).read_text(encoding="utf-8")

    downgrade_source = source.split("def downgrade", maxsplit=1)[1]
    assert "GRANT " not in downgrade_source
    assert "_revoke_table_and_sequence" in downgrade_source
    assert '(*INTERNAL_TABLES, "scheduled_cron_log")' in downgrade_source


def test_users_disabled_by_index_migration() -> None:
    """Self-referential moderation FK has covering index."""
    migration = _load_migration(
        "2026-07-30_f2a4c6e8b0d1_index_users_disabled_by_user_id.py",
        "users_disabled_by_index",
    )

    assert migration.revision == "f2a4c6e8b0d1"
    assert migration.down_revision == "b9e0f1a2c3d4"

    with patch.object(migration.op, "create_index") as create_index:
        migration.upgrade()
    create_index.assert_called_once_with(
        "ix_users_disabled_by_user_id",
        "users",
        ["disabled_by_user_id"],
    )

    with patch.object(migration.op, "drop_index") as drop_index:
        migration.downgrade()
    drop_index.assert_called_once_with(
        "ix_users_disabled_by_user_id",
        table_name="users",
    )


def test_request_review_invariants_migration_contract() -> None:
    filename = "2026-08-17_d7e4f9a1c2b3_add_request_review_auth_invariants.py"
    migration = _load_migration(filename, "request_review_invariants")
    source = (MIGRATIONS_DIR / filename).read_text(encoding="utf-8")

    assert migration.revision == "d7e4f9a1c2b3"
    assert migration.down_revision == "4f7c2a9d1e6b"
    assert "chapter_id" in source
    assert "uq_reviews_user_novel" in source
    assert "ix_users_email_lower" in source
    assert "HAVING COUNT(*) > 1" in source


def test_runtime_role_migration_is_least_privilege() -> None:
    source = (MIGRATIONS_DIR / "2026-07-30_c7d9e1f3a5b2_add_novelai_app_runtime_role.py").read_text(encoding="utf-8")

    assert "CREATE ROLE novelai_app NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS" in source
    assert "GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO novelai_app" in source
    assert "GRANT USAGE, SELECT, UPDATE ON ALL SEQUENCES IN SCHEMA public TO novelai_app" in source
    assert "ALTER DEFAULT PRIVILEGES IN SCHEMA public" in source
    assert "FOR ROLE postgres" not in source
    assert "CREATE POLICY novelai_app_runtime_all" in source
    assert "GRANT ALL" not in source
    assert "DROP ROLE" not in source
