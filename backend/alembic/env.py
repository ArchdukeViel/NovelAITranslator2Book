"""Alembic migration environment.

Wired to novelai.db.base.Base.metadata for autogenerate support.
DATABASE_URL is read from settings (which reads from .env / environment).
"""

from __future__ import annotations

import os
import sys
from importlib import import_module
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from sqlalchemy import engine_from_config, pool

# Ensure backend/src is on sys.path so novelai imports resolve when running
# alembic directly (e.g. `alembic upgrade head` from the repo root).
_BACKEND_SRC = Path(__file__).resolve().parents[2] / "src"
if str(_BACKEND_SRC) not in sys.path:
    sys.path.insert(0, str(_BACKEND_SRC))

# Import Base and ALL models so their tables are registered in metadata
# before autogenerate inspects it.  Add new models here as they are created.
from novelai.db.base import Base  # noqa: E402

for _model_module in (
    "novelai.db.models.chapter",
    "novelai.db.models.genre",
    "novelai.db.models.glossary",
    "novelai.db.models.jobs",
    "novelai.db.models.novel",
    "novelai.db.models.system",
    "novelai.db.models.tag",
    "novelai.db.models.users",
):
    import_module(_model_module)

# Alembic Config object for .ini values.
config = context.config

# Set up logging from the ini file.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Target metadata for autogenerate.
target_metadata = Base.metadata


def _get_url() -> str:
    """Return the DATABASE_URL from settings, with env override support."""
    # Allow DATABASE_URL to be overridden via environment (e.g. in CI or Docker).
    url = os.environ.get("DATABASE_URL")
    if url:
        return url
    from novelai.config.settings import settings
    if settings.DATABASE_URL:
        return settings.DATABASE_URL
    raise RuntimeError(
        "DATABASE_URL is not configured. "
        "Set DATABASE_URL in .env or as an environment variable."
    )


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode (no live DB connection required)."""
    url = _get_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode (connects to the database)."""
    ini_section = config.get_section(config.config_ini_section, {})
    ini_section["sqlalchemy.url"] = _get_url()
    connectable = engine_from_config(
        ini_section,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
