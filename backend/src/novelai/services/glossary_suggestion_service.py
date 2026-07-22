"""File-backed glossary suggestion storage and review workflow.

Stores suggestions in a per-novel JSON file (glossary_suggestions.json).
Supports add, list, accept, reject and bulk operations.
"""

from __future__ import annotations

import contextlib
import json
import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field

from novelai.utils import atomic_write

logger = logging.getLogger(__name__)

SuggestionStatus = Literal["pending", "accepted", "rejected"]
SuggestionSource = Literal["frequency", "llm"]


class GlossarySuggestion(BaseModel):
    """A single glossary term suggestion with review state."""

    id: str
    source_term: str
    occurrence_count: int
    chapter_count: int
    context_snippets: list[str] = Field(default_factory=list)
    source: SuggestionSource = "frequency"
    status: SuggestionStatus = "pending"
    term_type: str = "character"
    confidence: float = 0.5
    approved_translation: str | None = None
    rejection_reason: str | None = None
    created_at: str = ""
    updated_at: str | None = None


def _storage_dir(base_dir: Path, novel_id: str) -> Path:
    novel_dir = base_dir / novel_id if base_dir else Path(novel_id)
    novel_dir.mkdir(parents=True, exist_ok=True)
    return novel_dir


def _utc_now_iso() -> str:
    return datetime.now(UTC).isoformat()


class GlossarySuggestionService:
    """File-backed suggestion store with review workflow."""

    FILENAME = "glossary_suggestions.json"

    def __init__(self, base_dir: Path | None = None) -> None:
        self.base_dir = base_dir  # ponytail: direct file I/O (path.read_text/atomic_write), migrate to StorageService

    # --- helpers ---

    def _path(self, novel_id: str) -> Path:
        if self.base_dir is None:
            return Path(novel_id) / self.FILENAME
        return self.base_dir / novel_id / self.FILENAME

    def _load(self, novel_id: str) -> dict[str, Any]:
        path = self._path(novel_id)
        if not path.exists():
            return {"schema_version": 1, "suggestions": []}
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(data, dict) and isinstance(data.get("suggestions"), list):
                return data
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("Failed to load suggestions for %s: %s", novel_id, exc)
        return {"schema_version": 1, "suggestions": []}

    def _save(self, novel_id: str, data: dict[str, Any]) -> None:
        path = self._path(novel_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        atomic_write(path, json.dumps(data, ensure_ascii=False, indent=2))

    def _next_id(self, suggestions: list[dict[str, Any]]) -> str:
        existing = {
            int(s.get("id", 0))
            for s in suggestions
            if isinstance(s.get("id"), (int, str)) and str(s.get("id", "")).isdigit()
        }
        existing |= {int(s.get("id", 0)) for s in suggestions if isinstance(s.get("id"), int)}
        next_num = 1
        while next_num in existing:
            next_num += 1
        return str(next_num)

    # --- public API ---

    def add_suggestions(self, novel_id: str, suggestions: list[GlossarySuggestion]) -> list[GlossarySuggestion]:
        """Add suggestions with merge/dedup. Same source_term merges into existing pending item."""
        data = self._load(novel_id)
        existing: list[dict[str, Any]] = data["suggestions"]

        # Build lookup: (source_term, status) -> index for pending items
        pending_map: dict[str, int] = {}
        for i, s in enumerate(existing):
            if s.get("status") == "pending":
                pending_map[s.get("source_term", "")] = i

        now = _utc_now_iso()
        added: list[GlossarySuggestion] = []

        for sug in suggestions:
            # Skip if rejected term
            if any(s.get("source_term") == sug.source_term and s.get("status") == "rejected" for s in existing):
                continue

            idx = pending_map.get(sug.source_term)
            if idx is not None:
                # Merge: update occurrence count
                existing[idx]["occurrence_count"] = max(existing[idx].get("occurrence_count", 0), sug.occurrence_count)
                existing[idx]["chapter_count"] = max(existing[idx].get("chapter_count", 0), sug.chapter_count)
                existing[idx]["updated_at"] = now
            else:
                # New entry
                sug.id = self._next_id(existing)
                sug.created_at = now
                sug.status = "pending"
                existing.append(sug.model_dump(exclude_none=True))
                pending_map[sug.source_term] = len(existing) - 1
                added.append(sug)

        data["suggestions"] = existing
        self._save(novel_id, data)
        return added

    def list_suggestions(
        self,
        novel_id: str,
        *,
        status: SuggestionStatus | None = None,
        source: SuggestionSource | None = None,
    ) -> list[GlossarySuggestion]:
        """List suggestions with optional filtering."""
        data = self._load(novel_id)
        results = []
        for s in data["suggestions"]:
            if status is not None and s.get("status") != status:
                continue
            if source is not None and s.get("source") != source:
                continue
            try:
                results.append(GlossarySuggestion(**s))
            except Exception as exc:
                logger.warning("Skipping malformed suggestion %s: %s", s.get("id"), exc)
        return results

    def get_suggestion(self, novel_id: str, suggestion_id: str) -> GlossarySuggestion | None:
        data = self._load(novel_id)
        for s in data["suggestions"]:
            if str(s.get("id")) == suggestion_id:
                try:
                    return GlossarySuggestion(**s)
                except Exception as exc:
                    logger.warning("Malformed suggestion %s: %s", suggestion_id, exc)
                    return None
        return None

    def accept(
        self, novel_id: str, suggestion_id: str, *, modified_translation: str | None = None
    ) -> GlossarySuggestion | None:
        """Mark suggestion as accepted. Optionally override translation."""
        data = self._load(novel_id)
        for s in data["suggestions"]:
            if str(s.get("id")) == suggestion_id and s.get("status") == "pending":
                s["status"] = "accepted"
                if modified_translation is not None:
                    s["approved_translation"] = modified_translation
                s["updated_at"] = _utc_now_iso()
                self._save(novel_id, data)
                return GlossarySuggestion(**s)
        return None

    def reject(self, novel_id: str, suggestion_id: str, *, reason: str | None = None) -> GlossarySuggestion | None:
        """Mark suggestion as rejected."""
        data = self._load(novel_id)
        for s in data["suggestions"]:
            if str(s.get("id")) == suggestion_id and s.get("status") == "pending":
                s["status"] = "rejected"
                if reason is not None:
                    s["rejection_reason"] = reason
                s["updated_at"] = _utc_now_iso()
                self._save(novel_id, data)
                return GlossarySuggestion(**s)
        return None

    def accept_all(self, novel_id: str) -> list[GlossarySuggestion]:
        """Accept all pending suggestions."""
        data = self._load(novel_id)
        now = _utc_now_iso()
        accepted: list[GlossarySuggestion] = []
        for s in data["suggestions"]:
            if s.get("status") == "pending":
                s["status"] = "accepted"
                s["updated_at"] = now
                with contextlib.suppress(Exception):
                    accepted.append(GlossarySuggestion(**s))
        self._save(novel_id, data)
        return accepted

    def reject_all(self, novel_id: str) -> list[GlossarySuggestion]:
        """Reject all pending suggestions."""
        data = self._load(novel_id)
        now = _utc_now_iso()
        rejected: list[GlossarySuggestion] = []
        for s in data["suggestions"]:
            if s.get("status") == "pending":
                s["status"] = "rejected"
                s["updated_at"] = now
                with contextlib.suppress(Exception):
                    rejected.append(GlossarySuggestion(**s))
        self._save(novel_id, data)
        return rejected

    def count_pending(self, novel_id: str) -> int:
        data = self._load(novel_id)
        return sum(1 for s in data["suggestions"] if s.get("status") == "pending")
