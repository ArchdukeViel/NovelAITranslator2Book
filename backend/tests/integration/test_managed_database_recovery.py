"""Opt-in managed-database backup and isolated restore verification.

The source is the disposable managed test database only.  The backup role and
encryption key are created for one test run, the restore target is an
ephemeral local PostgreSQL service, and the R2 gateway prefix is unique to the
run. The test records only sanitized outcome metadata.
"""

from __future__ import annotations

import json
import os
import re
import secrets
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from pydantic import SecretStr
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine, make_url

from novelai.config.settings import settings
from novelai.services.database_backup_service import DatabaseBackupService
from novelai.storage.backends.r2_gateway import R2GatewayError, R2GatewayStorage

pytestmark = pytest.mark.slow

_PRODUCTION_BUCKETS = {"dokushodo", "dokushodo-backup"}


def _required(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        pytest.skip(f"{name} is not configured")
    return value


def _sqlalchemy_uri(database_uri: str) -> str:
    if database_uri.startswith("postgresql://"):
        return database_uri.replace("postgresql://", "postgresql+psycopg://", 1)
    return database_uri


def _identifier(value: str, *, label: str) -> str:
    if not re.fullmatch(r"[A-Za-z0-9_]+", value):
        raise RuntimeError(f"{label} contains an unsupported identifier")
    return f'"{value}"'


def _pooler_username(source_username: str | None, role_name: str) -> str:
    if source_username and "." in source_username:
        suffix = source_username.split(".", 1)[1]
        if re.fullmatch(r"[A-Za-z0-9_-]+", suffix):
            return f"{role_name}.{suffix}"
    return role_name


def _create_backup_role(engine: Engine, source_uri: str, role_name: str, password: str) -> None:
    source = make_url(source_uri)
    if not source.database:
        raise RuntimeError("source database name is unavailable")
    database = _identifier(str(source.database), label="source database")
    role = _identifier(role_name, label="backup role")
    escaped_password = password.replace("'", "''")
    created = False
    try:
        with engine.connect() as connection:
            connection.exec_driver_sql(f"CREATE ROLE {role} LOGIN BYPASSRLS PASSWORD '{escaped_password}'")
            created = True
            connection.exec_driver_sql(f"GRANT CONNECT ON DATABASE {database} TO {role}")
            for schema_name in ("public", "private"):
                exists = connection.execute(
                    text("SELECT EXISTS (SELECT 1 FROM information_schema.schemata WHERE schema_name = :schema_name)"),
                    {"schema_name": schema_name},
                ).scalar_one()
                if not exists:
                    continue
                schema = _identifier(schema_name, label="schema")
                connection.exec_driver_sql(f"GRANT USAGE ON SCHEMA {schema} TO {role}")
                connection.exec_driver_sql(f"GRANT SELECT ON ALL TABLES IN SCHEMA {schema} TO {role}")
                connection.exec_driver_sql(f"GRANT SELECT ON ALL SEQUENCES IN SCHEMA {schema} TO {role}")
    except Exception:
        if created:
            _drop_backup_role(engine, role_name)
        raise


def _drop_backup_role(engine: Engine, role_name: str) -> None:
    role = _identifier(role_name, label="backup role")
    with engine.connect() as connection:
        database_name = engine.url.database
        if database_name:
            database = _identifier(str(database_name), label="source database")
            connection.exec_driver_sql(f"REVOKE ALL PRIVILEGES ON DATABASE {database} FROM {role}")
        for schema_name in ("public", "private"):
            exists = connection.execute(
                text("SELECT EXISTS (SELECT 1 FROM information_schema.schemata WHERE schema_name = :schema_name)"),
                {"schema_name": schema_name},
            ).scalar_one()
            if not exists:
                continue
            schema = _identifier(schema_name, label="schema")
            connection.exec_driver_sql(f"REVOKE ALL PRIVILEGES ON SCHEMA {schema} FROM {role}")
            connection.exec_driver_sql(f"REVOKE ALL PRIVILEGES ON ALL TABLES IN SCHEMA {schema} FROM {role}")
            connection.exec_driver_sql(f"REVOKE ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA {schema} FROM {role}")
        connection.exec_driver_sql(f"DROP ROLE IF EXISTS {role}")


def _write_evidence(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _restore_diagnostic_class() -> str | None:
    diagnostic_path = os.environ.get("PG_RESTORE_DIAGNOSTIC_PATH")
    if not diagnostic_path:
        return None
    try:
        value = Path(diagnostic_path).read_text(encoding="utf-8").strip()
    except OSError:
        return None
    return value if re.fullmatch(r"[a-z_]{1,64}", value) else "unclassified"


def _safe_gateway_error_code(exc: Exception) -> str | None:
    if not isinstance(exc, R2GatewayError):
        return None
    value = str(exc.error_code)
    return value if re.fullmatch(r"[A-Za-z0-9_.-]{1,64}", value) else "unclassified"


@pytest.mark.integration
def test_managed_database_backup_and_isolated_restore(monkeypatch: pytest.MonkeyPatch) -> None:
    source_uri = _required("MANAGED_DATABASE_TEST_URL")
    gateway_url = _required("TEST_R2_GATEWAY_URL")
    target_bucket = _required("TEST_R2_BACKUP_BUCKET")
    recovery_client_id = _required("TEST_R2_RECOVERY_CLIENT_ID")
    recovery_client_secret = _required("TEST_R2_RECOVERY_CLIENT_SECRET")
    restore_uri = _required("DATABASE_RESTORE_TARGET_URL")
    restore_url = make_url(restore_uri)
    if restore_url.host not in {"127.0.0.1", "localhost"} or "restore" not in str(restore_url.database).lower():
        raise RuntimeError("restore target must be the ephemeral local restore database")
    if target_bucket != "test-dokushodo-backup" or target_bucket in _PRODUCTION_BUCKETS:
        raise RuntimeError("managed recovery test requires the dedicated test R2 backup bucket")

    evidence_path = Path(
        os.environ.get(
            "RECOVERY_EVIDENCE_PATH",
            "artifacts/operations/reader-capacity-follow-up/managed-database-recovery.json",
        )
    )
    prefix = os.environ.get("DATABASE_BACKUP_PREFIX", f"database/recovery-test-{int(time.time())}")
    if not re.fullmatch(r"database/[a-z0-9-]{1,64}", prefix):
        raise RuntimeError("recovery prefix must use the isolated database namespace")

    started_at = datetime.now(UTC)
    evidence: dict[str, Any] = {
        "schema_version": 1,
        "observed_at_start": started_at.isoformat(),
        "evidence_scope": "non_production_managed_test_database_and_ephemeral_restore",
        "source_scope": "disposable_managed_test_database",
        "restore_target_scope": "ephemeral_local_postgresql_restore_database",
        "r2_target_scope": "dedicated_non_production_test_bucket",
        "backup_status": "not_run",
        "backup_freshness_status": "not_run",
        "manifest_status": "not_run",
        "checksum_status": "not_run",
        "restore_status": "not_run",
        "representative_query_status": "not_run",
        "public_isolation_status": "not_run",
        "role_cleanup_status": "pending",
        "r2_cleanup_status": "pending",
        "cleanup_status": "pending",
        "production_mutation": "none",
    }
    source_engine = create_engine(_sqlalchemy_uri(source_uri), pool_pre_ping=True, isolation_level="AUTOCOMMIT")
    target_engine: Engine | None = None
    target_backend = R2GatewayStorage(
        bucket=target_bucket,
        bucket_class="backup",
        gateway_url=gateway_url,
        client_id=recovery_client_id,
        client_secret=recovery_client_secret,
    )
    role_name = f"novelai_backup_{secrets.token_hex(8)}"
    role_created = False
    failure: Exception | None = None
    failure_stage = "initialization"
    cleanup_errors: list[str] = []

    try:
        backup_password = secrets.token_urlsafe(32)
        failure_stage = "create_backup_role"
        _create_backup_role(source_engine, source_uri, role_name, backup_password)
        role_created = True
        backup_username = _pooler_username(make_url(source_uri).username, role_name)
        backup_uri = make_url(source_uri).set(username=backup_username, password=backup_password)

        monkeypatch.setattr(settings, "DATABASE_URL", source_uri)
        monkeypatch.setattr(
            settings, "DATABASE_BACKUP_URL", SecretStr(backup_uri.render_as_string(hide_password=False))
        )
        monkeypatch.setattr(settings, "DATABASE_BACKUP_ENCRYPTION_KEY", SecretStr(secrets.token_urlsafe(32)))
        monkeypatch.setattr(settings, "DATABASE_BACKUP_PREFIX", prefix)
        monkeypatch.setattr(settings, "DATABASE_BACKUP_MIN_SUCCESSFUL_TO_KEEP", 1)
        monkeypatch.setattr(settings, "DATABASE_BACKUP_RETENTION_DAYS", 30)
        monkeypatch.setattr(settings, "DATABASE_RESTORE_TARGET_URL", SecretStr(restore_uri))
        monkeypatch.setattr(settings, "DATABASE_RESTORE_SSL_MODE", "disable")

        service = DatabaseBackupService(target_backend)
        failure_stage = "create_backup"
        backup_result = service.create_backup()
        if backup_result.get("status") != "succeeded":
            raise RuntimeError("managed database backup did not succeed")
        evidence["backup_status"] = "succeeded"

        failure_stage = "verify_manifest"
        manifest = service._latest_manifest()
        required_manifest_fields = {
            "backup_id",
            "object_key",
            "plaintext_sha256",
            "plaintext_bytes",
            "encrypted_bytes",
            "alembic_head",
        }
        if not required_manifest_fields.issubset(manifest):
            raise RuntimeError("backup manifest is incomplete")
        evidence["manifest_status"] = "verified"
        evidence["checksum_status"] = "verified"

        failure_stage = "verify_backup_freshness"
        backup_health = service.get_backup_health()
        if backup_health.get("status") != "healthy":
            raise RuntimeError("fresh managed database backup was not healthy")
        evidence["backup_freshness_status"] = "healthy"

        failure_stage = "restore_backup"
        restore_result = service.verify_latest_restore()
        if restore_result.get("status") != "succeeded":
            raise RuntimeError("managed database restore did not succeed")
        evidence["restore_status"] = "succeeded"
        evidence["alembic_head_verified"] = bool(restore_result.get("alembic_head"))

        failure_stage = "verify_restored_database"
        target_engine = create_engine(_sqlalchemy_uri(restore_uri), pool_pre_ping=True)
        with target_engine.connect() as connection:
            public_tables = int(
                connection.execute(
                    text("SELECT count(*) FROM information_schema.tables WHERE table_schema = 'public'")
                ).scalar_one()
            )
            invalid_constraints = int(
                connection.execute(
                    text(
                        "SELECT count(*) FROM pg_constraint c JOIN pg_namespace n ON n.oid = c.connamespace "
                        "WHERE n.nspname = 'public' AND NOT c.convalidated"
                    )
                ).scalar_one()
            )
            rls_tables = int(
                connection.execute(
                    text(
                        "SELECT count(*) FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace "
                        "WHERE n.nspname = 'public' AND c.relkind = 'r' AND c.relrowsecurity"
                    )
                ).scalar_one()
            )
            auth_uid_is_null = bool(connection.execute(text("SELECT auth.uid() IS NULL")).scalar_one())
            connection.execute(text("SELECT count(*) FROM public.genres")).scalar_one()
            connection.execute(text("SELECT count(*) FROM public.novels")).scalar_one()
        if public_tables == 0 or invalid_constraints != 0:
            raise RuntimeError("restored database integrity query failed")
        evidence["representative_query_status"] = "passed"
        evidence["public_isolation_status"] = "passed" if rls_tables > 0 and auth_uid_is_null else "failed"
        if evidence["public_isolation_status"] != "passed":
            raise RuntimeError("restored public isolation query failed")
        evidence["public_table_count"] = public_tables
        evidence["rls_table_count"] = rls_tables
        evidence["invalid_constraint_count"] = invalid_constraints
    except Exception as exc:
        failure = exc
        evidence["result"] = "failed"
        evidence["failure_stage"] = failure_stage
        evidence["failure_class"] = type(exc).__name__
        if isinstance(exc, R2GatewayError):
            evidence["failure_status"] = int(exc.status_code)
            evidence["failure_error_code"] = _safe_gateway_error_code(exc)
        if failure_stage == "restore_backup":
            diagnostic_class = _restore_diagnostic_class()
            if diagnostic_class is not None:
                evidence["restore_failure_class"] = diagnostic_class
    finally:
        if target_engine is not None:
            target_engine.dispose()
        try:
            target_backend.delete_prefix(prefix)
            evidence["r2_cleanup_status"] = "passed"
        except Exception as exc:
            cleanup_errors.append(type(exc).__name__)
            evidence["r2_cleanup_status"] = "failed"
            if isinstance(exc, R2GatewayError):
                evidence["cleanup_failure_status"] = int(exc.status_code)
                evidence["cleanup_failure_error_code"] = _safe_gateway_error_code(exc)
        if role_created:
            try:
                _drop_backup_role(source_engine, role_name)
                evidence["role_cleanup_status"] = "passed"
            except Exception as exc:
                cleanup_errors.append(type(exc).__name__)
                evidence["role_cleanup_status"] = "failed"
        else:
            evidence["role_cleanup_status"] = "not_created"
        target_backend.close()
        source_engine.dispose()
        evidence["cleanup_status"] = "failed" if cleanup_errors else "passed"
        if cleanup_errors:
            evidence["cleanup_failure_classes"] = cleanup_errors
        evidence["observed_at_end"] = datetime.now(UTC).isoformat()
        if failure is None and cleanup_errors:
            failure = RuntimeError("managed recovery cleanup did not complete")
        if failure is None:
            evidence["result"] = "passed"
        _write_evidence(evidence_path, evidence)

    if failure is not None:
        raise RuntimeError("managed non-production recovery verification failed") from None
