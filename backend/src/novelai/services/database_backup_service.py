"""Encrypted logical PostgreSQL backups committed through the R2 gateway."""

from __future__ import annotations

import contextlib
import hashlib
import json
import os
import secrets
import struct
import subprocess
import tempfile
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

from novelai.config.settings import settings
from novelai.storage.backends.r2_gateway import R2ObjectMetadata

_MAGIC = b"NADB1"
_CHUNK_SIZE = 1024 * 1024


def _key() -> bytes:
    if settings.DATABASE_BACKUP_ENCRYPTION_KEY is None:
        raise RuntimeError("Database backup encryption key is not configured")
    return hashlib.sha256(settings.DATABASE_BACKUP_ENCRYPTION_KEY.get_secret_value().encode()).digest()


def _encrypt_stream(source: Any, target: Any) -> tuple[str, int]:
    aes = AESGCM(_key())
    nonce_prefix = secrets.token_bytes(4)
    target.write(_MAGIC + nonce_prefix)
    digest = hashlib.sha256()
    total = 0
    counter = 0
    while chunk := source.read(_CHUNK_SIZE):
        digest.update(chunk)
        total += len(chunk)
        nonce = nonce_prefix + counter.to_bytes(8, "big")
        ciphertext = aes.encrypt(nonce, chunk, _MAGIC + counter.to_bytes(8, "big"))
        target.write(struct.pack(">I", len(ciphertext)))
        target.write(ciphertext)
        counter += 1
    target.write(struct.pack(">I", 0))
    return digest.hexdigest(), total


def decrypt_backup(source: Any, target: Any) -> str:
    header = source.read(9)
    if len(header) != 9 or not header.startswith(_MAGIC):
        raise RuntimeError("Invalid encrypted database backup")
    nonce_prefix = header[5:]
    aes = AESGCM(_key())
    digest = hashlib.sha256()
    counter = 0
    while True:
        raw_length = source.read(4)
        if len(raw_length) != 4:
            raise RuntimeError("Truncated encrypted database backup")
        length = struct.unpack(">I", raw_length)[0]
        if length == 0:
            break
        ciphertext = source.read(length)
        if len(ciphertext) != length:
            raise RuntimeError("Truncated encrypted database backup")
        nonce = nonce_prefix + counter.to_bytes(8, "big")
        plaintext = aes.decrypt(nonce, ciphertext, _MAGIC + counter.to_bytes(8, "big"))
        target.write(plaintext)
        digest.update(plaintext)
        counter += 1
    return digest.hexdigest()


def _pg_environment(database_url: str, *, ssl_mode: str) -> dict[str, str]:
    url = make_url(database_url)
    if not url.host or not url.database:
        raise RuntimeError("PostgreSQL backup URL must include a host and database")
    environment = os.environ.copy()
    environment["PGHOST"] = url.host
    environment["PGPORT"] = str(url.port or 5432)
    environment["PGDATABASE"] = url.database
    if url.username:
        environment["PGUSER"] = url.username
    if url.password:
        environment["PGPASSWORD"] = url.password
    environment["PGSSLMODE"] = ssl_mode
    return environment


def _database_backup_uri() -> str:
    configured = settings.DATABASE_BACKUP_URL
    if configured is None or not configured.get_secret_value():
        raise RuntimeError("DATABASE_BACKUP_URL is not configured")

    backup_uri = configured.get_secret_value().replace("postgresql+psycopg://", "postgresql://", 1)
    source_uri = (settings.DATABASE_URL or "").replace("postgresql+psycopg://", "postgresql://", 1)
    if source_uri and make_url(backup_uri).render_as_string(hide_password=False) == make_url(
        source_uri
    ).render_as_string(hide_password=False):
        raise RuntimeError("DATABASE_BACKUP_URL must identify a dedicated backup-capable database role")
    return backup_uri


def _is_backup_stale(modified: datetime | None, max_age_hours: int) -> bool:
    if modified is None:
        return True
    if modified.tzinfo is None:
        modified = modified.replace(tzinfo=UTC)
    return (datetime.now(UTC) - modified) > timedelta(hours=max_age_hours)


