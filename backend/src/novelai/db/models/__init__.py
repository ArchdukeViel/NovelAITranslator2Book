"""ORM models for the Novel AI database boundary.

Importing this package registers every model with ``Base.metadata`` so that
Alembic autogenerate and ``create_all`` see the full schema. Add new models
to the imports and ``__all__`` below.
"""

from __future__ import annotations

from novelai.db.models.chapter import Chapter
from novelai.db.models.genre import Genre, novel_genres
from novelai.db.models.jobs import CrawlJob, ProviderRequest, TranslationJob
from novelai.db.models.novel import Novel
from novelai.db.models.system import AuditLog, SystemSetting
from novelai.db.models.tag import Tag, novel_tags
from novelai.db.models.users import (
    EmailVerificationToken,
    LibraryItem,
    NovelRequest,
    PasswordResetToken,
    ReadingHistory,
    ReadingProgress,
    Review,
    User,
)

__all__ = [
    "AuditLog",
    "Chapter",
    "CrawlJob",
    "EmailVerificationToken",
    "Genre",
    "LibraryItem",
    "Novel",
    "NovelRequest",
    "PasswordResetToken",
    "ProviderRequest",
    "ReadingHistory",
    "ReadingProgress",
    "Review",
    "SystemSetting",
    "Tag",
    "TranslationJob",
    "User",
    "novel_genres",
    "novel_tags",
]
