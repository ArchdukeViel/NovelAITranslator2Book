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

from sqlalchemy import Engine, create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from novelai.config.settings import settings


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
    return create_engine(db_url, pool_pre_ping=True)


def get_sessionmaker(url: str | None = None) -> sessionmaker[Session]:
    """Return a sessionmaker bound to the engine for the given URL."""
    engine = get_engine(url)
    return sessionmaker(bind=engine, autocommit=False, autoflush=False)


@contextmanager
def session_scope(url: str | None = None) -> Generator[Session, None, None]:
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
