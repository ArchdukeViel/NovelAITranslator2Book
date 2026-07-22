from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

from novelai.core.chapter_state import ChapterState, ChapterStateTransition
from novelai.core.security import validate_storage_identifier
from novelai.storage.common import CheckpointInfo, _utc_now, _utc_now_iso

logger = logging.getLogger(__name__)


def _get_state_dir(self: Any, novel_id: str) -> Path:
    """Get the directory for chapter state files."""
    novel_dir = self._novel_dir(novel_id)
    state_dir = novel_dir / "state"
    self._mkdirs(state_dir)
    return state_dir


def save_chapter_state(self: Any, novel_id: str, chapter_id: str, state_data: dict[str, Any]) -> Path:
    """Save chapter state tracking information (including transitions)."""
    state_dir = self._get_state_dir(novel_id)
    safe_chapter_id = validate_storage_identifier(str(chapter_id), "chapter_id")

    # Serialize ChapterMetadata to JSON-safe format
    transitions = []
    for transition in state_data.get("transitions", []):
        if isinstance(transition, ChapterStateTransition):
            from_state = transition.from_state.value if transition.from_state else None
            to_state = transition.to_state.value if transition.to_state else None
            timestamp = (
                transition.timestamp.isoformat() if isinstance(transition.timestamp, datetime) else transition.timestamp
            )
            error = transition.error
        elif isinstance(transition, dict):
            from_state_raw = transition.get("from_state")
            to_state_raw = transition.get("to_state")
            if isinstance(from_state_raw, ChapterState):
                from_state = from_state_raw.value
            else:
                from_state = from_state_raw if isinstance(from_state_raw, str) else None

            if isinstance(to_state_raw, ChapterState):
                to_state = to_state_raw.value
            else:
                to_state = to_state_raw if isinstance(to_state_raw, str) else None

            timestamp_raw = transition.get("timestamp")
            timestamp = timestamp_raw.isoformat() if isinstance(timestamp_raw, datetime) else timestamp_raw
            error = transition.get("error")
        else:
            continue

        transitions.append(
            {
                "from_state": from_state,
                "to_state": to_state,
                "timestamp": timestamp,
                "error": error,
            }
        )

    payload = {
        "chapter_id": safe_chapter_id,
        "current_state": state_data["current_state"].value
        if isinstance(state_data["current_state"], ChapterState)
        else state_data["current_state"],
        "transitions": transitions,
        "last_updated": state_data["last_updated"].isoformat()
        if isinstance(state_data["last_updated"], datetime)
        else state_data["last_updated"],
        "error_count": state_data.get("error_count", 0),
        "retry_count": state_data.get("retry_count", 0),
    }

    path = state_dir / f"{safe_chapter_id}.json"
    self._write_text(path, json.dumps(payload, ensure_ascii=False, indent=2))
    return path


def load_chapter_state(self: Any, novel_id: str, chapter_id: str) -> dict[str, Any] | None:
    """Load chapter state tracking information."""
    state_dir = self._get_state_dir(novel_id)
    safe_chapter_id = validate_storage_identifier(str(chapter_id), "chapter_id")
    path = state_dir / f"{safe_chapter_id}.json"

    if not self._path_exists(path):
        return None

    try:
        data = json.loads(self._read_text(path))

        # Deserialize to proper types
        transitions = []
        for t in data.get("transitions", []):
            transitions.append(
                ChapterStateTransition(
                    from_state=ChapterState(t["from_state"]) if t["from_state"] else None,
                    to_state=ChapterState(t["to_state"]) if t["to_state"] else ChapterState.SCRAPED,
                    timestamp=datetime.fromisoformat(t["timestamp"])
                    if isinstance(t["timestamp"], str)
                    else t["timestamp"],
                    error=t.get("error"),
                )
            )

        return {
            "chapter_id": data["chapter_id"],
            "current_state": ChapterState(data["current_state"]),
            "transitions": transitions,
            "last_updated": datetime.fromisoformat(data["last_updated"])
            if isinstance(data["last_updated"], str)
            else data["last_updated"],
            "error_count": data.get("error_count", 0),
            "retry_count": data.get("retry_count", 0),
        }
    except (json.JSONDecodeError, OSError, KeyError, ValueError):
        logger.warning("Failed to load chapter state %s/%s.", novel_id, chapter_id)
        return None


