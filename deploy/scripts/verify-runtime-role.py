"""Verify runtime DB least privilege without persisting data or printing secrets."""

from __future__ import annotations

from sqlalchemy import create_engine, text
from sqlalchemy.exc import DBAPIError

from novelai.config.settings import settings


def main() -> int:
    if not settings.DATABASE_URL:
        print("database_url_present=false")
        return 1
    engine = create_engine(settings.DATABASE_URL)
    checks: dict[str, bool] = {}
    try:
        with engine.connect() as connection, connection.begin():
            checks["runtime_identity"] = (
                connection.execute(text("SELECT current_user")).scalar_one() == "novelai_runtime"
            )
            checks["application_read"] = (
                connection.execute(text("SELECT count(*) FROM alembic_version")).scalar_one() == 1
            )
            checks["application_write"] = (
                connection.execute(text("UPDATE alembic_version SET version_num = version_num")).rowcount == 1
            )
            checks["create_extension_denied"] = not connection.execute(
                text("SELECT has_database_privilege(current_user, current_database(), 'CREATE')")
            ).scalar_one()
            denied = {
                "create_schema_denied": "CREATE SCHEMA novelai_runtime_acceptance",
                "create_role_denied": "CREATE ROLE novelai_runtime_acceptance",
                "alter_table_denied": "ALTER TABLE alembic_version ADD COLUMN novelai_runtime_acceptance integer",
            }
            for name, statement in denied.items():
                savepoint = connection.begin_nested()
                try:
                    connection.execute(text(statement))
                except DBAPIError:
                    checks[name] = True
                else:
                    checks[name] = False
                finally:
                    savepoint.rollback()
    finally:
        engine.dispose()

    for name, passed in checks.items():
        print(f"{name}={str(passed).lower()}")
    return 0 if checks and all(checks.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
