from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class ApiErrorEnvelope(BaseModel):
    code: str
    message: str
    explanation: str
    details: Any | None = None
    trace_id: str | None = None


class ModelStatePayload(BaseModel):
    provider_key: str
    provider_model: str
    status: str
    cooldown_until: str | None = None
    exhausted_until: str | None = None


class JobProgressPayload(BaseModel):
    status: str
    current_stage: str | None = None
    current_label: str | None = None
    completed: int | None = None
    total: int | None = None
    paused_reason: str | None = None
    resume_after: str | None = None
    errors: list[Any] = Field(default_factory=list)
    warnings: list[Any] = Field(default_factory=list)
    model_states: list[ModelStatePayload | dict[str, Any]] = Field(default_factory=list)


class ActivityRecordResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: str
    activity_id: str
    job_id: str
    type: Literal["crawl", "translation"]
    kind: str
    novel_id: str
    source_key: str | None = None
    source_url: str | None = None
    chapters: str | None = None
    provider: str | None = None
    model: str | None = None
    provider_key: str | None = None
    provider_model: str | None = None
    status: str
    created_at: str | None = None
    started_at: str | None = None
    finished_at: str | None = None
    retry_count: int = 0
    error: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    current_stage: str | None = None
    current_label: str | None = None
    completed: int | None = None
    total: int | None = None
    paused_reason: str | None = None
    resume_after: str | None = None
    errors: list[Any] = Field(default_factory=list)
    warnings: list[Any] = Field(default_factory=list)
    model_states: list[ModelStatePayload | dict[str, Any]] = Field(default_factory=list)


class ActivityListResponse(BaseModel):
    activity: list[ActivityRecordResponse]
    jobs: list[ActivityRecordResponse]