def update_chapter_state(
    self: Any,
    novel_id: str,
    chapter_id: str,
    new_state: ChapterState,
    error: str | None = None,
) -> None:
    """Update a chapter's state with a new transition."""
    # Load existing state or create new
    state_data = self.load_chapter_state(novel_id, chapter_id)

    if state_data is None:
        # Create new state
        state_data = {
            "chapter_id": chapter_id,
            "current_state": new_state,
            "transitions": [
                ChapterStateTransition(
                    from_state=None,
                    to_state=new_state,
                    error=error,
                )
            ],
            "last_updated": _utc_now(),
            "error_count": 1 if error else 0,
            "retry_count": 0,
        }
    else:
        # Update existing state
        if error:
            state_data["error_count"] += 1
        else:
            state_data["retry_count"] = 0

        # Add transition
        state_data["transitions"].append(
            ChapterStateTransition(
                from_state=state_data["current_state"],
                to_state=new_state,
                error=error,
            )
        )
        state_data["current_state"] = new_state
        state_data["last_updated"] = _utc_now()

    self.save_chapter_state(novel_id, chapter_id, state_data)


def _get_checkpoints_dir(self: Any, novel_id: str) -> Path:
    """Get directory for chapter checkpoints."""
    novel_dir = self._novel_dir(novel_id)
    checkpoints_dir = novel_dir / "checkpoints"
    self._mkdirs(checkpoints_dir)
    return checkpoints_dir


def create_checkpoint(self: Any, novel_id: str, chapter_id: str, checkpoint_name: str = "auto") -> Path:
    """Create a checkpoint of current chapter state.

    Args:
        novel_id: Novel identifier
        chapter_id: Chapter identifier
        checkpoint_name: Name for checkpoint (auto-generates if not provided)

    Returns:
        Path to checkpoint file
    """
    checkpoints_dir = self._get_checkpoints_dir(novel_id)
    safe_chapter_id = validate_storage_identifier(str(chapter_id), "chapter_id")
    safe_checkpoint_name = validate_storage_identifier(str(checkpoint_name), "checkpoint_name")

    # Load current state
    raw_chapter = self.load_chapter(novel_id, safe_chapter_id)
    translated_chapter = self.load_translated_chapter(novel_id, safe_chapter_id)
    chapter_state = self.load_chapter_state(novel_id, safe_chapter_id)

    # Create checkpoint
    checkpoint_data = {
        "chapter_id": safe_chapter_id,
        "timestamp": _utc_now_iso(),
        "checkpoint_name": safe_checkpoint_name,
        "raw_chapter": raw_chapter,
        "translated_chapter": translated_chapter,
        "chapter_state": self._serialize_checkpoint_state(chapter_state),
    }

    # Use timestamp in filename if no name provided
    if safe_checkpoint_name == "auto":
        filename = f"{safe_chapter_id}__{_utc_now().strftime('%Y%m%d_%H%M%S')}.json"
    else:
        filename = f"{safe_chapter_id}__{safe_checkpoint_name}.json"

    path = checkpoints_dir / filename
    self._write_text(path, json.dumps(checkpoint_data, ensure_ascii=False, indent=2))
    logger.info(f"Checkpoint created: {safe_checkpoint_name} for {novel_id}/{safe_chapter_id}")
    return path


def list_checkpoints(self: Any, novel_id: str, chapter_id: str) -> list[CheckpointInfo]:
    """List all checkpoints for a chapter.

    Args:
        novel_id: Novel identifier
        chapter_id: Chapter identifier

    Returns:
        List of checkpoint info dicts
    """
    checkpoints_dir = self._get_checkpoints_dir(novel_id)
    safe_chapter_id = validate_storage_identifier(str(chapter_id), "chapter_id")
    if not self._path_exists(checkpoints_dir):
        return []

    checkpoints: list[CheckpointInfo] = []
    for checkpoint_file in sorted(self._glob(checkpoints_dir, f"{safe_chapter_id}__*.json")):
        try:
            data = json.loads(self._read_text(checkpoint_file))
            if not isinstance(data, dict):
                continue
            timestamp = data.get("timestamp")
            checkpoint_name = data.get("checkpoint_name")
            if not isinstance(timestamp, str):
                continue
            if not isinstance(checkpoint_name, str):
                continue
            checkpoints.append(
                {
                    "filename": checkpoint_file.name,
                    "timestamp": timestamp,
                    "checkpoint_name": checkpoint_name,
                }
            )
        except (json.JSONDecodeError, OSError):
            logger.debug("Skipping unreadable checkpoint file %s.", checkpoint_file)
            continue

    return checkpoints


