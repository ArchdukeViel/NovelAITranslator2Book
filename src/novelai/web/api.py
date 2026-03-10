from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from novelai.app.bootstrap import bootstrap
from novelai.config.settings import settings
from novelai.web.error_handlers import add_error_handlers
from novelai.web.routers import novels


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    bootstrap()

    app = FastAPI(title="Novel AI")

    # CORS — restrict to configured origins (empty list = nothing allowed)
    if settings.WEB_CORS_ORIGINS:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.WEB_CORS_ORIGINS,
            allow_credentials=True,
            allow_methods=["GET", "POST", "DELETE"],
            allow_headers=["Authorization", "Content-Type"],
        )

    # Register error handlers
    add_error_handlers(app)

    app.include_router(novels.router, prefix="/novels", tags=["novels"])
    return app


app = create_app()
