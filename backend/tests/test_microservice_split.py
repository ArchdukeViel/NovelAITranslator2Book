"""Tests for microservice split: monolith mode, split mode, endpoint exclusivity.

Uses OpenAPI schema introspection — no DB required.
"""

from __future__ import annotations

import os
from typing import Any

import pytest
from fastapi import FastAPI
from starlette.middleware.sessions import SessionMiddleware

from novelai.api.app import create_app as create_monolith_app
from novelai.api.routers.health import router as health_router
from novelai.api.routers.public_catalog import router as public_catalog_router
from novelai.api.routers.public_chapter import router as public_chapter_router
from novelai.api.routers.public_novel import router as public_novel_router
from novelai.api.routers.user_data import router as user_data_router
from novelai.runtime.bootstrap import bootstrap

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _sqlite_db(monkeypatch: Any) -> None:
    """Override DATABASE_URL so bootstrap doesn't fail probing Postgres."""
    monkeypatch.setenv("DATABASE_URL", "sqlite:///")
    monkeypatch.setenv("TESTING", "1")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _route_paths(app: FastAPI) -> set[str]:
    """Return set of registered route paths via OpenAPI schema."""
    return set(app.openapi()["paths"].keys())


def _public_only_app() -> FastAPI:
    """Build minimal app mirroring main_reader.py (public + user_data)."""
    bootstrap()
    app = FastAPI(title="Novel AI Reader")
    app.add_middleware(SessionMiddleware, secret_key="test", https_only=False)
    app.include_router(public_catalog_router)
    app.include_router(public_novel_router)
    app.include_router(public_chapter_router)
    app.include_router(user_data_router)
    app.include_router(health_router)
    return app


# ---------------------------------------------------------------------------
# Monolith mode
# ---------------------------------------------------------------------------


class TestMonolithMode:
    """Monolith registers all route categories."""

    def test_monolith_has_public_routes(self) -> None:
        paths = _route_paths(create_monolith_app())
        assert any(p.startswith("/api/public") for p in paths), "Monolith missing /api/public routes"

    def test_monolith_has_admin_routes(self) -> None:
        paths = _route_paths(create_monolith_app())
        assert any(p.startswith("/api/admin") for p in paths), "Monolith missing /api/admin routes"

    def test_monolith_has_auth_routes(self) -> None:
        paths = _route_paths(create_monolith_app())
        assert any(p.startswith("/api/auth") for p in paths), "Monolith missing /api/auth routes"

    def test_monolith_has_health(self) -> None:
        paths = _route_paths(create_monolith_app())
        assert "/health/live" in paths
        assert "/health/ready" in paths
        assert "/health" not in paths
        assert "/api/health" not in paths


# ---------------------------------------------------------------------------
# Split mode — endpoint exclusivity via OpenAPI introspection
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def reader_app() -> FastAPI:
    return _public_only_app()


@pytest.fixture(scope="module")
def admin_app() -> FastAPI:
    return create_monolith_app()


class TestReaderServiceEndpoints:
    """Reader service registers ONLY public + user_data routes + health."""

    def test_reader_has_public_routes(self, reader_app: FastAPI) -> None:
        paths = _route_paths(reader_app)
        assert any(p.startswith("/api/public") for p in paths), "Reader must serve /api/public routes"

    def test_reader_rejects_admin(self, reader_app: FastAPI) -> None:
        paths = _route_paths(reader_app)
        assert not any(p.startswith("/api/admin") for p in paths), "Reader must NOT have admin routes"

    def test_reader_rejects_auth(self, reader_app: FastAPI) -> None:
        paths = _route_paths(reader_app)
        assert not any(p.startswith("/api/auth") for p in paths), "Reader must NOT have auth routes"

    def test_reader_health(self, reader_app: FastAPI) -> None:
        paths = _route_paths(reader_app)
        assert "/health/live" in paths
        assert "/health/ready" in paths
        assert "/health" not in paths
        assert "/api/health" not in paths

    def test_reader_no_db_catalog(self, reader_app: FastAPI) -> None:
        """Reader can serve /api/public/catalog without crash."""
        paths = _route_paths(reader_app)
        assert "/api/public/catalog" in paths, "Reader missing /api/public/catalog route"


class TestAdminServiceEndpoints:
    """Admin service registers admin + auth + public routes."""

    def test_admin_has_admin_routes(self, admin_app: FastAPI) -> None:
        paths = _route_paths(admin_app)
        assert any(p.startswith("/api/admin") for p in paths), "Admin must serve admin routes"

    def test_admin_has_auth_routes(self, admin_app: FastAPI) -> None:
        paths = _route_paths(admin_app)
        assert any(p.startswith("/api/auth") for p in paths), "Admin must serve auth routes"

    def test_admin_has_public_routes(self, admin_app: FastAPI) -> None:
        paths = _route_paths(admin_app)
        assert any(p.startswith("/api/public") for p in paths), "Admin must also serve public routes"


# ---------------------------------------------------------------------------
# DEPLOY_MODE env var
# ---------------------------------------------------------------------------


class TestDeployModeEnvVar:
    """DEPLOY_MODE environment variable controls start path."""

    def test_default_is_monolith(self, monkeypatch: Any) -> None:
        monkeypatch.delenv("DEPLOY_MODE", raising=False)
        assert os.environ.get("DEPLOY_MODE", "monolith") == "monolith"

    def test_can_set_split(self, monkeypatch: Any) -> None:
        monkeypatch.setenv("DEPLOY_MODE", "split")
        assert os.environ["DEPLOY_MODE"] == "split"
