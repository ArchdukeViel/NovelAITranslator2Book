"""SQLAlchemy declarative base with naming conventions.

All ORM models import Base from here. The naming convention ensures
generated constraint names are consistent and migration-safe.
"""

from __future__ import annotations

from sqlalchemy import MetaData
from sqlalchemy.orm import DeclarativeBase

# Explicit naming convention so Alembic can identify and rename constraints.
_NAMING_CONVENTION: dict[str, str] = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    """Shared declarative base for all Novel AI ORM models."""

    metadata = MetaData(naming_convention=_NAMING_CONVENTION)
