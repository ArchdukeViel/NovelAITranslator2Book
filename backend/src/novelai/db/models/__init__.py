"""ORM models for the Novel AI database boundary.

Importing this package registers every model with ``Base.metadata`` so that
Alembic autogenerate and ``create_all`` see the full schema. Add new models
to the imports and ``__all__`` below.
"""

from __future__ import annotations

from novelai.db.models.analytics_event import AnalyticsEvent
from novelai.db.models.chapter import Chapter
from novelai.db.models.contributor import ContributorCredential, ContributorUsageLedger
from novelai.db.models.genre import Genre, novel_genres
from novelai.db.models.glossary import (
    NovelGlossaryAlias,
    NovelGlossaryDecisionEvent,
    NovelGlossaryEntry,
    NovelGlossaryQAFinding,
    NovelGlossarySourceProvenance,
    UserGlossaryDisplayOverride,
)
from novelai.db.models.jobs import CrawlJob, ProviderRequest, TranslationJob
from novelai.db.models.notification import Notification, NotificationDelivery, NotificationPreference
from novelai.db.models.novel import Novel
from novelai.db.models.scheduler_runtime_state import SchedulerRuntimeState
from novelai.db.models.system import AuditLog, ProviderCredential, ScheduledJobLease, SystemSetting
from novelai.db.models.tag import Tag, novel_tags
from novelai.db.models.takedown import TakedownRequest
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
    "REGISTERED_MODELS",
    "AnalyticsEvent",
    "AuditLog",
    "Chapter",
    "ContributorCredential",
    "ContributorUsageLedger",
    "CrawlJob",
    "EmailVerificationToken",
    "Genre",
    "LibraryItem",
    "Notification",
    "NotificationDelivery",
    "NotificationPreference",
    "Novel",
    "NovelGlossaryAlias",
    "NovelGlossaryDecisionEvent",
    "NovelGlossaryEntry",
    "NovelGlossaryQAFinding",
    "NovelGlossarySourceProvenance",
    "NovelRequest",
    "PasswordResetToken",
    "ProviderCredential",
    "ProviderRequest",
    "ReadingHistory",
    "ReadingProgress",
    "Review",
    "ScheduledJobLease",
    "SchedulerRuntimeState",
    "SystemSetting",
    "Tag",
    "TakedownRequest",
    "TranslationJob",
    "User",
    "UserGlossaryDisplayOverride",
    "novel_genres",
    "novel_tags",
]

REGISTERED_MODELS = (
    AnalyticsEvent,
    AuditLog,
    Chapter,
    CrawlJob,
    ContributorCredential,
    ContributorUsageLedger,
    EmailVerificationToken,
    Genre,
    LibraryItem,
    Novel,
    Notification,
    NotificationDelivery,
    NotificationPreference,
    NovelGlossaryAlias,
    NovelGlossaryDecisionEvent,
    NovelGlossaryEntry,
    NovelGlossaryQAFinding,
    NovelGlossarySourceProvenance,
    NovelRequest,
    PasswordResetToken,
    ProviderCredential,
    ProviderRequest,
    ReadingHistory,
    ReadingProgress,
    Review,
    SchedulerRuntimeState,
    ScheduledJobLease,
    SystemSetting,
    Tag,
    TranslationJob,
    User,
    UserGlossaryDisplayOverride,
)
