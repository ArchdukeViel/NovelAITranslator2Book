from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from novelai.config.settings import settings
from novelai.core.platform import CrawlJobKind, JobStatus, TranslationJobKind
from novelai.utils import atomic_write


def _utc_now_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


class JobQueueService:
    """Small durable job queue used by the web/platform layer.

    The first implementation stores job records in one JSON file. That keeps
    the local-first app simple while giving crawler/translation work a real
    lifecycle that later workers can consume.
    """

    VALID_JOB_TYPES = {"crawl", "translation"}

    def __init__(self, base_dir: Path | None = None) -> None:
        self.base_dir = (base_dir or settings.DATA_DIR).resolve()
        self.jobs_dir = self.base_dir / "jobs"
        self.jobs_dir.mkdir(parents=True, exist_ok=True)
        self.jobs_file = self.jobs_dir / "queue.json"
        self.source_health_file = self.jobs_dir / "source_health.json"

    def _load_jobs(self) -> list[dict[str, Any]]:
        if not self.jobs_file.exists():
            return []
        try:
            data = json.loads(self.jobs_file.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return []
        if not isinstance(data, list):
            return []
        return [dict(item) for item in data if isinstance(item, dict)]

    def _persist_jobs(self, jobs: list[dict[str, Any]]) -> None:
        atomic_write(self.jobs_file, json.dumps(jobs, ensure_ascii=False, indent=2))

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
    def _new_job_id(prefix: str) -> str:
        return f"{prefix}_{uuid4().hex}"

    @staticmethod
    def _normalize_status(status: str | JobStatus | None) -> str | None:
        if isinstance(status, JobStatus):
            return status.value
        if isinstance(status, str) and status in {item.value for item in JobStatus}:
            return status
        return None

    @staticmethod
    def _status_sort_key(job: dict[str, Any]) -> tuple[int, str]:
        priority = {
            JobStatus.RUNNING.value: 0,
            JobStatus.PENDING.value: 1,
            JobStatus.FAILED.value: 2,
            JobStatus.COMPLETED.value: 3,
            JobStatus.CANCELLED.value: 4,
        }
        return (priority.get(str(job.get("status")), 99), str(job.get("created_at") or ""))

    def create_crawl_job(
        self,
        *,
        novel_id: str,
        source_key: str,
        kind: CrawlJobKind | str = CrawlJobKind.CHAPTERS,
        chapters: str | None = "all",
        source_url: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        job_kind = kind.value if isinstance(kind, CrawlJobKind) else str(kind)
        if job_kind not in {item.value for item in CrawlJobKind}:
            raise ValueError(f"Unsupported crawl job kind: {kind}")

        job: dict[str, Any] = {
            "id": self._new_job_id("crawl"),
            "type": "crawl",
            "kind": job_kind,
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
        jobs = self._load_jobs()
        jobs.append(job)
        self._persist_jobs(jobs)
        return dict(job)

    def create_translation_job(
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
        job_kind = kind.value if isinstance(kind, TranslationJobKind) else str(kind)
        if job_kind not in {item.value for item in TranslationJobKind}:
            raise ValueError(f"Unsupported translation job kind: {kind}")

        job: dict[str, Any] = {
            "id": self._new_job_id("translation"),
            "type": "translation",
            "kind": job_kind,
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
        jobs = self._load_jobs()
        jobs.append(job)
        self._persist_jobs(jobs)
        return dict(job)

    def list_jobs(
        self,
        *,
        status: str | JobStatus | None = None,
        job_type: str | None = None,
        novel_id: str | None = None,
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        normalized_status = self._normalize_status(status)
        normalized_type = job_type.strip().lower() if isinstance(job_type, str) and job_type.strip() else None
        if normalized_type is not None and normalized_type not in self.VALID_JOB_TYPES:
            raise ValueError(f"Unsupported job type: {job_type}")

        jobs = self._load_jobs()
        if normalized_status is not None:
            jobs = [job for job in jobs if job.get("status") == normalized_status]
        if normalized_type is not None:
            jobs = [job for job in jobs if job.get("type") == normalized_type]
        if isinstance(novel_id, str) and novel_id.strip():
            jobs = [job for job in jobs if job.get("novel_id") == novel_id.strip()]

        jobs.sort(key=self._status_sort_key)
        if limit is not None:
            jobs = jobs[: max(0, int(limit))]
        return [dict(job) for job in jobs]

    def get_job(self, job_id: str) -> dict[str, Any] | None:
        for job in self._load_jobs():
            if job.get("id") == job_id:
                return dict(job)
        return None

    def update_job_status(
        self,
        job_id: str,
        status: JobStatus | str,
        *,
        error: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        normalized_status = self._normalize_status(status)
        if normalized_status is None:
            raise ValueError(f"Unsupported job status: {status}")

        jobs = self._load_jobs()
        for index, job in enumerate(jobs):
            if job.get("id") != job_id:
                continue

            updated = dict(job)
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
                merged_metadata = dict(updated.get("metadata") if isinstance(updated.get("metadata"), dict) else {})
                merged_metadata.update(metadata)
                updated["metadata"] = merged_metadata

            jobs[index] = updated
            self._persist_jobs(jobs)
            return dict(updated)
        return None

    def next_pending_job(self, *, job_type: str | None = None) -> dict[str, Any] | None:
        pending = self.list_jobs(status=JobStatus.PENDING, job_type=job_type, limit=1)
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