class DatabaseBackupService:
    def __init__(self, backend: Any) -> None:
        self._backend = backend
        self._bucket = backend.bucket
        self._prefix = settings.DATABASE_BACKUP_PREFIX.strip("/")

    def _manifest_objects(self) -> list[R2ObjectMetadata]:
        return [
            item
            for item in self._backend.list_objects(self._prefix, recursive=True).objects
            if item.key.endswith("/manifest.json")
        ]

    def create_backup(self) -> dict[str, Any]:
        if not settings.DATABASE_URL:
            raise RuntimeError("DATABASE_URL is not configured")
        backup_id = f"database-{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}-{secrets.token_hex(4)}"
        object_key = f"{self._prefix}/{backup_id}/dump.custom.aesgcm"
        manifest_key = f"{self._prefix}/{backup_id}/manifest.json"
        database_uri = _database_backup_uri()
        environment = _pg_environment(database_uri, ssl_mode=settings.DB_SSL_MODE)
        encrypted_path: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(prefix="novelai-db-", suffix=".aesgcm", delete=False) as encrypted:
                encrypted_path = Path(encrypted.name)
                process = subprocess.Popen(
                    [
                        settings.PG_DUMP_PATH,
                        "--format=custom",
                        "--no-owner",
                        "--no-privileges",
                        "--schema=public",
                        "--schema=private",
                    ],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    env=environment,
                )
                assert process.stdout is not None
                plaintext_sha256, plaintext_bytes = _encrypt_stream(process.stdout, encrypted)
                stderr = process.stderr.read() if process.stderr is not None else b""
                if process.wait() != 0:
                    raise RuntimeError(f"pg_dump failed ({len(stderr)} diagnostic bytes)")
            assert encrypted_path is not None
            with encrypted_path.open("rb") as body:
                encrypted_size = encrypted_path.stat().st_size
                self._backend.save_stream(object_key, body, content_length=encrypted_size)
            manifest = {
                "schema_version": 1,
                "backup_id": backup_id,
                "created_at": datetime.now(UTC).isoformat(),
                "format": "pg_dump-custom+chunked-aes-256-gcm",
                "postgres_major": 17,
                "schemas": ["public", "private"],
                "object_key": object_key,
                "plaintext_sha256": plaintext_sha256,
                "plaintext_bytes": plaintext_bytes,
                "encrypted_bytes": encrypted_size,
                "alembic_head": self._alembic_head(database_uri),
            }
            self._backend.save(
                manifest_key,
                json.dumps(manifest, sort_keys=True).encode(),
                content_type="application/json",
            )
            self.apply_retention()
            return {"status": "succeeded", "backup_id": backup_id, "manifest_key": manifest_key}
        except Exception:
            with contextlib.suppress(Exception):
                self._backend.delete(object_key)
            raise
        finally:
            if encrypted_path is not None:
                encrypted_path.unlink(missing_ok=True)

    def apply_retention(self) -> None:
        manifests = self._manifest_objects()
        manifests.sort(key=lambda item: item.last_modified or datetime.min.replace(tzinfo=UTC), reverse=True)
        cutoff = datetime.now(UTC) - timedelta(days=settings.DATABASE_BACKUP_RETENTION_DAYS)
        for item in manifests[settings.DATABASE_BACKUP_MIN_SUCCESSFUL_TO_KEEP :]:
            modified = item.last_modified
            if modified is None or modified >= cutoff:
                continue
            root = item.key.rsplit("/", 1)[0]
            for child in self._backend.list_keys(root, recursive=True):
                self._backend.delete(child)

    def get_backup_health(self) -> dict[str, Any]:
        manifests = self._manifest_objects()
        if not manifests:
            return {"status": "unhealthy", "message": "No committed database backup exists"}
        latest = max(manifests, key=lambda item: item.last_modified or datetime.min.replace(tzinfo=UTC))
        modified = latest.last_modified
        if _is_backup_stale(modified, settings.OPERATOR_ALERT_STALE_BACKUP_HOURS):
            return {
                "status": "unhealthy",
                "message": "Latest backup exceeds freshness threshold",
                "last_backup_at": modified.isoformat() if modified is not None else None,
            }
        return {
            "status": "healthy",
            "message": "Committed encrypted database backup exists",
            "last_backup_at": modified.isoformat() if modified is not None else None,
        }

    def verify_latest_restore(self) -> dict[str, Any]:
        if settings.DATABASE_RESTORE_TARGET_URL is None:
            raise RuntimeError("Database restore target is not configured")
        target_uri = settings.DATABASE_RESTORE_TARGET_URL.get_secret_value()
        source_uri = (settings.DATABASE_URL or "").replace("postgresql+psycopg://", "postgresql://", 1)
        if target_uri.replace("postgresql+psycopg://", "postgresql://", 1) == source_uri:
            raise RuntimeError("Refusing to restore over the source database")
        if "restore" not in urlparse(target_uri).path.lower():
            raise RuntimeError("Restore target must be a dedicated restore-verification database")
        manifest = self._latest_manifest()
        self._prepare_restore_target(target_uri)
        encrypted_path: Path | None = None
        plaintext_path: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(prefix="novelai-restore-", suffix=".aesgcm", delete=False) as encrypted:
                encrypted_path = Path(encrypted.name)
                encrypted.write(self._backend.load(str(manifest["object_key"])))
            with tempfile.NamedTemporaryFile(prefix="novelai-restore-", suffix=".custom", delete=False) as plaintext:
                plaintext_path = Path(plaintext.name)
                with encrypted_path.open("rb") as encrypted:
                    digest = decrypt_backup(encrypted, plaintext)
            if digest != manifest["plaintext_sha256"]:
                raise RuntimeError("Decrypted database backup checksum mismatch")
            environment = _pg_environment(target_uri, ssl_mode=settings.DATABASE_RESTORE_SSL_MODE)
            completed = subprocess.run(
                [
                    settings.PG_RESTORE_PATH,
                    "--dbname=",
                    "--exit-on-error",
                    "--clean",
                    "--if-exists",
                    "--no-owner",
                    "--no-privileges",
                    str(plaintext_path),
                ],
                capture_output=True,
                env=environment,
                check=False,
            )
            if completed.returncode != 0:
                raise RuntimeError(f"pg_restore failed ({len(completed.stderr)} diagnostic bytes)")
            verification = self._restore_metadata(target_uri)
            if verification["alembic_head"] != manifest.get("alembic_head"):
                raise RuntimeError("Restored Alembic head does not match backup manifest")
            if verification["invalid_constraints"] != 0 or verification["public_tables"] == 0:
                raise RuntimeError("Restored database integrity verification failed")
            return {"status": "succeeded", "backup_id": manifest["backup_id"], **verification}
        finally:
            if plaintext_path is not None:
                plaintext_path.unlink(missing_ok=True)
            if encrypted_path is not None:
                encrypted_path.unlink(missing_ok=True)

    def _latest_manifest(self) -> dict[str, Any]:
        manifests = self._manifest_objects()
        if not manifests:
            raise RuntimeError("No committed database backup exists")
        latest = max(manifests, key=lambda item: item.last_modified or datetime.min.replace(tzinfo=UTC))
        return json.loads(self._backend.load(latest.key))

    @staticmethod
    def _alembic_head(database_uri: str) -> str:
        return DatabaseBackupService._restore_metadata(database_uri)["alembic_head"]

    @staticmethod
    def _restore_metadata(database_uri: str) -> dict[str, Any]:
        sqlalchemy_uri = database_uri.replace("postgresql://", "postgresql+psycopg://", 1)
        engine = create_engine(sqlalchemy_uri, pool_pre_ping=True)
        try:
            with engine.connect() as connection:
                return {
                    "alembic_head": str(
                        connection.execute(text("SELECT version_num FROM public.alembic_version")).scalar_one()
                    ),
                    "public_tables": int(
                        connection.execute(
                            text("SELECT count(*) FROM information_schema.tables WHERE table_schema = 'public'")
                        ).scalar_one()
                    ),
                    "invalid_constraints": int(
                        connection.execute(
                            text(
                                "SELECT count(*) FROM pg_constraint c JOIN pg_namespace n ON n.oid = c.connamespace "
                                "WHERE n.nspname = 'public' AND NOT c.convalidated"
                            )
                        ).scalar_one()
                    ),
                }
        finally:
            engine.dispose()

    @staticmethod
    def _prepare_restore_target(database_uri: str) -> None:
        sqlalchemy_uri = database_uri.replace("postgresql://", "postgresql+psycopg://", 1)
        engine = create_engine(sqlalchemy_uri, pool_pre_ping=True, isolation_level="AUTOCOMMIT")
        try:
            with engine.connect() as connection:
                for role_name in ("anon", "authenticated", "service_role", "novelai_app"):
                    exists = connection.execute(
                        text("SELECT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = :role_name)"),
                        {"role_name": role_name},
                    ).scalar_one()
                    if not exists:
                        connection.exec_driver_sql(f'CREATE ROLE "{role_name}" NOLOGIN')
                connection.exec_driver_sql("CREATE SCHEMA IF NOT EXISTS auth")
                connection.exec_driver_sql(
                    "CREATE OR REPLACE FUNCTION auth.uid() RETURNS uuid LANGUAGE sql STABLE AS 'SELECT NULL::uuid'"
                )
        finally:
            engine.dispose()
