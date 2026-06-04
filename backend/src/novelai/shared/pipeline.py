from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import StrEnum
from typing import Any, Protocol


class ChapterTranslationStatus(StrEnum):
    PENDING = "pending"
    FETCHED = "fetched"
    PARSED = "parsed"
    QUALITY_FAILED = "quality_failed"
    SEGMENTED = "segmented"
    TRANSLATING = "translating"
    TRANSLATED_PARTIAL = "translated_partial"
    TRANSLATED = "translated"
    QA_FAILED = "qa_failed"
    NEEDS_RETRY = "needs_retry"
    NEEDS_REVIEW = "needs_review"
    EXPORTED = "exported"
    FAILED = "failed"


class ChunkTranslationStatus(StrEnum):
    PENDING = "pending"
    TRANSLATING = "translating"
    TRANSLATED = "translated"
    QA_FAILED = "qa_failed"
    NEEDS_RETRY = "needs_retry"
    NEEDS_REVIEW = "needs_review"
    FAILED = "failed"


class SchedulerModelStatus(StrEnum):
    AVAILABLE = "available"
    COOLING_DOWN = "cooling_down"
    DAILY_EXHAUSTED = "daily_exhausted"
    DISABLED = "disabled"
    FAILED = "failed"


@dataclass
class PipelineContext:
    job_id: str | None = None
    activity_id: str | None = None
    novel_id: str | None = None
    chapter_id: str | None = None
    source_key: str | None = None
    provider_key: str | None = None
    provider_model: str | None = None
    current_stage: str | None = None
    data: dict[str, Any] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    errors: list[dict[str, Any]] = field(default_factory=list)


class PipelineStep(Protocol):
    name: str

    async def run(self, context: PipelineContext) -> PipelineContext:
        ...


@dataclass
class PipelineEvent:
    job_id: str | None = None
    activity_id: str | None = None
    novel_id: str | None = None
    chapter_id: str | None = None
    source_key: str | None = None
    provider_key: str | None = None
    provider_model: str | None = None
    credential_id: str | None = None
    credential_owner_user_id: str | None = None
    requesting_user_id: str | None = None
    chunk_id: str | None = None
    stage_name: str | None = None
    status_before: str | None = None
    status_after: str | None = None
    warning_code: str | None = None
    error_code: str | None = None
    message: str | None = None
    timestamp: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {key: value for key, value in asdict(self).items() if value is not None}


@dataclass
class TranslationChunkState:
    chunk_id: str
    novel_id: str
    chapter_ids: list[str] = field(default_factory=list)
    paragraph_ids: list[str] = field(default_factory=list)
    requesting_user_id: str | None = None
    credential_id: str | None = None
    credential_owner_user_id: str | None = None
    credential_scope: str | None = None
    contribution_mode: str | None = None
    provider_key: str | None = None
    provider_model: str | None = None
    attempt_number: int = 0
    status: str = ChunkTranslationStatus.PENDING.value
    error_code: str | None = None
    qa_score: float | None = None
    created_at: str | None = None
    updated_at: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class SchedulerModelState:
    provider_key: str
    provider_model: str
    priority_order: int = 0
    rpm_limit: int | None = None
    rpd_limit: int | None = None
    requests_this_minute: int = 0
    requests_today: int = 0
    window_started_at: str | None = None
    cooldown_until: str | None = None
    exhausted_until: str | None = None
    last_error_code: str | None = None
    last_error_message: str | None = None
    status: str = SchedulerModelStatus.AVAILABLE.value

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
