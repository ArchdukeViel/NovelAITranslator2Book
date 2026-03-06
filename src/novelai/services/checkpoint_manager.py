"""Checkpoint system for progress tracking and recovery."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from novelai.core.chapter_state import ChapterState
from novelai.services.storage_service import StorageService

logger = logging.getLogger(__name__)


def _utc_now_iso() -> str:
    """Return a serialized UTC timestamp with a trailing Z."""
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


@dataclass
class CheckpointMetadata:
    """Metadata for a checkpoint."""

    novel_id: str
    chapter_id: str
    checkpoint_id: str  # Unique identifier
    timestamp: str  # ISO format
    state: str  # ChapterState value
    error: Optional[str] = None
    progress: Optional[dict[str, Any]] = None


class CheckpointManager:
    """Manages checkpoints for recovery and progress tracking."""

    def __init__(self, storage: StorageService):
        """Initialize checkpoint manager.
        
        Args:
            storage: StorageService instance
        """
        self.storage = storage
        self._checkpoints: dict[str, CheckpointMetadata] = {}
        self._checkpoint_dir = Path(storage.base_dir) / "checkpoints"
        self._checkpoint_dir.mkdir(parents=True, exist_ok=True)

    def _get_checkpoint_id(self, novel_id: str, chapter_id: str) -> str:
        """Generate checkpoint ID."""
        return f"{novel_id}_{chapter_id}"

    async def create_checkpoint(
        self,
        novel_id: str,
        chapter_id: str,
        state: ChapterState,
        error: Optional[str] = None,
        progress: Optional[dict[str, Any]] = None,
    ) -> CheckpointMetadata:
        """Create a checkpoint.
        
        Args:
            novel_id: Novel identifier
            chapter_id: Chapter identifier
            state: Current chapter state
            error: Optional error message
            progress: Optional progress data
            
        Returns:
            CheckpointMetadata
        """
        checkpoint_id = self._get_checkpoint_id(novel_id, chapter_id)
        
        metadata = CheckpointMetadata(
            novel_id=novel_id,
            chapter_id=chapter_id,
            checkpoint_id=checkpoint_id,
            timestamp=_utc_now_iso(),
            state=state.value,
            error=error,
            progress=progress or {},
        )
        
        # Save to storage
        self.storage.create_checkpoint(novel_id, chapter_id, checkpoint_id)
        
        # Track in memory
        self._checkpoints[checkpoint_id] = metadata
        
        logger.debug(f"Checkpoint created: {checkpoint_id}")
        return metadata

    async def restore_checkpoint(
        self,
        novel_id: str,
        chapter_id: str,
        checkpoint_id: str | None = None,
    ) -> bool:
        """Restore chapter from checkpoint.
        
        Args:
            novel_id: Novel identifier
            chapter_id: Chapter identifier
            checkpoint_id: Checkpoint to restore (latest if not specified)
            
        Returns:
            True if restored successfully
        """
        if checkpoint_id is None:
            # Get latest checkpoint
            checkpoints = self.storage.list_checkpoints(novel_id, chapter_id)
            if not checkpoints:
                logger.warning(f"No checkpoints available for {novel_id}/{chapter_id}")
                return False
            # Use the last one (chronologically)
            checkpoint_id = checkpoints[-1]["checkpoint_name"]

        if checkpoint_id is None:
            return False

        success = self.storage.restore_from_checkpoint(novel_id, chapter_id, checkpoint_id)
        if success:
            self._checkpoints.pop(self._get_checkpoint_id(novel_id, chapter_id), None)
        
        return success

    def get_checkpoint_history(
        self, novel_id: str, chapter_id: str
    ) -> list[CheckpointMetadata]:
        """Get checkpoint history for a chapter.
        
        Args:
            novel_id: Novel identifier
            chapter_id: Chapter identifier
            
        Returns:
            List of CheckpointMetadata sorted by timestamp
        """
        checkpoint_id = self._get_checkpoint_id(novel_id, chapter_id)
        history: list[CheckpointMetadata] = []
        
        # Check in-memory cache
        if checkpoint_id in self._checkpoints:
            history.append(self._checkpoints[checkpoint_id])
        
        # Load from storage
        checkpoints = self.storage.list_checkpoints(novel_id, chapter_id)
        for cp in checkpoints:
            # Parse checkpoint name format: chapter_id__name.json
            try:
                metadata = CheckpointMetadata(
                    novel_id=novel_id,
                    chapter_id=chapter_id,
                    checkpoint_id=cp["checkpoint_name"],
                    timestamp=cp["timestamp"],
                    state="unknown",
                )
                history.append(metadata)
            except Exception:
                continue
        
        # Sort by timestamp
        history.sort(key=lambda x: x.timestamp)
        return history

    async def cleanup_old_checkpoints(
        self, novel_id: str, chapter_id: str, keep_count: int = 5
    ) -> int:
        """Remove old checkpoints, keeping only recent ones.
        
        Args:
            novel_id: Novel identifier
            chapter_id: Chapter identifier
            keep_count: Number of recent checkpoints to keep
            
        Returns:
            Number of checkpoints deleted
        """
        checkpoints = self.storage.list_checkpoints(novel_id, chapter_id)
        
        if len(checkpoints) <= keep_count:
            return 0
        
        # Delete older checkpoints
        to_delete = checkpoints[:-keep_count]
        deleted_count = 0
        
        for cp in to_delete:
            try:
                checkpoint_file = self.storage._get_checkpoints_dir(novel_id) / cp["filename"]
                if checkpoint_file.exists():
                    checkpoint_file.unlink()
                    deleted_count += 1
                    logger.debug(f"Deleted checkpoint: {cp['filename']}")
            except Exception as e:
                logger.error(f"Failed to delete checkpoint {cp['filename']}: {e}")
        
        return deleted_count

    async def get_recovery_point(self, novel_id: str, chapter_id: str) -> Optional[ChapterState]:
        """Get the last successful state for recovery.
        
        Args:
            novel_id: Novel identifier
            chapter_id: Chapter identifier
            
        Returns:
            Last successful ChapterState, or None
        """
        state_data = self.storage.load_chapter_state(novel_id, chapter_id)
        if state_data and state_data.get("error_count", 0) == 0:
            return state_data["current_state"]
        
        # If current state has errors, check checkpoints
        history = self.get_checkpoint_history(novel_id, chapter_id)
        for checkpoint in reversed(history):
            if not checkpoint.error:
                try:
                    return ChapterState(checkpoint.state)
                except ValueError:
                    continue
        
        return None


class AutoCheckpointHandler:
    """Automatically creates checkpoints at regular intervals."""

    def __init__(self, checkpoint_manager: CheckpointManager, interval: float = 60.0):
        """Initialize auto-checkpoint handler.
        
        Args:
            checkpoint_manager: CheckpointManager instance
            interval: Checkpoint interval in seconds
        """
        self.checkpoint_manager = checkpoint_manager
        self.interval = interval
        self._active_chapters: dict[str, ChapterState] = {}
        self._running = False

    async def track_chapter(
        self, novel_id: str, chapter_id: str, state: ChapterState
    ) -> None:
        """Start tracking a chapter for auto-checkpointing.
        
        Args:
            novel_id: Novel identifier
            chapter_id: Chapter identifier
            state: Current state
        """
        key = f"{novel_id}_{chapter_id}"
        self._active_chapters[key] = state

    async def update_chapter_state(
        self,
        novel_id: str,
        chapter_id: str,
        state: ChapterState,
        error: Optional[str] = None,
    ) -> None:
        """Update chapter state (and create checkpoint if needed).
        
        Args:
            novel_id: Novel identifier
            chapter_id: Chapter identifier
            state: New state
            error: Optional error message
        """
        key = f"{novel_id}_{chapter_id}"
        self._active_chapters[key] = state
        
        # Create checkpoint
        await self.checkpoint_manager.create_checkpoint(
            novel_id, chapter_id, state, error=error
        )

    async def start_periodic_checkpointing(self) -> None:
        """Start periodic checkpointing for all active chapters."""
        if self._running:
            return
        
        self._running = True
        logger.info("Starting periodic checkpointing")
        
        while self._running:
            try:
                await asyncio.sleep(self.interval)
                
                # Create checkpoints for all active chapters
                for key, state in list(self._active_chapters.items()):
                    try:
                        novel_id, chapter_id = key.split("_", 1)
                        await self.checkpoint_manager.create_checkpoint(
                            novel_id, chapter_id, state
                        )
                    except Exception as e:
                        logger.error(f"Failed to checkpoint {key}: {e}")
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in periodic checkpointing: {e}")

    async def stop_periodic_checkpointing(self) -> None:
        """Stop periodic checkpointing."""
        self._running = False
        logger.info("Stopping periodic checkpointing")

    async def cleanup(self) -> None:
        """Clean up old checkpoints for all tracked chapters."""
        logger.info("Cleaning up old checkpoints")
        
        total_deleted = 0
        for key in self._active_chapters.keys():
            try:
                novel_id, chapter_id = key.split("_", 1)
                deleted = await self.checkpoint_manager.cleanup_old_checkpoints(
                    novel_id, chapter_id, keep_count=5
                )
                total_deleted += deleted
            except Exception as e:
                logger.error(f"Failed to cleanup {key}: {e}")
        
        logger.info(f"Cleanup complete: {total_deleted} checkpoints deleted")
