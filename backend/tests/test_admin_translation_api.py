"""Tests for admin translation observability API endpoints.

Covers:
- scheduler_health endpoint handler returns correct structure
- Secrets redacted in response
- Endpoint registration
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from fastapi.routing import APIRoute

from novelai.storage.service import StorageService


class TestSchedulerHealthHandler:
    """Directly test the scheduler_health endpoint handler with overridden deps."""

    def _fake_service(self, tmp_path: Path) -> Any:
        from novelai.services.admin_service import AdminService

        fake_prefs = type(
            "FakePrefs",
            (),
            {
                "prefs_path": "nope",
                "get_provider_management": lambda self: {},
                "get_preferred_provider": lambda self: "gemini",
                "get_provider_model": lambda self: "gemini-3.1-flash-lite",
                "get_api_key": lambda self, pk: "fake-key",
                "reload": lambda self: None,
                "clear": lambda self: None,
            },
        )()

        svc = AdminService(
            preferences=fake_prefs,  # type: ignore[arg-type]
            translation_cache=type(
                "FakeCache", (), {"cache_file": "nope", "reload": lambda: None, "clear": lambda: None}
            )(),  # type: ignore[arg-type]
            usage=type("FakeUsage", (), {"usage_path": "nope", "reload": lambda: None, "clear": lambda: None})(),  # type: ignore[arg-type]
            activity_runner=type("FakeRunner", (), {"status": lambda self: {}})(),  # type: ignore[arg-type]
            storage=StorageService(tmp_path),
        )
        svc.scheduler_policy_models = lambda **kw: [
            {
                "provider_key": "gemini",
                "provider_model": "gemini-3.1-flash-lite",
                "priority_order": 0,
                "rpm_limit": 10,
                "rpd_limit": 100,
            },
            {"provider_key": "gemini", "provider_model": "gemma-4-31b-it", "priority_order": 1},
        ]
        return svc

    @pytest.mark.asyncio
    async def test_handler_returns_valid_response(self, tmp_path: Path) -> None:
        from novelai.api.routers.admin import scheduler_health

        svc = self._fake_service(tmp_path)
        result = await scheduler_health(service=svc)
        assert isinstance(result, dict)
        assert "policy" in result
        assert "models" in result

    @pytest.mark.asyncio
    async def test_handler_policy_fields(self, tmp_path: Path) -> None:
        from novelai.api.routers.admin import scheduler_health

        svc = self._fake_service(tmp_path)
        result = await scheduler_health(service=svc)
        assert "default_provider" in result["policy"]
        assert "default_model" in result["policy"]
        assert "allow_cross_provider_fallback" in result["policy"]

    @pytest.mark.asyncio
    async def test_handler_model_fields(self, tmp_path: Path) -> None:
        from novelai.api.routers.admin import scheduler_health

        svc = self._fake_service(tmp_path)
        result = await scheduler_health(service=svc)
        assert isinstance(result["models"], list)
        assert len(result["models"]) == 2
        for model in result["models"]:
            assert "provider_key" in model
            assert "provider_model" in model
            assert "configured" in model

    @pytest.mark.asyncio
    async def test_handler_secrets_redacted(self, tmp_path: Path) -> None:
        from novelai.api.routers.admin import scheduler_health

        svc = self._fake_service(tmp_path)
        result = await scheduler_health(service=svc)
        dumped = str(result).lower()
        assert "api_key" not in dumped
        assert "secret" not in dumped

    @pytest.mark.asyncio
    async def test_handler_json_serializable(self, tmp_path: Path) -> None:
        import json

        from novelai.api.routers.admin import scheduler_health

        svc = self._fake_service(tmp_path)
        result = await scheduler_health(service=svc)
        json.dumps(result)

    def test_endpoint_is_registered(self) -> None:
        """The scheduler-health route exists on the admin router."""
        from novelai.api.routers import admin as admin_router

        found = False
        for route in admin_router.router.routes:
            if isinstance(route, APIRoute) and "scheduler-health" in route.path:
                found = True
                break
        assert found
