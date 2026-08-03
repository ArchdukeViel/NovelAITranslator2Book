"""Tests for microservice split: monolith mode, split mode, endpoint exclusivity.

Uses OpenAPI schema introspection — no DB required.
"""

from __future__ import annotations

import os
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware

from novelai.api.app import create_app as create_monolith_app
from novelai.api.auth.session import GUEST, get_current_user
from novelai.api.middleware.security import RequestBodyEnforcementMiddleware, SecurityHeadersMiddleware
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


def _route_methods_paths(app: FastAPI) -> set[tuple[str, str]]:
    """Return set of (METHOD, path) tuples via OpenAPI schema.

    Excludes HEAD (implicit on GET) so the combined/split parity comparison is
    not polluted by Starlette auto-HEAD generation.
    """
    out: set[tuple[str, str]] = set()
    for path, item in app.openapi()["paths"].items():
        for method in item:
            if method.upper() == "HEAD":
                continue
            out.add((method.upper(), path))
    return out


def _assert_middleware_registered(app: FastAPI, cls: type) -> None:
    """Assert a middleware class is registered on the app."""
    assert any(m.cls is cls for m in app.user_middleware), f"{cls.__name__} not in app.user_middleware"


def _assert_middleware_ordering(app: FastAPI) -> None:
    """Assert outer response middleware wraps request-body enforcement."""
    midw = list(app.user_middleware)
    si = next(i for i, m in enumerate(midw) if m.cls is SecurityHeadersMiddleware)
    ri = next(i for i, m in enumerate(midw) if m.cls is RequestBodyEnforcementMiddleware)
    assert si < ri, f"SecurityHeaders[{si}] must be outer than RequestBody[{ri}]"
    if any(m.cls is TrustedHostMiddleware for m in midw):
        ti = next(i for i, m in enumerate(midw) if m.cls is TrustedHostMiddleware)
        assert ti < si, f"TrustedHost[{ti}] must be outer than SecurityHeaders[{si}]"
    if any(m.cls is CORSMiddleware for m in midw):
        ci = next(i for i, m in enumerate(midw) if m.cls is CORSMiddleware)
        assert ci < ri, f"CORS[{ci}] must be outer than RequestBody[{ri}]"


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

    def test_monolith_has_body_enforcement_middleware(self) -> None:
        app = create_monolith_app()
        _assert_middleware_registered(app, RequestBodyEnforcementMiddleware)
        _assert_middleware_ordering(app)


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

    def test_reader_resolves_session_users_as_guests(self, reader_app: FastAPI) -> None:
        assert reader_app.dependency_overrides[get_current_user]() is GUEST

    def test_reader_has_body_enforcement_middleware(self, reader_app: FastAPI) -> None:
        _assert_middleware_registered(reader_app, RequestBodyEnforcementMiddleware)
        _assert_middleware_ordering(reader_app)


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

    def test_admin_has_body_enforcement_middleware(self, admin_app: FastAPI) -> None:
        _assert_middleware_registered(admin_app, RequestBodyEnforcementMiddleware)
        _assert_middleware_ordering(admin_app)


# ---------------------------------------------------------------------------
# Split-mode regression: critical frontend-consumed public write routes
# (Caddy routes /api/public/* solely to the reader service in deploy/compose.yml)
# ---------------------------------------------------------------------------


class TestCriticalPublicWriteRouteOwnership:
    """Contact, DMCA, and analytics ingestion MUST live only in the reader service.

    These are frontend-consumed public writes that the combined app previously
    served but the split reader service did not, leaving the frontend forms
    hitting 404 through the Caddy proxy in DEPLOY_MODE=split.
    """

    REQUIRED_READER_ROUTES = {
        ("POST", "/api/public/contact"),
        ("POST", "/api/public/dmca"),
        ("POST", "/api/public/analytics/events"),
    }

    def test_reader_serves_critical_public_writes(self, reader_app: FastAPI) -> None:
        methods_paths = _route_methods_paths(reader_app)
        missing = self.REQUIRED_READER_ROUTES - methods_paths
        assert not missing, f"Reader missing critical public write routes: {missing}"

    def test_admin_does_not_serve_critical_public_writes(self, admin_app: FastAPI) -> None:
        methods_paths = _route_methods_paths(admin_app)
        leaked = self.REQUIRED_READER_ROUTES & methods_paths
        assert not leaked, f"Admin must not serve public reader write routes: {leaked}"


# ---------------------------------------------------------------------------
# Combined-app compatibility: every endpoint reaches at least one split service
# ---------------------------------------------------------------------------


class TestCombinedAppSplitParity:
    """Every combined-app endpoint MUST be reachable via admin OR reader in split mode.

    Guards against drift where a router is added only to app.py and silently
    disappears from production DEPLOY_MODE=split topology.
    """

    def test_no_combined_only_routes(self) -> None:
        combined = _route_methods_paths(create_monolith_app())
        admin = _route_methods_paths(split_admin_app)
        reader = _route_methods_paths(split_reader_app)
        stranded = combined - (admin | reader)
        assert not stranded, f"Combined-app-only routes unreachable in DEPLOY_MODE=split: {sorted(stranded)}"


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
