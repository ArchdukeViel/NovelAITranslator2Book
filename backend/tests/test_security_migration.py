from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType

MIGRATIONS_DIR = Path(__file__).parents[1] / "alembic" / "versions"


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
    source = (
        MIGRATIONS_DIR / "2026-07-16_3da9f497264c_remove_pg_net_and_reconcile_rls_policies.py"
    ).read_text(encoding="utf-8")

    assert "SELECT rolname FROM pg_roles WHERE rolname = ANY(:role_names)" in source
    assert "if available_roles is None:" in source


def test_security_migration_removes_pg_net_and_cron_table_grants() -> None:
    source = (
        MIGRATIONS_DIR / "2026-07-16_3da9f497264c_remove_pg_net_and_reconcile_rls_policies.py"
    ).read_text(encoding="utf-8")

    assert "DROP EXTENSION IF EXISTS pg_net" in source
    assert "REVOKE ALL PRIVILEGES ON TABLE public.scheduled_cron_log FROM {data_api_roles}" in source
    assert '_existing_roles("anon, authenticated")' in source
    assert "SET search_path = ''" in source
    assert "CREATE OR REPLACE FUNCTION private.current_user_id()" in source
    assert "CREATE OR REPLACE FUNCTION private.is_owner()" in source
    assert "DROP FUNCTION IF EXISTS public.current_user_id()" in source
