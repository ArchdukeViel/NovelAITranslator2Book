from __future__ import annotations

import io

import pytest
from pydantic import SecretStr

from novelai.config.settings import settings
from novelai.services.database_backup_service import (
    _database_backup_uri,
    _encrypt_stream,
    _pg_environment,
    decrypt_backup,
)


def test_database_backup_encryption_round_trip(monkeypatch) -> None:
    monkeypatch.setattr(settings, "DATABASE_BACKUP_ENCRYPTION_KEY", SecretStr("x" * 64))
    plaintext = (b"postgres-backup-data" * 100_000) + b"tail"
    encrypted = io.BytesIO()
    digest, size = _encrypt_stream(io.BytesIO(plaintext), encrypted)
    assert size == len(plaintext)
    assert plaintext not in encrypted.getvalue()
    restored = io.BytesIO()
    encrypted.seek(0)
    assert decrypt_backup(encrypted, restored) == digest
    assert restored.getvalue() == plaintext


def test_pg_environment_uses_discrete_libpq_values(monkeypatch) -> None:
    monkeypatch.setattr(settings, "DB_SSL_MODE", "require")
    environment = _pg_environment(
        "postgresql+psycopg://user:p%40ss@db.example:6543/novelai",
        ssl_mode="require",
    )
    assert environment["PGHOST"] == "db.example"
    assert environment["PGPORT"] == "6543"
    assert environment["PGDATABASE"] == "novelai"
    assert environment["PGUSER"] == "user"
    assert environment["PGPASSWORD"] == "p@ss"
    assert environment["PGSSLMODE"] == "require"


def test_database_backup_uri_requires_a_dedicated_role(monkeypatch) -> None:
    monkeypatch.setattr(settings, "DATABASE_URL", "postgresql+psycopg://runtime:secret@db/novelai")
    monkeypatch.setattr(
        settings,
        "DATABASE_BACKUP_URL",
        SecretStr("postgresql+psycopg://backup:secret@db/novelai"),
    )

    assert _database_backup_uri() == "postgresql://backup:secret@db/novelai"


def test_database_backup_uri_rejects_runtime_role(monkeypatch) -> None:
    source = "postgresql+psycopg://runtime:secret@db/novelai"
    monkeypatch.setattr(settings, "DATABASE_URL", source)
    monkeypatch.setattr(settings, "DATABASE_BACKUP_URL", SecretStr(source))

    with pytest.raises(RuntimeError, match="dedicated backup-capable"):
        _database_backup_uri()
