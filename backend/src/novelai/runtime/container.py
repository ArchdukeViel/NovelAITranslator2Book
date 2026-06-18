from __future__ import annotations

from dataclasses import dataclass

from novelai.activity.queue import ActivityQueueService
from novelai.activity.runner import BackgroundActivityRunner
from novelai.activity.worker import ActivityWorkerService
from novelai.config.settings import settings
from novelai.providers.registry import get_provider
from novelai.services.export_service import ExportService
from novelai.services.novel_request_service import NovelRequestService
from novelai.services.novel_orchestration_service import NovelOrchestrationService
from novelai.services.preferences_service import PreferencesService
from novelai.storage.service import StorageService
from novelai.services.translation_cache import TranslationCache
from novelai.translation.service import TranslationService
from novelai.services.usage_service import UsageService


@dataclass
class Container:
    """Application dependency container.

    This is a simple, explicit DI container used to create and reuse shared
    services throughout the web backend and background worker.

    All services are singletons: instantiated once and reused.
    """

    _storage: StorageService | None = None
    _translation_cache: TranslationCache | None = None
    _settings: PreferencesService | None = None
    _preferences: PreferencesService | None = None
    _usage: UsageService | None = None
    _activity_log: ActivityQueueService | None = None
    _requests: NovelRequestService | None = None
    _translation: TranslationService | None = None
    _export: ExportService | None = None
    _orchestrator: NovelOrchestrationService | None = None
    _activity_worker: ActivityWorkerService | None = None
    _activity_runner: BackgroundActivityRunner | None = None

    @property
    def storage(self) -> StorageService:
        if self._storage is None:
            self._storage = StorageService()
        return self._storage

    @property
    def translation_cache(self) -> TranslationCache:
        if self._translation_cache is None:
            self._translation_cache = TranslationCache()
        return self._translation_cache

    @property
    def settings(self) -> PreferencesService:
        if self._settings is None:
            self._settings = PreferencesService()
        return self._settings

    @property
    def preferences(self) -> PreferencesService:
        # Compatibility alias: older code asks for "preferences" while the
        # translation pipeline asks for "settings". They must share one live
        # service so admin changes affect translation immediately.
        return self.settings

    @property
    def usage(self) -> UsageService:
        if self._usage is None:
            self._usage = UsageService()
        return self._usage

    @property
    def activity_log(self) -> ActivityQueueService:
        if self._activity_log is None:
            self._activity_log = ActivityQueueService()
        return self._activity_log

    @property
    def jobs(self) -> ActivityQueueService:
        return self.activity_log

    @property
    def requests(self) -> NovelRequestService:
        # Deprecated legacy file-backed request service. Admin/public request
        # moderation must use DB-backed NovelRequest rows instead.
        if self._requests is None:
            self._requests = NovelRequestService()
        return self._requests

    @property
    def activity_worker(self) -> ActivityWorkerService:
        if self._activity_worker is None:
            self._activity_worker = ActivityWorkerService(self.activity_log, self.orchestrator)
        return self._activity_worker

    @property
    def job_worker(self) -> ActivityWorkerService:
        return self.activity_worker

    @property
    def activity_runner(self) -> BackgroundActivityRunner:
        if self._activity_runner is None:
            self._activity_runner = BackgroundActivityRunner(
                self.activity_worker,
                poll_seconds=settings.JOB_WORKER_POLL_SECONDS,
            )
        return self._activity_runner

    @property
    def job_runner(self) -> BackgroundActivityRunner:
        return self.activity_runner

    @property
    def translation(self) -> TranslationService:
        if self._translation is None:
            # Build translation service with all dependencies
            from novelai.translation.pipeline.pipeline import TranslationPipeline
            from novelai.translation.pipeline.stages.fetch import FetchStage
            from novelai.translation.pipeline.stages.parse import ParseStage
            from novelai.translation.pipeline.stages.post_process import PostProcessStage
            from novelai.translation.pipeline.stages.segment import SegmentStage
            from novelai.translation.pipeline.stages.translation_qa import TranslationQAStage
            from novelai.translation.pipeline.stages.translate import TranslateStage

            stages = [
                FetchStage(),
                ParseStage(),
                SegmentStage(),
                TranslateStage(
                    provider_factory=get_provider,
                    cache=self.translation_cache,
                    settings_service=self.settings,
                    usage_service=self.usage,
                    storage=self.storage,
                ),
                TranslationQAStage(),
                PostProcessStage(),
            ]
            self._translation = TranslationService(pipeline=TranslationPipeline(stages=stages))
        return self._translation

    @property
    def export(self) -> ExportService:
        if self._export is None:
            self._export = ExportService()
        return self._export

    @property
    def orchestrator(self) -> NovelOrchestrationService:
        if self._orchestrator is None:
            from novelai.sources.registry import get_source
            self._orchestrator = NovelOrchestrationService(
                storage=self.storage,
                translation=self.translation,
                source_factory=get_source,
            )
        return self._orchestrator


# Global singleton container used by application entrypoints.
container = Container()
