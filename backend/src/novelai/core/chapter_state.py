"""Chapter state machine for tracking processing progress."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum


def _utc_now() -> datetime:
    """Return a timezone-aware UTC timestamp."""
    return datetime.now(UTC)


class ChapterState(Enum):
    """Enum representing the processing state of a chapter."""

    PENDING = "pending"
    SCRAPED = "scraped"  # Chapter content fetched from source
    FETCHED = "fetched"
    PARSED = "parsed"  # Raw text parsed and normalized
    QUALITY_FAILED = "quality_failed"
    SEGMENTED = "segmented"  # Text split into translatable chunks
    TRANSLATING = "translating"
    TRANSLATED_PARTIAL = "translated_partial"
    TRANSLATED = "translated"  # Chunks translated
    QA_FAILED = "qa_failed"
    NEEDS_RETRY = "needs_retry"
    NEEDS_REVIEW = "needs_review"
    EXPORTED = "exported"  # Final content exported to file
    FAILED = "failed"


@dataclass
class ChapterStateTransition:
    """Track state changes with timestamps."""

    from_state: ChapterState | None = None
    to_state: ChapterState = ChapterState.SCRAPED
    timestamp: datetime = field(default_factory=_utc_now)
    error: str | None = None  # If transition failed, store error message


def _default_transitions() -> list[ChapterStateTransition]:
    """Create an empty typed transition list for dataclass defaults."""
    return []


@dataclass
class ChapterMetadata:
    """Metadata for a chapter including state tracking."""

    chapter_id: str
    current_state: ChapterState = ChapterState.SCRAPED
    transitions: list[ChapterStateTransition] = field(default_factory=_default_transitions)
    last_updated: datetime = field(default_factory=_utc_now)
    error_count: int = 0
    retry_count: int = 0

    def transition_to(
        self, new_state: ChapterState, error: str | None = None
    ) -> None:
        """Record a state transition."""
        if error:
            self.error_count += 1

        transition = ChapterStateTransition(
            from_state=self.current_state,
            to_state=new_state,
            error=error,
        )
        self.transitions.append(transition)
        self.current_state = new_state
        self.last_updated = _utc_now()

    def can_proceed_to(self, target_state: ChapterState) -> bool:
        """Check if chapter can proceed to target state based on current state."""
        state_order = [
            ChapterState.PENDING,
            ChapterState.SCRAPED,
            ChapterState.FETCHED,
            ChapterState.PARSED,
            ChapterState.SEGMENTED,
            ChapterState.TRANSLATING,
            ChapterState.TRANSLATED_PARTIAL,
            ChapterState.TRANSLATED,
            ChapterState.NEEDS_REVIEW,
            ChapterState.EXPORTED,
        ]

        current_order = state_order.index(self.current_state)
        target_order = state_order.index(target_state)

        # Allow proceeding to next state or same state (idempotent)
        return target_order >= current_order

    def get_state_progress(self) -> dict[str, int]:
        """Get count of transitions to each state."""
        progress = {state.value: 0 for state in ChapterState}
        for transition in self.transitions:
            if transition.to_state:
                progress[transition.to_state.value] += 1
        return progress
