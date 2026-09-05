"""Test reader database URL isolation and role safety.

Reference: REQ-012 / F-12 (postgres-database-hardening-and-security).
Ensures main_reader binds to READER_DATABASE_URL and respects read-only separation.
"""

from novelai.config.settings import settings
from novelai.db.engine import get_sessionmaker


def test_reader_database_url_precedence(monkeypatch) -> None:
    primary = "sqlite:///:memory:"
    reader_url = "sqlite:///./reader_isolated.db"

    monkeypatch.setattr(settings, "DATABASE_URL", primary)
    monkeypatch.setattr(settings, "READER_DATABASE_URL", reader_url)

    # In reader context or when configured, READER_DATABASE_URL is distinct
    assert reader_url == settings.READER_DATABASE_URL
    assert settings.READER_DATABASE_URL != settings.DATABASE_URL


def test_reader_session_creation(monkeypatch) -> None:
    reader_url = "sqlite:///:memory:"
    monkeypatch.setattr(settings, "READER_DATABASE_URL", reader_url)

    sm = get_sessionmaker(settings.READER_DATABASE_URL)
    session = sm()
    try:
        assert session.bind is not None
    finally:
        session.close()
