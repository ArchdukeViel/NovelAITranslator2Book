from __future__ import annotations

import hashlib
import json
import logging
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from novelai.config.settings import settings
from novelai.services.query_builder import ChapterQueryBuilder

logger = logging.getLogger(__name__)


def _utc_now() -> datetime:
    """Return a timezone-aware UTC timestamp."""
    return datetime.now(timezone.utc)


def _utc_now_iso() -> str:
    """Return a serialized UTC timestamp with a trailing Z."""
    return _utc_now().isoformat().replace("+00:00", "Z")


class StorageService:
    """Filesystem-backed storage service.

    Each novel is stored in a folder under `data/novels/<folder_name>`.
    The folder name is derived from the translated title (when available),
    and falls back to the novel ID when no translated title exists.

    The folder contains:
      - metadata.json
      - raw/<chapter_id>.json
      - translated/<chapter_id>.json

    A simple index file keeps the mapping from novel ID to folder name.
    """

    INDEX_FILENAME = "index.json"

    @staticmethod
    def _sanitize_folder_name(name: str) -> str:
        """Create a filesystem-safe folder name from an arbitrary title."""
        name = name.strip().replace(" ", "_")
        name = re.sub(r"[^A-Za-z0-9_\-\.]+", "", name)
        return name or "novel"

    @staticmethod
    def _hash_text(text: str) -> str:
        return hashlib.sha256(text.encode("utf-8")).hexdigest()

    def __init__(self, base_dir: Path | None = None) -> None:
        self.base_dir = (base_dir or settings.DATA_DIR).resolve()
        self.base_dir.mkdir(parents=True, exist_ok=True)

        self.novels_dir = self.base_dir / "novels"
        self.novels_dir.mkdir(parents=True, exist_ok=True)

    def _index_path(self) -> Path:
        return self.novels_dir / self.INDEX_FILENAME

    def _load_index(self) -> dict[str, dict[str, Any]]:
        path = self._index_path()
        if not path.exists():
            return {}
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return {}

    def _persist_index(self, index: dict[str, dict[str, Any]]) -> None:
        path = self._index_path()
        path.write_text(json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8")

    def _compute_folder_name(self, novel_id: str, metadata: dict[str, Any]) -> str:
        """Return a folder name for a novel.

        Prefer translated title when present. Fall back to the original title,
        then the novel ID.
        """
        translated_title = metadata.get("translated_title")
        if translated_title:
            return self._sanitize_folder_name(translated_title)

        title = metadata.get("title")
        if title:
            return self._sanitize_folder_name(title)

        return self._sanitize_folder_name(novel_id)

    def _get_folder_name(self, novel_id: str) -> str:
        index = self._load_index()
        entry = index.get(novel_id, {})
        return entry.get("folder_name", novel_id)

    def _novel_dir(self, novel_id: str) -> Path:
        folder = self._get_folder_name(novel_id)
        return self.novels_dir / folder

    def _ensure_novel_dir(self, novel_id: str, folder_name: str) -> Path:
        """Ensure the novel directory exists and the index is updated."""
        index = self._load_index()
        entry = index.get(novel_id, {})
        old_folder = entry.get("folder_name")

        # If the folder name has changed, rename the existing folder to preserve data.
        if old_folder and old_folder != folder_name:
            old_dir = self.novels_dir / old_folder
            new_dir = self.novels_dir / folder_name
            if old_dir.exists() and not new_dir.exists():
                shutil.move(str(old_dir), str(new_dir))

        novel_dir = self.novels_dir / folder_name
        novel_dir.mkdir(parents=True, exist_ok=True)

        index[novel_id] = {
            "folder_name": folder_name,
            "updated_at": _utc_now_iso(),
        }
        self._persist_index(index)
        return novel_dir

    def delete_novel(self, novel_id: str) -> None:
        """Delete stored data for a novel (used for full re-scrapes)."""
        folder_name = self._get_folder_name(novel_id)
        novel_dir = self.novels_dir / folder_name
        if novel_dir.exists():
            shutil.rmtree(novel_dir)

        index = self._load_index()
        if novel_id in index:
            del index[novel_id]
            self._persist_index(index)

    def existing_chapter_hash(self, novel_id: str, chapter_id: str) -> Optional[str]:
        """Return SHA256 hash of an existing raw chapter file (if present)."""
        json_path = self._novel_dir(novel_id) / "raw" / f"{chapter_id}.json"
        txt_path = self._novel_dir(novel_id) / "raw" / f"{chapter_id}.txt"

        if json_path.exists():
            return self._hash_text(json_path.read_text(encoding="utf-8"))
        if txt_path.exists():
            return self._hash_text(txt_path.read_text(encoding="utf-8"))
        return None

    def save_chapter(
        self,
        novel_id: str,
        chapter_id: str,
        text: str,
        title: str | None = None,
        source_key: str | None = None,
        source_url: str | None = None,
    ) -> Path:
        """Save a raw / scraped chapter as structured JSON."""
        novel_dir = self._novel_dir(novel_id)
        raw_dir = novel_dir / "raw"
        raw_dir.mkdir(parents=True, exist_ok=True)

        payload = {
            "id": chapter_id,
            "title": title,
            "source_key": source_key,
            "source_url": source_url,
            "scraped_at": _utc_now_iso(),
            "text": text,
        }

        path = raw_dir / f"{chapter_id}.json"
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return path

    def load_chapter(self, novel_id: str, chapter_id: str) -> Optional[dict[str, Any]]:
        json_path = self._novel_dir(novel_id) / "raw" / f"{chapter_id}.json"
        txt_path = self._novel_dir(novel_id) / "raw" / f"{chapter_id}.txt"

        if json_path.exists():
            try:
                return json.loads(json_path.read_text(encoding="utf-8"))
            except Exception:
                return None

        if txt_path.exists():
            # Backwards compatibility: older versions stored raw chapters as plain text.
            return {"id": chapter_id, "text": txt_path.read_text(encoding="utf-8")}

        return None

    def save_translated_chapter(
        self,
        novel_id: str,
        chapter_id: str,
        text: str,
        provider: str | None = None,
        model: str | None = None,
    ) -> Path:
        """Save a translated chapter as structured JSON."""
        novel_dir = self._novel_dir(novel_id)
        translated_dir = novel_dir / "translated"
        translated_dir.mkdir(parents=True, exist_ok=True)

        payload = {
            "id": chapter_id,
            "provider": provider,
            "model": model,
            "translated_at": _utc_now_iso(),
            "text": text,
        }

        path = translated_dir / f"{chapter_id}.json"
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return path

    def load_translated_chapter(self, novel_id: str, chapter_id: str) -> Optional[dict[str, Any]]:
        json_path = self._novel_dir(novel_id) / "translated" / f"{chapter_id}.json"
        txt_path = self._novel_dir(novel_id) / "translated" / f"{chapter_id}.txt"

        if json_path.exists():
            try:
                return json.loads(json_path.read_text(encoding="utf-8"))
            except Exception:
                return None

        if txt_path.exists():
            # Backwards compatibility: older versions stored translated chapters as plain text.
            return {"id": chapter_id, "text": txt_path.read_text(encoding="utf-8")}

        return None

    def save_metadata(self, novel_id: str, data: dict[str, Any]) -> Path:
        """Save novel metadata (chapter list, title, etc.) as JSON."""
        # Enhance metadata with tracking fields
        data["novel_id"] = novel_id
        data["scraped_at"] = data.get("scraped_at") or _utc_now_iso()

        folder_name = self._compute_folder_name(novel_id, data)
        data["folder_name"] = folder_name

        novel_dir = self._ensure_novel_dir(novel_id, folder_name)
        path = novel_dir / "metadata.json"
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        return path

    def load_metadata(self, novel_id: str) -> Optional[dict[str, Any]]:
        path = self._novel_dir(novel_id) / "metadata.json"
        if not path.exists():
            return None
        content = path.read_text(encoding="utf-8")
        try:
            return json.loads(content)
        except Exception:
            return None

    def list_translated_chapters(self, novel_id: str) -> list[str]:
        translated_dir = self._novel_dir(novel_id) / "translated"
        if not translated_dir.exists():
            return []

        stems: set[str] = set()
        for p in translated_dir.iterdir():
            if not p.is_file():
                continue
            if p.suffix.lower() in {".json", ".txt"}:
                stems.add(p.stem)
        return sorted(stems)

    def count_translated_chapters(self, novel_id: str) -> int:
        return len(self.list_translated_chapters(novel_id))

    # State Tracking Methods
    def _get_state_dir(self, novel_id: str) -> Path:
        """Get the directory for chapter state files."""
        novel_dir = self._novel_dir(novel_id)
        state_dir = novel_dir / "state"
        state_dir.mkdir(parents=True, exist_ok=True)
        return state_dir

    def save_chapter_state(self, novel_id: str, chapter_id: str, state_data: dict[str, Any]) -> Path:
        """Save chapter state tracking information (including transitions)."""
        from novelai.core.chapter_state import ChapterMetadata, ChapterState

        state_dir = self._get_state_dir(novel_id)
        
        # Serialize ChapterMetadata to JSON-safe format
        transitions = []
        for transition in state_data.get("transitions", []):
            transitions.append({
                "from_state": transition.from_state.value if transition.from_state else None,
                "to_state": transition.to_state.value if transition.to_state else None,
                "timestamp": transition.timestamp.isoformat() if isinstance(transition.timestamp, datetime) else transition.timestamp,
                "error": transition.error,
            })
        
        payload = {
            "chapter_id": chapter_id,
            "current_state": state_data["current_state"].value if isinstance(state_data["current_state"], ChapterState) else state_data["current_state"],
            "transitions": transitions,
            "last_updated": state_data["last_updated"].isoformat() if isinstance(state_data["last_updated"], datetime) else state_data["last_updated"],
            "error_count": state_data.get("error_count", 0),
            "retry_count": state_data.get("retry_count", 0),
        }
        
        path = state_dir / f"{chapter_id}.json"
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return path

    def load_chapter_state(self, novel_id: str, chapter_id: str) -> Optional[dict[str, Any]]:
        """Load chapter state tracking information."""
        from novelai.core.chapter_state import ChapterMetadata, ChapterState, ChapterStateTransition

        state_dir = self._get_state_dir(novel_id)
        path = state_dir / f"{chapter_id}.json"
        
        if not path.exists():
            return None
        
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            
            # Deserialize to proper types
            transitions = []
            for t in data.get("transitions", []):
                transitions.append(ChapterStateTransition(
                    from_state=ChapterState(t["from_state"]) if t["from_state"] else None,
                    to_state=ChapterState(t["to_state"]) if t["to_state"] else ChapterState.SCRAPED,
                    timestamp=datetime.fromisoformat(t["timestamp"]) if isinstance(t["timestamp"], str) else t["timestamp"],
                    error=t.get("error"),
                ))
            
            return {
                "chapter_id": data["chapter_id"],
                "current_state": ChapterState(data["current_state"]),
                "transitions": transitions,
                "last_updated": datetime.fromisoformat(data["last_updated"]) if isinstance(data["last_updated"], str) else data["last_updated"],
                "error_count": data.get("error_count", 0),
                "retry_count": data.get("retry_count", 0),
            }
        except Exception:
            return None

    def update_chapter_state(
        self,
        novel_id: str,
        chapter_id: str,
        new_state: "ChapterState",
        error: Optional[str] = None,
    ) -> None:
        """Update a chapter's state with a new transition."""
        from novelai.core.chapter_state import ChapterMetadata, ChapterState, ChapterStateTransition

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

    def get_chapters_by_state(self, novel_id: str, state: "ChapterState") -> list[str]:
        """Get all chapters in a specific state."""
        from novelai.core.chapter_state import ChapterState

        state_dir = self._get_state_dir(novel_id)
        if not state_dir.exists():
            return []
        
        chapters = []
        for state_file in state_dir.glob("*.json"):
            try:
                state_data = json.loads(state_file.read_text(encoding="utf-8"))
                if ChapterState(state_data["current_state"]) == state:
                    chapters.append(state_data["chapter_id"])
            except Exception:
                continue
        
        return sorted(chapters)

    def get_chapter_progress(self, novel_id: str) -> dict[str, int]:
        """Get count of chapters in each state."""
        from novelai.core.chapter_state import ChapterState

        progress = {s.value: 0 for s in ChapterState}
        
        state_dir = self._get_state_dir(novel_id)
        if not state_dir.exists():
            return progress
        
        for state_file in state_dir.glob("*.json"):
            try:
                state_data = json.loads(state_file.read_text(encoding="utf-8"))
                current_state = state_data["current_state"]
                progress[current_state] += 1
            except Exception:
                continue
        
        return progress

    # Query Methods
    def query_chapters(self, novel_id: str) -> ChapterQueryBuilder:
        """Create a query builder for chapters."""
        state_dir = self._get_state_dir(novel_id)
        return ChapterQueryBuilder(state_dir)

    def get_chapters_ready_for_export(self, novel_id: str) -> list[str]:
        """Get all chapters that have been translated (ready for export)."""
        from novelai.core.chapter_state import ChapterState

        results = (
            self.query_chapters(novel_id)
            .by_states([ChapterState.TRANSLATED, ChapterState.EXPORTED])
            .sort_by("updated")
            .execute()
        )
        logger.info(f"Found {len(results)} chapters ready for export in {novel_id}")
        return [r.chapter_id for r in results]

    def get_chapters_with_errors(self, novel_id: str, limit: int = 100) -> list[str]:
        """Get chapters that have errors, for retry."""
        results = (
            self.query_chapters(novel_id)
            .has_errors()
            .sort_by("errors", reverse=True)
            .limit(limit)
            .execute()
        )
        logger.info(f"Found {len(results)} chapters with errors in {novel_id}")
        return [r.chapter_id for r in results]

    def get_scraping_progress(self, novel_id: str) -> dict[str, Any]:
        """Get detailed scraping progress for a novel."""
        from novelai.core.chapter_state import ChapterState

        progress = {
            "total": 0,
            "by_state": self.get_chapter_progress(novel_id),
            "with_errors": 0,
            "success_rate": 0.0,
        }

        state_dir = self._get_state_dir(novel_id)
        if not state_dir.exists():
            return progress

        total_files = 0
        error_count = 0

        for state_file in state_dir.glob("*.json"):
            try:
                state_data = json.loads(state_file.read_text(encoding="utf-8"))
                total_files += 1
                if state_data.get("error_count", 0) > 0:
                    error_count += 1
            except Exception:
                continue

        progress["total"] = total_files
        progress["with_errors"] = error_count
        if total_files > 0:
            progress["success_rate"] = ((total_files - error_count) / total_files) * 100

        logger.debug(
            f"Progress for {novel_id}: {progress['by_state']} "
            f"(success rate: {progress['success_rate']:.1f}%)"
        )
        return progress

    # Rollback & Recovery Methods
    def _get_checkpoints_dir(self, novel_id: str) -> Path:
        """Get directory for chapter checkpoints."""
        novel_dir = self._novel_dir(novel_id)
        checkpoints_dir = novel_dir / "checkpoints"
        checkpoints_dir.mkdir(parents=True, exist_ok=True)
        return checkpoints_dir

    def create_checkpoint(self, novel_id: str, chapter_id: str, checkpoint_name: str = "auto") -> Path:
        """Create a checkpoint of current chapter state.
        
        Args:
            novel_id: Novel identifier
            chapter_id: Chapter identifier
            checkpoint_name: Name for checkpoint (auto-generates if not provided)
            
        Returns:
            Path to checkpoint file
        """
        checkpoints_dir = self._get_checkpoints_dir(novel_id)
        
        # Load current state
        raw_chapter = self.load_chapter(novel_id, chapter_id)
        translated_chapter = self.load_translated_chapter(novel_id, chapter_id)
        chapter_state = self.load_chapter_state(novel_id, chapter_id)
        
        # Create checkpoint
        checkpoint_data = {
            "chapter_id": chapter_id,
            "timestamp": _utc_now_iso(),
            "checkpoint_name": checkpoint_name,
            "raw_chapter": raw_chapter,
            "translated_chapter": translated_chapter,
            "chapter_state": chapter_state,
        }
        
        # Use timestamp in filename if no name provided
        if checkpoint_name == "auto":
            filename = f"{chapter_id}__{_utc_now().strftime('%Y%m%d_%H%M%S')}.json"
        else:
            filename = f"{chapter_id}__{checkpoint_name}.json"
        
        path = checkpoints_dir / filename
        path.write_text(json.dumps(checkpoint_data, ensure_ascii=False, indent=2), encoding="utf-8")
        logger.info(f"Checkpoint created: {checkpoint_name} for {novel_id}/{chapter_id}")
        return path

    def list_checkpoints(self, novel_id: str, chapter_id: str) -> list[dict[str, Any]]:
        """List all checkpoints for a chapter.
        
        Args:
            novel_id: Novel identifier
            chapter_id: Chapter identifier
            
        Returns:
            List of checkpoint info dicts
        """
        checkpoints_dir = self._get_checkpoints_dir(novel_id)
        if not checkpoints_dir.exists():
            return []
        
        checkpoints = []
        for checkpoint_file in sorted(checkpoints_dir.glob(f"{chapter_id}__*.json")):
            try:
                data = json.loads(checkpoint_file.read_text(encoding="utf-8"))
                checkpoints.append({
                    "filename": checkpoint_file.name,
                    "timestamp": data.get("timestamp"),
                    "checkpoint_name": data.get("checkpoint_name"),
                })
            except Exception:
                continue
        
        return checkpoints

    def restore_from_checkpoint(
        self,
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
        checkpoint_file = None
        
        for cf in checkpoints_dir.glob(f"{chapter_id}__*.json"):
            try:
                data = json.loads(cf.read_text(encoding="utf-8"))
                if data.get("checkpoint_name") == checkpoint_name:
                    checkpoint_file = cf
                    break
            except Exception:
                continue
        
        if not checkpoint_file:
            logger.warning(f"Checkpoint not found: {checkpoint_name}")
            return False
        
        try:
            checkpoint_data = json.loads(checkpoint_file.read_text(encoding="utf-8"))
            
            # Restore raw chapter
            if checkpoint_data.get("raw_chapter"):
                raw_dir = self._novel_dir(novel_id) / "raw"
                raw_dir.mkdir(parents=True, exist_ok=True)
                raw_path = raw_dir / f"{chapter_id}.json"
                raw_path.write_text(
                    json.dumps(checkpoint_data["raw_chapter"], ensure_ascii=False, indent=2),
                    encoding="utf-8"
                )
            
            # Restore translated chapter
            if checkpoint_data.get("translated_chapter"):
                translated_dir = self._novel_dir(novel_id) / "translated"
                translated_dir.mkdir(parents=True, exist_ok=True)
                translated_path = translated_dir / f"{chapter_id}.json"
                translated_path.write_text(
                    json.dumps(checkpoint_data["translated_chapter"], ensure_ascii=False, indent=2),
                    encoding="utf-8"
                )
            
            # Restore state (if available)
            if checkpoint_data.get("chapter_state"):
                self.save_chapter_state(novel_id, chapter_id, checkpoint_data["chapter_state"])
            
            logger.info(f"Restored from checkpoint: {checkpoint_name} for {novel_id}/{chapter_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to restore checkpoint {checkpoint_name}: {e}")
            return False

    def rollback_to_state(self, novel_id: str, chapter_id: str, target_state: "ChapterState") -> None:
        """Rollback chapter to a previous state.
        
        Args:
            novel_id: Novel identifier
            chapter_id: Chapter identifier
            target_state: Target state to rollback to
        """
        from novelai.core.chapter_state import ChapterState
        
        state_data = self.load_chapter_state(novel_id, chapter_id)
        if not state_data:
            logger.warning(f"No state found for {novel_id}/{chapter_id}")
            return
        
        current_state = state_data["current_state"]
        
        # Check if rolling back
        state_order = [
            ChapterState.SCRAPED,
            ChapterState.PARSED,
            ChapterState.SEGMENTED,
            ChapterState.TRANSLATED,
            ChapterState.EXPORTED,
        ]
        
        current_idx = state_order.index(current_state)
        target_idx = state_order.index(target_state)
        
        if target_idx >= current_idx:
            logger.warning(f"Cannot rollback to {target_state.value} from {current_state.value}")
            return
        
        # Delete files for states beyond target
        if target_idx < state_order.index(ChapterState.TRANSLATED):
            translated_path = self._novel_dir(novel_id) / "translated" / f"{chapter_id}.json"
            if translated_path.exists():
                translated_path.unlink()
                logger.debug(f"Deleted translated chapter {chapter_id}")
        
        if target_idx < state_order.index(ChapterState.SEGMENTED):
            # Segmentation is in-memory only, but we mark state
            pass
        
        # Update state
        self.update_chapter_state(novel_id, chapter_id, target_state)
        logger.info(f"Rolled back {novel_id}/{chapter_id} to {target_state.value}")

    def list_novels(self) -> list[str]:
        index = self._load_index()
        return list(index.keys())
