from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware

from novelai.api.error_handlers import add_error_handlers
from novelai.api.middleware.security import SecurityHeadersMiddleware
from novelai.api.routers import (
    activity,
    admin,
    admin_glossary,
    admin_taxonomy,
    editor,
    health,
    library,
    library_actions,
    library_detail,
    novels,
    operations,
    requests,
    sources,
)
from novelai.api.routers.auth import router as auth_router
from novelai.api.routers.health import admin_router as health_admin_router
from novelai.api.routers.library import NovelSummary, list_novels
from novelai.api.routers.public import router as public_router
from novelai.api.routers.user_data import router as user_data_router
from novelai.config.production_validator import assert_production_config
from novelai.config.settings import settings
from novelai.runtime.bootstrap import bootstrap
from novelai.runtime.container import container


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    if settings.JOB_WORKER_ENABLED:
        await container.activity_runner.start()
    if settings.BACKUP_ENABLED or settings.MAINTENANCE_ENABLED or settings.DATABASE_BACKUP_ENABLED:
        container.scheduler_service.start()
    try:
        yield
    finally:
        if container.activity_runner.is_running():
            await container.activity_runner.stop()
        if container.scheduler_service.is_running:
            await container.scheduler_service.stop()
        from novelai.db.engine import dispose_engines

        dispose_engines()


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    bootstrap()

    if settings.ENV == "production":
        assert_production_config(settings)

    app = FastAPI(title="Novel AI", lifespan=lifespan)

    # Session middleware (HTTP-only signed cookies — v1 auth strategy, architecture §19).
    # Must be added before CORS middleware.
    app.add_middleware(
        SessionMiddleware,
        secret_key=settings.SESSION_SECRET_KEY,
        session_cookie="novelai_session",
        max_age=settings.SESSION_MAX_AGE,
        same_site="lax",
        https_only=(
            settings.SESSION_COOKIE_SECURE
            if settings.SESSION_COOKIE_SECURE is not None
            else settings.ENV == "production"
        ),
    )

    # CORS: restrict to configured origins (empty list = nothing allowed)
    if settings.WEB_CORS_ORIGINS:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.WEB_CORS_ORIGINS,
            allow_credentials=True,
            allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
            allow_headers=["Authorization", "Content-Type", "X-CSRF-Token"],
        )

    app.add_middleware(SecurityHeadersMiddleware)
    if settings.ALLOWED_HOSTS:
        app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.ALLOWED_HOSTS)

    # Register error handlers
    add_error_handlers(app)

    # Auth routes (login/logout/me — no API key required)
    app.include_router(auth_router)

    # Public catalog routes (guest-accessible, no auth required)
    app.include_router(public_router)

    # User data routes (authenticated users: library, progress, history, reviews, requests)
    app.include_router(user_data_router)

    app.include_router(admin.router, prefix="/api", tags=["admin-api"])
    app.include_router(sources.router, prefix="/api/admin", tags=["admin-api"])
    app.include_router(activity.router, prefix="/api/admin", tags=["admin-api"])
    app.include_router(requests.router, prefix="/api/admin", tags=["admin-api"])
    app.include_router(admin_glossary.router, prefix="/api/admin", tags=["admin-api"])
    app.include_router(admin_taxonomy.router, prefix="/api/admin/novels", tags=["admin-api"])
    app.include_router(editor.router, prefix="/api/admin/novels", tags=["admin-api"])
    app.include_router(operations.router, prefix="/api/admin/novels", tags=["admin-api"])
    app.include_router(library.router, prefix="/api/admin/novels", tags=["admin-api"])
    app.include_router(library.read_router, prefix="/api", tags=["admin-api"])
    app.include_router(library_detail.router, prefix="/api/admin/novels", tags=["admin-api"])
    app.include_router(library_actions.router, prefix="/api/admin/novels", tags=["admin-api"])
    app.add_api_route(
        "/api/admin/novels",
        list_novels,
        methods=["GET"],
        response_model=list[NovelSummary],
        include_in_schema=False,
    )

    app.include_router(novels.router, prefix="/novels", tags=["novels"])
    app.include_router(novels.router, prefix="/api/novels", tags=["novels-api"])
    app.add_api_route(
        "/novels",
        list_novels,
        methods=["GET"],
        response_model=list[NovelSummary],
        include_in_schema=False,
    )
    app.add_api_route(
        "/api/novels",
        list_novels,
        methods=["GET"],
        response_model=list[NovelSummary],
        include_in_schema=False,
    )

    app.include_router(health.router)
    app.include_router(health_admin_router, prefix="/api", tags=["health"])

    # Backward-compatible aliases for /health and /api/health (point to liveness)
    @app.get("/health", tags=["health"], include_in_schema=False)
    async def _health_alias() -> dict[str, str]:
        return {"status": "ok", "service": "novelai", "timestamp": ""}

    @app.get("/api/health", tags=["health"])
    async def _api_health_alias() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()


def get_app() -> FastAPI:
    """Get the FastAPI application (alias for the module-level app)."""
    return app
