from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from novelai.activity.queue import ActivityQueueService
from novelai.activity.runner import BackgroundActivityRunner
from novelai.activity.worker import ActivityWorkerService
from novelai.config.settings import settings
from novelai.providers.registry import get_provider
from novelai.services.analytics_service import AnalyticsService
from novelai.services.backup_service import BackupService
from novelai.services.database_backup_service import DatabaseBackupService
from novelai.services.email import AuthEmailService, NoopAuthEmailService, SMTPAuthEmailService
from novelai.services.health_service import HealthService
from novelai.services.library_summary_service import LibrarySummaryService
from novelai.services.maintenance_service import MaintenanceService
from novelai.services.maintenance_status_service import MaintenanceStatusService
from novelai.services.notification_service import NotificationService
from novelai.services.novel_orchestration_service import NovelOrchestrationService
from novelai.services.operator_alert_service import OperatorAlertService
from novelai.services.preferences_service import PreferencesService
from novelai.services.scheduler_runtime_state_service import SchedulerRuntimeStateService
from novelai.services.scheduler_service import SchedulerService
from novelai.services.translation_cache import TranslationCache
from novelai.services.usage_service import UsageService
from novelai.sources.base import SourceAdapter
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
    _preferences: PreferencesService | None = None
    _usage: UsageService | None = None
    _activity_log: ActivityQueueService | None = None
    _translation: TranslationService | None = None
    _orchestrator: NovelOrchestrationService | None = None
    _activity_worker: ActivityWorkerService | None = None
    _activity_runner: BackgroundActivityRunner | None = None
    _auth_email: AuthEmailService | None = None
    _scheduler_runtime_state: SchedulerRuntimeStateService | None = None
    _backup_service: BackupService | None = None
    _maintenance_service: MaintenanceService | None = None
    _maintenance_status_service: MaintenanceStatusService | None = None
    _scheduler_service: SchedulerService | None = None
    _database_backup_service: DatabaseBackupService | None = None
    _operator_alert_service: OperatorAlertService | None = None
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
    def preferences(self) -> PreferencesService:
        if self._preferences is None:
            self._preferences = PreferencesService()
        return self._preferences

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
    def activity_worker(self) -> ActivityWorkerService:
        if self._activity_worker is None:
            self._activity_worker = ActivityWorkerService(
                self.activity_log, self.orchestrator, self._create_notification
            )
        return self._activity_worker

    @staticmethod
    def _create_notification(payload: dict[str, Any]) -> object:
        from novelai.db.engine import session_scope

        with session_scope() as db_session:
            return NotificationService(db_session=db_session).persistence().create(**payload)

    @property
    def activity_runner(self) -> BackgroundActivityRunner:
        if self._activity_runner is None:
            self._activity_runner = BackgroundActivityRunner(
                self.activity_worker,
                poll_seconds=settings.JOB_WORKER_POLL_SECONDS,
            )
        return self._activity_runner

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
            from novelai.translation.pipeline.stages.cache_flush import CacheFlushStage
            from novelai.translation.pipeline.stages.fetch import FetchStage
            from novelai.translation.pipeline.stages.parse import ParseStage
            from novelai.translation.pipeline.stages.post_process import PostProcessStage
            from novelai.translation.pipeline.stages.segment import SmartSegmentStage
            from novelai.translation.pipeline.stages.translate import TranslateStage
            from novelai.translation.pipeline.stages.translation_qa import TranslationQAStage

            stages = [
                FetchStage(),
                ParseStage(),
                SmartSegmentStage(),
                TranslateStage(
                    provider_factory=get_provider,
                    cache=self.translation_cache,
                    settings_service=self.preferences,
                    usage_service=self.usage,
                    storage=self.storage,
                ),
                TranslationQAStage(storage=self.storage),
                CacheFlushStage(),
                PostProcessStage(),
            ]
            self._translation = TranslationService(pipeline=TranslationPipeline(stages=stages))
        return self._translation

    @property
    def orchestrator(self) -> NovelOrchestrationService:
        if self._orchestrator is None:
            from novelai.sources.registry import get_registry

            def source_factory(source_key: str) -> SourceAdapter:
                source = get_registry().get_by_key(source_key)
                if source is None:
                    raise KeyError(source_key)
                return source

            self._orchestrator = NovelOrchestrationService(
                storage=self.storage,
                translation=self.translation,
                source_factory=source_factory,
            )
        return self._orchestrator

    @property
    def backup_service(self) -> BackupService:
        if self._backup_service is None:
            from novelai.storage.backends import build_r2_recovery_storage
            from novelai.storage.r2_backup import R2IncrementalBackupTarget

            snapshot_target = None
            if settings.R2_BACKUP_ENABLED:
                if not settings.R2_BUCKET or not settings.R2_BACKUP_BUCKET:
                    raise RuntimeError("Application and backup R2 buckets must be configured")
                snapshot_target = R2IncrementalBackupTarget(
                    source_backend=build_r2_recovery_storage(bucket_class="app"),
                    target_backend=build_r2_recovery_storage(bucket_class="backup"),
                    target_prefix=settings.R2_BACKUP_PREFIX,
                )
            self._backup_service = BackupService(
                runtime_dir=settings.RUNTIME_DIR,
                snapshot_target=snapshot_target,
            )
        return self._backup_service

    @property
    def maintenance_service(self) -> MaintenanceService:
        if self._maintenance_service is None:
            self._maintenance_service = MaintenanceService(
                storage=self.storage,
                activity_log=self.activity_log,
                backup_service=self.backup_service,
                scheduler_runtime_state_service=self.scheduler_runtime_state,
                analytics_service=AnalyticsService(),
                notification_cleanup=self._cleanup_notifications,
                contributor_usage_cleanup=self._cleanup_contributor_usage,
            )
        return self._maintenance_service

    @property
    def maintenance_status_service(self) -> MaintenanceStatusService:
        if self._maintenance_status_service is None:
            self._maintenance_status_service = MaintenanceStatusService(self.scheduler_runtime_state)
        return self._maintenance_status_service

    @staticmethod
    def _cleanup_notifications(retention_days: int, batch_size: int) -> int:
        from novelai.db.engine import session_scope

        with session_scope() as db_session:
            return (
                NotificationService(db_session=db_session)
                .persistence()
                .cleanup_retention(older_than_days=retention_days, batch_size=batch_size)
            )

    @staticmethod
    def _cleanup_contributor_usage(retention_days: int) -> int:
        from novelai.db.engine import session_scope
        from novelai.services.provider_credentials import ProviderCredentialService

        with session_scope() as db_session:
            return ProviderCredentialService(db_session).cleanup_old_usage(ttl_days=retention_days)

    @property
    def operator_alert_service(self) -> OperatorAlertService:
        if self._operator_alert_service is None:
            self._operator_alert_service = OperatorAlertService()
        return self._operator_alert_service

    @property
    def database_backup_service(self) -> DatabaseBackupService | None:
        if not settings.DATABASE_BACKUP_ENABLED:
            return None
        if self._database_backup_service is None:
            if not settings.R2_BACKUP_BUCKET:
                raise RuntimeError("Database backup bucket is not configured")
            from novelai.storage.backends import build_r2_recovery_storage

            self._database_backup_service = DatabaseBackupService(
                build_r2_recovery_storage(bucket_class="backup"),
            )
        return self._database_backup_service

    @property
    def scheduler_service(self) -> SchedulerService:
        if self._scheduler_service is None:
            from novelai.db.engine import session_scope

            self._scheduler_service = SchedulerService(
                backup_service=self.backup_service,
                maintenance_service=self.maintenance_service,
                database_backup_service=self.database_backup_service,
                operator_alert_service=self.operator_alert_service,
                db_session_scope_factory=session_scope,
                storage_service=self.storage,
            )
        return self._scheduler_service

    @property
    def health_service(self) -> HealthService:
        if self._health_service is None:
            self._health_service = HealthService(
                storage=self.storage,
                activity_runner=self.activity_runner,
                backup_service=self.backup_service if settings.BACKUP_ENABLED else None,
                database_backup_service=self.database_backup_service if settings.DATABASE_BACKUP_ENABLED else None,
                operator_alert_service=self.operator_alert_service,
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
