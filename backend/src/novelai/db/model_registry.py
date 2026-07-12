"""Database model registry.

Provides an explicit initialization function for registering all ORM models
with SQLAlchemy's ``Base.metadata``. This replaces scattered side-effect imports
of individual model modules throughout the test suite.

Usage:
    from novelai.db.model_registry import register_database_models
    register_database_models()
"""

from __future__ import annotations

from sqlalchemy.orm import configure_mappers

from novelai.db.models import REGISTERED_MODELS


def register_database_models() -> None:
    """Configure all ORM model relationships and verify registration.

    Idempotent: safe to call multiple times. The first call configures
    SQLAlchemy relationship mappers; subsequent calls are no-ops.
    """
    if not REGISTERED_MODELS:
        raise RuntimeError("No database models were registered")
    configure_mappers()
