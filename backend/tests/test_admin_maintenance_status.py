from __future__ import annotations

from fastapi import FastAPI
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient

from novelai.api.auth.session import SessionUser, get_current_user
from novelai.api.routers import admin
from novelai.api.routers.dependencies import get_maintenance_status_service


def test_owner_maintenance_status_route_is_registered() -> None:
    route = next(
        route
        for route in admin.router.routes
        if isinstance(route, APIRoute) and route.path == "/admin/maintenance/status"
    )

    assert route.methods == {"GET"}
    assert any(
        getattr(dependency.call, "__qualname__", "") == "require_role.<locals>._check"
        for dependency in route.dependant.dependencies
    )


class StubStatus:
    def status(self):
        return {"status": "healthy", "tasks": []}


def test_maintenance_status_requires_owner() -> None:
    app = FastAPI()
    app.include_router(admin.router, prefix="/api")
    app.dependency_overrides[get_maintenance_status_service] = StubStatus
    app.dependency_overrides[get_current_user] = lambda: SessionUser(
        user_id=2,
        email="user@example.test",
        role="user",
    )

    response = TestClient(app).get("/api/admin/maintenance/status")

    assert response.status_code == 403


def test_owner_receives_redacted_maintenance_status() -> None:
    app = FastAPI()
    app.include_router(admin.router, prefix="/api")
    app.dependency_overrides[get_maintenance_status_service] = StubStatus
    app.dependency_overrides[get_current_user] = lambda: SessionUser(
        user_id=1,
        email="owner@example.test",
        role="owner",
    )

    response = TestClient(app).get("/api/admin/maintenance/status")

    assert response.status_code == 200
    assert response.json() == {"status": "healthy", "tasks": []}
