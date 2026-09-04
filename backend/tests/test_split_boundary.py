"""Architectural boundary checks for server entry points and split deployment modes."""

from __future__ import annotations

from fastapi.routing import APIRoute

from novelai.main_reader import app as reader_app


def test_reader_app_mounts_zero_admin_routes() -> None:
    """Reader app on port 8001 must never expose admin, owner, or auth routes."""
    prohibited_prefixes = ("/api/admin", "/api/auth/login", "/api/auth/register", "/api/system")

    for route in reader_app.routes:
        if isinstance(route, APIRoute):
            for prefix in prohibited_prefixes:
                assert not route.path.startswith(prefix), (
                    f"Prohibited admin route {route.path} found mounted on reader app"
                )
