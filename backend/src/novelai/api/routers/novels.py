from __future__ import annotations

from fastapi import APIRouter

from novelai.api.routers import (
    activity,
    admin,
    editor,
    library,
    library_actions,
    library_detail,
    operations,
    requests,
    sources,
)
from novelai.api.routers.dependencies import (
    _hits,
    _rate_limit,
    get_activity_log,
    get_activity_runner,
    get_activity_worker,
    get_orchestrator,
    get_preferences,
    get_storage,
    get_translation_cache,
    get_usage,
    verify_api_key,
)

router = APIRouter()

router.include_router(sources.router)
router.include_router(activity.router)
router.include_router(requests.router)
router.include_router(admin.router)
router.include_router(editor.router)
router.include_router(operations.router)
router.include_router(library.router)
router.include_router(library_detail.router)
router.include_router(library_actions.router)

__all__ = [
    "_hits",
    "_rate_limit",
    "get_activity_log",
    "get_activity_runner",
    "get_activity_worker",
    "get_orchestrator",
    "get_preferences",
    "get_storage",
    "get_translation_cache",
    "get_usage",
    "router",
    "verify_api_key",
]
