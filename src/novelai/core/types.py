from __future__ import annotations

from enum import Enum
from typing import TypedDict, Any, Optional


class TranslationStatus(str, Enum):
    QUEUED = "queued"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


class ChapterMeta(TypedDict):
    novel_id: str
    chapter_id: str
    title: str
    order: int
    source_url: str


class TranslationResult(TypedDict):
    text: str
    tokens_used: Optional[int]
    provider: str
    model: str
    metadata: dict[str, Any]
