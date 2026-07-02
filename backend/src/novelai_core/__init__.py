"""novelai-core — shared package for reader & admin services.

Both services consume the same codebase; this facade documents and stabilises
the shared surface. Install via `pip install -e backend/src/novelai_core`.
"""

from __future__ import annotations

from novelai.config.settings import settings
from novelai.db.base import Base
from novelai.db.engine import get_engine, get_sessionmaker, session_scope
from novelai.storage.service import StorageService

__all__ = [
    "Base",
    "StorageService",
    "get_engine",
    "get_sessionmaker",
    "session_scope",
    "settings",
]
