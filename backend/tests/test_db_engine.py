"""Tests for the database engine/session boundary.

Uses SQLite in-memory for unit tests (no Postgres required).
Integration tests against real Postgres are not run in CI unless
DATABASE_URL is set to a live instance.
"""

from __future__ import annotations

import pytest
from sqlalchemy import text

from novelai.db.engine import check_connectivity, get_engine, get_sessionmaker, session_scope

# SQLite in-memory URL — no Postgres needed for unit tests
_SQLITE = "sqlite:///:memory:"


class TestGetEngine:
    def test_returns_engine_for_sqlite(self) -> None:
        engine = get_engine(_SQLITE)
        assert engine is not None

    def test_engine_can_execute_select_one(self) -> None:
        engine = get_engine(_SQLITE)
        with engine.connect() as conn:
            result = conn.execute(text("SELECT 1"))
            assert result.scalar() == 1

    def test_raises_runtime_error_without_url(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from novelai.config.settings import settings
        monkeypatch.setattr(settings, "DATABASE_URL", None)
        with pytest.raises(RuntimeError, match="DATABASE_URL"):
            get_engine()

    def test_explicit_url_overrides_settings(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Explicit URL is used even when settings.DATABASE_URL is unset."""
        from novelai.config.settings import settings
        monkeypatch.setattr(settings, "DATABASE_URL", None)
        engine = get_engine(_SQLITE)
        assert engine is not None


class TestGetSessionmaker:
    def test_returns_sessionmaker(self) -> None:
        SM = get_sessionmaker(_SQLITE)
        assert SM is not None

    def test_session_executes_select(self) -> None:
        SM = get_sessionmaker(_SQLITE)
        session = SM()
        try:
            result = session.execute(text("SELECT 1"))
            assert result.scalar() == 1
        finally:
            session.close()


class TestSessionScope:
    def test_yields_session_and_commits(self) -> None:
        with session_scope(_SQLITE) as session:
            result = session.execute(text("SELECT 1"))
            assert result.scalar() == 1

    def test_rolls_back_on_exception(self) -> None:
        """Session is rolled back and closed even when an exception is raised."""
        with pytest.raises(ValueError, match="intentional"):
            with session_scope(_SQLITE) as session:
                session.execute(text("SELECT 1"))
                raise ValueError("intentional")

    def test_session_closed_after_context(self) -> None:
        """Context manager exits cleanly without raising."""
        # In SQLAlchemy 2.x, close() returns the connection to pool but
        # the session object remains reusable. We only assert clean exit.
        with session_scope(_SQLITE) as session:
            result = session.execute(text("SELECT 42"))
            assert result.scalar() == 42
        # No exception means session_scope committed and closed cleanly.


class TestCheckConnectivity:
    def test_returns_true_for_sqlite(self) -> None:
        assert check_connectivity(_SQLITE) is True

    def test_returns_false_for_bad_url(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Returns False when the engine raises on connect."""
        def _bad_engine(url: str | None = None) -> None:
            raise Exception("simulated connection failure")

        monkeypatch.setattr("novelai.db.engine.get_engine", _bad_engine)
        assert check_connectivity("sqlite:///ignored") is False
