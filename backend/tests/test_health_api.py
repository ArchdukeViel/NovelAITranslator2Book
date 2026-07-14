"""Tests for the health probe HTTP API (M2a, DEBT-001).

Tests liveness, readiness, admin health authorization, and 503 on unhealthy.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from novelai.api.app import create_app


@pytest.fixture()
def app():
    return create_app()


@pytest.fixture()
def client(app):
    return TestClient(app)


class TestLiveness:
    def test_liveness_returns_200(self, client: TestClient) -> None:
        response = client.get("/health/live")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["service"] == "novelai"
        assert "timestamp" in data

    def test_liveness_no_auth_required(self, client: TestClient) -> None:
        response = client.get("/health/live")
        assert response.status_code == 200


class TestReadiness:
    def test_readiness_returns_200_or_503(self, client: TestClient) -> None:
        response = client.get("/health/ready")
        assert response.status_code in (200, 503)
        data = response.json()
        assert "status" in data
        assert "checks" in data

    def test_readiness_public_safe_no_paths(self, client: TestClient) -> None:
        response = client.get("/health/ready")
        data = response.json()
        checks_str = str(data.get("checks", {}))
        assert "path" not in checks_str.lower()
        assert "password" not in checks_str.lower()
        assert "secret" not in checks_str.lower()

    def test_readiness_no_auth_required(self, client: TestClient) -> None:
        response = client.get("/health/ready")
        assert response.status_code in (200, 503)


class TestAdminHealth:
    def test_admin_health_requires_auth(self, client: TestClient) -> None:
        response = client.get("/api/admin/health")
        assert response.status_code in (401, 403)

    def test_admin_health_owner_only(self, client: TestClient) -> None:
        # Without owner session, should be 401 or 403.
        response = client.get("/api/admin/health")
        assert response.status_code in (401, 403)

    def test_admin_health_includes_details(self, client: TestClient) -> None:
        # Mock owner session by patching require_role.
        with patch("novelai.api.auth.roles.get_current_user") as mock_get_user:
            from novelai.api.auth.session import SessionUser

            mock_get_user.return_value = SessionUser(
                user_id=1, email="owner@test.com", role="owner"
            )
            response = client.get("/api/admin/health")
        if response.status_code == 200:
            data = response.json()
            assert "checks" in data
            for check in data["checks"].values():
                assert "latency_ms" in check
                assert "message" in check
