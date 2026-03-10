from __future__ import annotations

from fastapi import FastAPI

from novelai.app.bootstrap import bootstrap
from novelai.web.error_handlers import add_error_handlers
from novelai.web.routers import novels


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    bootstrap()

    app = FastAPI(title="Novel AI")

    # Register error handlers
    add_error_handlers(app)

    app.include_router(novels.router, prefix="/novels", tags=["novels"])
    return app


app = create_app()
