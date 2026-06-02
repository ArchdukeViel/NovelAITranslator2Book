from __future__ import annotations

import contextlib
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from novelai.core.chapter_state import ChapterState, ChapterStateTransition

DEFAULT_GLOSSARY_EXTRACTION_PROMPT = (
    "Extract up to {max_terms} important source-language glossary terms from the following novel excerpt. "
    "Return only a JSON array of unique terms (strings). Do not translate terms. "
    "Ignore common words, chapter headings, numbers-only tokens, and punctuation-only tokens.\n\n"
    "Source Language: {source_language}\n"
    "Excerpt:\n{text}"
)

GLOSSARY_EXTRACTION_JSON_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "terms": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "source": {"type": "string"},
                },
                "required": ["source"],
            },
        }
    },
    "required": ["terms"],
}


def _utc_now_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _make_state_data(
    state: ChapterState,
    *,
    error: str | None = None,
    previous: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a state_data dict suitable for StorageService.save_chapter_state."""
    now = datetime.now(UTC)
    prev_state = None
    transitions: list[ChapterStateTransition] = []
    error_count = 0

    if previous:
        prev_state_raw = previous.get("current_state")
        if isinstance(prev_state_raw, ChapterState):
            prev_state = prev_state_raw
        elif isinstance(prev_state_raw, str):
            with contextlib.suppress(ValueError):
                prev_state = ChapterState(prev_state_raw)
        transitions = previous.get("transitions", [])
        error_count = previous.get("error_count", 0)

    transitions.append(ChapterStateTransition(
        from_state=prev_state,
        to_state=state,
        timestamp=now,
        error=error,
    ))

    if error:
        error_count += 1

    return {
        "current_state": state,
        "transitions": transitions,
        "last_updated": now,
        "error_count": error_count,
        "retry_count": previous.get("retry_count", 0) if previous else 0,
    }


@dataclass(frozen=True)
class PreflightIssue:
    code: str
    reason: str
