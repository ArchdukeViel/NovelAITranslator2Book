from __future__ import annotations

from fastapi import FastAPI

from novelai.web.routers import novels


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(title="Novel AI")
    app.include_router(novels.router, prefix="/novels", tags=["novels"])
    return app


app = create_app()
