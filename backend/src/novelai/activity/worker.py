from __future__ import annotations

from typing import Any

from novelai.activity.queue import ActivityQueueService
from novelai.core.platform import CrawlJobKind, JobStatus, TranslationJobKind
from novelai.services.novel_orchestration_service import NovelOrchestrationService


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

    def _resolve_translation_source_key(self, activity: dict[str, Any]) -> str:
        source_key = activity.get("source_key")
        if isinstance(source_key, str) and source_key.strip():
            return source_key.strip()

        novel_id = str(activity.get("novel_id") or "")
        metadata = self.orchestrator.storage.load_metadata(novel_id) or {}
        metadata_source = metadata.get("source")
        if isinstance(metadata_source, str) and metadata_source.strip():
            return metadata_source.strip()

        raise ValueError("Translation activity requires source_key or stored metadata.source.")

    async def _run_crawl_activity(self, activity: dict[str, Any]) -> dict[str, Any]:
        kind = str(activity.get("kind") or "")
        metadata = self._activity_metadata(activity)
        novel_id = str(activity.get("novel_id") or "")
        source_key = str(activity.get("source_key") or "")
        if not novel_id.strip():
            raise ValueError("Crawl activity is missing novel_id.")
        if not source_key.strip():
            raise ValueError("Crawl activity is missing source_key.")

        mode = str(metadata.get("mode") or "update")
        if kind == CrawlJobKind.METADATA.value:
            max_chapter = metadata.get("max_chapter")
            if not isinstance(max_chapter, int):
                max_chapter = None
            result = await self.orchestrator.scrape_metadata(
                source_key,
                novel_id,
                mode=mode,
                max_chapter=max_chapter,
            )
            return {"chapter_count": len(result.get("chapters", [])) if isinstance(result, dict) else 0}

        if kind in {CrawlJobKind.CHAPTERS.value, CrawlJobKind.RECRAWL_CHAPTER.value}:
            chapters = activity.get("chapters")
            if not isinstance(chapters, str) or not chapters.strip():
                chapters = str(metadata.get("chapter_id") or "all")
            await self.orchestrator.scrape_chapters(
                source_key,
                novel_id,
                chapters,
                mode=mode,
            )
            return {"chapters": chapters}

        raise ValueError(f"Unsupported crawl activity kind: {kind}")

    async def _run_translation_activity(self, activity: dict[str, Any]) -> dict[str, Any]:
        kind = str(activity.get("kind") or "")
        if kind not in {item.value for item in TranslationJobKind}:
            raise ValueError(f"Unsupported translation activity kind: {kind}")

        metadata = self._activity_metadata(activity)
        novel_id = str(activity.get("novel_id") or "")
        if not novel_id.strip():
            raise ValueError("Translation activity is missing novel_id.")

        chapters = activity.get("chapters")
        if not isinstance(chapters, str) or not chapters.strip():
            chapters = "all"

        provider = activity.get("provider") if isinstance(activity.get("provider"), str) else None
        model = activity.get("model") if isinstance(activity.get("model"), str) else None
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

        await self.orchestrator.translate_chapters(
            self._resolve_translation_source_key(activity),
            novel_id,
            chapters,
            provider_key=provider,
            provider_model=model,
            force=force,
            source_language=source_language,
            target_language=target_language,
        )
        return {"chapters": chapters, "force": force, "target_language": target_language or "English"}

    async def run_activity(self, activity_id: str) -> dict[str, Any] | None:
        activity = self.activity_log.get_activity(activity_id)
        if activity is None:
            return None

        if activity.get("status") in {JobStatus.RUNNING.value, JobStatus.COMPLETED.value, JobStatus.CANCELLED.value}:
            raise ValueError(f"Activity cannot be run from status: {activity.get('status')}")

        activity_metadata = {
            "activity_subtype": self._activity_subtype(activity),
            "activity_phase": self._activity_phase(activity),
        }
        self.activity_log.update_activity_status(activity_id, JobStatus.RUNNING, metadata=activity_metadata)
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
            failed = self.activity_log.update_activity_status(
                activity_id,
                JobStatus.FAILED,
                error=str(exc),
                metadata={
                    **activity_metadata,
                    "failure_code": self._failure_code(activity),
                    "failure_category": activity_metadata["activity_subtype"],
                    "failure_explanation": str(exc),
                },
            )
            if failed is None:
                raise
            return failed

        completed = self.activity_log.update_activity_status(
            activity_id,
            JobStatus.COMPLETED,
            metadata={**activity_metadata, "result": result_metadata},
        )
        return completed

    async def run_next(self, *, activity_type: str | None = None, job_type: str | None = None) -> dict[str, Any] | None:
        activity = self.activity_log.next_pending_activity(activity_type=activity_type or job_type)
        if activity is None:
            return None
        return await self.run_activity(str(activity["id"]))

    async def run_job(self, job_id: str) -> dict[str, Any] | None:
        return await self.run_activity(job_id)


JobWorkerService = ActivityWorkerService
