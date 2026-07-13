"""Owner admin service — authenticated orchestration endpoints only.

Port 8000.  Includes session middleware, CSRF, all admin routers.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware

from novelai.api.error_handlers import add_error_handlers
from novelai.api.routers import (
    activity,
    admin,
    admin_glossary,
    admin_taxonomy,
    editor,
    library,
    novels,
    operations,
    requests,
    sources,
)
from novelai.api.routers.auth import router as auth_router
from novelai.api.routers.library import NovelSummary, list_novels
from novelai.config.settings import settings
from novelai.runtime.bootstrap import bootstrap
from novelai.runtime.container import container

if settings.ENV == "production" and settings.SESSION_SECRET_KEY == "changeme-generate-a-real-secret-in-production":
    raise RuntimeError("SESSION_SECRET_KEY must be set to a strong secret in production.")


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    if settings.JOB_WORKER_ENABLED:
        await container.activity_runner.start()
    try:
        yield
    finally:
        if container.activity_runner.is_running():
            await container.activity_runner.stop()


bootstrap()

app = FastAPI(title="NovelAI Admin", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    SessionMiddleware,
    secret_key=settings.SESSION_SECRET_KEY,
    session_cookie="novelai_session",
    max_age=settings.SESSION_MAX_AGE,
    same_site="lax",
    https_only=settings.ENV == "production",
)

if settings.WEB_CORS_ORIGINS:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.WEB_CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
        allow_headers=["Authorization", "Content-Type", "X-CSRF-Token"],
    )

add_error_handlers(app)

# Auth routes (login/logout/me)
app.include_router(auth_router)

# Admin orchestration routers
app.include_router(admin.router, prefix="/api", tags=["admin-api"])
app.include_router(sources.router, prefix="/api/admin", tags=["admin-api"])
app.include_router(activity.router, prefix="/api/admin", tags=["admin-api"])
app.include_router(requests.router, prefix="/api/admin", tags=["admin-api"])
app.include_router(admin_glossary.router, prefix="/api/admin", tags=["admin-api"])
app.include_router(admin_taxonomy.router, prefix="/api/admin/novels", tags=["admin-api"])
app.include_router(editor.router, prefix="/api/admin/novels", tags=["admin-api"])
app.include_router(operations.router, prefix="/api/admin/novels", tags=["admin-api"])
app.include_router(library.router, prefix="/api/admin/novels", tags=["admin-api"])
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


@app.get("/api/admin/health", tags=["health"])
async def admin_health() -> dict[str, str]:
    return {"status": "ok"}
