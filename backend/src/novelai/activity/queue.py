from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from novelai.config.settings import settings
from novelai.core.platform import CrawlJobKind, JobStatus, TranslationJobKind
from novelai.utils import atomic_write

logger = logging.getLogger(__name__)


def _utc_now_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


class ActivityQueueService:
    """Small durable activity queue used by the web/platform layer.

    Records are still stored in one JSON file. The public concept is activity:
    preliminary crawl, scraping, translation, and future workflow phases.
    """

    VALID_ACTIVITY_TYPES = {"crawl", "translation"}
    ACTIVITY_LOG_DIRNAME = "activity_log"
    LEGACY_JOBS_DIRNAME = "jobs"

    def __init__(self, base_dir: Path | None = None) -> None:
        self.base_dir = (base_dir or settings.DATA_DIR).resolve()
        self.activity_log_dir = self.base_dir / self.ACTIVITY_LOG_DIRNAME
        self.legacy_jobs_dir = self.base_dir / self.LEGACY_JOBS_DIRNAME
        self.activity_log_dir.mkdir(parents=True, exist_ok=True)
        self.activity_dir = self.activity_log_dir
        self.jobs_dir = self.activity_log_dir
        self.activity_file = self.activity_log_dir / "queue.json"
        self.jobs_file = self.activity_file
        self.source_health_file = self.activity_log_dir / "source_health.json"
        self._migrate_legacy_jobs_dir()

    def _migrate_legacy_jobs_dir(self) -> None:
        if not self.legacy_jobs_dir.exists() or self.legacy_jobs_dir == self.activity_log_dir:
            return

        self._migrate_json_file(
            self.legacy_jobs_dir / "queue.json",
            self.activity_file,
            merge_kind="activity",
        )
        self._migrate_json_file(
            self.legacy_jobs_dir / "source_health.json",
            self.source_health_file,
            merge_kind="source_health",
        )
        try:
            self.legacy_jobs_dir.rmdir()
        except OSError:
            logger.debug("Leaving non-empty legacy jobs folder at %s.", self.legacy_jobs_dir)

    def _migrate_json_file(self, legacy_path: Path, target_path: Path, *, merge_kind: str) -> None:
        if not legacy_path.exists():
            return
        if not target_path.exists():
            legacy_path.replace(target_path)
            return

        try:
            legacy_data = json.loads(legacy_path.read_text(encoding="utf-8"))
            target_data = json.loads(target_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("Could not migrate legacy activity log file %s: %s", legacy_path, exc)
            return

        if merge_kind == "activity" and isinstance(legacy_data, list) and isinstance(target_data, list):
            by_id: dict[str, dict[str, Any]] = {}
            for item in [*target_data, *legacy_data]:
                if isinstance(item, dict) and isinstance(item.get("id"), str):
                    by_id[item["id"]] = dict(item)
            atomic_write(target_path, json.dumps(list(by_id.values()), ensure_ascii=False, indent=2))
            legacy_path.unlink(missing_ok=True)
            return

        if merge_kind == "source_health" and isinstance(legacy_data, dict) and isinstance(target_data, dict):
            merged = {
                **{str(key): value for key, value in target_data.items() if isinstance(value, dict)},
                **{str(key): value for key, value in legacy_data.items() if isinstance(value, dict)},
            }
            atomic_write(target_path, json.dumps(merged, ensure_ascii=False, indent=2))
            legacy_path.unlink(missing_ok=True)

    def _load_activity(self) -> list[dict[str, Any]]:
        if not self.activity_file.exists():
            return []
        try:
            data = json.loads(self.activity_file.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return []
        if not isinstance(data, list):
            return []
        return [dict(item) for item in data if isinstance(item, dict)]

    def _persist_activity(self, activity: list[dict[str, Any]]) -> None:
        atomic_write(self.activity_file, json.dumps(activity, ensure_ascii=False, indent=2))

    def _load_source_health(self) -> dict[str, dict[str, Any]]:
        if not self.source_health_file.exists():
            return {}
        try:
            data = json.loads(self.source_health_file.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {}
        if not isinstance(data, dict):
            return {}
        return {str(key): dict(value) for key, value in data.items() if isinstance(value, dict)}

    def _persist_source_health(self, health: dict[str, dict[str, Any]]) -> None:
        atomic_write(self.source_health_file, json.dumps(health, ensure_ascii=False, indent=2))

    @staticmethod
    def _new_activity_id(prefix: str) -> str:
        return f"{prefix}_{uuid4().hex}"

    @staticmethod
    def _normalize_status(status: str | JobStatus | None) -> str | None:
        if isinstance(status, JobStatus):
            return status.value
        if isinstance(status, str) and status in {item.value for item in JobStatus}:
            return status
        return None

    @staticmethod
    def _status_sort_key(activity: dict[str, Any]) -> tuple[int, str]:
        priority = {
            JobStatus.RUNNING.value: 0,
            JobStatus.PENDING.value: 1,
            JobStatus.FAILED.value: 2,
            JobStatus.COMPLETED.value: 3,
            JobStatus.CANCELLED.value: 4,
        }
        return (priority.get(str(activity.get("status")), 99), str(activity.get("created_at") or ""))

    def create_crawl_activity(
        self,
        *,
        novel_id: str,
        source_key: str,
        kind: CrawlJobKind | str = CrawlJobKind.CHAPTERS,
        chapters: str | None = "all",
        source_url: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        activity_kind = kind.value if isinstance(kind, CrawlJobKind) else str(kind)
        if activity_kind not in {item.value for item in CrawlJobKind}:
            raise ValueError(f"Unsupported crawl activity kind: {kind}")

        activity: dict[str, Any] = {
            "id": self._new_activity_id("crawl"),
            "type": "crawl",
            "kind": activity_kind,
            "novel_id": novel_id,
            "source_key": source_key,
            "chapters": chapters,
            "source_url": source_url,
            "status": JobStatus.PENDING.value,
            "created_at": _utc_now_iso(),
            "started_at": None,
            "finished_at": None,
            "retry_count": 0,
            "error": None,
            "metadata": dict(metadata or {}),
        }
        activity_log = self._load_activity()
        activity_log.append(activity)
        self._persist_activity(activity_log)
        return dict(activity)

    def create_translation_activity(
        self,
        *,
        novel_id: str,
        source_key: str | None = None,
        kind: TranslationJobKind | str = TranslationJobKind.TRANSLATE,
        chapters: str = "all",
        provider: str | None = None,
        model: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        activity_kind = kind.value if isinstance(kind, TranslationJobKind) else str(kind)
        if activity_kind not in {item.value for item in TranslationJobKind}:
            raise ValueError(f"Unsupported translation activity kind: {kind}")

        activity: dict[str, Any] = {
            "id": self._new_activity_id("translation"),
            "type": "translation",
            "kind": activity_kind,
            "novel_id": novel_id,
            "source_key": source_key,
            "chapters": chapters,
            "provider": provider,
            "model": model,
            "status": JobStatus.PENDING.value,
            "created_at": _utc_now_iso(),
            "started_at": None,
            "finished_at": None,
            "retry_count": 0,
            "error": None,
            "metadata": dict(metadata or {}),
        }
        activity_log = self._load_activity()
        activity_log.append(activity)
        self._persist_activity(activity_log)
        return dict(activity)

    def list_activity(
        self,
        *,
        status: str | JobStatus | None = None,
        activity_type: str | None = None,
        novel_id: str | None = None,
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        normalized_status = self._normalize_status(status)
        normalized_type = activity_type.strip().lower() if isinstance(activity_type, str) and activity_type.strip() else None
        if normalized_type is not None and normalized_type not in self.VALID_ACTIVITY_TYPES:
            raise ValueError(f"Unsupported activity type: {activity_type}")

        activity_log = self._load_activity()
        if normalized_status is not None:
            activity_log = [activity for activity in activity_log if activity.get("status") == normalized_status]
        if normalized_type is not None:
            activity_log = [activity for activity in activity_log if activity.get("type") == normalized_type]
        if isinstance(novel_id, str) and novel_id.strip():
            activity_log = [activity for activity in activity_log if activity.get("novel_id") == novel_id.strip()]

        activity_log.sort(key=self._status_sort_key)
        if limit is not None:
            activity_log = activity_log[: max(0, int(limit))]
        return [dict(activity) for activity in activity_log]

    def get_activity(self, activity_id: str) -> dict[str, Any] | None:
        for activity in self._load_activity():
            if activity.get("id") == activity_id:
                return dict(activity)
        return None

    def delete_activity(self, activity_id: str) -> bool:
        activity_log = self._load_activity()
        remaining = [activity for activity in activity_log if activity.get("id") != activity_id]
        if len(remaining) == len(activity_log):
            return False
        self._persist_activity(remaining)
        return True

    def update_activity_status(
        self,
        activity_id: str,
        status: JobStatus | str,
        *,
        error: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        normalized_status = self._normalize_status(status)
        if normalized_status is None:
            raise ValueError(f"Unsupported activity status: {status}")

        activity_log = self._load_activity()
        for index, activity in enumerate(activity_log):
            if activity.get("id") != activity_id:
                continue

            updated = dict(activity)
            previous_status = updated.get("status")
            updated["status"] = normalized_status
            if normalized_status == JobStatus.RUNNING.value and previous_status != JobStatus.RUNNING.value:
                updated["started_at"] = updated.get("started_at") or _utc_now_iso()
            if normalized_status in {
                JobStatus.COMPLETED.value,
                JobStatus.FAILED.value,
                JobStatus.CANCELLED.value,
            }:
                updated["finished_at"] = _utc_now_iso()
            if normalized_status == JobStatus.FAILED.value:
                updated["retry_count"] = int(updated.get("retry_count", 0) or 0) + 1
            updated["error"] = error if error is not None else None
            if isinstance(metadata, dict):
                existing_metadata = updated.get("metadata")
                merged_metadata: dict[str, Any] = dict(existing_metadata) if isinstance(existing_metadata, dict) else {}
                merged_metadata.update(metadata)
                updated["metadata"] = merged_metadata

            activity_log[index] = updated
            self._persist_activity(activity_log)
            return dict(updated)
        return None

    def next_pending_activity(self, *, activity_type: str | None = None) -> dict[str, Any] | None:
        pending = self.list_activity(status=JobStatus.PENDING, activity_type=activity_type, limit=1)
        return pending[0] if pending else None

    def record_source_health(
        self,
        source_key: str,
        *,
        success: bool,
        error: str | None = None,
    ) -> dict[str, Any]:
        normalized_source = source_key.strip() if isinstance(source_key, str) else ""
        if not normalized_source:
            raise ValueError("source_key is required.")

        health = self._load_source_health()
        now = _utc_now_iso()
        entry = dict(
            health.get(
                normalized_source,
                {
                    "source_key": normalized_source,
                    "success_count": 0,
                    "failure_count": 0,
                    "last_success_at": None,
                    "last_failure_at": None,
                    "last_error": None,
                    "updated_at": None,
                },
            )
        )

        if success:
            entry["success_count"] = int(entry.get("success_count", 0) or 0) + 1
            entry["last_success_at"] = now
            entry["last_error"] = None
        else:
            entry["failure_count"] = int(entry.get("failure_count", 0) or 0) + 1
            entry["last_failure_at"] = now
            entry["last_error"] = error
        entry["updated_at"] = now
        health[normalized_source] = entry
        self._persist_source_health(health)
        return dict(entry)

    def list_source_health(self) -> list[dict[str, Any]]:
        health = self._load_source_health()
        return [dict(health[key]) for key in sorted(health)]

    def get_source_health(self, source_key: str) -> dict[str, Any] | None:
        normalized_source = source_key.strip() if isinstance(source_key, str) else ""
        if not normalized_source:
            return None
        return self._load_source_health().get(normalized_source)

    def create_crawl_job(self, **kwargs: Any) -> dict[str, Any]:
        return self.create_crawl_activity(**kwargs)

    def create_translation_job(self, **kwargs: Any) -> dict[str, Any]:
        return self.create_translation_activity(**kwargs)

    def list_jobs(
        self,
        *,
        status: str | JobStatus | None = None,
        job_type: str | None = None,
        novel_id: str | None = None,
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        return self.list_activity(status=status, activity_type=job_type, novel_id=novel_id, limit=limit)

    def get_job(self, job_id: str) -> dict[str, Any] | None:
        return self.get_activity(job_id)

    def delete_job(self, job_id: str) -> bool:
        return self.delete_activity(job_id)

    def update_job_status(
        self,
        job_id: str,
        status: JobStatus | str,
        *,
        error: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        return self.update_activity_status(job_id, status, error=error, metadata=metadata)

    def next_pending_job(self, *, job_type: str | None = None) -> dict[str, Any] | None:
        return self.next_pending_activity(activity_type=job_type)


JobQueueService = ActivityQueueService
