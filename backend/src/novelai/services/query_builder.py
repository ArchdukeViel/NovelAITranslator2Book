"""Fluent query builder for storage operations."""

from __future__ import annotations

import json
import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Literal

from novelai.core.chapter_state import ChapterState

logger = logging.getLogger(__name__)


def _parse_datetime(value: object) -> datetime | None:
    """Parse a stored datetime field into a datetime instance."""
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            return None
    return None


def _as_int(value: object, default: int = 0) -> int:
    """Coerce persisted numeric values to int when possible."""
    return value if isinstance(value, int) else default


@dataclass
class ChapterQueryResult:
    """Result of a chapter query."""

    chapter_id: str
    current_state: ChapterState
    last_updated: datetime
    error_count: int
    retry_count: int
    transitions_count: int

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "chapter_id": self.chapter_id,
            "current_state": self.current_state.value,
            "last_updated": self.last_updated.isoformat(),
            "error_count": self.error_count,
            "retry_count": self.retry_count,
            "transitions_count": self.transitions_count,
        }


class ChapterQueryBuilder:
    """Fluent query builder for filtering and querying chapters."""

    def __init__(self, state_dir: Path):
        """Initialize query builder with state directory."""
        self.state_dir = state_dir
        self._filters: list[Callable[[dict[str, Any]], bool]] = []
        self._sort_key: Callable[[ChapterQueryResult], Any] | None = None
        self._sort_reverse = False
        self._limit_val: int | None = None
        self._offset_val = 0

    def by_state(self, state: ChapterState) -> ChapterQueryBuilder:
        """Filter by chapter state."""
        self._filters.append(
            lambda data: ChapterState(data.get("current_state")) == state
        )
        return self

    def by_states(self, states: list[ChapterState]) -> ChapterQueryBuilder:
        """Filter by multiple states (OR condition)."""
        state_values = {s.value for s in states}
        self._filters.append(
            lambda data: data.get("current_state") in state_values
        )
        return self

    def has_errors(self) -> ChapterQueryBuilder:
        """Filter chapters that have errors."""
        self._filters.append(lambda data: _as_int(data.get("error_count")) > 0)
        return self

    def no_errors(self) -> ChapterQueryBuilder:
        """Filter chapters with no errors."""
        self._filters.append(lambda data: _as_int(data.get("error_count")) == 0)
        return self

    def error_count_gte(self, count: int) -> ChapterQueryBuilder:
        """Filter by error count greater than or equal."""
        self._filters.append(lambda data: _as_int(data.get("error_count")) >= count)
        return self

    def error_count_lte(self, count: int) -> ChapterQueryBuilder:
        """Filter by error count less than or equal."""
        self._filters.append(lambda data: _as_int(data.get("error_count")) <= count)
        return self

    def retry_count_gte(self, count: int) -> ChapterQueryBuilder:
        """Filter by retry count greater than or equal."""
        self._filters.append(lambda data: _as_int(data.get("retry_count")) >= count)
        return self

    def updated_after(self, timestamp: datetime) -> ChapterQueryBuilder:
        """Filter chapters updated after timestamp."""
        def filter_fn(data: dict[str, Any]) -> bool:
            last_updated = _parse_datetime(data.get("last_updated"))
            return last_updated is not None and last_updated >= timestamp
        self._filters.append(filter_fn)
        return self

    def updated_before(self, timestamp: datetime) -> ChapterQueryBuilder:
        """Filter chapters updated before timestamp."""
        def filter_fn(data: dict[str, Any]) -> bool:
            last_updated = _parse_datetime(data.get("last_updated"))
            return last_updated is not None and last_updated <= timestamp
        self._filters.append(filter_fn)
        return self

    def sort_by(
        self,
        key: Literal["state", "updated", "errors", "retries"] = "updated",
        reverse: bool = False,
    ) -> ChapterQueryBuilder:
        """Sort results by specified key."""
        if key == "state":
            self._sort_key = lambda r: r.current_state.value
        elif key == "updated":
            self._sort_key = lambda r: r.last_updated
        elif key == "errors":
            self._sort_key = lambda r: r.error_count
        elif key == "retries":
            self._sort_key = lambda r: r.retry_count

        self._sort_reverse = reverse
        return self

    def limit(self, count: int) -> ChapterQueryBuilder:
        """Limit results to count items."""
        self._limit_val = count
        return self

    def offset(self, count: int) -> ChapterQueryBuilder:
        """Skip first count items."""
        self._offset_val = count
        return self

    def paginate(self, page: int = 1, per_page: int = 10) -> ChapterQueryBuilder:
        """Paginate results (1-indexed pages)."""
        self._limit_val = per_page
        self._offset_val = (page - 1) * per_page
        return self

    def execute(self) -> list[ChapterQueryResult]:
        """Execute query and return results."""
        results: list[ChapterQueryResult] = []

        if not self.state_dir.exists():
            return results

        logger.debug(f"Executing query on {self.state_dir}")

        # Load and filter
        for state_file in self.state_dir.glob("*.json"):
            try:
                data = json.loads(state_file.read_text(encoding="utf-8"))
                if not isinstance(data, dict):
                    continue

                # Apply filters
                if not all(f(data) for f in self._filters):
                    continue

                chapter_id = data.get("chapter_id")
                current_state = data.get("current_state")
                last_updated = _parse_datetime(data.get("last_updated"))
                transitions = data.get("transitions")

                if not isinstance(chapter_id, str):
                    continue
                if not isinstance(current_state, str):
                    continue
                if last_updated is None:
                    continue

                # Build result
                result = ChapterQueryResult(
                    chapter_id=chapter_id,
                    current_state=ChapterState(current_state),
                    last_updated=last_updated,
                    error_count=_as_int(data.get("error_count")),
                    retry_count=_as_int(data.get("retry_count")),
                    transitions_count=len(transitions) if isinstance(transitions, list) else 0,
                )
                results.append(result)
            except Exception as e:
                logger.warning(f"Failed to process state file {state_file}: {e}")
                continue

        # Sort
        if self._sort_key:
            results.sort(key=self._sort_key, reverse=self._sort_reverse)

        # Paginate
        if self._offset_val > 0:
            results = results[self._offset_val :]

        if self._limit_val:
            results = results[: self._limit_val]

        logger.debug(f"Query returned {len(results)} results")
        return results

    def count(self) -> int:
        """Get count of results without pagination."""
        # Temporarily clear pagination
        old_limit = self._limit_val
        old_offset = self._offset_val
        self._limit_val = None
        self._offset_val = 0

        count = len(self.execute())

        # Restore pagination
        self._limit_val = old_limit
        self._offset_val = old_offset

        return count

    def exists(self) -> bool:
        """Check if any results match query."""
        return len(self.limit(1).execute()) > 0
