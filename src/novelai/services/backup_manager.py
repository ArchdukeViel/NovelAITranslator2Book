"""Backup and restore functionality for data recovery."""

from __future__ import annotations

import gzip
import json
import logging
import tarfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, TypedDict

logger = logging.getLogger(__name__)


def _utc_now() -> datetime:
    """Return a timezone-aware UTC timestamp."""
    return datetime.now(timezone.utc)


def _utc_now_iso() -> str:
    """Return a serialized UTC timestamp with a trailing Z."""
    return _utc_now().isoformat().replace("+00:00", "Z")


@dataclass
class BackupInfo:
    """Information about a backup."""

    backup_id: str  # Unique identifier
    timestamp: str  # ISO format
    novel_id: str
    size_bytes: int
    compressed: bool
    files_count: int
    description: Optional[str] = None


class BackupManifestEntry(TypedDict):
    """Validated manifest entry stored on disk."""

    timestamp: str
    novel_id: str
    size_bytes: int
    compressed: bool
    files_count: int
    description: str | None


def _parse_manifest_entry(value: object) -> BackupManifestEntry | None:
    """Validate a manifest entry loaded from JSON."""
    if not isinstance(value, dict):
        return None

    timestamp = value.get("timestamp")
    novel_id = value.get("novel_id")
    if not isinstance(timestamp, str) or not isinstance(novel_id, str):
        return None

    size_bytes = value.get("size_bytes")
    compressed = value.get("compressed")
    files_count = value.get("files_count")
    description = value.get("description")

    return {
        "timestamp": timestamp,
        "novel_id": novel_id,
        "size_bytes": size_bytes if isinstance(size_bytes, int) else 0,
        "compressed": compressed if isinstance(compressed, bool) else False,
        "files_count": files_count if isinstance(files_count, int) else 0,
        "description": description if isinstance(description, str) else None,
    }


