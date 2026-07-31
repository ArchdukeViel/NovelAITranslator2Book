"""Verify runtime DB least privilege without persisting data or printing secrets.

Runs as the long-running application role (``novelai_runtime``, a LOGIN member
of the ``novelai_app`` NOLOGIN role). All probes run inside one outer
transaction that is always rolled back so the database is left unchanged.

The script never prints connection strings, hostnames, passwords, or raw
exception text. It emits only ``name=true|false`` lines for deterministic
operator evidence. Exit code is non-zero if any check fails.

Denial probes count as successful only when PostgreSQL returns the specific
SQLSTATE ``42501`` (``insufficient_privilege``). Other errors (syntax,
connection, deadlock, lock timeout) fail the check rather than pass silently.
"""

from __future__ import annotations

import secrets
from typing import Any

from sqlalchemy import create_engine, text
from sqlalchemy.exc import DBAPIError

from novelai.config.settings import settings

# PostgreSQL SQLSTATE for insufficient_privilege. Any other SQLSTATE — or no
# SQLSTATE at all — means the failure was not an authorization denial.
_INSUFFICIENT_PRIVILEGE = "42501"

# Role attributes the runtime role must hold (least-privilege contract).
_SECURE_ROLE_FLAGS: dict[str, bool] = {
    "rolsuper": False,
    "rolcreatedb": False,
    "rolcreaterole": False,
    "rolreplication": False,
    "rolbypassrls": False,
    "rolinherit": True,
    "rolcanlogin": True,
}

# Parent-role attributes that must never be held by any role the runtime
# role inherits privileges from.
_DANGEROUS_PARENT_FLAGS: tuple[str, ...] = (
    "rolsuper",
    "rolcreatedb",
    "rolcreaterole",
    "rolreplication",
    "rolbypassrls",  # inherited BYPASSRLS lets runtime skip RLS on all tables
)

# DDL operations that must be denied to the runtime role.
_DENIED_DDL: dict[str, str] = {
    "create_schema_denied": "CREATE SCHEMA novelai_runtime_acceptance",
    "create_role_denied": "CREATE ROLE novelai_runtime_acceptance",
    "alter_application_table_denied": (
        "ALTER TABLE public.system_settings ADD COLUMN novelai_runtime_acceptance integer"
    ),
    "drop_application_table_denied": "DROP TABLE public.system_settings",
    "create_database_denied": "CREATE DATABASE novelai_runtime_acceptance",
}


def _sqlstate(error: DBAPIError) -> str | None:
    """Return the PostgreSQL SQLSTATE from a SQLAlchemy-wrapped DBAPI error.

    psycopg v3 exposes ``sqlstate`` on the ``orig`` exception. Other drivers
    may expose ``pgcode`` or ``sqlstate``; we read any of them defensively and
    never print the exception object (which can embed the connection string).
    """
    # Check orig first (psycopg v3), then fall back to the DBAPIError itself.
    for source in (getattr(error, "orig", None), error):
        if source is None:
            continue
        for attr in ("sqlstate", "pgcode"):
            value = getattr(source, attr, None)
            if isinstance(value, str) and value:
                return value
    return None


def _denied(connection: Any, statement: str) -> bool:
    """True only when ``statement`` fails specifically with SQLSTATE 42501."""
    savepoint = connection.begin_nested()
    try:
        connection.execute(text(statement))
    except DBAPIError as error:
        # Any non-42501 failure (syntax, connection loss, lock timeout, etc.)
        # must not be mistaken for a successful authorization denial.
        return _sqlstate(error) == _INSUFFICIENT_PRIVILEGE
    else:
        # The statement executed, so the privilege was NOT denied.
        return False
    finally:
        savepoint.rollback()


