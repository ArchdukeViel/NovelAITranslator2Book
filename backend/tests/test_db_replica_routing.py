"""Test read-replica database URL routing and read session dependency.

Reference: REQ-011 / F-11 (postgres-database-hardening-and-security).
"""

from unittest.mock import patch

import pytest

from novelai.config.settings import settings
from novelai.db.engine import read_session_scope


def test_read_session_scope_routes_to_replica_when_configured(monkeypatch: pytest.MonkeyPatch) -> None:
    replica_url = "sqlite:///:memory:"
    primary_url = "sqlite:///:memory:"
    monkeypatch.setattr(settings, "DATABASE_REPLICA_URL", replica_url)
    monkeypatch.setattr(settings, "DATABASE_URL", primary_url)

    with patch("novelai.db.engine.get_sessionmaker") as mock_get_sessionmaker:
        mock_sm = mock_get_sessionmaker.return_value
        mock_session = mock_sm.return_value

        with read_session_scope():
            pass

        mock_get_sessionmaker.assert_called_once_with(replica_url)
        mock_session.rollback.assert_called_once()
        mock_session.close.assert_called_once()


def test_read_session_scope_falls_back_to_primary(monkeypatch: pytest.MonkeyPatch) -> None:
    primary_url = "sqlite:///:memory:"
    monkeypatch.setattr(settings, "DATABASE_REPLICA_URL", None)
    monkeypatch.setattr(settings, "DATABASE_URL", primary_url)

    with patch("novelai.db.engine.get_sessionmaker") as mock_get_sessionmaker:
        mock_sm = mock_get_sessionmaker.return_value
        mock_session = mock_sm.return_value

        with read_session_scope():
            pass

        mock_get_sessionmaker.assert_called_once_with(primary_url)
        mock_session.rollback.assert_called_once()
        mock_session.close.assert_called_once()
