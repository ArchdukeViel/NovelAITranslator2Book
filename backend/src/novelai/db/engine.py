"""SQLAlchemy engine and session factory.

Usage:
    from novelai.db.engine import session_scope

    with session_scope() as session:
        session.execute(...)

The engine is created fresh per call (pool_pre_ping=True handles reconnects).
For production, the URL comes from settings.DATABASE_URL (postgresql+psycopg).
For tests, pass an explicit SQLite in-memory URL.
"""

from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager
from threading import Lock
from typing import Any

from sqlalchemy import Engine, create_engine, text
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import NullPool

from novelai.config.settings import settings

_ENGINE_CACHE: dict[tuple[object, ...], Engine] = {}
_ENGINE_CACHE_LOCK = Lock()


def _engine_key(db_url: str) -> tuple[object, ...]:
    if not db_url.startswith("postgresql"):
        return (db_url,)
    return (
        db_url,
        settings.DB_CONNECTION_MODE,
        settings.DB_POOL_SIZE,
        settings.DB_MAX_OVERFLOW,
        settings.DB_POOL_TIMEOUT_SECONDS,
        settings.DB_POOL_RECYCLE_SECONDS,
        settings.DB_CONNECT_TIMEOUT_SECONDS,
        settings.DB_SSL_MODE,
        settings.DB_STATEMENT_TIMEOUT_MS,
        settings.DB_LOCK_TIMEOUT_MS,
        settings.DB_IDLE_IN_TRANSACTION_TIMEOUT_MS,
    )


def _create_configured_engine(db_url: str) -> Engine:
    kwargs: dict[str, Any] = {"pool_pre_ping": True}
    if db_url.startswith("postgresql"):
        connect_args: dict[str, Any] = {
            "connect_timeout": settings.DB_CONNECT_TIMEOUT_SECONDS,
            "sslmode": settings.DB_SSL_MODE,
            "options": " ".join(
                (
                    f"-c statement_timeout={settings.DB_STATEMENT_TIMEOUT_MS}",
                    f"-c lock_timeout={settings.DB_LOCK_TIMEOUT_MS}",
                    "-c idle_in_transaction_session_timeout="
                    f"{settings.DB_IDLE_IN_TRANSACTION_TIMEOUT_MS}",
                )
            ),
        }
        if settings.DB_CONNECTION_MODE == "transaction":
            kwargs["poolclass"] = NullPool
            connect_args["prepare_threshold"] = None
        else:
            kwargs.update(
                pool_size=settings.DB_POOL_SIZE,
                max_overflow=settings.DB_MAX_OVERFLOW,
                pool_timeout=settings.DB_POOL_TIMEOUT_SECONDS,
                pool_recycle=settings.DB_POOL_RECYCLE_SECONDS,
            )
        kwargs["connect_args"] = connect_args
    return create_engine(db_url, **kwargs)


def get_engine(url: str | None = None) -> Engine:
    """Create a SQLAlchemy engine.

    Args:
        url: explicit connection URL; falls back to settings.DATABASE_URL.

    Raises:
        RuntimeError: if no URL is configured.
    """
    db_url = url or settings.DATABASE_URL
    if not db_url:
        raise RuntimeError(
            "DATABASE_URL is not configured. "
            "Set DATABASE_URL in .env or pass url= explicitly. "
            "Example: postgresql+psycopg://novelai:novelai@localhost:5432/novelai"
        )
    key = _engine_key(db_url)
    with _ENGINE_CACHE_LOCK:
        engine = _ENGINE_CACHE.get(key)
        if engine is None:
            engine = _create_configured_engine(db_url)
            _ENGINE_CACHE[key] = engine
        return engine


def dispose_engines() -> None:
    """Dispose every cached engine and clear the process-local cache."""
    with _ENGINE_CACHE_LOCK:
        engines = list(_ENGINE_CACHE.values())
        _ENGINE_CACHE.clear()
    for engine in engines:
        engine.dispose()


def get_sessionmaker(url: str | None = None) -> sessionmaker[Session]:
    """Return a sessionmaker bound to the engine for the given URL."""
    engine = get_engine(url)
    return sessionmaker(bind=engine, autocommit=False, autoflush=False)


@contextmanager
def session_scope(url: str | None = None) -> Generator[Session]:
    """Context manager that provides a transactional database session.

    Commits on clean exit, rolls back on exception, always closes.

    Args:
        url: explicit connection URL; falls back to settings.DATABASE_URL.

    Example:
        with session_scope() as session:
            session.add(obj)
    """
    Session_ = get_sessionmaker(url)
    session = Session_()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def check_connectivity(url: str | None = None) -> bool:
    """Return True if the database is reachable, False otherwise.

    Used by health checks and the CLI doctor command.
    """
    try:
        engine = get_engine(url)
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False
