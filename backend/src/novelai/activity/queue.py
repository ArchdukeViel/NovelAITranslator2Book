from __future__ import annotations

import json
import logging
import threading
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from novelai.config.settings import settings
from novelai.core.platform import CrawlJobKind, JobStatus, TranslationJobKind
from novelai.utils import atomic_write

logger = logging.getLogger(__name__)


def EnrichSourceHealthFromCrawlResult(
    crawl_result: dict[str, Any],
) -> dict[str, Any]:
    succeeded = int(crawl_result.get("succeeded") or 0)
    skipped = int(crawl_result.get("skipped") or 0)
    failed = int(crawl_result.get("failed") or 0)
    failures: list[dict[str, Any]] = crawl_result.get("failures") or []

    error_category_counts: dict[str, int] = {}
    http_status_counts: dict[str, int] = {}

    for f in failures:
        cat = f.get("error_category") or "unknown"
        error_category_counts[cat] = error_category_counts.get(cat, 0) + 1

        status_code = f.get("http_status_code")
        if status_code is not None:
            http_status_counts[str(status_code)] = http_status_counts.get(str(status_code), 0) + 1

    return {
        "total_chapters_attempted": succeeded + skipped + failed,
        "total_chapters_succeeded": succeeded,
        "total_chapters_failed": failed,
        "error_category_counts": error_category_counts,
        "http_status_counts": http_status_counts,
    }


def _utc_now_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


