from __future__ import annotations

from enum import StrEnum


class PlatformReviewStatus(StrEnum):
    DRAFT = "draft"
    NEEDS_REVIEW = "needs_review"
    PUBLISHED = "published"
    HIDDEN = "hidden"


class NovelRequestStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    RELEASED = "released"


class JobStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    PAUSED = "paused"
    PAUSED_UNTIL_COOLDOWN = "paused_until_cooldown"
    PAUSED_UNTIL_QUOTA_RESET = "paused_until_quota_reset"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class CrawlJobKind(StrEnum):
    METADATA = "metadata"
    CHAPTERS = "chapters"
    RECRAWL_CHAPTER = "recrawl_chapter"


class TranslationJobKind(StrEnum):
    TRANSLATE = "translate"
    RETRANSLATE = "retranslate"
    BATCH_RETRANSLATE = "batch_retranslate"


class ChapterVersionKind(StrEnum):
    MACHINE_TRANSLATION = "machine_translation"
    MANUAL_EDIT = "manual_edit"
    ROLLBACK = "rollback"
    GLOSSARY_APPLY = "glossary_apply"
