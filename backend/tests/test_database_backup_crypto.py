from __future__ import annotations

import io

from pydantic import SecretStr

from novelai.config.settings import settings
from novelai.services.database_backup_service import _encrypt_stream, _pg_environment, decrypt_backup


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
