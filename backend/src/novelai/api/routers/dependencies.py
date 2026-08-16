from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session

from novelai.activity.queue import ActivityQueueService
from novelai.activity.runner import BackgroundActivityRunner
from novelai.activity.worker import ActivityWorkerService
from novelai.api.middleware.security import get_client_ip
from novelai.config.settings import settings
from novelai.infrastructure.http.rate_limiter import RateLimiter, create_rate_limiter
from novelai.runtime.container import container
from novelai.services.admin_service import AdminService
from novelai.services.editor_service import EditorService
from novelai.services.glossary_workflow_service import GlossaryWorkflowService
from novelai.services.health_service import HealthService
from novelai.services.library_service import LibraryService
from novelai.services.library_summary_service import LibrarySummaryService
from novelai.services.maintenance_status_service import MaintenanceStatusService
from novelai.services.notification_service import NotificationPersistenceService, NotificationService
from novelai.services.novel_orchestration_service import NovelOrchestrationService
from novelai.services.novel_request_service import NovelRequestService
from novelai.services.preferences_service import PreferencesService
from novelai.services.public_catalog_service import PublicCatalogService
from novelai.services.reading_service import ReadingService
from novelai.services.review_service import ReviewService
from novelai.services.scheduler_runtime_state_service import SchedulerRuntimeStateService
from novelai.services.translation_cache import TranslationCache
from novelai.services.usage_service import UsageService
from novelai.services.user_library_service import UserLibraryService
from novelai.storage.service import StorageService

if TYPE_CHECKING:
    from novelai.services.auth_service import AuthService

_RATE_WINDOW = 60
_RATE_LIMITS: dict[str, int] = {
    "scrape": 5,
    "translate": 5,
    "edit": 20,
    "delete": 10,
    "analytics": 60,
    "contact": 5,
    "dmca": 3,
}

_hits: dict[str, list[float]] = defaultdict(list)

_DEFAULT_LIMITER: RateLimiter | None = None
_DEFAULT_LIMITER_SIGNATURE: tuple[str, tuple[tuple[str, int], ...], int] | None = None


def _get_rate_limiter() -> RateLimiter:
    global _DEFAULT_LIMITER, _DEFAULT_LIMITER_SIGNATURE
    signature = (
        settings.WEB_RATE_LIMITER_BACKEND.strip().lower(),
        tuple(sorted(_RATE_LIMITS.items())),
        _RATE_WINDOW,
    )
    if _DEFAULT_LIMITER is None or signature != _DEFAULT_LIMITER_SIGNATURE:
        _DEFAULT_LIMITER = create_rate_limiter(
            settings.WEB_RATE_LIMITER_BACKEND,
            limits=_RATE_LIMITS,
            window_seconds=_RATE_WINDOW,
            hits_storage=_hits,
        )
        _DEFAULT_LIMITER_SIGNATURE = signature
    return _DEFAULT_LIMITER


def _rate_limit(
    request: Request,
    action: str,
    *,
    client_id: str | None = None,
    key_transform: Callable[[str], str] | None = None,
) -> None:
    try:
        client = client_id if client_id is not None else get_client_ip(request)
    except Exception:
        client = "unknown"

    if not _get_rate_limiter().hit(client, action, key_transform=key_transform):
        raise HTTPException(status_code=429, detail="Rate limit exceeded")


def get_storage() -> StorageService:
    """FastAPI dependency for storage service using the runtime container singleton."""
    return container.storage


def get_orchestrator() -> NovelOrchestrationService:
    return container.orchestrator


def get_activity_log() -> ActivityQueueService:
    return container.activity_log


def get_jobs() -> ActivityQueueService:
    return container.activity_log


def get_activity_worker() -> ActivityWorkerService:
    return container.activity_worker


def get_job_worker() -> ActivityWorkerService:
    return container.activity_worker


def get_activity_runner() -> BackgroundActivityRunner:
    return container.activity_runner


def get_job_runner() -> BackgroundActivityRunner:
    return container.activity_runner


def get_preferences() -> PreferencesService:
    return container.preferences


def get_translation_cache() -> TranslationCache:
    return container.translation_cache


def get_usage() -> UsageService:
    return container.usage