class BackupManager:
    """Manages backups and restoration."""

    def __init__(self, base_dir: Path):
        """Initialize backup manager.
        
        Args:
            base_dir: Base directory for backups
        """
        self.base_dir = base_dir
        self.backups_dir = base_dir / "backups"
        self.backups_dir.mkdir(parents=True, exist_ok=True)
        self._backup_manifest = self.backups_dir / "manifest.json"

    def _load_manifest(self) -> dict[str, BackupManifestEntry]:
        """Load backup manifest."""
        if self._backup_manifest.exists():
            try:
                raw_manifest = json.loads(self._backup_manifest.read_text(encoding="utf-8"))
                if not isinstance(raw_manifest, dict):
                    return {}
                manifest: dict[str, BackupManifestEntry] = {}
                for backup_id, info in raw_manifest.items():
                    if not isinstance(backup_id, str):
                        continue
                    parsed = _parse_manifest_entry(info)
                    if parsed is not None:
                        manifest[backup_id] = parsed
                return manifest
            except Exception:
                return {}
        return {}

    def _save_manifest(self, manifest: dict[str, BackupManifestEntry]) -> None:
        """Save backup manifest."""
        self._backup_manifest.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    def _get_backup_path(self, backup_id: str, compressed: bool = True) -> Path:
        """Get path for backup file."""
        ext = ".tar.gz" if compressed else ".tar"
        return self.backups_dir / f"{backup_id}{ext}"

    async def create_full_backup(
        self,
        novel_id: str,
        source_dir: Path,
        description: Optional[str] = None,
        compress: bool = True,
    ) -> BackupInfo:
        """Create a full backup of a novel.
        
        Args:
            novel_id: Novel identifier
            source_dir: Directory containing novel data
            description: Optional backup description
            compress: Whether to compress backup (gzip)
            
        Returns:
            BackupInfo with backup details
        """
        backup_id = f"{novel_id}__{_utc_now().strftime('%Y%m%d_%H%M%S')}"
        backup_path = self._get_backup_path(backup_id, compress)
        
        logger.info(f"Creating backup: {backup_id} from {source_dir}")
        
        try:
            # Create tar archive
            if compress:
                with tarfile.open(backup_path, "w:gz") as tar:
                    tar.add(source_dir, arcname=Path(source_dir).name)
            else:
                with tarfile.open(backup_path, "w") as tar:
                    tar.add(source_dir, arcname=Path(source_dir).name)
            
            size_bytes = backup_path.stat().st_size
            
            # Count files in archive
            files_count = 0
            if compress:
                with gzip.open(backup_path, "rb") as gz:
                    with tarfile.open(fileobj=gz) as tar:
                        files_count = len(tar.getmembers())
            else:
                with tarfile.open(backup_path) as tar:
                    files_count = len(tar.getmembers())
            
            # Create backup info
            backup_info = BackupInfo(
                backup_id=backup_id,
                timestamp=_utc_now_iso(),
                novel_id=novel_id,
                size_bytes=size_bytes,
                compressed=compress,
                files_count=files_count,
                description=description,
            )
            
            # Update manifest
            manifest = self._load_manifest()
            manifest[backup_id] = {
                "timestamp": backup_info.timestamp,
                "novel_id": novel_id,
                "size_bytes": size_bytes,
                "compressed": compress,
                "files_count": files_count,
                "description": description,
            }
            self._save_manifest(manifest)
            
            logger.info(
                f"Backup created: {backup_id} "
                f"({size_bytes / 1024 / 1024:.2f}MB, {files_count} files)"
            )
            return backup_info
            
        except Exception as e:
            logger.error(f"Backup creation failed: {e}")
            if backup_path.exists():
                backup_path.unlink()
            raise

    def _last_backup_timestamp(self, novel_id: str) -> datetime | None:
        """Return the timestamp of the most recent backup for *novel_id*."""
        backups = self.list_backups(novel_id)
        if not backups:
            return None
        try:
            return datetime.fromisoformat(backups[0].timestamp.replace("Z", "+00:00"))
        except Exception:
            return None

    @staticmethod
    def _collect_changed_files(source_dir: Path, since: datetime) -> list[Path]:
        """Return files under *source_dir* whose mtime is newer than *since*."""
        since_ts = since.timestamp()
        changed: list[Path] = []
        for path in source_dir.rglob("*"):
            if not path.is_file():
                continue
            if path.stat().st_mtime > since_ts:
                changed.append(path)
        return changed

    async def create_incremental_backup(
        self,
        novel_id: str,
        source_dir: Path,
        last_backup_id: Optional[str] = None,
        description: Optional[str] = None,
    ) -> BackupInfo:
        """Create an incremental backup (only files modified after last backup).

        If no previous backup exists, falls back to a full backup automatically.

        Args:
            novel_id: Novel identifier
            source_dir: Directory containing novel data
            last_backup_id: Last backup ID to base incremental on (auto-detected if omitted)
            description: Optional backup description

        Returns:
            BackupInfo with backup details
        """
        # Determine the reference timestamp.
        since: datetime | None = None
        if last_backup_id:
            manifest = self._load_manifest()
            entry = manifest.get(last_backup_id)
            if entry:
                try:
                    since = datetime.fromisoformat(entry["timestamp"].replace("Z", "+00:00"))
                except Exception:
                    pass
        if since is None:
            since = self._last_backup_timestamp(novel_id)

        # No prior backup → fall back to a full backup.
        if since is None:
            logger.info("No prior backup found for %s; falling back to full backup.", novel_id)
            return await self.create_full_backup(
                novel_id, source_dir, description=description or "Incremental (initial full)"
            )

        changed = self._collect_changed_files(source_dir, since)
        if not changed:
            logger.info("No files changed since last backup for %s.", novel_id)
            # Return a zero-file info entry without creating an archive.
            return BackupInfo(
                backup_id=f"{novel_id}_inc_{_utc_now().strftime('%Y%m%d_%H%M%S')}",
                timestamp=_utc_now_iso(),
                novel_id=novel_id,
                size_bytes=0,
                compressed=True,
                files_count=0,
                description=description or "Incremental backup (no changes)",
            )

        backup_id = f"{novel_id}_inc_{_utc_now().strftime('%Y%m%d_%H%M%S')}"
        backup_path = self._get_backup_path(backup_id, compressed=True)

        logger.info("Creating incremental backup %s (%d changed files).", backup_id, len(changed))

        try:
            with tarfile.open(backup_path, "w:gz") as tar:
                for file_path in changed:
                    arcname = str(Path(source_dir.name) / file_path.relative_to(source_dir))
                    tar.add(file_path, arcname=arcname)

            size_bytes = backup_path.stat().st_size
            files_count = len(changed)

            backup_info = BackupInfo(
                backup_id=backup_id,
                timestamp=_utc_now_iso(),
                novel_id=novel_id,
                size_bytes=size_bytes,
                compressed=True,
                files_count=files_count,
                description=description or "Incremental backup",
            )

            manifest = self._load_manifest()
            manifest[backup_id] = {
                "timestamp": backup_info.timestamp,
                "novel_id": novel_id,
                "size_bytes": size_bytes,
                "compressed": True,
                "files_count": files_count,
                "description": backup_info.description,
            }
            self._save_manifest(manifest)

            logger.info(
                "Incremental backup created: %s (%d files, %.2f MB).",
                backup_id, files_count, size_bytes / 1024 / 1024,
            )
            return backup_info

        except Exception as e:
            logger.error("Incremental backup failed: %s", e)
            if backup_path.exists():
                backup_path.unlink()
            raise

    async def restore_backup(
        self,
        backup_id: str,
        target_dir: Path,
        overwrite: bool = False,
    ) -> bool:
        """Restore a backup to target directory.
        
        Args:
            backup_id: Backup identifier to restore
            target_dir: Directory to restore to
            overwrite: Whether to overwrite existing data
            
        Returns:
            True if restored successfully
        """
        manifest = self._load_manifest()
        
        if backup_id not in manifest:
            logger.warning(f"Backup not found: {backup_id}")
            return False
        
        backup_path = self._get_backup_path(backup_id, manifest[backup_id]["compressed"])
        
        if not backup_path.exists():
            logger.warning(f"Backup file not found: {backup_path}")
            return False
        
        logger.info(f"Restoring backup {backup_id} to {target_dir}")
        
        try:
            # Check if target exists
            if target_dir.exists() and not overwrite:
                logger.warning(f"Target directory exists: {target_dir} (use overwrite=True)")
                return False
            
            # Extract backup
            if manifest[backup_id]["compressed"]:
                with tarfile.open(backup_path, "r:gz") as tar:
                    tar.extractall(target_dir.parent)
            else:
                with tarfile.open(backup_path, "r") as tar:
                    tar.extractall(target_dir.parent)
            
            logger.info(f"Backup restored: {backup_id}")
            return True
            
        except Exception as e:
            logger.error(f"Backup restoration failed: {e}")
            return False

    def list_backups(self, novel_id: Optional[str] = None) -> list[BackupInfo]:
        """List all available backups.
        
        Args:
            novel_id: Filter by novel ID (optional)
            
        Returns:
            List of BackupInfo sorted by timestamp (newest first)
        """
        manifest = self._load_manifest()
        backups: list[BackupInfo] = []
        
        for backup_id, info in manifest.items():
            if novel_id and info.get("novel_id") != novel_id:
                continue
            
            backup_info = BackupInfo(
                backup_id=backup_id,
                timestamp=info["timestamp"],
                novel_id=info["novel_id"],
                size_bytes=info["size_bytes"],
                compressed=info["compressed"],
                files_count=info["files_count"],
                description=info["description"],
            )
            backups.append(backup_info)
        
        # Sort by timestamp (newest first)
        backups.sort(key=lambda x: x.timestamp, reverse=True)
        return backups

    async def delete_backup(self, backup_id: str) -> bool:
        """Delete a backup.
        
        Args:
            backup_id: Backup ID to delete
            
        Returns:
            True if deleted successfully
        """
        manifest = self._load_manifest()
        
        if backup_id not in manifest:
            logger.warning(f"Backup not found: {backup_id}")
            return False
        
        try:
            # Delete backup file
            backup_info = manifest[backup_id]
            backup_path = self._get_backup_path(backup_id, backup_info.get("compressed", True))
            
            if backup_path.exists():
                backup_path.unlink()
            
            # Update manifest
            del manifest[backup_id]
            self._save_manifest(manifest)
            
            logger.info(f"Backup deleted: {backup_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to delete backup {backup_id}: {e}")
            return False

    async def cleanup_old_backups(
        self, novel_id: str, keep_count: int = 5, max_age_days: int = 30
    ) -> int:
        """Clean up old backups, keeping recent and within age limit.
        
        Args:
            novel_id: Novel identifier
            keep_count: Minimum number of backups to keep
            max_age_days: Maximum age of backup to keep
            
        Returns:
            Number of backups deleted
        """
        backups = self.list_backups(novel_id)
        
        cutoff_date = _utc_now()
        
        deleted_count = 0
        for i, backup in enumerate(backups):
            should_delete = False
            
            # Delete if older than max_age_days and have enough recent backups
            if i >= keep_count:
                try:
                    backup_date = datetime.fromisoformat(backup.timestamp.replace("Z", "+00:00"))
                    age_days = (cutoff_date - backup_date).days
                    if age_days > max_age_days:
                        should_delete = True
                except Exception:
                    pass
            
            if should_delete:
                if await self.delete_backup(backup.backup_id):
                    deleted_count += 1
        
        logger.info(f"Cleanup complete: {deleted_count} backups deleted for {novel_id}")
        return deleted_count

    def get_backup_size(self, novel_id: str) -> int:
        """Get total size of all backups for a novel.
        
        Args:
            novel_id: Novel identifier
            
        Returns:
            Total size in bytes
        """
        backups = self.list_backups(novel_id)
        return sum(b.size_bytes for b in backups)
