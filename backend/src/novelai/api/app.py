from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware

from novelai.api.error_handlers import add_error_handlers
from novelai.api.middleware.security import RequestBodyEnforcementMiddleware, SecurityHeadersMiddleware
from novelai.api.middleware.timing import RequestTimingMiddleware
from novelai.api.routers import (
    activity,
    admin,
    admin_analytics,
    admin_audit,
    admin_contributions,
    admin_glossary,
    admin_reviews,
    admin_takedown,
    admin_taxonomy,
    admin_users,
    editor,
    health,
    library,
    library_actions,
    library_detail,
    operations,
    requests,
    sources,
)
from novelai.api.routers.auth import router as auth_router
from novelai.api.routers.health import admin_router as health_admin_router
from novelai.api.routers.library import NovelSummary, list_novels
from novelai.api.routers.metrics import router as metrics_router
from novelai.api.routers.notifications import router as notifications_router
from novelai.api.routers.public_catalog import router as public_catalog_router
from novelai.api.routers.public_chapter import router as public_chapter_router
from novelai.api.routers.public_contact import router as public_contact_router
from novelai.api.routers.public_dmca import router as public_dmca_router
from novelai.api.routers.public_novel import router as public_novel_router
from novelai.api.routers.public_rankings import router as public_rankings_router
from novelai.api.routers.user_contributions import router as user_contributions_router
from novelai.api.routers.user_data import router as user_data_router
from novelai.config.production_validator import assert_production_config
from novelai.config.settings import session_cookie_secure, settings
from novelai.runtime.bootstrap import bootstrap
from novelai.runtime.container import container
from novelai.services.runtime_telemetry import runtime_telemetry


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    runtime_telemetry.configure(
        max_observations=settings.RUNTIME_TELEMETRY_MAX_OBSERVATIONS,
        sample_interval_seconds=settings.RUNTIME_TELEMETRY_SAMPLE_INTERVAL_SECONDS,
    )
    await runtime_telemetry.start()
    if settings.JOB_WORKER_ENABLED:
        await container.activity_runner.start()
    scheduler_started = False
    if settings.BACKUP_ENABLED or settings.MAINTENANCE_ENABLED or settings.DATABASE_BACKUP_ENABLED:
        container.scheduler_service.start()
        scheduler_started = True
    try:
        yield
    finally:
        from novelai.services.analytics_writer import shutdown_analytics_writer

        shutdown_analytics_writer()
        if container.activity_runner.is_running():
            await container.activity_runner.stop()
        if scheduler_started and container.scheduler_service.is_running:
            await container.scheduler_service.stop()
        from novelai.infrastructure.http.fetch_service import get_default_fetch_service

        await get_default_fetch_service().aclose()
        from novelai.db.engine import dispose_engines

        dispose_engines()
        await runtime_telemetry.stop()


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    bootstrap()

    if settings.ENV == "production":
        assert_production_config(settings)

    docs_url: str | None = "/docs"
    redoc_url: str | None = "/redoc"
    openapi_url: str | None = "/openapi.json"
    if settings.ENV == "production" and not settings.ENABLE_OPENAPI_DOCS:
        docs_url = None
        redoc_url = None
        openapi_url = None

    app = FastAPI(
        title="Novel AI",
        lifespan=lifespan,
        docs_url=docs_url,
        redoc_url=redoc_url,
        openapi_url=openapi_url,
    )

    # Session middleware (HTTP-only signed cookies — v1 auth strategy, architecture §19).
    # Must be added before CORS middleware.
    app.add_middleware(
        SessionMiddleware,
        secret_key=settings.SESSION_SECRET_KEY,
        session_cookie="novelai_session",
        max_age=settings.SESSION_MAX_AGE,
        same_site="lax",
        https_only=session_cookie_secure(),
    )

    # RequestBody enforcement must be registered before CORS so CORS sits outer,
    # ensuring CORS headers appear on 413/415 responses.
    app.add_middleware(RequestBodyEnforcementMiddleware)
    app.add_middleware(RequestTimingMiddleware)

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
    app.include_router(public_catalog_router)
    app.include_router(public_contact_router)
    app.include_router(public_dmca_router)
    app.include_router(public_novel_router)
    app.include_router(public_rankings_router)
    app.include_router(public_chapter_router)

    # User data routes (authenticated users: library, progress, history, reviews, requests)
    app.include_router(user_data_router)
    app.include_router(user_contributions_router)
    app.include_router(notifications_router)

    if settings.SERVICE_ROLE != "reader":
        app.include_router(admin.router, prefix="/api", tags=["admin-api"])
        app.include_router(admin_analytics.router)
        app.include_router(admin_analytics.ingestion_router)
        app.include_router(admin_audit.router)
        app.include_router(admin_users.router)
        app.include_router(admin_contributions.router)
        app.include_router(admin_takedown.router)
        app.include_router(admin_reviews.router)
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
        app.include_router(health_admin_router, prefix="/api", tags=["health"])

    app.include_router(health.router)
    app.include_router(metrics_router)

    return app


app = create_app()
