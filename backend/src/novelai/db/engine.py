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
from time import perf_counter_ns
from typing import Any

from sqlalchemy import Engine, create_engine, event, text
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import NullPool

from novelai.config.settings import settings
from novelai.services.timing_contract import record_internal_span, record_internal_unavailable_span

_ENGINE_CACHE: dict[tuple[object, ...], Engine] = {}
_ENGINE_CACHE_LOCK = Lock()


def _install_timing_listeners(engine: Engine) -> None:
    """Attach fixed-label SQL timing without retaining statement contents."""

    @event.listens_for(engine, "before_cursor_execute")
    def _before_cursor_execute(
        connection: Any, cursor: Any, statement: Any, parameters: Any, context: Any, executemany: bool
    ) -> None:
        del connection, cursor, statement, parameters, executemany
        context._novelai_sql_started_ns = perf_counter_ns()

    @event.listens_for(engine, "after_cursor_execute")
    def _after_cursor_execute(
        connection: Any, cursor: Any, statement: Any, parameters: Any, context: Any, executemany: bool
    ) -> None:
        del connection, cursor, statement, parameters, executemany
        started_ns = getattr(context, "_novelai_sql_started_ns", None)
        if isinstance(started_ns, int):
            record_internal_span(
                "sql_execution",
                source="database",
                duration_ms=(perf_counter_ns() - started_ns) / 1_000_000,
            )
            context._novelai_sql_started_ns = None

    @event.listens_for(engine, "handle_error")
    def _handle_sql_error(exception_context: Any) -> None:
        context = getattr(exception_context, "execution_context", None)
        if context is None:
            return
        started_ns = getattr(context, "_novelai_sql_started_ns", None)
        if isinstance(started_ns, int):
            record_internal_span(
                "sql_execution",
                source="database",
                duration_ms=(perf_counter_ns() - started_ns) / 1_000_000,
            )
            context._novelai_sql_started_ns = None

    @event.listens_for(engine, "engine_connect")
    def _engine_connect(connection: Any) -> None:
        del connection
        record_internal_unavailable_span(
            "db_pool_checkout",
            source="database",
            reason="pooler_granularity_unavailable",
        )


@event.listens_for(Session, "before_commit")
def _session_commit_started(session: Session) -> None:
    session.info["_novelai_commit_started_ns"] = perf_counter_ns()


@event.listens_for(Session, "after_commit")
def _session_commit_finished(session: Session) -> None:
    started_ns = session.info.pop("_novelai_commit_started_ns", None)
    if isinstance(started_ns, int):
        record_internal_span(
            "database_commit",
            source="database",
            duration_ms=(perf_counter_ns() - started_ns) / 1_000_000,
        )


@event.listens_for(Session, "after_soft_rollback")
def _session_rollback_finished(session: Session, previous_transaction: Any) -> None:
    del previous_transaction
    record_internal_unavailable_span(
        "rollback",
        source="database",
        reason="span_not_instrumented",
    )


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
                    f"-c idle_in_transaction_session_timeout={settings.DB_IDLE_IN_TRANSACTION_TIMEOUT_MS}",
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
    engine = create_engine(db_url, **kwargs)
    _install_timing_listeners(engine)
    return engine


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
def read_session_scope(url: str | None = None) -> Generator[Session]:
    """Context manager for read-only database sessions.

    Prefers settings.DATABASE_REPLICA_URL, falls back to explicit url or settings.DATABASE_URL.
    Always rolls back on exit to prevent accidental writes.
    """
    target_url = url or settings.DATABASE_REPLICA_URL or settings.DATABASE_URL
    Session_ = get_sessionmaker(target_url)
    session = Session_()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


@contextmanager
def session_scope(url: str | None = None, *, current_user_id: str | None = None) -> Generator[Session]:
    """Context manager that provides a transactional database session.

    Commits on clean exit, rolls back on exception, always closes.
    If current_user_id is provided, sets transaction-scoped RLS context (SET LOCAL app.current_user_id).

    Args:
        url: explicit connection URL; falls back to settings.DATABASE_URL.
        current_user_id: optional UUID/string user identifier for RLS policies.

    Example:
        with session_scope(current_user_id=user_id) as session:
            session.add(obj)
    """
    Session_ = get_sessionmaker(url)
    session = Session_()
    try:
        if current_user_id is not None:
            # Set local variable for RLS; fail-safe across Postgres dialects
            bind = session.get_bind()
            if bind and bind.dialect.name == "postgresql":
                session.execute(
                    text("SET LOCAL app.current_user_id = :uid"),
                    {"uid": str(current_user_id)},
                )
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        for storage in session.info.get("_novelai_r2_bound_storages", ()):
            if getattr(storage, "_test_db_session", None) is session:
                delattr(storage, "_test_db_session")
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
