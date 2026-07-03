"""Segment-level checkpoint manager for translation resume.

Stores per-chapter translation progress as JSON files in the novel's
checkpoint directory.  Used by TranslationService to resume interrupted
jobs at the last completed segment or stage.

REQ-2, REQ-5.2
"""

from __future__ import annotations

import json
import logging
import os
import tempfile
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from novelai.core.chapter_state import TranslationState

logger = logging.getLogger(__name__)

CHECKPOINT_MAX_AGE_DAYS = int(os.environ.get("CHECKPOINT_MAX_AGE_DAYS", "7"))


class Checkpoint:
    """Serializable checkpoint recording translation progress for one chapter."""

    def __init__(
        self,
        chapter_id: str,
        state: TranslationState = TranslationState.PENDING,
        completed_stages: list[str] | None = None,
        current_stage: str | None = None,
        segments_completed: int = 0,
        segments_total: int = 0,
        last_updated: str = "",
        error: str | None = None,
    ) -> None:
        self.chapter_id = chapter_id
        self.state = state
        self.completed_stages = completed_stages or []
        self.current_stage = current_stage
        self.segments_completed = segments_completed
        self.segments_total = segments_total
        self.last_updated = last_updated
        self.error = error

    def to_dict(self) -> dict[str, Any]:
        return {
            "chapter_id": self.chapter_id,
            "state": self.state.value,
            "completed_stages": list(self.completed_stages),
            "current_stage": self.current_stage,
            "segments_completed": self.segments_completed,
            "segments_total": self.segments_total,
            "last_updated": self.last_updated,
            "error": self.error,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Checkpoint:
        return cls(
            chapter_id=str(data["chapter_id"]),
            state=TranslationState(str(data["state"])),
            completed_stages=list(data.get("completed_stages", [])),
            current_stage=data.get("current_stage"),
            segments_completed=int(data.get("segments_completed", 0)),
            segments_total=int(data.get("segments_total", 0)),
            last_updated=str(data.get("last_updated", "")),
            error=data.get("error"),
        )


class CheckpointManager:
    """Manages segment-level checkpoint files on disk.

    Checkpoints live under ``storage/novel_library/{slug}/checkpoints/``,
    one JSON file per chapter.  Writes are atomic (write-to-temp then
    rename).  Stale checkpoints older than ``CHECKPOINT_MAX_AGE_DAYS``
    are silently invalidated.
    """

    def __init__(self, checkpoint_dir: str | Path) -> None:
        self.checkpoint_dir = Path(checkpoint_dir)
        self.checkpoint_dir.mkdir(parents=True, exist_ok=True)

    def _path(self, chapter_id: str) -> Path:
        return self.checkpoint_dir / f"{chapter_id}.json"

    def load(self, chapter_id: str) -> Checkpoint | None:
        """Load checkpoint for *chapter_id*.

        Returns ``None`` if missing, corrupt, or stale.  Corrupt and
        stale files are removed silently (REQ-3.3, REQ-5.2).
        """
        path = self._path(chapter_id)
        if not path.exists():
            return None
        try:
            raw = path.read_text(encoding="utf-8")
            data: dict[str, Any] = json.loads(raw)
            cp = Checkpoint.from_dict(data)

            # Staleness check (REQ-5.2)
            if cp.last_updated:
                last = datetime.fromisoformat(cp.last_updated)
                age = datetime.now(UTC) - last
                if age > timedelta(days=CHECKPOINT_MAX_AGE_DAYS):
                    logger.warning(
                        "Stale checkpoint %s — age %s > %d days",
                        chapter_id, age, CHECKPOINT_MAX_AGE_DAYS,
                    )
                    path.unlink(missing_ok=True)
                    return None
            return cp
        except (json.JSONDecodeError, KeyError, ValueError, OSError) as exc:
            logger.warning("Corrupt checkpoint %s — %s, restarting chapter", chapter_id, exc)
            path.unlink(missing_ok=True)
            return None

    def save(self, checkpoint: Checkpoint) -> None:
        """Write *checkpoint* atomically (REQ-2.4).

        Failures are logged at WARNING level and swallowed so they
        don't block translation (REQ-5.1).
        """
        checkpoint.last_updated = datetime.now(UTC).isoformat()
        path = self._path(checkpoint.chapter_id)
        try:
            fd, tmp = tempfile.mkstemp(
                dir=str(self.checkpoint_dir),
                suffix=".tmp",
                prefix=f"{checkpoint.chapter_id}_",
            )
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(checkpoint.to_dict(), f, ensure_ascii=False, indent=2)
            os.replace(tmp, str(path))
        except OSError as exc:
            logger.warning(
                "Failed to write checkpoint %s — %s (translation continues)",
                checkpoint.chapter_id, exc,
            )

    def delete(self, chapter_id: str) -> None:
        """Remove checkpoint file (called after successful completion)."""
        self._path(chapter_id).unlink(missing_ok=True)
