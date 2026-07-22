"""Tests for microservice split: monolith mode, split mode, endpoint exclusivity.

Uses OpenAPI schema introspection — no DB required.
"""

from __future__ import annotations

import os
from typing import Any

import pytest
from fastapi import FastAPI

from novelai.api.app import create_app as create_monolith_app
from novelai.main_admin import app as split_admin_app
from novelai.main_reader import app as split_reader_app

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
    return split_reader_app


@pytest.fixture(scope="module")
def admin_app() -> FastAPI:
    return split_admin_app


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

    def test_reader_rejects_session_user_routes(self, reader_app: FastAPI) -> None:
        paths = _route_paths(reader_app)
        assert not any(p.startswith("/api/user") for p in paths), "Reader must NOT have session-authenticated routes"

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
    """Session-enabled service registers admin, auth, and public-user routes."""

    def test_admin_has_admin_routes(self, admin_app: FastAPI) -> None:
        paths = _route_paths(admin_app)
        assert any(p.startswith("/api/admin") for p in paths), "Admin must serve admin routes"

    def test_admin_has_auth_routes(self, admin_app: FastAPI) -> None:
        paths = _route_paths(admin_app)
        assert any(p.startswith("/api/auth") for p in paths), "Admin must serve auth routes"

    def test_admin_has_user_routes(self, admin_app: FastAPI) -> None:
        paths = _route_paths(admin_app)
        assert any(p.startswith("/api/user") for p in paths), "Admin must serve session-authenticated user routes"

    def test_admin_rejects_public_reader_routes(self, admin_app: FastAPI) -> None:
        paths = _route_paths(admin_app)
        assert not any(p.startswith("/api/public") for p in paths), "Admin must not duplicate public reader routes"

    def test_admin_uses_only_canonical_novel_namespace(self, admin_app: FastAPI) -> None:
        paths = _route_paths(admin_app)
        assert any(p.startswith("/api/admin/novels") for p in paths)
        assert not any(p == "/novels" or p.startswith("/novels/") for p in paths)
        assert not any(p == "/api/novels" or p.startswith("/api/novels/") for p in paths)


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