def get_db_session():
    """FastAPI dependency: yield a SQLAlchemy session, commit on clean exit.

    Requires DATABASE_URL to be configured. Raises 503 if not.
    Override in tests via app.dependency_overrides[get_db_session].
    """
    from fastapi import HTTPException

    from novelai.config.settings import settings
    from novelai.db.engine import get_sessionmaker

    if not settings.DATABASE_URL:
        raise HTTPException(
            status_code=503,
            detail="Database is not configured on this server.",
        )
    SM = get_sessionmaker()
    session = SM()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_auth_service(
    db_session: Session = Depends(get_db_session),
) -> AuthService:
    from novelai.services.auth_service import AuthService

    return AuthService(db_session=db_session, mailer=container.auth_email)


def metadata_chapters(meta: dict[str, Any]) -> list[dict[str, Any]]:
    chapters = meta.get("chapters")
    return [chapter for chapter in chapters if isinstance(chapter, dict)] if isinstance(chapters, list) else []


def reader_title(meta: dict[str, Any]) -> str | None:
    title = meta.get("translated_title") or meta.get("title")
    return title if isinstance(title, str) else None


def reader_author(meta: dict[str, Any]) -> str | None:
    author = meta.get("translated_author") or meta.get("author")
    return author if isinstance(author, str) else None


def get_admin_service(
    preferences: PreferencesService = Depends(get_preferences),
    translation_cache: TranslationCache = Depends(get_translation_cache),
    usage: UsageService = Depends(get_usage),
    activity_runner: BackgroundActivityRunner = Depends(get_activity_runner),
    storage: StorageService = Depends(get_storage),
) -> AdminService:
    return AdminService(
        preferences=preferences,
        translation_cache=translation_cache,
        usage=usage,
        activity_runner=activity_runner,
        storage=storage,
    )


def get_admin_db_service(
    preferences: PreferencesService = Depends(get_preferences),
    translation_cache: TranslationCache = Depends(get_translation_cache),
    usage: UsageService = Depends(get_usage),
    activity_runner: BackgroundActivityRunner = Depends(get_activity_runner),
    storage: StorageService = Depends(get_storage),
    db_session: Session = Depends(get_db_session),
) -> AdminService:
    return AdminService(
        preferences=preferences,
        translation_cache=translation_cache,
        usage=usage,
        activity_runner=activity_runner,
        storage=storage,
        db_session=db_session,
    )


def get_library_service(
    storage: StorageService = Depends(get_storage),
    db_session: Session = Depends(get_db_session),
) -> LibraryService:
    return LibraryService(storage=storage, db_session=db_session)


def get_library_summary_service() -> LibrarySummaryService:
    return container.library_summary


def get_editor_service(
    storage: StorageService = Depends(get_storage),
    db_session: Session = Depends(get_db_session),
) -> EditorService:
    return EditorService(storage=storage, db_session=db_session)


def get_novel_request_service(
    db_session: Session = Depends(get_db_session),
) -> NovelRequestService:
    return NovelRequestService(db_session=db_session)


def get_user_library_service(
    db_session: Session = Depends(get_db_session),
) -> UserLibraryService:
    return UserLibraryService(db_session=db_session)


def get_reading_service(
    db_session: Session = Depends(get_db_session),
) -> ReadingService:
    return ReadingService(db_session=db_session)


def get_review_service(
    db_session: Session = Depends(get_db_session),
) -> ReviewService:
    return ReviewService(db_session=db_session)


def get_notification_persistence_service(
    db_session: Session = Depends(get_db_session),
) -> NotificationPersistenceService:
    return NotificationService(db_session=db_session).persistence()


def get_public_catalog_service(
    storage: StorageService = Depends(get_storage),
    db_session: Session = Depends(get_db_session),
) -> PublicCatalogService:
    return PublicCatalogService(storage=storage, db_session=db_session)


def get_glossary_workflow_service(
    storage: StorageService = Depends(get_storage),
    db_session: Session = Depends(get_db_session),
) -> GlossaryWorkflowService:
    from novelai.services.glossary_workflow_service import GlossaryWorkflowService

    return GlossaryWorkflowService(storage=storage, db_session=db_session)


def get_scheduler_runtime_state_service() -> SchedulerRuntimeStateService:
    """FastAPI dependency for the scheduler runtime state service."""
    return container.scheduler_runtime_state


def get_maintenance_status_service() -> MaintenanceStatusService:
    """FastAPI dependency for owner maintenance status."""
    return container.maintenance_status_service


def get_health_service() -> HealthService:
    """FastAPI dependency for the health probe service."""
    return container.health_service
