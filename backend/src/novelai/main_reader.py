"""Public reader service — serves guest-accessible endpoints only.

Port 8001.  No auth, no session middleware, no CSRF.
Reads from the same DB and filesystem as the admin service.
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from novelai.api.error_handlers import add_error_handlers
from novelai.api.middleware.security import SecurityHeadersMiddleware
from novelai.api.routers.health import router as health_router
from novelai.api.routers.public import router as public_router
from novelai.api.routers.user_data import router as user_data_router
from novelai.config.production_validator import assert_production_config
from novelai.config.settings import settings
from novelai.runtime.bootstrap import bootstrap

if settings.ENV == "production":
    assert_production_config(settings)

bootstrap()

app = FastAPI(title="NovelAI Reader", version="1.0.0")

if settings.WEB_CORS_ORIGINS:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.WEB_CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
        allow_headers=["Authorization", "Content-Type", "X-CSRF-Token"],
    )

app.add_middleware(SecurityHeadersMiddleware)

add_error_handlers(app)

# Public endpoints (guest-accessible)
app.include_router(public_router)

# User data endpoints (auth'd, but auth is per-request — reader has no session)
app.include_router(user_data_router)

# Health (liveness + readiness only — no admin health on reader)
app.include_router(health_router)
