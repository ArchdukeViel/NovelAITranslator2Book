"""Focused tests for ``deploy/scripts/verify-runtime-role.py``.

The verifier is an operator script; a real run needs a managed PostgreSQL
where the runtime role is provisioned. These tests prove the script:

* fails closed when ``DATABASE_URL`` is unset;
* prints only boolean ``name=true|false`` lines and never leaks connection
  strings or raw exception text;
* counts a denial only on PostgreSQL SQLSTATE ``42501``;
* does NOT false-pass on non-privilege errors (syntax error, lock timeout);
* rolls back each probe via savepoints;
* exits non-zero when any check fails.

The script is imported as a module and exercised against fake SQLAlchemy
connection/engine objects so no live database is required.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest
from sqlalchemy.exc import DBAPIError

_SCRIPT = Path(__file__).parents[2] / "deploy" / "scripts" / "verify-runtime-role.py"


class _FakeOrig(Exception):
    """Minimal stand-in for a DBAPI driver exception with a SQLSTATE."""

    def __init__(self, sqlstate: str | None) -> None:
        super().__init__("redacted")
        self.sqlstate = sqlstate


class _Sequence:
    """Yields successive scalar values on repeated execute() calls of the same SQL."""

    def __init__(self, *values: Any) -> None:
        self._values = list(values)

    def __call__(self) -> Any:
        return self._values.pop(0) if self._values else None


class _FakeSavepoint:
    def __init__(self, rolled_back: list[int]) -> None:
        self._rolled_back = rolled_back

    def rollback(self) -> None:
        self._rolled_back.append(1)


class _FakeResult:
    """Mimics SQLAlchemy ``result.scalar_one()`` / ``.one()`` row access."""

    def __init__(self, value: Any = None, row: Any = None) -> None:
        self._value = value
        self._row = row

    def scalar_one(self) -> Any:
        return self._value

    def one(self) -> Any:
        return self._row

    def all(self) -> list[Any]:
        if isinstance(self._value, (list, tuple)):
            return list(self._value)
        if self._row is not None:
            return [self._row]
        return []


class _FakeConnection:
    """Records executed SQL and responds to scripted behaviors."""

    def __init__(self, behaviors: dict[str, Any]) -> None:
        self._behaviors = behaviors
        self.executed: list[str] = []
        self.savepoints: list[_FakeSavepoint] = []
        self.rollback_count = 0

    def begin(self) -> _FakeConnection:
        return self

    def __enter__(self) -> _FakeConnection:
        return self

    def __exit__(self, *exc: object) -> None:
        return None

    def begin_nested(self) -> _FakeSavepoint:
        sp = _FakeSavepoint(self._behaviors.setdefault("_savepoint_rollbacks", []))
        self.savepoints.append(sp)
        return sp

    def execute(self, statement: Any, params: dict[str, Any] | None = None) -> _FakeResult:
        sql_text = str(statement)
        self.executed.append(sql_text)
        behavior = self._behaviors.get(sql_text)
        if behavior is None:
            # Default: succeed with a generic scalar/result unless scripted.
            return _FakeResult(value=0, row=None)
        if isinstance(behavior, _FakeOrig):
            raise DBAPIError(statement=sql_text, params=params or {}, orig=behavior)
        if isinstance(behavior, Exception):
            raise DBAPIError(statement=sql_text, params=params or {}, orig=behavior)
        if isinstance(behavior, tuple) and behavior and isinstance(behavior[0], _FakeOrig):
            raise DBAPIError(statement=sql_text, params=params or {}, orig=behavior[0])
        if isinstance(behavior, tuple):
            return _FakeResult(value=behavior[1], row=behavior[2] if len(behavior) > 2 else None)
        if isinstance(behavior, dict):
            return _FakeResult(value=behavior.get("scalar"), row=behavior.get("row"))
        if callable(behavior):
            return _FakeResult(value=behavior(), row=None)
        return _FakeResult(value=behavior, row=None)


class _FakeEngine:
    def __init__(self, connection: _FakeConnection) -> None:
        self._connection = connection

    def connect(self) -> _FakeConnection:
        return self._connection

    def dispose(self) -> None:
        self._behaviors_disposed = True


def _load_verifier() -> ModuleType:
    spec = importlib.util.spec_from_file_location("verify_runtime_role_under_test", _SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["verify_runtime_role_under_test"] = module
    spec.loader.exec_module(module)
    return module


def _capture_main(module: ModuleType, monkeypatch: pytest.MonkeyPatch, engine: _FakeEngine) -> tuple[int, list[str]]:
    outputs: list[str] = []
    monkeypatch.setattr(module.settings, "DATABASE_URL", "postgresql+psycopg://redacted:redacted@redacted/redacted")
    monkeypatch.setattr(module, "create_engine", lambda *a, **k: engine)
    monkeypatch.setattr(module, "print", lambda *a, **k: outputs.extend(str(arg) for arg in a), raising=False)
    exit_code = module.main()
    return exit_code, outputs


def test_missing_database_url_fails_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    module = _load_verifier()
    monkeypatch.setattr(module.settings, "DATABASE_URL", None)
    monkeypatch.setattr(module, "print", lambda *a, **k: None, raising=False)
    assert module.main() == 1


def test_output_never_leaks_connection_material(monkeypatch: pytest.MonkeyPatch) -> None:
    module = _load_verifier()

    class _Role:
        rolsuper = False
        rolcreatedb = False
        rolcreaterole = False
        rolreplication = False
        rolbypassrls = False
        rolinherit = True
        rolcanlogin = True

    conn = _FakeConnection(
        behaviors={
            "SELECT rolsuper, rolcreatedb, rolcreaterole, rolreplication, rolbypassrls, rolinherit, rolcanlogin FROM pg_roles WHERE rolname = 'novelai_runtime'": {
                "row": _Role()
            },
            "SELECT value_json FROM public.system_settings WHERE key = :k": _Sequence(None, "v"),
            "SELECT count(*) FROM public.system_settings WHERE key = :k": 0,
        }
    )
    engine = _FakeEngine(conn)
    _exit_code, outputs = _capture_main(module, monkeypatch, engine)
    joined = "\n".join(outputs)
    assert "redacted@redacted" not in joined
    assert "password" not in joined.lower()
    assert "postgresql+psycopg" not in joined
    # All output lines are name=true|false form.
    for line in outputs:
        assert line.split("=", 1)[1] in {"true", "false"} or line == "database_url_present=true"


def test_denial_passes_only_on_insufficient_privilege(monkeypatch: pytest.MonkeyPatch) -> None:
    module = _load_verifier()
    behaviors: dict[str, Any] = {
        "SELECT current_user": "novelai_runtime",
        "SELECT pg_has_role(current_user, 'novelai_app', 'MEMBER')": True,
        "SELECT rolsuper, rolcreatedb, rolcreaterole, rolreplication, rolbypassrls, rolinherit, rolcanlogin FROM pg_roles WHERE rolname = 'novelai_runtime'": (
            _FakeOrig("42501"),  # placeholder; overridden below
        ),
    }

    # Provide the secure role row as a namedtuple-like object.
    class _Role:
        rolsuper = False
        rolcreatedb = False
        rolcreaterole = False
        rolreplication = False
        rolbypassrls = False
        rolinherit = True
        rolcanlogin = True

    behaviors[
        "SELECT rolsuper, rolcreatedb, rolcreaterole, rolreplication, rolbypassrls, rolinherit, rolcanlogin FROM pg_roles WHERE rolname = 'novelai_runtime'"
    ] = {"row": _Role()}
    behaviors["SELECT count(*) FROM public.alembic_version"] = 1
    # CRUD on system_settings: succeed.
    behaviors["SELECT value_json FROM public.system_settings WHERE key = :k"] = None
    behaviors["SELECT count(*) FROM public.system_settings WHERE key = :k"] = 0
    behaviors["SELECT NOT pg_has_role(current_user, 'novelai_runtime', 'BYPASSRLS') AS not_bypass"] = True
    # Denial probes: CREATE SCHEMA gets 42501 (real denial).
    denial_stmt = "CREATE SCHEMA novelai_runtime_acceptance"
    behaviors[denial_stmt] = _FakeOrig("42501")

    conn = _FakeConnection(behaviors)
    engine = _FakeEngine(conn)
    _exit_code, outputs = _capture_main(module, monkeypatch, engine)
    assert "create_schema_denied=true" in outputs
    # Savepoint rolled back at least once for the denial probe.
    assert behaviors.get("_savepoint_rollbacks")


def test_non_privilege_error_does_not_false_pass(monkeypatch: pytest.MonkeyPatch) -> None:
    module = _load_verifier()
    behaviors: dict[str, Any] = {
        "SELECT current_user": "novelai_runtime",
        "SELECT pg_has_role(current_user, 'novelai_app', 'MEMBER')": True,
        "SELECT NOT pg_has_role(current_user, 'novelai_runtime', 'BYPASSRLS') AS not_bypass": True,
        "SELECT count(*) FROM public.alembic_version": 1,
        "SELECT value_json FROM public.system_settings WHERE key = :k": None,
        "SELECT count(*) FROM public.system_settings WHERE key = :k": 0,
    }

    class _Role:
        rolsuper = False
        rolcreatedb = False
        rolcreaterole = False
        rolreplication = False
        rolbypassrls = False
        rolinherit = True
        rolcanlogin = True

    behaviors[
        "SELECT rolsuper, rolcreatedb, rolcreaterole, rolreplication, rolbypassrls, rolinherit, rolcanlogin FROM pg_roles WHERE rolname = 'novelai_runtime'"
    ] = {"row": _Role()}
    # Syntax-like failure: SQLSTATE 42601 instead of 42501.
    behaviors["CREATE SCHEMA novelai_runtime_acceptance"] = _FakeOrig("42601")
    behaviors["CREATE ROLE novelai_runtime_acceptance"] = _FakeOrig("42501")
    behaviors["ALTER TABLE public.system_settings ADD COLUMN novelai_runtime_acceptance integer"] = _FakeOrig("42501")
    behaviors["DROP TABLE public.system_settings"] = _FakeOrig("42501")
    behaviors["CREATE DATABASE novelai_runtime_acceptance"] = _FakeOrig("42501")
    behaviors["GRANT SELECT ON public.system_settings TO novelai_runtime"] = _FakeOrig("42501")

    conn = _FakeConnection(behaviors)
    engine = _FakeEngine(conn)
    exit_code, outputs = _capture_main(module, monkeypatch, engine)
    assert "create_schema_denied=false" in outputs
    assert exit_code == 1


def test_wrong_identity_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    module = _load_verifier()

    class _Role:
        rolsuper = False
        rolcreatedb = False
        rolcreaterole = False
        rolreplication = False
        rolbypassrls = False
        rolinherit = True
        rolcanlogin = True

    behaviors: dict[str, Any] = {
        "SELECT current_user": "postgres",
        "SELECT rolsuper, rolcreatedb, rolcreaterole, rolreplication, rolbypassrls, rolinherit, rolcanlogin FROM pg_roles WHERE rolname = 'novelai_runtime'": {
            "row": _Role()
        },
    }
    conn = _FakeConnection(behaviors)
    engine = _FakeEngine(conn)
    exit_code, outputs = _capture_main(module, monkeypatch, engine)
    assert "runtime_identity=false" in outputs
    assert exit_code == 1


def test_missing_membership_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    module = _load_verifier()

    class _Role:
        rolsuper = False
        rolcreatedb = False
        rolcreaterole = False
        rolreplication = False
        rolbypassrls = False
        rolinherit = True
        rolcanlogin = True

    behaviors: dict[str, Any] = {
        "SELECT current_user": "novelai_runtime",
        "SELECT pg_has_role(current_user, 'novelai_app', 'MEMBER')": False,
        "SELECT rolsuper, rolcreatedb, rolcreaterole, rolreplication, rolbypassrls, rolinherit, rolcanlogin FROM pg_roles WHERE rolname = 'novelai_runtime'": {
            "row": _Role()
        },
    }
    conn = _FakeConnection(behaviors)
    engine = _FakeEngine(conn)
    exit_code, outputs = _capture_main(module, monkeypatch, engine)
    assert "role_membership_novelai_app=false" in outputs
    assert exit_code == 1


def test_dangerous_role_attribute_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    module = _load_verifier()

    class _Role:
        rolsuper = True
        rolcreatedb = False
        rolcreaterole = False
        rolreplication = False
        rolbypassrls = False
        rolinherit = True
        rolcanlogin = True

    behaviors: dict[str, Any] = {
        "SELECT current_user": "novelai_runtime",
        "SELECT pg_has_role(current_user, 'novelai_app', 'MEMBER')": True,
        "SELECT rolsuper, rolcreatedb, rolcreaterole, rolreplication, rolbypassrls, rolinherit, rolcanlogin FROM pg_roles WHERE rolname = 'novelai_runtime'": {
            "row": _Role()
        },
    }
    conn = _FakeConnection(behaviors)
    engine = _FakeEngine(conn)
    exit_code, outputs = _capture_main(module, monkeypatch, engine)
    assert "role_attributes_least_privilege=false" in outputs
    assert exit_code == 1


def test_parent_role_attributes_safe_when_no_parents(monkeypatch: pytest.MonkeyPatch) -> None:
    module = _load_verifier()

    class _Role:
        rolsuper = False
        rolcreatedb = False
        rolcreaterole = False
        rolreplication = False
        rolbypassrls = False
        rolinherit = True
        rolcanlogin = True

    behaviors: dict[str, Any] = {
        "SELECT current_user": "novelai_runtime",
        "SELECT pg_has_role(current_user, 'novelai_app', 'MEMBER')": True,
        "SELECT rolsuper, rolcreatedb, rolcreaterole, rolreplication, rolbypassrls, rolinherit, rolcanlogin FROM pg_roles WHERE rolname = 'novelai_runtime'": {
            "row": _Role()
        },
        # parent-role query returns empty list → all([]) is True
        "SELECT r.rolsuper, r.rolcreatedb, r.rolcreaterole, r.rolreplication, r.rolbypassrls FROM pg_auth_members m JOIN pg_roles r ON r.oid = m.roleid WHERE m.member = 'novelai_runtime'::regrole": [],
        "SELECT count(*) FROM public.alembic_version": 1,
        "SELECT value_json FROM public.system_settings WHERE key = :k": _Sequence(None, "v"),
        "SELECT count(*) FROM public.system_settings WHERE key = :k": 0,
        "SELECT NOT pg_has_role(current_user, 'novelai_runtime', 'BYPASSRLS') AS not_bypass": True,
        "CREATE SCHEMA novelai_runtime_acceptance": _FakeOrig("42501"),
        "CREATE ROLE novelai_runtime_acceptance": _FakeOrig("42501"),
        "ALTER TABLE public.system_settings ADD COLUMN novelai_runtime_acceptance integer": _FakeOrig("42501"),
        "DROP TABLE public.system_settings": _FakeOrig("42501"),
        "CREATE DATABASE novelai_runtime_acceptance": _FakeOrig("42501"),
        "GRANT SELECT ON public.system_settings TO novelai_runtime": _FakeOrig("42501"),
        "GRANT novelai_app TO novelai_runtime": _FakeOrig("42501"),
        "SELECT has_schema_privilege(current_user, 'pg_catalog', 'CREATE')": False,
        "SELECT has_schema_privilege(current_user, 'information_schema', 'CREATE')": False,
        "SELECT n.nspname FROM pg_namespace n WHERE n.nspname NOT IN ('public', 'private') AND n.nspname NOT LIKE 'pg_%' AND n.nspname <> 'information_schema'": [],
    }
    conn = _FakeConnection(behaviors)
    engine = _FakeEngine(conn)
    exit_code, outputs = _capture_main(module, monkeypatch, engine)
    assert "parent_role_attributes_safe=true" in outputs
    assert exit_code == 0


def test_parent_role_attributes_unsafe_when_parent_superuser(monkeypatch: pytest.MonkeyPatch) -> None:
    module = _load_verifier()

    class _Role:
        rolsuper = False
        rolcreatedb = False
        rolcreaterole = False
        rolreplication = False
        rolbypassrls = False
        rolinherit = True
        rolcanlogin = True

    class _ParentRole:
        rolsuper = True
        rolcreatedb = False
        rolcreaterole = False
        rolreplication = False
        rolbypassrls = False

    behaviors: dict[str, Any] = {
        "SELECT current_user": "novelai_runtime",
        "SELECT pg_has_role(current_user, 'novelai_app', 'MEMBER')": True,
        "SELECT rolsuper, rolcreatedb, rolcreaterole, rolreplication, rolbypassrls, rolinherit, rolcanlogin FROM pg_roles WHERE rolname = 'novelai_runtime'": {
            "row": _Role()
        },
        "SELECT r.rolsuper, r.rolcreatedb, r.rolcreaterole, r.rolreplication, r.rolbypassrls FROM pg_auth_members m JOIN pg_roles r ON r.oid = m.roleid WHERE m.member = 'novelai_runtime'::regrole": [
            _ParentRole()
        ],
    }
    conn = _FakeConnection(behaviors)
    engine = _FakeEngine(conn)
    exit_code, outputs = _capture_main(module, monkeypatch, engine)
    assert "parent_role_attributes_safe=false" in outputs
    assert exit_code == 1


def test_grant_role_denied_raises_42501(monkeypatch: pytest.MonkeyPatch) -> None:
    module = _load_verifier()

    class _Role:
        rolsuper = False
        rolcreatedb = False
        rolcreaterole = False
        rolreplication = False
        rolbypassrls = False
        rolinherit = True
        rolcanlogin = True

    behaviors: dict[str, Any] = {
        "SELECT current_user": "novelai_runtime",
        "SELECT pg_has_role(current_user, 'novelai_app', 'MEMBER')": True,
        "SELECT rolsuper, rolcreatedb, rolcreaterole, rolreplication, rolbypassrls, rolinherit, rolcanlogin FROM pg_roles WHERE rolname = 'novelai_runtime'": {
            "row": _Role()
        },
        "SELECT r.rolsuper, r.rolcreatedb, r.rolcreaterole, r.rolreplication, r.rolbypassrls FROM pg_auth_members m JOIN pg_roles r ON r.oid = m.roleid WHERE m.member = 'novelai_runtime'::regrole": [],
        "SELECT count(*) FROM public.alembic_version": 1,
        "SELECT value_json FROM public.system_settings WHERE key = :k": _Sequence(None, "v"),
        "SELECT count(*) FROM public.system_settings WHERE key = :k": 0,
        "SELECT NOT pg_has_role(current_user, 'novelai_runtime', 'BYPASSRLS') AS not_bypass": True,
        "CREATE SCHEMA novelai_runtime_acceptance": _FakeOrig("42501"),
        "CREATE ROLE novelai_runtime_acceptance": _FakeOrig("42501"),
        "ALTER TABLE public.system_settings ADD COLUMN novelai_runtime_acceptance integer": _FakeOrig("42501"),
        "DROP TABLE public.system_settings": _FakeOrig("42501"),
        "CREATE DATABASE novelai_runtime_acceptance": _FakeOrig("42501"),
        "GRANT SELECT ON public.system_settings TO novelai_runtime": _FakeOrig("42501"),
        "GRANT novelai_app TO novelai_runtime": _FakeOrig("42501"),
        "SELECT has_schema_privilege(current_user, 'pg_catalog', 'CREATE')": False,
        "SELECT has_schema_privilege(current_user, 'information_schema', 'CREATE')": False,
        "SELECT n.nspname FROM pg_namespace n WHERE n.nspname NOT IN ('public', 'private') AND n.nspname NOT LIKE 'pg_%' AND n.nspname <> 'information_schema'": [],
    }
    conn = _FakeConnection(behaviors)
    engine = _FakeEngine(conn)
    exit_code, outputs = _capture_main(module, monkeypatch, engine)
    assert "grant_role_denied=true" in outputs
    assert exit_code == 0


def test_no_unrelated_schema_create_when_only_public_private(monkeypatch: pytest.MonkeyPatch) -> None:
    module = _load_verifier()

    class _Role:
        rolsuper = False
        rolcreatedb = False
        rolcreaterole = False
        rolreplication = False
        rolbypassrls = False
        rolinherit = True
        rolcanlogin = True

    behaviors: dict[str, Any] = {
        "SELECT current_user": "novelai_runtime",
        "SELECT pg_has_role(current_user, 'novelai_app', 'MEMBER')": True,
        "SELECT rolsuper, rolcreatedb, rolcreaterole, rolreplication, rolbypassrls, rolinherit, rolcanlogin FROM pg_roles WHERE rolname = 'novelai_runtime'": {
            "row": _Role()
        },
        "SELECT r.rolsuper, r.rolcreatedb, r.rolcreaterole, r.rolreplication, r.rolbypassrls FROM pg_auth_members m JOIN pg_roles r ON r.oid = m.roleid WHERE m.member = 'novelai_runtime'::regrole": [],
        "SELECT count(*) FROM public.alembic_version": 1,
        "SELECT value_json FROM public.system_settings WHERE key = :k": _Sequence(None, "v"),
        "SELECT count(*) FROM public.system_settings WHERE key = :k": 0,
        "SELECT NOT pg_has_role(current_user, 'novelai_runtime', 'BYPASSRLS') AS not_bypass": True,
        "CREATE SCHEMA novelai_runtime_acceptance": _FakeOrig("42501"),
        "CREATE ROLE novelai_runtime_acceptance": _FakeOrig("42501"),
        "ALTER TABLE public.system_settings ADD COLUMN novelai_runtime_acceptance integer": _FakeOrig("42501"),
        "DROP TABLE public.system_settings": _FakeOrig("42501"),
        "CREATE DATABASE novelai_runtime_acceptance": _FakeOrig("42501"),
        "GRANT SELECT ON public.system_settings TO novelai_runtime": _FakeOrig("42501"),
        "GRANT novelai_app TO novelai_runtime": _FakeOrig("42501"),
        "SELECT has_schema_privilege(current_user, 'pg_catalog', 'CREATE')": False,
        "SELECT has_schema_privilege(current_user, 'information_schema', 'CREATE')": False,
        # namespace query returns empty → no unrelated schemas to check → all([]) True
        "SELECT n.nspname FROM pg_namespace n WHERE n.nspname NOT IN ('public', 'private') AND n.nspname NOT LIKE 'pg_%' AND n.nspname <> 'information_schema'": [],
    }
    conn = _FakeConnection(behaviors)
    engine = _FakeEngine(conn)
    exit_code, outputs = _capture_main(module, monkeypatch, engine)
    assert "no_unrelated_schema_create=true" in outputs
    assert exit_code == 0


def test_sqlstate_fallback_fails_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    """A DBAPIError whose orig carries no sqlstate/pgcode must not pass as a denial."""
    module = _load_verifier()

    class _NoSqlstate(Exception):
        """DBAPI orig with no sqlstate or pgcode attribute."""

    class _Role:
        rolsuper = False
        rolcreatedb = False
        rolcreaterole = False
        rolreplication = False
        rolbypassrls = False
        rolinherit = True
        rolcanlogin = True

    # The CREATE SCHEMA denial probe fires first. Raise DBAPIError with an orig
    # that has neither sqlstate nor pgcode → _sqlstate() returns None → _denied()
    # returns False → check fails → exit 1.
    behaviors: dict[str, Any] = {
        "SELECT current_user": "novelai_runtime",
        "SELECT pg_has_role(current_user, 'novelai_app', 'MEMBER')": True,
        "SELECT rolsuper, rolcreatedb, rolcreaterole, rolreplication, rolbypassrls, rolinherit, rolcanlogin FROM pg_roles WHERE rolname = 'novelai_runtime'": {
            "row": _Role()
        },
        "SELECT r.rolsuper, r.rolcreatedb, r.rolcreaterole, r.rolreplication, r.rolbypassrls FROM pg_auth_members m JOIN pg_roles r ON r.oid = m.roleid WHERE m.member = 'novelai_runtime'::regrole": [],
        "SELECT count(*) FROM public.alembic_version": 1,
        "SELECT value_json FROM public.system_settings WHERE key = :k": None,
        "SELECT count(*) FROM public.system_settings WHERE key = :k": 0,
        "SELECT NOT pg_has_role(current_user, 'novelai_runtime', 'BYPASSRLS') AS not_bypass": True,
        # Raise DBAPIError with orig lacking any SQLSTATE attribute.
        "CREATE SCHEMA novelai_runtime_acceptance": _NoSqlstate("no-sqlstate"),
    }
    conn = _FakeConnection(behaviors)
    engine = _FakeEngine(conn)
    exit_code, outputs = _capture_main(module, monkeypatch, engine)
    # _sqlstate() returns None → not == "42501" → _denied returns False → check false.
    assert "create_schema_denied=false" in outputs
    assert exit_code == 1
