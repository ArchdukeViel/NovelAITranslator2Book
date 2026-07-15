from __future__ import annotations

from dataclasses import dataclass

from novelai.activity.queue import ActivityQueueService
from novelai.activity.runner import BackgroundActivityRunner
from novelai.activity.worker import ActivityWorkerService
from novelai.config.settings import settings
from novelai.providers.registry import get_provider
from novelai.services.backup_service import BackupService
from novelai.services.email import AuthEmailService, NoopAuthEmailService, SMTPAuthEmailService
from novelai.services.export_service import ExportService
from novelai.services.health_service import HealthService
from novelai.services.library_summary_service import LibrarySummaryService
from novelai.services.maintenance_service import MaintenanceService
from novelai.services.novel_orchestration_service import NovelOrchestrationService
from novelai.services.preferences_service import PreferencesService
from novelai.services.scheduler_runtime_state_service import SchedulerRuntimeStateService
from novelai.services.scheduler_service import SchedulerService
from novelai.services.translation_cache import TranslationCache
from novelai.services.usage_service import UsageService
from novelai.storage.service import StorageService
from novelai.translation.service import TranslationService


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
    _translation: TranslationService | None = None
    _export: ExportService | None = None
    _orchestrator: NovelOrchestrationService | None = None
    _activity_worker: ActivityWorkerService | None = None
    _activity_runner: BackgroundActivityRunner | None = None
    _auth_email: AuthEmailService | None = None
    _scheduler_runtime_state: SchedulerRuntimeStateService | None = None
    _backup_service: BackupService | None = None
    _maintenance_service: MaintenanceService | None = None
    _scheduler_service: SchedulerService | None = None
    _health_service: HealthService | None = None
    _library_summary: LibrarySummaryService | None = None

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
    def auth_email(self) -> AuthEmailService:
        if self._auth_email is None:
            mode = settings.AUTH_EMAIL_DELIVERY_MODE.strip().lower()
            common = {
                "public_base_url": settings.PUBLIC_FRONTEND_URL,
                "password_reset_path": settings.AUTH_PASSWORD_RESET_PATH,
                "email_verification_path": settings.AUTH_EMAIL_VERIFICATION_PATH,
            }
            if mode == "noop":
                self._auth_email = NoopAuthEmailService(**common)
            elif mode == "smtp":
                self._auth_email = SMTPAuthEmailService(
                    **common,
                    host=settings.SMTP_HOST,
                    port=settings.SMTP_PORT,
                    username=settings.SMTP_USERNAME,
                    password=settings.SMTP_PASSWORD,
                    from_email=settings.SMTP_FROM_EMAIL,
                    from_name=settings.SMTP_FROM_NAME,
                    starttls=settings.SMTP_STARTTLS,
                    use_ssl=settings.SMTP_USE_SSL,
                    timeout_seconds=settings.SMTP_TIMEOUT_SECONDS,
                    smtp_factory=None,
                )
            else:
                raise ValueError(f"Unsupported AUTH_EMAIL_DELIVERY_MODE: {settings.AUTH_EMAIL_DELIVERY_MODE!r}")
        return self._auth_email

    @property
    def scheduler_runtime_state(self) -> SchedulerRuntimeStateService:
        if self._scheduler_runtime_state is None:
            self._scheduler_runtime_state = SchedulerRuntimeStateService()
        return self._scheduler_runtime_state

    @property
    def translation(self) -> TranslationService:
        if self._translation is None:
            # Build translation service with all dependencies
            from novelai.translation.pipeline.pipeline import TranslationPipeline
            from novelai.translation.pipeline.stages.fetch import FetchStage
            from novelai.translation.pipeline.stages.parse import ParseStage
            from novelai.translation.pipeline.stages.post_process import PostProcessStage
            from novelai.translation.pipeline.stages.segment import SegmentStage
            from novelai.translation.pipeline.stages.translate import TranslateStage
            from novelai.translation.pipeline.stages.translation_qa import TranslationQAStage

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

    @property
    def backup_service(self) -> BackupService:
        if self._backup_service is None:
            from novelai.services.backup_manager import BackupManager
            backup_manager = BackupManager(base_dir=settings.DATA_DIR / "backups")
            self._backup_service = BackupService(backup_manager=backup_manager)
        return self._backup_service

    @property
    def maintenance_service(self) -> MaintenanceService:
        if self._maintenance_service is None:
            self._maintenance_service = MaintenanceService(
                storage=self.storage,
                activity_log=self.activity_log,
                scheduler_runtime_state_service=self.scheduler_runtime_state,
            )
        return self._maintenance_service

    @property
    def scheduler_service(self) -> SchedulerService:
        if self._scheduler_service is None:
            from novelai.db.engine import session_scope
            self._scheduler_service = SchedulerService(
                backup_service=self.backup_service,
                maintenance_service=self.maintenance_service,
                db_session_scope_factory=session_scope,
            )
        return self._scheduler_service

    @property
    def health_service(self) -> HealthService:
        if self._health_service is None:
            self._health_service = HealthService(
                storage=self.storage,
                activity_runner=self.activity_runner,
            )
        return self._health_service

    @property
    def library_summary(self) -> LibrarySummaryService:
        if self._library_summary is None:
            self._library_summary = LibrarySummaryService(
                storage=self.storage,
                activity_log=self.activity_log,
            )
        return self._library_summary


# Global singleton container used by application entrypoints.
container = Container()
