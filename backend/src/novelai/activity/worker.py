from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime
from typing import Any

from novelai.activity.queue import ActivityQueueService
from novelai.core.errors import ProviderError
from novelai.core.platform import CrawlJobKind, JobStatus, TranslationJobKind
from novelai.services.export_manifest_service import check_all_exports_freshness
from novelai.services.glossary_diagnostics import aggregate_glossary_diagnostics
from novelai.services.novel_orchestration_service import NovelOrchestrationService

logger = logging.getLogger(__name__)


def _utc_now_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


class ActivityWorkerService:
    """Executes queued crawl and translation activity through the orchestrator."""

    def __init__(self, activity_log: ActivityQueueService, orchestrator: NovelOrchestrationService) -> None:
        self.activity_log = activity_log
        self.jobs = activity_log
        self.orchestrator = orchestrator

    @staticmethod
    def _activity_metadata(activity: dict[str, Any]) -> dict[str, Any]:
        metadata = activity.get("metadata")
        return dict(metadata) if isinstance(metadata, dict) else {}

    def _activity_subtype(self, activity: dict[str, Any]) -> str:
        metadata = self._activity_metadata(activity)
        configured = metadata.get("activity_subtype")
        if isinstance(configured, str) and configured.strip():
            return configured.strip()

        if activity.get("type") == "translation":
            return "translating"

        if activity.get("type") == "crawl":
            kind = str(activity.get("kind") or "")
            if kind == CrawlJobKind.METADATA.value:
                return "crawling"
            if kind in {CrawlJobKind.CHAPTERS.value, CrawlJobKind.RECRAWL_CHAPTER.value}:
                return "scraping"

        return str(activity.get("type") or "activity")

    def _activity_phase(self, activity: dict[str, Any]) -> str:
        metadata = self._activity_metadata(activity)
        configured = metadata.get("activity_phase")
        if isinstance(configured, str) and configured.strip():
            return configured.strip()

        if activity.get("type") == "translation":
            return str(activity.get("kind") or TranslationJobKind.TRANSLATE.value)

        if activity.get("type") == "crawl":
            kind = str(activity.get("kind") or "")
            if kind == CrawlJobKind.METADATA.value:
                return "preliminary_crawl" if metadata.get("preliminary_crawl") else "metadata_crawl"
            if kind == CrawlJobKind.RECRAWL_CHAPTER.value:
                return "chapter_recrawl"
            if kind == CrawlJobKind.CHAPTERS.value:
                return "chapter_scrape"

        return str(activity.get("kind") or "activity")

    def _failure_code(self, activity: dict[str, Any]) -> str:
        subtype = self._activity_subtype(activity)
        if subtype == "scraping":
            return "SCRAPE_ACTIVITY_FAILED"
        if subtype == "crawling":
            return "CRAWL_ACTIVITY_FAILED"
        if subtype == "translating":
            return "TRANSLATION_ACTIVITY_FAILED"
        return "ACTIVITY_FAILED"

    @staticmethod
    def _provider_failure_metadata(activity: dict[str, Any], exc: BaseException) -> dict[str, Any]:
        if not isinstance(exc, ProviderError):
            return {}

        metadata = activity.get("metadata")
        activity_metadata = dict(metadata) if isinstance(metadata, dict) else {}
        activity_id = str(activity.get("id") or "")
        provider_payload = {
            **exc.activity_details(),
            "activity_id": activity_id,
            "job_id": activity_id,
            "novel_id": str(activity.get("novel_id") or ""),
            "chapter_id": activity_metadata.get("chapter_id"),
            "chunk_id": exc.details.get("chunk_id"),
            "attempt_number": exc.details.get("attempt_number", int(activity.get("retry_count", 0) or 0) + 1),
            "timestamp": _utc_now_iso(),
        }
        return {
            "provider_key": exc.provider_key,
            "provider_model": exc.provider_model,
            "provider_error_code": exc.provider_error_code.value,
            "retry_after_seconds": exc.retry_after_seconds,
            "cooldown_until": exc.cooldown_until,
            "exhausted_until": exc.exhausted_until,
            "requests_this_minute": exc.requests_this_minute,
            "requests_today": exc.requests_today,
            "provider_error": provider_payload,
        }

    @staticmethod
    def _pause_status(exc: BaseException) -> JobStatus | None:
        paused_reason = getattr(exc, "paused_reason", None)
        if not isinstance(paused_reason, str) or not paused_reason.strip():
            return None
        if paused_reason == "all_models_cooling_down":
            return JobStatus.PAUSED_UNTIL_COOLDOWN
        if paused_reason == "all_models_daily_exhausted":
            return JobStatus.PAUSED_UNTIL_QUOTA_RESET
        return JobStatus.PAUSED

    def _resolve_translation_source_key(self, activity: dict[str, Any]) -> str:
        source_key = activity.get("source_key")
        if isinstance(source_key, str) and source_key.strip():
            return source_key.strip()

        novel_id = str(activity.get("novel_id") or "")
        metadata = self.orchestrator.storage.load_metadata(novel_id) or {}
        metadata_source = metadata.get("source_key")
        if isinstance(metadata_source, str) and metadata_source.strip():
            return metadata_source.strip()

        raise ValueError("Translation activity requires source_key or stored metadata.source_key.")

    @staticmethod
    def _resolve_current_glossary_revision(novel_id: str) -> int | None:
        """Resolve the current glossary revision for a novel.

        Opens a temporary DB session to read the value. Returns None
        when the novel or revision field cannot be resolved.
        """
        try:
            from novelai.db.engine import session_scope
            from novelai.db.models.novel import Novel

            with session_scope() as session:
                novel = session.query(Novel).filter_by(slug=novel_id).one_or_none()
                if novel is not None:
                    return int(novel.glossary_revision or 0)
        except Exception:
            return None
        return None

    def _check_cancelled(self, activity_id: str) -> None:
        """Raise ``CancelledError`` if the activity has been cancelled."""
        if self.activity_log.is_activity_cancelled(activity_id):
            raise asyncio.CancelledError(f"Activity {activity_id} was cancelled by user")

    async def _run_crawl_activity(self, activity: dict[str, Any]) -> dict[str, Any]:
        kind = str(activity.get("kind") or "")
        metadata = self._activity_metadata(activity)
        novel_id = str(activity.get("novel_id") or "")
        source_key = str(activity.get("source_key") or "")
        activity_id = str(activity.get("id") or "")
        if not novel_id.strip():
            raise ValueError("Crawl activity is missing novel_id.")
        if not source_key.strip():
            raise ValueError("Crawl activity is missing source_key.")

        self._check_cancelled(activity_id)

        mode = str(metadata.get("mode") or "update")
        if kind == CrawlJobKind.METADATA.value:
            max_chapter = metadata.get("max_chapter")
            if not isinstance(max_chapter, int):
                max_chapter = None
            self._check_cancelled(activity_id)
            result = await self.orchestrator.scrape_metadata(
                source_key,
                novel_id,
                mode=mode,
                max_chapter=max_chapter,
            )
            self._check_cancelled(activity_id)
            return {"chapter_count": len(result.get("chapters", [])) if isinstance(result, dict) else 0}

        if kind in {CrawlJobKind.CHAPTERS.value, CrawlJobKind.RECRAWL_CHAPTER.value}:
            chapters = activity.get("chapters")
            if not isinstance(chapters, str) or not chapters.strip():
                chapters = str(metadata.get("chapter_id") or "all")

            meta = self.orchestrator.storage.load_metadata(novel_id) or {}
            chapter_list = meta.get("chapters")
            total = len(chapter_list) if isinstance(chapter_list, list) else None

            completed = [0]

            def _cancelled_check() -> bool:
                return self.activity_log.is_activity_cancelled(activity_id)

            def _progress_callback(message: str) -> None:
                completed[0] += 1
                try:
                    self.activity_log.update_activity_metadata(
                        activity_id,
                        {
                            "progress": {
                                "completed": completed[0],
                                "total": total,
                                "current_label": message,
                            }
                        },
                    )
                except Exception:
                    logger.debug("Failed to update crawl progress", exc_info=True)

            self._check_cancelled(activity_id)
            result = await self.orchestrator.scrape_chapters(
                source_key,
                novel_id,
                chapters,
                mode=mode,
                progress_callback=_progress_callback,
                cancellation_check=_cancelled_check,
            )

            self._check_cancelled(activity_id)
            crawl_result = {
                "succeeded": result.get("succeeded", 0),
                "skipped": result.get("skipped", 0),
                "failed": result.get("failed", 0),
                "failures": result.get("failures", []),
                "image_download_failures": result.get("image_download_failures", 0),
            }
            self.activity_log.update_activity_metadata(activity_id, {"crawl_result": crawl_result})

            return {"chapters": chapters, "crawl_result": crawl_result}

        raise ValueError(f"Unsupported crawl activity kind: {kind}")

    async def _run_translation_activity(self, activity: dict[str, Any]) -> dict[str, Any]:
        kind = str(activity.get("kind") or "")
        if kind not in {item.value for item in TranslationJobKind}:
            raise ValueError(f"Unsupported translation activity kind: {kind}")

        metadata = self._activity_metadata(activity)
        novel_id = str(activity.get("novel_id") or "")
        if not novel_id.strip():
            raise ValueError("Translation activity is missing novel_id.")

        # Detect stale scheduled glossary snapshot (REQ-11).
        # If the scheduled glossary revision differs from the current
        # revision, cancel this job and reschedule with current glossary.
        scheduled_revision = metadata.get("scheduled_glossary_revision")
        if isinstance(scheduled_revision, int):
            try:
                current_revision = self._resolve_current_glossary_revision(novel_id)
                if current_revision != scheduled_revision:
                    logger.info(
                        "Translation job %s stale: scheduled_glossary_revision=%d != current=%d. "
                        "Cancelling and rescheduling.",
                        activity.get("id"),
                        scheduled_revision,
                        current_revision,
                    )
                    # Cancel this activity and reschedule a new one with current revision
                    meta = self.orchestrator.storage.load_metadata(novel_id) or {}
                    source_key = meta.get("source_key") or activity.get("source_key") or ""
                    new_activity = self.activity_log.create_translation_activity(
                        novel_id=novel_id,
                        source_key=str(source_key),
                        kind=kind,
                        chapters=str(activity.get("chapters") or "all"),
                        provider_key=activity.get("provider_key"),
                        provider_model=activity.get("provider_model"),
                        metadata={
                            **metadata,
                            "scheduled_glossary_revision": current_revision,
                            "stale_before_run": True,
                            "previous_activity_id": str(activity.get("id") or ""),
                        },
                    )
                    self.activity_log.update_activity_status(
                        str(activity["id"]),
                        "cancelled",
                        error=f"Stale glossary: revision {scheduled_revision} -> {current_revision}",
                    )
                    return {
                        "chapters": activity.get("chapters") or "all",
                        "stale_before_run": True,
                        "rescheduled_activity_id": new_activity.get("id"),
                    }
            except Exception:
                logger.debug("Failed to check glossary revision freshness", exc_info=True)

        chapters = activity.get("chapters")
        if not isinstance(chapters, str) or not chapters.strip():
            chapters = "all"

        provider_value = activity.get("provider_key")
        model_value = activity.get("provider_model")
        provider = provider_value if isinstance(provider_value, str) else None
        model = model_value if isinstance(model_value, str) else None
        source_language = (
            metadata.get("source_language")
            if isinstance(metadata.get("source_language"), str)
            else None
        )
        target_language = (
            metadata.get("target_language")
            if isinstance(metadata.get("target_language"), str)
            else None
        )
        force = bool(metadata.get("force")) or kind in {
            TranslationJobKind.RETRANSLATE.value,
            TranslationJobKind.BATCH_RETRANSLATE.value,
        }
        allow_cross_provider_fallback = metadata.get("allow_cross_provider_fallback", True) is not False
        skip_glossary_gate = metadata.get("skip_glossary_gate") is True

        summary = await self.orchestrator.translate_chapters(
            self._resolve_translation_source_key(activity),
            novel_id,
            chapters,
            provider_key=provider,
            provider_model=model,
            job_id=str(activity.get("id") or ""),
            activity_id=str(activity.get("id") or ""),
            force=force,
            source_language=source_language,
            target_language=target_language,
            allow_cross_provider_fallback=allow_cross_provider_fallback,
            skip_glossary_gate=skip_glossary_gate,
        )
        result: dict[str, Any] = {
            "chapters": chapters,
            "force": force,
            "target_language": target_language or "English",
        }
        if isinstance(summary, dict):
            chapter_progress = summary.get("chapter_progress")
            if isinstance(chapter_progress, dict):
                result["chapter_progress"] = chapter_progress
            for key in ("succeeded", "failed", "skipped", "total"):
                if key in summary:
                    result[key] = summary[key]
            scheduler_summary = summary.get("scheduler_summary")
            if isinstance(scheduler_summary, dict):
                result["scheduler_summary"] = scheduler_summary
            # Aggregate glossary diagnostics across chapters (REQ-1.2)
            chapter_diagnostics = summary.get("glossary_diagnostics")
            if isinstance(chapter_diagnostics, list):
                result["glossary_diagnostics_summary"] = aggregate_glossary_diagnostics(chapter_diagnostics)
        return result

    async def run_activity(self, activity_id: str) -> dict[str, Any] | None:
        activity = self.activity_log.get_activity(activity_id)
        if activity is None:
            return None

        if activity.get("status") != JobStatus.PENDING.value:
            raise ValueError(f"Activity cannot be run from status: {activity.get('status')}")

        activity_metadata = {
            "activity_subtype": self._activity_subtype(activity),
            "activity_phase": self._activity_phase(activity),
            "current_stage": "queued",
            "current_label": None,
            "errors": [],
            "warnings": [],
            "completed": 0,
            "total": None,
            "paused_reason": None,
            "resume_after": None,
            "model_states": [],
        }
        self.activity_log.update_activity_status(
            activity_id,
            JobStatus.RUNNING,
            metadata={**activity_metadata, "current_stage": "running"},
        )
        try:
            if activity.get("type") == "crawl":
                result_metadata = await self._run_crawl_activity(activity)
                self.activity_log.record_source_health(str(activity.get("source_key") or ""), success=True)
            elif activity.get("type") == "translation":
                result_metadata = await self._run_translation_activity(activity)
            else:
                raise ValueError(f"Unsupported activity type: {activity.get('type')}")
        except Exception as exc:
            if (
                activity.get("type") == "crawl"
                and isinstance(activity.get("source_key"), str)
                and str(activity.get("source_key") or "").strip()
            ):
                self.activity_log.record_source_health(str(activity.get("source_key") or ""), success=False, error=str(exc))
            # Per-chapter progress attached by the orchestrator for partial-failure
            # summary (REQ-3.3).  Surface it on both the paused and failed paths.
            chapter_progress = getattr(exc, "chapter_progress", None)
            if not isinstance(chapter_progress, dict):
                chapter_progress = None
            chapter_summary = getattr(exc, "chapter_summary", None)
            if not isinstance(chapter_summary, dict):
                chapter_summary = None
            if isinstance(exc, asyncio.CancelledError):
                cancelled_metadata: dict[str, Any] = {
                    **activity_metadata,
                    "current_stage": "cancelled",
                    "cancelled_by": "owner",
                    "errors": [{"message": str(exc), "error_code": "CANCELLED"}],
                }
                cancelled = self.activity_log.update_activity_status(
                    activity_id,
                    JobStatus.CANCELLED,
                    error=str(exc),
                    metadata=cancelled_metadata,
                )
                if cancelled is None:
                    raise
                return cancelled

            paused_status = self._pause_status(exc)
            if paused_status is not None:
                paused_metadata: dict[str, Any] = {
                    **activity_metadata,
                    "current_stage": "paused",
                    "status": "paused",
                    "paused_reason": getattr(exc, "paused_reason", None),
                    "resume_after": getattr(exc, "resume_after", None),
                    "model_states": getattr(exc, "model_states", []),
                    "errors": [
                        {
                            "message": str(exc),
                            "error_code": getattr(exc, "error_code", exc.__class__.__name__),
                        }
                    ],
                }
                if chapter_progress is not None:
                    paused_metadata["chapter_progress"] = chapter_progress
                if chapter_summary is not None:
                    paused_metadata["chapter_summary"] = chapter_summary
                paused = self.activity_log.update_activity_status(
                    activity_id,
                    paused_status,
                    error=str(exc),
                    metadata=paused_metadata,
                )
                if paused is None:
                    raise
                return paused
            failed_metadata: dict[str, Any] = {
                **activity_metadata,
                **self._provider_failure_metadata(activity, exc),
                "current_stage": "failed",
                "errors": [{"message": str(exc), "error_code": getattr(getattr(exc, "provider_error_code", None), "value", exc.__class__.__name__)}],
                "failure_code": self._failure_code(activity),
                "failure_category": activity_metadata["activity_subtype"],
                "failure_explanation": str(exc),
            }
            if chapter_progress is not None:
                failed_metadata["chapter_progress"] = chapter_progress
            if chapter_summary is not None:
                failed_metadata["chapter_summary"] = chapter_summary
            failed = self.activity_log.update_activity_status(
                activity_id,
                JobStatus.FAILED,
                error=str(exc),
                metadata=failed_metadata,
            )
            if failed is None:
                raise
            return failed

        completed = self.activity_log.update_activity_status(
            activity_id,
            JobStatus.COMPLETED,
            metadata={**activity_metadata, "current_stage": "completed", "completed": 1, "result": result_metadata},
        )
        return completed

    async def run_next(self, *, activity_type: str | None = None) -> dict[str, Any] | None:
        activity = self.activity_log.next_pending_activity(activity_type=activity_type)
        if activity is None:
            return None
        return await self.run_activity(str(activity["id"]))

    async def retry_activity(self, activity_id: str) -> dict[str, Any] | None:
        return self.activity_log.retry_activity(activity_id)



async def run_export_freshness_check(
    storage,
    *,
    interval_seconds: int = 3600,
    stop_event: asyncio.Event | None = None,
) -> None:
    """Run the export freshness check as a background task.

    This can be started as a background task alongside the activity worker.
    """
    await check_all_exports_freshness(
        storage,
        interval_seconds=interval_seconds,
        stop_event=stop_event,
    )
