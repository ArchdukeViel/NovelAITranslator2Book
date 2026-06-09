"""Database boundary: engine, session, models, and migrations.

All database access for the Novel AI platform lives behind this boundary.
Consumers (services/*) import from here; routers never touch sessions directly.
"""

from __future__ import annotations

from novelai.db.engine import get_engine, get_sessionmaker, session_scope

__all__ = ["get_engine", "get_sessionmaker", "session_scope"]
