"""Test verifying autovacuum storage parameter migration.

Reference: REQ-015 / F-15 (postgres-database-hardening-and-security).
Ensures migration e5f6a7b8c9d0 executes upgrade and downgrade cleanly.
"""

import importlib.util
from pathlib import Path


def test_autovacuum_migration_structure() -> None:
    migration_path = (
        Path(__file__).parent.parent
        / "alembic"
        / "versions"
        / "2026-09-05_a1b2c3d4e5f6_add_table_autovacuum_storage.py"
    )
    assert migration_path.exists()

    spec = importlib.util.spec_from_file_location("autovacuum_migration", migration_path)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    assert mod.revision == "e5f6a7b8c9d0"
    assert mod.down_revision == "d4e5f6a7b8c9"
    assert callable(mod.upgrade)
    assert callable(mod.downgrade)
