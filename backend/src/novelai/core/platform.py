from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import StrEnum
from typing import Any


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


@dataclass(frozen=True)
class CrawlJob:
    id: str
    novel_id: str
    kind: CrawlJobKind
    source_key: str
    status: JobStatus = JobStatus.PENDING
    chapters: str | None = None
    source_url: str | None = None
    created_at: str | None = None
    started_at: str | None = None
    finished_at: str | None = None
    retry_count: int = 0
    error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return _serialize_dataclass(self)


@dataclass(frozen=True)
class TranslationJob:
    id: str
    novel_id: str
    kind: TranslationJobKind
    status: JobStatus = JobStatus.PENDING
    source_key: str | None = None
    chapters: str = "all"
    provider: str | None = None
    model: str | None = None
    created_at: str | None = None
    started_at: str | None = None
    finished_at: str | None = None
    retry_count: int = 0
    error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return _serialize_dataclass(self)


@dataclass(frozen=True)
class ChapterVersion:
    id: str
    kind: ChapterVersionKind
    text: str
    created_at: str
    provider: str | None = None
    model: str | None = None
    editor: str | None = None
    note: str | None = None
    base_version_id: str | None = None
    confidence_score: float | None = None
    polish_needed: bool | None = None
    confidence_details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return _serialize_dataclass(self)


@dataclass(frozen=True)
class EditHistoryEntry:
    id: str
    action: ChapterVersionKind
    version_id: str
    created_at: str
    editor: str | None = None
    note: str | None = None
    previous_version_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return _serialize_dataclass(self)


def _serialize_dataclass(value: Any) -> dict[str, Any]:
    payload = asdict(value)
    return _serialize_enums(payload)


def _serialize_enums(value: Any) -> Any:
    if isinstance(value, StrEnum):
        return value.value
    if isinstance(value, dict):
        return {key: _serialize_enums(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_serialize_enums(item) for item in value]
    return value
