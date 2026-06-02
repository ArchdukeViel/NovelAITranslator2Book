from __future__ import annotations

import logging
from collections import defaultdict
from typing import Any

from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from novelai.config.settings import settings
from novelai.runtime.container import container
from novelai.services.job_queue_service import JobQueueService
from novelai.services.job_runner_service import BackgroundJobRunner
from novelai.services.job_worker_service import JobWorkerService
from novelai.services.novel_orchestration_service import NovelOrchestrationService
from novelai.services.novel_request_service import NovelRequestService
from novelai.services.storage_service import StorageService
from novelai.utils.rate_limiter import get_default_rate_limiter

_bearer_scheme = HTTPBearer(auto_error=False)


async def verify_api_key(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
) -> None:
    """Reject requests when WEB_API_KEY is set and no valid token is provided."""
    expected = settings.WEB_API_KEY
    if expected is None:
        return

    expected_value = expected.get_secret_value()
    allowed = [value.strip() for value in expected_value.split(",") if value.strip()]
    supplied = credentials.credentials if credentials is not None else None
    if supplied is None or supplied not in allowed:
        logging.getLogger(__name__).warning("Failed web API auth attempt from unknown")
        raise HTTPException(status_code=403, detail="Invalid or missing API key")


_RATE_WINDOW = 60
_RATE_LIMITS: dict[str, int] = {
    "scrape": 5,
    "translate": 5,
    "export": 10,
    "edit": 20,
    "delete": 10,
}

_hits: dict[str, list[float]] = defaultdict(list)

_DEFAULT_LIMITER = get_default_rate_limiter(
    backend=settings.WEB_RATE_LIMITER_BACKEND,
    limits=_RATE_LIMITS,
    window_seconds=_RATE_WINDOW,
    hits_storage=_hits,
)


def _rate_limit(request: Request, action: str) -> None:
    try:
        client = request.client.host if request.client else "unknown"
    except Exception:
        client = "unknown"

    if not _DEFAULT_LIMITER.hit(client, action):
        raise HTTPException(status_code=429, detail="Rate limit exceeded")


def get_storage() -> StorageService:
    """FastAPI dependency for storage service using the runtime container singleton."""
    return container.storage


def get_orchestrator() -> NovelOrchestrationService:
    return container.orchestrator


def get_jobs() -> JobQueueService:
    return container.jobs


def get_job_worker() -> JobWorkerService:
    return container.job_worker


def get_job_runner() -> BackgroundJobRunner:
    return container.job_runner


def get_requests() -> NovelRequestService:
    return container.requests


def metadata_chapters(meta: dict[str, Any]) -> list[dict[str, Any]]:
    chapters = meta.get("chapters")
    return [chapter for chapter in chapters if isinstance(chapter, dict)] if isinstance(chapters, list) else []


def reader_title(meta: dict[str, Any]) -> str | None:
    title = meta.get("translated_title") or meta.get("title")
    return title if isinstance(title, str) else None


def reader_author(meta: dict[str, Any]) -> str | None:
    author = meta.get("translated_author") or meta.get("author")
    return author if isinstance(author, str) else None