def main() -> int:
    if not settings.DATABASE_URL:
        print("database_url_present=false")
        return 1
    print("database_url_present=true")

    engine = create_engine(settings.DATABASE_URL, pool_pre_ping=True)
    checks: dict[str, bool] = {}
    acceptance_key = f"runtime_acceptance_{secrets.token_hex(8)}"
    try:
        with engine.connect() as connection, connection.begin():
            checks["runtime_identity"] = (
                connection.execute(text("SELECT current_user")).scalar_one() == "novelai_runtime"
            )
            checks["role_membership_novelai_app"] = bool(
                connection.execute(text("SELECT pg_has_role(current_user, 'novelai_app', 'MEMBER')")).scalar_one()
            )

            role_row = connection.execute(
                text(
                    "SELECT rolsuper, rolcreatedb, rolcreaterole, rolreplication,"
                    " rolbypassrls, rolinherit, rolcanlogin"
                    " FROM pg_roles WHERE rolname = 'novelai_runtime'"
                )
            ).one()
            checks["role_attributes_least_privilege"] = all(
                bool(getattr(role_row, name)) is expected for name, expected in _SECURE_ROLE_FLAGS.items()
            )

            parent_rows = connection.execute(
                text(
                    "SELECT r.rolsuper, r.rolcreatedb, r.rolcreaterole,"
                    " r.rolreplication, r.rolbypassrls"
                    " FROM pg_auth_members m JOIN pg_roles r ON r.oid = m.roleid"
                    " WHERE m.member = 'novelai_runtime'::regrole"
                )
            ).all()
            checks["parent_role_attributes_safe"] = all(
                all(not bool(getattr(row, flag)) for flag in _DANGEROUS_PARENT_FLAGS) for row in parent_rows
            )

            checks["application_read"] = (
                connection.execute(text("SELECT count(*) FROM public.alembic_version")).scalar_one() == 1
            )

            # Representative application CRUD on public.system_settings, fully
            # rolled back by the enclosing transaction. Never touches the
            # alembic_version table that the read probe above inspects.
            connection.execute(
                text("INSERT INTO public.system_settings (key, value_json) VALUES (:k, NULL)"),
                {"k": acceptance_key},
            )
            inserted = connection.execute(
                text("SELECT value_json FROM public.system_settings WHERE key = :k"),
                {"k": acceptance_key},
            ).scalar_one()
            checks["application_insert"] = inserted is None

            connection.execute(
                text("UPDATE public.system_settings SET value_json = 'v' WHERE key = :k"),
                {"k": acceptance_key},
            )
            # rowcount is 0 for UPDATE()
            updated_value = connection.execute(
                text("SELECT value_json FROM public.system_settings WHERE key = :k"),
                {"k": acceptance_key},
            ).scalar_one()
            checks["application_update"] = updated_value == "v"

            connection.execute(
                text("DELETE FROM public.system_settings WHERE key = :k"),
                {"k": acceptance_key},
            )
            remaining = connection.execute(
                text("SELECT count(*) FROM public.system_settings WHERE key = :k"),
                {"k": acceptance_key},
            ).scalar_one()
            checks["application_delete"] = remaining == 0

            checks["no_bypass_rls"] = bool(
                connection.execute(
                    text("SELECT NOT pg_has_role(current_user, 'novelai_runtime', 'BYPASSRLS') AS not_bypass")
                ).scalar_one()
            )

            # Explicit denials. Each probe runs in its own savepoint and counts
            # only on SQLSTATE 42501; other failures fail rather than pass.
            for label, statement in _DENIED_DDL.items():
                checks[label] = _denied(connection, statement)

            # The runtime role must not hold CREATEROLE: ensure it cannot
            # GRANT privileges it should not be able to delegate.
            checks["grant_application_table_denied"] = _denied(
                connection,
                "GRANT SELECT ON public.system_settings TO novelai_runtime",
            )
            checks["grant_role_denied"] = _denied(connection, "GRANT novelai_app TO novelai_runtime")

            # Schema-scope probes: no CREATE anywhere outside the runtime's
            # own application schemas.
            checks["no_pg_catalog_create"] = not bool(
                connection.execute(
                    text("SELECT has_schema_privilege(current_user, 'pg_catalog', 'CREATE')")
                ).scalar_one()
            )
            checks["no_information_schema_create"] = not bool(
                connection.execute(
                    text("SELECT has_schema_privilege(current_user, 'information_schema', 'CREATE')")
                ).scalar_one()
            )

            unrelated_rows = connection.execute(
                text(
                    "SELECT n.nspname FROM pg_namespace n"
                    " WHERE n.nspname NOT IN ('public', 'private')"
                    " AND n.nspname NOT LIKE 'pg_%' AND n.nspname <> 'information_schema'"
                )
            ).all()
            checks["no_unrelated_schema_create"] = all(
                not bool(
                    connection.execute(
                        text("SELECT has_schema_privilege(current_user, :s, 'CREATE')"),
                        {"s": row[0]},
                    ).scalar_one()
                )
                for row in unrelated_rows
            )
    except Exception:
        # Non-DBAPI failure (pool exhaustion, DNS, connection timeout, etc.).
        # Never print the exception object — it can embed the connection string.
        print("connection_error=true")
        return 1
    finally:
        engine.dispose()

    for name, passed in checks.items():
        print(f"{name}={str(passed).lower()}")
    return 0 if checks and all(checks.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
