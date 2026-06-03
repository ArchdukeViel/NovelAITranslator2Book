from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from novelai.config.settings import settings
from novelai.api.error_handlers import add_error_handlers
from novelai.api.routers.library import NovelSummary, list_novels
from novelai.api.routers import novels
from novelai.runtime.bootstrap import bootstrap
from novelai.runtime.container import container


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    if settings.JOB_WORKER_ENABLED:
        await container.activity_runner.start()
    try:
        yield
    finally:
        if container.activity_runner.is_running():
            await container.activity_runner.stop()


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    bootstrap()

    app = FastAPI(title="Novel AI", lifespan=lifespan)

    # CORS: restrict to configured origins (empty list = nothing allowed)
    if settings.WEB_CORS_ORIGINS:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.WEB_CORS_ORIGINS,
            allow_credentials=True,
            allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
            allow_headers=["Authorization", "Content-Type"],
        )

    # Register error handlers
    add_error_handlers(app)

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

    @app.get("/api/health", tags=["health"])
    async def api_health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