class ActivityQueueService:
    """Small durable activity queue used by the web/platform layer.

    Records are still stored in one JSON file. The public concept is activity:
    preliminary crawl, scraping, translation, and future workflow phases.
    """

    VALID_ACTIVITY_TYPES = {"crawl", "translation"}
    ACTIVE_STATUSES = {
        JobStatus.PENDING.value,
        JobStatus.RUNNING.value,
        JobStatus.PAUSED.value,
        JobStatus.PAUSED_UNTIL_COOLDOWN.value,
        JobStatus.PAUSED_UNTIL_QUOTA_RESET.value,
    }
    ACTIVITY_LOG_DIRNAME = "activity_log"
    LEGACY_JOBS_DIRNAME = "jobs"
    DEFAULT_PRUNE_KEEP_COMPLETED = 200
    DEFAULT_PRUNE_KEEP_FAILED = 100
    SOURCE_HEALTH_CACHE_TTL = 60.0

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
        self._lock = threading.Lock()
        self._source_health_cache: dict[str, tuple[float, Any]] = {}
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
            JobStatus.PAUSED.value: 1,
            JobStatus.PAUSED_UNTIL_COOLDOWN.value: 1,
            JobStatus.PAUSED_UNTIL_QUOTA_RESET.value: 1,
            JobStatus.PENDING.value: 2,
            JobStatus.FAILED.value: 3,
            JobStatus.COMPLETED.value: 4,
            JobStatus.CANCELLED.value: 5,
        }
        return (priority.get(str(activity.get("status")), 99), str(activity.get("created_at") or ""))

    @staticmethod
    def _newest_activity_sort_key(activity: dict[str, Any]) -> str:
        return str(activity.get("finished_at") or activity.get("started_at") or activity.get("created_at") or "")

    def prune_activity_log(
        self,
        *,
        keep_completed: int = DEFAULT_PRUNE_KEEP_COMPLETED,
        keep_failed: int = DEFAULT_PRUNE_KEEP_FAILED,
        dry_run: bool = True,
    ) -> dict[str, Any]:
        """Prune old terminal activity records while preserving active/retryable work.

        This helper is intentionally opt-in. Pending/running/paused records are
        always kept, and failed/cancelled records are kept by a separate bound so
        recent retry context remains available.
        """
        if not self.activity_file.exists():
            return {"dry_run": dry_run, "deleted": 0, "candidates": [], "kept": 0}

        keep_completed = max(0, int(keep_completed))
        keep_failed = max(0, int(keep_failed))
        activity_log = self._load_activity()
        completed_like = [
            activity
            for activity in activity_log
            if str(activity.get("status")) == JobStatus.COMPLETED.value
        ]
        failed_like = [
            activity
            for activity in activity_log
            if str(activity.get("status")) in {JobStatus.FAILED.value, JobStatus.CANCELLED.value}
        ]

        completed_like.sort(key=self._newest_activity_sort_key, reverse=True)
        failed_like.sort(key=self._newest_activity_sort_key, reverse=True)
        candidate_ids = {
            str(activity.get("id"))
            for activity in [*completed_like[keep_completed:], *failed_like[keep_failed:]]
            if activity.get("id") is not None
        }

        candidates = [activity for activity in activity_log if str(activity.get("id")) in candidate_ids]
        if not dry_run and candidate_ids:
            remaining = [
                activity
                for activity in activity_log
                if str(activity.get("status")) in self.ACTIVE_STATUSES or str(activity.get("id")) not in candidate_ids
            ]
            self._persist_activity(remaining)
        return {
            "dry_run": dry_run,
            "deleted": 0 if dry_run else len(candidates),
            "candidates": [dict(activity) for activity in candidates],
            "kept": len(activity_log) if dry_run else len(self._load_activity()),
        }

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
            "provider_key": provider,
            "provider_model": model,
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
            self._invalidate_source_health_cache()
            return dict(updated)
        return None

    def update_activity_metadata(self, activity_id: str, patch: dict[str, Any]) -> bool:
        with self._lock:
            activity_log = self._load_activity()
            for _index, act in enumerate(activity_log):
                if act.get("id") == activity_id:
                    break
            else:
                return False

            activity = dict(act)
            metadata = dict(activity.get("metadata") or {})
            patch = dict(patch or {})

            if isinstance(patch.get("progress"), dict):
                progress = dict(metadata.get("progress") or {})
                progress.update(patch["progress"])
                patch["progress"] = progress

            metadata.update(patch)

            existing_meta = activity.get("metadata")
            merged: dict[str, Any] = dict(existing_meta) if isinstance(existing_meta, dict) else {}
            merged.update(metadata)
            activity["metadata"] = merged
            activity_log[_index] = activity
            self._persist_activity(activity_log)
            self._invalidate_source_health_cache()
            return True

    def _invalidate_source_health_cache(self) -> None:
        self._source_health_cache.clear()

    def retry_activity(self, activity_id: str) -> dict[str, Any] | None:
        activity_log = self._load_activity()
        for index, activity in enumerate(activity_log):
            if activity.get("id") != activity_id:
                continue

            current_status = str(activity.get("status") or "")
            if current_status not in {JobStatus.FAILED.value, JobStatus.CANCELLED.value}:
                raise ValueError(f"Activity cannot be retried from status: {current_status}")

            updated = dict(activity)
            metadata = updated.get("metadata")
            updated_metadata: dict[str, Any] = dict(metadata) if isinstance(metadata, dict) else {}
            retry_history = updated_metadata.get("retry_history")
            if not isinstance(retry_history, list):
                retry_history = []
            previous_metadata = dict(updated_metadata)
            previous_metadata.pop("retry_history", None)
            retry_history.append(
                {
                    "status": current_status,
                    "error": updated.get("error"),
                    "finished_at": updated.get("finished_at"),
                    "retry_count": int(updated.get("retry_count", 0) or 0),
                    "metadata": previous_metadata,
                }
            )
            updated_metadata["retry_history"] = retry_history
            updated_metadata["current_stage"] = "queued"
            updated_metadata["current_label"] = None
            updated_metadata["errors"] = []
            updated_metadata["paused_reason"] = None
            updated_metadata["resume_after"] = None
            for stale_key in (
                "failure_code",
                "failure_category",
                "failure_explanation",
                "provider_error",
                "provider_error_code",
                "retry_after_seconds",
                "cooldown_until",
                "exhausted_until",
            ):
                updated_metadata.pop(stale_key, None)

            updated["status"] = JobStatus.PENDING.value
            updated["started_at"] = None
            updated["finished_at"] = None
            updated["retry_count"] = int(updated.get("retry_count", 0) or 0) + 1
            updated["error"] = None
            updated["metadata"] = updated_metadata

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
        self._invalidate_source_health_cache()
        return self._build_source_health_envelope(normalized_source, entry)

    @staticmethod
    def _build_source_health_envelope(
        source_key: str, legacy: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        legacy = legacy or {}
        return {
            "source_key": source_key,
            "success_count": int(legacy.get("success_count", 0) or 0),
            "failure_count": int(legacy.get("failure_count", 0) or 0),
            "last_success_at": legacy.get("last_success_at"),
            "last_failure_at": legacy.get("last_failure_at"),
            "last_error": legacy.get("last_error"),
            "updated_at": legacy.get("updated_at"),
            "total_chapters_attempted": 0,
            "total_chapters_succeeded": 0,
            "total_chapters_failed": 0,
            "error_category_counts": {},
            "http_status_counts": {},
            "last_crawl_at": legacy.get("last_success_at") or legacy.get("last_failure_at"),
        }

    @staticmethod
    def _aggregate_crawl_into(envelope: dict[str, Any], activity: dict[str, Any]) -> None:
        crawl_result = activity.get("metadata", {}).get("crawl_result")
        if not isinstance(crawl_result, dict):
            return

        enriched = EnrichSourceHealthFromCrawlResult(crawl_result)
        envelope["total_chapters_attempted"] += enriched["total_chapters_attempted"]
        envelope["total_chapters_succeeded"] += enriched["total_chapters_succeeded"]
        envelope["total_chapters_failed"] += enriched["total_chapters_failed"]

        for cat, cnt in enriched["error_category_counts"].items():
            envelope["error_category_counts"][cat] = envelope["error_category_counts"].get(cat, 0) + cnt
        for sc, cnt in enriched["http_status_counts"].items():
            envelope["http_status_counts"][sc] = envelope["http_status_counts"].get(sc, 0) + cnt

        ts = activity.get("finished_at") or activity.get("started_at")
        if ts:
            existing_ts = envelope.get("last_crawl_at")
            if not existing_ts or str(ts) > str(existing_ts):
                envelope["last_crawl_at"] = str(ts)

    def list_source_health(self) -> list[dict[str, Any]]:
        now = time.monotonic()
        cached = self._source_health_cache.get("_list")
        if cached is not None and (now - cached[0]) < self.SOURCE_HEALTH_CACHE_TTL:
            return cached[1]

        envelopes: dict[str, dict[str, Any]] = {}
        legacy_map = self._load_source_health()
        for activity in self._load_activity():
            if str(activity.get("type")) != "crawl":
                continue
            source_key = str(activity.get("source_key") or "")
            if not source_key:
                continue
            if source_key not in envelopes:
                envelopes[source_key] = self._build_source_health_envelope(
                    source_key, legacy_map.get(source_key)
                )
            self._aggregate_crawl_into(envelopes[source_key], activity)

        for source_key in legacy_map:
            if source_key not in envelopes:
                envelopes[source_key] = self._build_source_health_envelope(
                    source_key, legacy_map[source_key]
                )

        result = [dict(envelopes[k]) for k in sorted(envelopes)]
        self._source_health_cache["_list"] = (now, result)
        return result

    def get_source_health(self, source_key: str) -> dict[str, Any] | None:
        normalized_source = source_key.strip() if isinstance(source_key, str) else ""
        if not normalized_source:
            return None

        cache_key = f"_src:{normalized_source}"
        now = time.monotonic()
        cached = self._source_health_cache.get(cache_key)
        if cached is not None and (now - cached[0]) < self.SOURCE_HEALTH_CACHE_TTL:
            return cached[1]

        legacy_map = self._load_source_health()
        envelope = self._build_source_health_envelope(
            normalized_source, legacy_map.get(normalized_source)
        )
        found_crawl = False
        for activity in self._load_activity():
            if str(activity.get("type")) != "crawl":
                continue
            if str(activity.get("source_key") or "") != normalized_source:
                continue
            crawl_result = activity.get("metadata", {}).get("crawl_result")
            if not isinstance(crawl_result, dict):
                continue
            self._aggregate_crawl_into(envelope, activity)
            found_crawl = True

        if not found_crawl and envelope["success_count"] == 0 and envelope["failure_count"] == 0:
            result: dict[str, Any] | None = None
        else:
            result = dict(envelope)

        if result is not None:
            self._source_health_cache[cache_key] = (now, result)
        return result

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