def restore_from_checkpoint(
    self: Any,
    novel_id: str,
    chapter_id: str,
    checkpoint_name: str,
) -> bool:
    """Restore a chapter from a checkpoint.

    Args:
        novel_id: Novel identifier
        chapter_id: Chapter identifier
        checkpoint_name: Name of checkpoint to restore from

    Returns:
        True if restored successfully
    """
    checkpoints_dir = self._get_checkpoints_dir(novel_id)
    safe_chapter_id = validate_storage_identifier(str(chapter_id), "chapter_id")
    safe_checkpoint_name = validate_storage_identifier(str(checkpoint_name), "checkpoint_name")
    checkpoint_file = None

    for cf in self._glob(checkpoints_dir, f"{safe_chapter_id}__*.json"):
        try:
            data = json.loads(self._read_text(cf))
            if data.get("checkpoint_name") == safe_checkpoint_name:
                checkpoint_file = cf
                break
        except (json.JSONDecodeError, OSError):
            logger.debug("Skipping unreadable checkpoint file %s.", cf)
            continue

    if not checkpoint_file:
        logger.warning(f"Checkpoint not found: {safe_checkpoint_name}")
        return False

    try:
        checkpoint_data = json.loads(self._read_text(checkpoint_file))

        # Restore raw chapter
        if checkpoint_data.get("raw_chapter"):
            raw_chapter = checkpoint_data["raw_chapter"]
            self.save_chapter(
                novel_id,
                safe_chapter_id,
                raw_chapter.get("text", ""),
                title=raw_chapter.get("title"),
                source_key=raw_chapter.get("source_key"),
                source_url=raw_chapter.get("source_url"),
                images=raw_chapter.get("images"),
            )

        # Restore translated chapter
        if checkpoint_data.get("translated_chapter"):
            translated_chapter = checkpoint_data["translated_chapter"]
            self.save_translated_chapter(
                novel_id,
                safe_chapter_id,
                translated_chapter.get("text", ""),
                provider_key=translated_chapter.get("provider_key"),
                provider_model=translated_chapter.get("provider_model"),
                glossary_revision=(
                    translated_chapter["glossary_revision"]
                    if isinstance(translated_chapter.get("glossary_revision"), int)
                    else 0
                ),
                confidence_score=translated_chapter.get("confidence_score")
                if isinstance(translated_chapter.get("confidence_score"), float)
                else None,
                polish_needed=translated_chapter.get("polish_needed")
                if isinstance(translated_chapter.get("polish_needed"), bool)
                else None,
                confidence_details=translated_chapter.get("confidence_details")
                if isinstance(translated_chapter.get("confidence_details"), dict)
                else None,
            )

        # Restore state (if available)
        if checkpoint_data.get("chapter_state"):
            self.save_chapter_state(novel_id, safe_chapter_id, checkpoint_data["chapter_state"])

        logger.info(f"Restored from checkpoint: {safe_checkpoint_name} for {novel_id}/{safe_chapter_id}")
        return True

    except (json.JSONDecodeError, OSError, KeyError) as e:
        logger.error(f"Failed to restore checkpoint {safe_checkpoint_name}: {e}")
        return False


def rollback_to_state(self: Any, novel_id: str, chapter_id: str, target_state: ChapterState) -> None:
    """Rollback chapter to a previous state.

    Args:
        novel_id: Novel identifier
        chapter_id: Chapter identifier
        target_state: Target state to rollback to
    """
    safe_chapter_id = validate_storage_identifier(str(chapter_id), "chapter_id")
    state_data = self.load_chapter_state(novel_id, safe_chapter_id)
    if not state_data:
        logger.warning(f"No state found for {novel_id}/{safe_chapter_id}")
        return

    current_state = state_data["current_state"]

    # Check if rolling back
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

    current_idx = state_order.index(current_state)
    target_idx = state_order.index(target_state)

    if target_idx >= current_idx:
        logger.warning(f"Cannot rollback to {target_state.value} from {current_state.value}")
        return

    # Delete files for states beyond target
    if target_idx < state_order.index(ChapterState.TRANSLATED):
        chapter_payload = self._load_chapter_bundle(novel_id, safe_chapter_id)
        if chapter_payload and "translation_versions" in chapter_payload:
            chapter_payload.pop("translation_versions", None)
            chapter_payload.pop("active_translation_version_id", None)
            chapter_payload.pop("edit_history", None)
            self._persist_chapter_bundle(novel_id, safe_chapter_id, chapter_payload)
            logger.debug(f"Deleted translated chapter {safe_chapter_id}")
        translated_path = self._novel_dir(novel_id) / "translated" / f"{safe_chapter_id}.json"
        if self._path_exists(translated_path):
            self._unlink_path(translated_path)

    if target_idx < state_order.index(ChapterState.SEGMENTED):
        # Segmentation is in-memory only, but we mark state
        pass

    # Update state
    self.update_chapter_state(novel_id, safe_chapter_id, target_state)
    logger.info(f"Rolled back {novel_id}/{safe_chapter_id} to {target_state.value}")
