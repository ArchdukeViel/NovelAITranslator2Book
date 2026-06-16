"""Tests for the FastAPI web API (auth, CORS, rate limiting, endpoints)."""

from __future__ import annotations

import json
import shutil
from collections import defaultdict
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient
from pydantic import BaseModel

from novelai.api import error_handlers as error_handler_module
from novelai.api.auth.session import SessionUser, get_current_user
from novelai.api.app import create_app
from novelai.api.routers import novels
from novelai.api.routers.novels import (
    get_activity_log,
    get_activity_runner,
    get_activity_worker,
    get_orchestrator,
    get_preferences,
    get_requests,
    get_storage,
    get_translation_cache,
    get_usage,
)
from novelai.config.settings import settings
from novelai.core.errors import ConfigError, ExportError, NovelAIError, PipelineError, ProviderError, ProviderErrorCode, StorageError
from novelai.activity.queue import ActivityQueueService
from novelai.activity.runner import BackgroundActivityRunner
from novelai.activity.worker import ActivityWorkerService
from novelai.providers.gemini_provider import GeminiProvider
from novelai.runtime.bootstrap import bootstrap
from novelai.services.novel_request_service import NovelRequestService
from novelai.services.preferences_service import PreferencesService
from novelai.services.translation_cache import TranslationCache
from novelai.services.usage_service import UsageService
from novelai.storage.service import StorageService

_TMP = Path(__file__).resolve().parent / ".tmp" / "web_api"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _fresh_storage() -> StorageService:
    d = _TMP / "lib"
    d.mkdir(parents=True, exist_ok=True)
    return StorageService(d)


def _seed_novel(storage: StorageService, novel_id: str = "test-n1") -> None:
    storage.save_metadata(novel_id, {
        "novel_id": novel_id,
        "title": "Test Novel",
        "author": "Author",
        "chapters": [{"id": "1", "title": "Ch1"}, {"id": "2", "title": "Ch2"}],
    })
    storage.save_chapter(novel_id, "1", "Raw text ch1", source_key="dummy", source_url="http://example.com/1")
    storage.save_translated_chapter(novel_id, "1", "Translated ch1", provider="dummy", model="dummy")


def _assert_provider_mirrors(payload: dict[str, object]) -> None:
    assert "provider" in payload
    assert "model" in payload
    assert "provider_key" in payload
    assert "provider_model" in payload
    assert payload["provider_key"] == payload["provider"]
    assert payload["provider_model"] == payload["model"]


OWNER_USER = SessionUser(user_id=1, email="owner@local", role="owner")
REGULAR_USER = SessionUser(user_id=2, email="reader@example.com", role="user")


def _make_app(
    storage: StorageService,
    activity_log: ActivityQueueService | None = None,
    worker: ActivityWorkerService | None = None,
    runner: BackgroundActivityRunner | None = None,
    requests: NovelRequestService | None = None,
    orchestrator: object | None = None,
    preferences: PreferencesService | None = None,
    translation_cache: TranslationCache | None = None,
    usage: UsageService | None = None,
    session_user: SessionUser | None = OWNER_USER,
) -> TestClient:
    """Create a TestClient with storage dependency overridden."""
    app = create_app()
    if session_user is not None:
        app.dependency_overrides[get_current_user] = lambda: session_user
    app.dependency_overrides[get_storage] = lambda: storage
    if activity_log is not None:
        app.dependency_overrides[get_activity_log] = lambda: activity_log
    if worker is not None:
        app.dependency_overrides[get_activity_worker] = lambda: worker
    if runner is not None:
        app.dependency_overrides[get_activity_runner] = lambda: runner
    if requests is not None:
        app.dependency_overrides[get_requests] = lambda: requests
    if orchestrator is not None:
        app.dependency_overrides[get_orchestrator] = lambda: orchestrator
    if preferences is not None:
        app.dependency_overrides[get_preferences] = lambda: preferences
    if translation_cache is not None:
        app.dependency_overrides[get_translation_cache] = lambda: translation_cache
    if usage is not None:
        app.dependency_overrides[get_usage] = lambda: usage
    return TestClient(app)


def _get_routes_from_router(router) -> set:
    """Recursively extract routes from a FastAPI router, including included routers."""
    routes = set()
    for route in router.routes:
        if hasattr(route, "methods") and hasattr(route, "path"):
            routes.add((tuple(sorted(route.methods)), route.path))
        elif hasattr(route, "original_router"):  # _IncludedRouter
            routes.update(_get_routes_from_router(route.original_router))
    return routes


def test_router_path_method_snapshot() -> None:
    expected_routes = {
        (("DELETE",), "/{novel_id}"),
        (("DELETE",), "/activity/{activity_id}"),
        (("DELETE",), "/jobs/{activity_id}"),
        (("GET",), "/"),
        (("GET",), "/activity"),
        (("GET",), "/activity/source-health"),
        (("GET",), "/activity/source-health/{source_key}"),
        (("GET",), "/activity/{activity_id}"),
        (("GET",), "/admin"),
        (("GET",), "/admin/providers/{provider}"),
        (("GET",), "/admin/provider-api-key/{provider}"),
        (("GET",), "/admin/runtime-state"),
        (("GET",), "/admin/worker"),
        (("GET",), "/input-adapters"),
        (("GET",), "/jobs"),
        (("GET",), "/jobs/source-health"),
        (("GET",), "/jobs/source-health/{source_key}"),
        (("GET",), "/jobs/{activity_id}"),
        (("GET",), "/requests"),
        (("GET",), "/requests/{request_id}"),
        (("GET",), "/sources"),
        (("GET",), "/{novel_id}"),
        (("GET",), "/{novel_id}/chapters"),
        (("GET",), "/{novel_id}/chapters/{chapter_id}"),
        (("GET",), "/{novel_id}/chapters/{chapter_id}/translated"),
        (("GET",), "/{novel_id}/chapters/{chapter_id}/translated/edit-history"),
        (("GET",), "/{novel_id}/chapters/{chapter_id}/translated/versions"),
        (("GET",), "/{novel_id}/progress"),
        (("GET",), "/{novel_id}/reader"),
        (("GET",), "/{novel_id}/reader/chapters/{chapter_id}"),
        (("PATCH",), "/activity/{activity_id}"),
        (("PATCH",), "/jobs/{activity_id}"),
        (("PATCH",), "/requests/{request_id}"),
        (("POST",), "/admin/worker/run-once"),
        (("POST",), "/admin/worker/start"),
        (("POST",), "/admin/worker/stop"),
        (("POST",), "/admin/providers"),
        (("POST",), "/admin/providers/{provider}/validate"),
        (("POST",), "/admin/provider-api-key"),
        (("POST",), "/admin/provider-api-key/validate"),
        (("POST",), "/admin/runtime-state/{state_key}/refresh"),
        (("POST",), "/activity/crawl"),
        (("POST",), "/activity/run-next"),
        (("POST",), "/activity/translation"),
        (("POST",), "/activity/{activity_id}/run"),
        (("POST",), "/jobs/crawl"),
        (("POST",), "/jobs/run-next"),
        (("POST",), "/jobs/translation"),
        (("POST",), "/jobs/{activity_id}/run"),
        (("POST",), "/requests"),
        (("POST",), "/requests/{request_id}/source-candidates"),
        (("POST",), "/requests/{request_id}/vote"),
        (("POST",), "/{novel_id}/chapters/{chapter_id}/translated/rollback"),
        (("POST",), "/{novel_id}/export"),
        (("POST",), "/{novel_id}/import"),
        (("POST",), "/{novel_id}/preliminary-crawl"),
        (("POST",), "/{novel_id}/scrape"),
        (("POST",), "/{novel_id}/translate"),
        (("PUT",), "/{novel_id}/chapters/{chapter_id}/translated"),
        (("DELETE",), "/admin/providers/{provider}"),
        (("DELETE",), "/admin/provider-api-key/{provider}"),
        (("DELETE",), "/admin/runtime-state/{state_key}"),
    }
    current_routes = _get_routes_from_router(novels.router)

    assert current_routes == expected_routes


def test_json_error_encodes_non_json_native_details() -> None:
    response = error_handler_module._json_error(
        status_code=500,
        code="STORAGE_ERROR",
        message="Storage failed",
        details={
            "path": Path("novels") / "n1",
            "tags": {"storage"},
            "exception": RuntimeError("not directly serializable"),
        },
        category="storage",
        trace_id="trace-123",
    )

    payload = json.loads(response.body.decode("utf-8"))

    assert payload["code"] == "STORAGE_ERROR"
    assert payload["category"] == "storage"
    assert payload["details"]["path"] == str(Path("novels") / "n1")
    assert payload["details"]["tags"] == ["storage"]
    assert isinstance(payload["details"]["exception"], dict)
    assert payload["trace_id"] == "trace-123"


def test_extract_novel_code_from_novel_paths() -> None:
    assert error_handler_module._extract_novel_code_from_path("/novels/n0813kx/translate") == "n0813kx"
    assert error_handler_module._extract_novel_code_from_path("/api/novels/n1962jz/chapters/1") == "n1962jz"
    assert error_handler_module._extract_novel_code_from_path("/novels/jobs") is None
    assert error_handler_module._extract_novel_code_from_path("/novels/activity") is None
    assert error_handler_module._extract_novel_code_from_path("/novels/requests") is None


def test_novelai_error_handler_uses_custom_exception_metadata(_no_api_key: None) -> None:
    class CustomNovelAIError(NovelAIError):
        status_code = 409
        code = "CUSTOM_CONFLICT"
        category = "custom"
        explanation = "Custom explanation."
        details = {"path": Path("novels") / "n1"}

    bootstrap()
    app = create_app()

    @app.get("/debug/custom-novelai-metadata")
    async def debug_custom_novelai_metadata() -> None:
        raise CustomNovelAIError("custom message")

    c = TestClient(app, raise_server_exceptions=False)
    resp = c.get("/debug/custom-novelai-metadata")
    payload = resp.json()

    assert resp.status_code == 409
    assert payload["code"] == "CUSTOM_CONFLICT"
    assert payload["message"] == "custom message"
    assert payload["category"] == "custom"
    assert payload["explanation"] == "Custom explanation."
    assert payload["details"]["path"] == str(Path("novels") / "n1")


def test_storage_error_handler_uses_file_not_found_cause(_no_api_key: None) -> None:
    bootstrap()
    app = create_app()

    @app.get("/debug/storage-missing")
    async def debug_storage_missing() -> None:
        raise StorageError("metadata missing") from FileNotFoundError("metadata.json")

    c = TestClient(app, raise_server_exceptions=False)
    resp = c.get("/debug/storage-missing")
    payload = resp.json()

    assert resp.status_code == 404
    assert payload["code"] == "STORAGE_FILE_NOT_FOUND"
    assert payload["category"] == "storage"


def test_provider_error_handler_returns_structured_public_envelope(_no_api_key: None) -> None:
    bootstrap()
    app = create_app()

    @app.get("/debug/provider/quota")
    async def debug_provider_quota() -> None:
        raise ProviderError(
            ProviderErrorCode.QUOTA_EXHAUSTED,
            provider_key="gemini",
            provider_model="gemini-2.5-flash-lite",
            message="raw provider traceback should not be public",
            retry_after_seconds=21,
            exhausted_until="2026-06-05T00:00:00Z",
            details={"raw_message": "secret provider internals", "traceback": "stack"},
        )

    c = TestClient(app, raise_server_exceptions=False)
    resp = c.get("/debug/provider/quota", headers={"x-request-id": "trace-provider-1"})
    payload = resp.json()

    assert resp.status_code == 503
    assert payload["code"] == "PROVIDER_ERROR"
    assert payload["message"] == "Provider quota exhausted"
    assert payload["category"] == "provider"
    assert payload["details"] == {
        "provider_key": "gemini",
        "provider_model": "gemini-2.5-flash-lite",
        "provider_error_code": "provider_quota_exhausted",
        "retry_after_seconds": 21,
        "cooldown_until": None,
        "exhausted_until": "2026-06-05T00:00:00Z",
    }
    assert payload["trace_id"] == "trace-provider-1"
    assert "raw provider traceback" not in json.dumps(payload)
    assert "secret provider internals" not in json.dumps(payload)


def test_provider_error_handler_maps_rate_limit_retry_after(_no_api_key: None) -> None:
    bootstrap()
    app = create_app()

    @app.get("/debug/provider/rate-limit")
    async def debug_provider_rate_limit() -> None:
        raise ProviderError(
            ProviderErrorCode.RATE_LIMITED,
            provider_key="gemini",
            provider_model="gemini-2.5-flash",
            message="Provider rate limit reached",
            retry_after_seconds=9,
            cooldown_until="2026-06-04T12:00:09Z",
        )

    c = TestClient(app, raise_server_exceptions=False)
    resp = c.get("/debug/provider/rate-limit")
    payload = resp.json()

    assert resp.status_code == 429
    assert payload["code"] == "PROVIDER_ERROR"
    assert payload["details"]["provider_key"] == "gemini"
    assert payload["details"]["provider_model"] == "gemini-2.5-flash"
    assert payload["details"]["provider_error_code"] == "provider_rate_limited"
    assert payload["details"]["retry_after_seconds"] == 9


def test_provider_error_handler_maps_unknown_provider_error(_no_api_key: None) -> None:
    bootstrap()
    app = create_app()

    @app.get("/debug/provider/unknown")
    async def debug_provider_unknown() -> None:
        raise ProviderError(
            ProviderErrorCode.UNKNOWN,
            provider_key="gemini",
            provider_model="gemini-2.5-flash",
            message="Provider request failed",
        )

    c = TestClient(app, raise_server_exceptions=False)
    resp = c.get("/debug/provider/unknown")

    assert resp.status_code == 502
    assert resp.json()["details"]["provider_error_code"] == "provider_unknown_error"


def test_unhandled_runtime_error_message_respects_debug_errors(
    _no_api_key: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bootstrap()
    app = create_app()

    @app.get("/debug/runtime")
    async def debug_runtime() -> None:
        raise RuntimeError("debug-only internal message")

    c = TestClient(app, raise_server_exceptions=False)

    monkeypatch.setattr(error_handler_module, "DEBUG_ERRORS", False)
    production_resp = c.get("/debug/runtime")
    production_payload = production_resp.json()
    assert production_resp.status_code == 500
    assert production_payload["message"] == "Internal Server Error"
    assert production_payload["detail"] == "Internal Server Error"
    assert production_payload["code"] == "RUNTIME_ERROR"
    assert "error" not in production_payload["details"]

    monkeypatch.setattr(error_handler_module, "DEBUG_ERRORS", True)
    debug_resp = c.get("/debug/runtime")
    debug_payload = debug_resp.json()
    assert debug_resp.status_code == 500
    assert debug_payload["message"] == "debug-only internal message"
    assert debug_payload["detail"] == "debug-only internal message"
    assert debug_payload["details"]["error"] == "debug-only internal message"


def test_unhandled_generic_exception_hides_message_in_production(
    _no_api_key: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bootstrap()
    app = create_app()

    @app.get("/debug/generic-exception")
    async def debug_generic_exception() -> None:
        raise Exception("secret generic internal message")

    monkeypatch.setattr(error_handler_module, "DEBUG_ERRORS", False)
    c = TestClient(app, raise_server_exceptions=False)

    resp = c.get("/debug/generic-exception")
    payload = resp.json()

    assert resp.status_code == 500
    assert payload["code"] == "INTERNAL_ERROR"
    assert payload["message"] == "Internal Server Error"
    assert payload["detail"] == "Internal Server Error"
    assert "error" not in payload["details"]


def test_unhandled_value_error_keeps_validation_message_in_production(
    _no_api_key: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bootstrap()
    app = create_app()

    @app.get("/debug/jobs/value-error")
    async def debug_jobs_value_error() -> None:
        raise ValueError("Activity payload is missing source_key.")

    monkeypatch.setattr(error_handler_module, "DEBUG_ERRORS", False)
    c = TestClient(app, raise_server_exceptions=False)

    resp = c.get("/debug/jobs/value-error")
    payload = resp.json()

    assert resp.status_code == 400
    assert payload["code"] == "ACTIVITY_VALIDATION_ERROR"
    assert payload["message"] == "Activity payload is missing source_key."
    assert payload["detail"] == "Activity payload is missing source_key."
    assert payload["details"]["error"] == "Activity payload is missing source_key."


def test_unhandled_job_and_request_runtime_errors_use_failed_dependency(
    _no_api_key: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bootstrap()
    app = create_app()

    @app.get("/debug/jobs/runtime")
    async def debug_jobs_runtime() -> None:
        raise RuntimeError("activity runner stopped")

    @app.get("/debug/requests/runtime")
    async def debug_requests_runtime() -> None:
        raise RuntimeError("request queue stopped")

    monkeypatch.setattr(error_handler_module, "DEBUG_ERRORS", True)
    c = TestClient(app, raise_server_exceptions=False)

    jobs_resp = c.get("/debug/jobs/runtime")
    jobs_payload = jobs_resp.json()
    assert jobs_resp.status_code == 424
    assert jobs_payload["code"] == "ACTIVITY_ERROR"
    assert jobs_payload["category"] == "activity"

    requests_resp = c.get("/debug/requests/runtime")
    requests_payload = requests_resp.json()
    assert requests_resp.status_code == 424
    assert requests_payload["code"] == "REQUEST_QUEUE_ERROR"
    assert requests_payload["category"] == "requests"


def test_unhandled_error_details_include_novel_code_for_novel_route(
    _no_api_key: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bootstrap()
    app = create_app()

    @app.get("/novels/n0813kx/debug-runtime")
    async def debug_novel_runtime() -> None:
        raise RuntimeError("debug novel activity")

    monkeypatch.setattr(error_handler_module, "DEBUG_ERRORS", True)
    c = TestClient(app, raise_server_exceptions=False)

    resp = c.get("/novels/n0813kx/debug-runtime")
    payload = resp.json()

    assert resp.status_code == 500
    assert payload["details"]["novel_code"] == "n0813kx"
    assert payload["details"]["path"] == "/novels/n0813kx/debug-runtime"


def test_request_validation_error_returns_validation_code(_no_api_key: None) -> None:
    class DebugPayload(BaseModel):
        count: int

    bootstrap()
    app = create_app()

    @app.post("/debug/validation")
    async def debug_validation(payload: DebugPayload) -> dict[str, int]:
        return {"count": payload.count}

    c = TestClient(app, raise_server_exceptions=False)
    resp = c.post("/debug/validation", json={"count": "not-an-int"})
    payload = resp.json()

    assert resp.status_code == 422
    assert payload["code"] == "VALIDATION_ERROR"
    assert payload["message"] == "Request validation failed."
    assert isinstance(payload["details"], list)


def test_unhandled_error_payload_distinguishes_translation_preflight(_no_api_key: None) -> None:
    bootstrap()
    app = create_app()

    @app.get("/debug/translation")
    async def debug_translation() -> None:
        raise RuntimeError("Translation preflight failed: missing_source_language: Source language is unknown.")

    c = TestClient(app, raise_server_exceptions=False)
    resp = c.get("/debug/translation")

    assert resp.status_code == 400
    assert resp.json()["code"] == "TRANSLATION_PREFLIGHT_FAILED"
    assert resp.json()["category"] == "translation"
    assert resp.json()["details"]["operation"] == "translation"


def test_unhandled_translation_runtime_error_keeps_message_in_production(
    _no_api_key: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bootstrap()
    app = create_app()

    @app.get("/debug/translation/runtime")
    async def debug_translation_runtime() -> None:
        raise RuntimeError("Translation provider returned malformed output.")

    monkeypatch.setattr(error_handler_module, "DEBUG_ERRORS", False)
    c = TestClient(app, raise_server_exceptions=False)
    resp = c.get("/debug/translation/runtime")
    payload = resp.json()

    assert resp.status_code == 502
    assert payload["code"] == "TRANSLATION_ERROR"
    assert payload["category"] == "translation"
    assert payload["message"] == "Translation provider returned malformed output."
    assert payload["detail"] == "Translation provider returned malformed output."


def test_unhandled_error_payload_distinguishes_source_parse_error(_no_api_key: None) -> None:
    bootstrap()
    app = create_app()

    @app.get("/debug/scrape")
    async def debug_scrape() -> None:
        raise RuntimeError("Source returned invalid chapter text for https://example.test/1.")

    c = TestClient(app, raise_server_exceptions=False)
    resp = c.get("/debug/scrape")

    assert resp.status_code == 502
    assert resp.json()["code"] == "SOURCE_PARSE_ERROR"
    assert resp.json()["category"] == "crawler"
    assert resp.json()["message"] == "Source returned invalid chapter text for https://example.test/1."
    assert resp.json()["detail"] == "Source returned invalid chapter text for https://example.test/1."


def test_unhandled_error_payload_distinguishes_storage_permission_error(_no_api_key: None) -> None:
    bootstrap()
    app = create_app()

    @app.get("/debug/storage")
    async def debug_storage() -> None:
        raise PermissionError("storage directory is not writable")

    c = TestClient(app, raise_server_exceptions=False)
    resp = c.get("/debug/storage")

    assert resp.status_code == 500
    assert resp.json()["code"] == "STORAGE_PERMISSION_ERROR"
    assert resp.json()["category"] == "storage"


def test_custom_novelai_error_handlers_use_domain_codes(_no_api_key: None) -> None:
    bootstrap()
    app = create_app()

    @app.get("/debug/custom-pipeline")
    async def debug_custom_pipeline() -> None:
        raise PipelineError("translation stage failed")

    @app.get("/debug/custom-storage")
    async def debug_custom_storage() -> None:
        raise StorageError("library write failed")

    @app.get("/debug/custom-export")
    async def debug_custom_export() -> None:
        raise ExportError("epub generation failed")

    @app.get("/debug/custom-config")
    async def debug_custom_config() -> None:
        raise ConfigError("missing provider configuration")

    @app.get("/debug/custom-application")
    async def debug_custom_application() -> None:
        raise NovelAIError("uncategorized application failure")

    c = TestClient(app, raise_server_exceptions=False)
    expected = {
        "/debug/custom-pipeline": (502, "PIPELINE_ERROR", "translation"),
        "/debug/custom-storage": (500, "STORAGE_ERROR", "storage"),
        "/debug/custom-export": (424, "EXPORT_ERROR", "export"),
        "/debug/custom-config": (500, "CONFIGURATION_ERROR", "config"),
        "/debug/custom-application": (500, "APPLICATION_ERROR", "application"),
    }
    seen_codes: set[str] = set()

    for path, (status_code, code, category) in expected.items():
        resp = c.get(path)
        payload = resp.json()
        assert resp.status_code == status_code
        assert payload["code"] == code
        assert payload["category"] == category
        assert payload["code"] not in seen_codes
        seen_codes.add(payload["code"])


class StubJobOrchestrator:
    def __init__(self, storage: StorageService) -> None:
        self.storage = storage
        self.calls: list[tuple[str, tuple[object, ...], dict[str, object]]] = []

    async def scrape_metadata(self, *args: object, **kwargs: object) -> dict[str, object]:
        self.calls.append(("scrape_metadata", args, kwargs))
        return {
            "title": "Original Title",
            "translated_title": "Translated Title",
            "author": "Original Author",
            "translated_author": "Translated Author",
            "synopsis": "Original Synopsis",
            "translated_synopsis": "Translated Synopsis",
            "chapters": [
                {
                    "id": "1",
                    "title": "Chapter One",
                    "translated_title": "Translated Chapter One",
                    "part": "Part One",
                    "date_added": "2025/01/13 20:00",
                }
            ],
        }

    async def scrape_chapters(self, *args: object, **kwargs: object) -> None:
        self.calls.append(("scrape_chapters", args, kwargs))

    async def translate_chapters(self, *args: object, **kwargs: object) -> None:
        self.calls.append(("translate_chapters", args, kwargs))


class FallbackPreliminaryOrchestrator(StubJobOrchestrator):
    async def scrape_metadata(self, *args: object, **kwargs: object) -> dict[str, object]:
        self.calls.append(("scrape_metadata", args, kwargs))
        source_key = str(args[0])
        if source_key == "syosetu_ncode":
            return {"chapters": []}
        return {"title": "Novel18 Test", "chapters": [{"id": "1"}, {"id": "2"}]}


class SyosetuPreliminaryFallbackOrchestrator(StubJobOrchestrator):
    async def scrape_metadata(self, *args: object, **kwargs: object) -> dict[str, object]:
        self.calls.append(("scrape_metadata", args, kwargs))
        source_key = str(args[0])
        if source_key == "novel18_syosetu":
            return {"chapters": []}
        return {"title": "Syosetu Test", "chapters": [{"id": "1"}]}


class FailingPreliminaryOrchestrator(StubJobOrchestrator):
    async def scrape_metadata(self, *args: object, **kwargs: object) -> dict[str, object]:
        self.calls.append(("scrape_metadata", args, kwargs))
        raise RuntimeError(f"{args[0]} unavailable")


class TimeoutThenEmptyPreliminaryOrchestrator(StubJobOrchestrator):
    async def scrape_metadata(self, *args: object, **kwargs: object) -> dict[str, object]:
        self.calls.append(("scrape_metadata", args, kwargs))
        source_key = str(args[0])
        if source_key == "novel18_syosetu":
            raise TimeoutError("source timeout")
        return {"chapters": []}


class StubRunner:
    def __init__(self) -> None:
        self.running = False
        self.activity_processed = 0

    def status(self) -> dict[str, object]:
        return {
            "running": self.running,
            "poll_seconds": 0.05,
            "activity_type": None,
            "job_type": None,
            "started_at": "start" if self.running else None,
            "stopped_at": None if self.running else "stop",
            "last_tick_at": None,
            "last_activity_id": "activity-1" if self.activity_processed else None,
            "last_job_id": "activity-1" if self.activity_processed else None,
            "last_error": None,
            "activity_processed": self.activity_processed,
            "jobs_processed": self.activity_processed,
            "idle_ticks": 0,
            "error_count": 0,
        }

    async def start(self) -> dict[str, object]:
        self.running = True
        return self.status()

    async def stop(self) -> dict[str, object]:
        self.running = False
        return self.status()

    async def run_once(self) -> dict[str, object]:
        self.activity_processed += 1
        return {"id": "activity-1", "status": "completed"}


class _FakeGeminiModelsAPI:
    def generate_content(self, **kwargs: object) -> object:
        return SimpleNamespace(text="ok")


class _FakeGeminiClient:
    def __init__(self, *, api_key: str) -> None:
        self.api_key = api_key
        self.models = _FakeGeminiModelsAPI()


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _clean_tmp():
    old_openai_key = settings.PROVIDER_OPENAI_API_KEY
    old_gemini_key = settings.PROVIDER_GEMINI_API_KEY
    novels._hits.clear()
    if _TMP.exists():
        shutil.rmtree(_TMP, ignore_errors=True)
    _TMP.mkdir(parents=True, exist_ok=True)
    yield
    settings.PROVIDER_OPENAI_API_KEY = old_openai_key
    settings.PROVIDER_GEMINI_API_KEY = old_gemini_key
    novels._hits.clear()
    shutil.rmtree(_TMP, ignore_errors=True)


@pytest.fixture()
def _no_api_key(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(settings, "WEB_API_KEY", None)


@pytest.fixture()
def _with_api_key(monkeypatch: pytest.MonkeyPatch):
    from pydantic import SecretStr
    monkeypatch.setattr(settings, "WEB_API_KEY", SecretStr("test-secret"))


@pytest.fixture()
def client(_no_api_key: None) -> TestClient:
    """Owner-authenticated client."""
    bootstrap()
    return _make_app(_fresh_storage())


@pytest.fixture()
def seeded_client(_no_api_key: None) -> TestClient:
    """Client with a pre-seeded novel."""
    bootstrap()
    storage = _fresh_storage()
    _seed_novel(storage)
    return _make_app(storage)


# ---------------------------------------------------------------------------
# Auth tests
# ---------------------------------------------------------------------------


class TestAuth:
    def test_owner_session_allows_dangerous_access(self, seeded_client: TestClient) -> None:
        resp = seeded_client.get("/novels/")
        assert resp.status_code == 200

    def test_unauthenticated_rejects_dangerous_access_when_web_api_key_unset(self, _no_api_key: None) -> None:
        bootstrap()
        c = _make_app(_fresh_storage(), session_user=None)
        resp = c.get("/novels/")
        assert resp.status_code == 401

    def test_non_owner_rejects_dangerous_access(self, _no_api_key: None) -> None:
        bootstrap()
        c = _make_app(_fresh_storage(), session_user=REGULAR_USER)
        resp = c.get("/novels/")
        assert resp.status_code == 403

    def test_valid_legacy_api_key_does_not_grant_owner_access(self, _with_api_key: None) -> None:
        bootstrap()
        c = _make_app(_fresh_storage(), session_user=None)
        resp = c.get("/novels/", headers={"Authorization": "Bearer test-secret"})
        assert resp.status_code == 401

    def test_bad_legacy_api_key_does_not_change_session_auth_result(self, _with_api_key: None) -> None:
        bootstrap()
        c = _make_app(_fresh_storage(), session_user=REGULAR_USER)
        resp = c.get("/novels/", headers={"Authorization": "Bearer wrong"})
        assert resp.status_code == 403

    @pytest.mark.parametrize(
        ("method", "path", "json_body"),
        [
            ("GET", "/novels/", None),
            ("GET", "/novels/sources", None),
            ("GET", "/novels/admin/worker", None),
            ("GET", "/novels/activity", None),
            ("POST", "/novels/activity/crawl", {"novel_id": "test-n1", "source_key": "dummy", "kind": "chapters"}),
            ("PATCH", "/novels/activity/activity-1", {"status": "failed"}),
            ("DELETE", "/novels/activity/activity-1", None),
            ("POST", "/novels/test-n1/scrape", {"source_key": "dummy", "url": "https://example.com/n1"}),
            ("PUT", "/novels/test-n1/chapters/1/translated", {"text": "edited"}),
            ("POST", "/novels/test-n1/chapters/1/translated/rollback", {"version_id": "v1"}),
            ("PATCH", "/novels/requests/request-1", {"status": "approved"}),
            ("POST", "/novels/test-n1/export", {"format": "epub"}),
            ("GET", "/api/admin/novels", None),
            ("GET", "/api/admin/sources", None),
            ("GET", "/api/admin/worker", None),
            ("GET", "/api/admin/activity", None),
            ("GET", "/api/admin/providers/gemini", None),
            ("POST", "/api/admin/activity/crawl", {"novel_id": "test-n1", "source_key": "dummy", "kind": "chapters"}),
            ("PATCH", "/api/admin/activity/activity-1", {"status": "failed"}),
            ("DELETE", "/api/admin/activity/activity-1", None),
            ("POST", "/api/admin/novels/test-n1/scrape", {"source_key": "dummy", "url": "https://example.com/n1"}),
            ("PUT", "/api/admin/novels/test-n1/chapters/1/translated", {"text": "edited"}),
            ("POST", "/api/admin/novels/test-n1/chapters/1/translated/rollback", {"version_id": "v1"}),
            ("PATCH", "/api/admin/requests/request-1", {"status": "approved"}),
            ("POST", "/api/admin/novels/test-n1/export", {"format": "epub"}),
        ],
    )
    def test_dangerous_routes_reject_guest_and_non_owner(
        self,
        _no_api_key: None,
        method: str,
        path: str,
        json_body: dict[str, object] | None,
    ) -> None:
        bootstrap()
        storage = _fresh_storage()
        _seed_novel(storage)
        guest = _make_app(storage, session_user=None)
        user = _make_app(storage, session_user=REGULAR_USER)

        guest_resp = guest.request(method, path, json=json_body)
        user_resp = user.request(method, path, json=json_body)

        assert guest_resp.status_code == 401
        assert user_resp.status_code == 403

    def test_public_guest_route_still_works(self, _no_api_key: None) -> None:
        bootstrap()
        storage = _fresh_storage()
        _seed_novel(storage)
        c = _make_app(storage, session_user=None)

        resp = c.get("/api/public/catalog")

        assert resp.status_code == 200

    def test_user_route_still_requires_user_session(self, _no_api_key: None) -> None:
        bootstrap()
        guest = _make_app(_fresh_storage(), session_user=None)

        resp = guest.get("/api/user/library")

        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# List / Detail endpoints
# ---------------------------------------------------------------------------


class TestListDetail:
    def test_api_health(self, client: TestClient) -> None:
        resp = client.get("/api/health")
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}

    def test_api_prefixed_novels_route(self, seeded_client: TestClient) -> None:
        resp = seeded_client.get("/api/novels/")
        assert resp.status_code == 200
        assert resp.json()[0]["novel_id"] == "test-n1"

    def test_api_prefixed_novels_route_without_trailing_slash_does_not_redirect(self, seeded_client: TestClient) -> None:
        resp = seeded_client.get("/api/novels", follow_redirects=False)
        assert resp.status_code == 200
        assert resp.json()[0]["novel_id"] == "test-n1"

    def test_api_admin_novels_route_without_trailing_slash_does_not_redirect(self, seeded_client: TestClient) -> None:
        resp = seeded_client.get("/api/admin/novels", follow_redirects=False)
        assert resp.status_code == 200
        assert resp.json()[0]["novel_id"] == "test-n1"

    def test_list_novels_empty(self, client: TestClient) -> None:
        resp = client.get("/novels/")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_list_novels_with_data(self, seeded_client: TestClient) -> None:
        resp = seeded_client.get("/novels/")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) >= 1
        assert data[0]["novel_id"] == "test-n1"
        assert data[0]["chapter_count"] == 2
        assert data[0]["scraped_count"] == 1
        assert data[0]["translated_count"] == 1

    def test_list_novels_includes_legacy_syosetu_folder_without_metadata(self, _no_api_key: None) -> None:
        bootstrap()
        storage = _fresh_storage()
        novel_dir = storage.novels_dir / "0813kx"
        chapter_dir = novel_dir / "chapters"
        chapter_dir.mkdir(parents=True)
        (chapter_dir / "1.json").write_text(
            json.dumps({"id": "1", "raw": {"text": "raw chapter"}}, ensure_ascii=False),
            encoding="utf-8",
        )
        c = _make_app(storage)

        resp = c.get("/novels/")
        assert resp.status_code == 200
        data = resp.json()

        assert data == [
            {
                "novel_id": "n0813kx",
                "title": "n0813kx",
                "author": None,
                "source": None,
                "source_url": None,
                "chapter_count": 1,
                "scraped_count": 1,
                "translated_count": 0,
            }
        ]

    def test_get_novel(self, seeded_client: TestClient) -> None:
        resp = seeded_client.get("/novels/test-n1")
        assert resp.status_code == 200
        assert resp.json()["title"] == "Test Novel"

    def test_get_novel_not_found(self, client: TestClient) -> None:
        resp = client.get("/novels/does-not-exist")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Chapter endpoints
# ---------------------------------------------------------------------------


class TestChapters:
    def test_list_chapters(self, seeded_client: TestClient) -> None:
        resp = seeded_client.get("/novels/test-n1/chapters")
        assert resp.status_code == 200
        chapters = resp.json()
        assert len(chapters) == 2
        assert chapters[0]["id"] == "1"

    def test_get_chapter(self, seeded_client: TestClient) -> None:
        resp = seeded_client.get("/novels/test-n1/chapters/1")
        assert resp.status_code == 200
        assert "text" in resp.json()

    def test_get_chapter_not_found(self, seeded_client: TestClient) -> None:
        resp = seeded_client.get("/novels/test-n1/chapters/999")
        assert resp.status_code == 404

    def test_get_translated_chapter(self, seeded_client: TestClient) -> None:
        resp = seeded_client.get("/novels/test-n1/chapters/1/translated")
        assert resp.status_code == 200
        payload = resp.json()
        assert payload["chapter_id"] == "1"
        _assert_provider_mirrors(payload)

    def test_get_translated_chapter_not_found(self, seeded_client: TestClient) -> None:
        resp = seeded_client.get("/novels/test-n1/chapters/2/translated")
        assert resp.status_code == 404

    def test_list_translated_chapter_versions(self, seeded_client: TestClient) -> None:
        resp = seeded_client.get("/novels/test-n1/chapters/1/translated/versions")
        assert resp.status_code == 200
        data = resp.json()
        assert data["chapter_id"] == "1"
        assert len(data["versions"]) == 1
        assert data["versions"][0]["text"] == "Translated ch1"
        assert data["versions"][0]["active"] is True
        _assert_provider_mirrors(data["versions"][0])

    def test_update_translated_chapter_creates_edit_history(self, seeded_client: TestClient) -> None:
        resp = seeded_client.put(
            "/novels/test-n1/chapters/1/translated",
            json={"text": "Edited ch1", "editor": "admin", "note": "line edit"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["text"] == "Edited ch1"
        assert data["version_kind"] == "manual_edit"
        _assert_provider_mirrors(data)

        history_resp = seeded_client.get("/novels/test-n1/chapters/1/translated/edit-history")
        assert history_resp.status_code == 200
        history = history_resp.json()["history"]
        assert len(history) == 1
        assert history[0]["action"] == "manual_edit"
        assert history[0]["editor"] == "admin"

    def test_rollback_translated_chapter_version(self, seeded_client: TestClient) -> None:
        edit_resp = seeded_client.put(
            "/novels/test-n1/chapters/1/translated",
            json={"text": "Edited ch1", "editor": "admin"},
        )
        assert edit_resp.status_code == 200

        rollback_resp = seeded_client.post(
            "/novels/test-n1/chapters/1/translated/rollback",
            json={"version_id": "v1", "editor": "admin", "note": "restore original"},
        )
        assert rollback_resp.status_code == 200
        rollback_payload = rollback_resp.json()
        assert rollback_payload["text"] == "Translated ch1"
        assert rollback_payload["version_id"] == "v1"
        _assert_provider_mirrors(rollback_payload)

        history_resp = seeded_client.get("/novels/test-n1/chapters/1/translated/edit-history")
        history = history_resp.json()["history"]
        assert history[-1]["action"] == "rollback"
        assert history[-1]["previous_version_id"] == "v2"


# ---------------------------------------------------------------------------
# Reader endpoints
# ---------------------------------------------------------------------------


class TestReader:
    def test_get_reader_novel(self, seeded_client: TestClient) -> None:
        resp = seeded_client.get("/novels/test-n1/reader")

        assert resp.status_code == 200
        data = resp.json()
        assert data["novel_id"] == "test-n1"
        assert data["title"] == "Test Novel"
        assert data["chapter_count"] == 2
        assert data["translated_count"] == 1
        assert data["chapters"][0]["translated"] is True
        assert data["chapters"][1]["translated"] is False

    def test_get_reader_chapter(self, seeded_client: TestClient) -> None:
        resp = seeded_client.get("/novels/test-n1/reader/chapters/1")

        assert resp.status_code == 200
        data = resp.json()
        assert data["chapter_id"] == "1"
        assert data["title"] == "Ch1"
        assert data["text"] == "Translated ch1"
        assert data["previous_chapter_id"] is None
        assert data["next_chapter_id"] == "2"

    def test_get_reader_chapter_requires_translation(self, seeded_client: TestClient) -> None:
        resp = seeded_client.get("/novels/test-n1/reader/chapters/2")

        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Delete endpoint
# ---------------------------------------------------------------------------


class TestDelete:
    def test_delete_novel(self, seeded_client: TestClient) -> None:
        resp = seeded_client.delete("/novels/test-n1")
        assert resp.status_code == 204
        # Verify gone
        resp2 = seeded_client.get("/novels/test-n1")
        assert resp2.status_code == 404

    def test_delete_novel_not_found(self, client: TestClient) -> None:
        resp = client.delete("/novels/does-not-exist")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Progress endpoint
# ---------------------------------------------------------------------------


class TestProgress:
    def test_progress(self, seeded_client: TestClient) -> None:
        resp = seeded_client.get("/novels/test-n1/progress")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 2
        assert data["scraped"] >= 1

    def test_progress_not_found(self, client: TestClient) -> None:
        resp = client.get("/novels/does-not-exist/progress")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Sources endpoint
# ---------------------------------------------------------------------------


class TestSources:
    def test_list_sources(self, client: TestClient) -> None:
        resp = client.get("/novels/sources")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)


# ---------------------------------------------------------------------------
# Admin endpoints
# ---------------------------------------------------------------------------


class TestAdmin:
    def test_admin_dashboard_html(self, _no_api_key: None) -> None:
        bootstrap()
        storage = _fresh_storage()
        runner = StubRunner()
        c = _make_app(storage, runner=runner)  # type: ignore[arg-type]

        resp = c.get("/novels/admin")

        assert resp.status_code == 200
        assert "Novel AI Admin" in resp.text
        assert "worker-status" in resp.text

    def test_admin_worker_controls(self, _no_api_key: None) -> None:
        bootstrap()
        storage = _fresh_storage()
        runner = StubRunner()
        c = _make_app(storage, runner=runner)  # type: ignore[arg-type]

        status_resp = c.get("/novels/admin/worker")
        assert status_resp.status_code == 200
        assert status_resp.json()["running"] is False
        canonical_status_resp = c.get("/api/admin/worker")
        assert canonical_status_resp.status_code == 200
        assert canonical_status_resp.json()["running"] is False

        start_resp = c.post("/novels/admin/worker/start")
        assert start_resp.status_code == 200
        assert start_resp.json()["running"] is True

        run_once_resp = c.post("/novels/admin/worker/run-once")
        assert run_once_resp.status_code == 200
        assert run_once_resp.json()["activity"]["id"] == "activity-1"
        assert run_once_resp.json()["job"]["id"] == "activity-1"
        assert run_once_resp.json()["worker"]["activity_processed"] == 1

        stop_resp = c.post("/novels/admin/worker/stop")
        assert stop_resp.status_code == 200
        assert stop_resp.json()["running"] is False

    def test_admin_provider_api_key_updates_runtime_and_global_provider(
        self,
        _no_api_key: None,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        bootstrap()
        monkeypatch.setattr(settings, "PROVIDER_GEMINI_API_KEY", None)
        monkeypatch.setattr(
            GeminiProvider,
            "_modern_client",
            staticmethod(lambda: _FakeGeminiClient),
        )
        storage = _fresh_storage()
        preferences = PreferencesService(_TMP / "prefs")
        c = _make_app(storage, preferences=preferences)

        status_resp = c.get("/novels/admin/provider-api-key/gemini")
        assert status_resp.status_code == 200
        assert status_resp.json()["configured"] is False
        assert status_resp.json()["provider_key"] == "gemini"
        assert status_resp.json()["provider_model"] == "gemini-2.5-flash"
        canonical_status_resp = c.get("/api/admin/provider-api-key/gemini")
        assert canonical_status_resp.status_code == 200
        assert canonical_status_resp.json()["provider_key"] == "gemini"
        credential_resp = c.get("/api/admin/providers/gemini")
        assert credential_resp.status_code == 200
        assert credential_resp.json()["id"] == "gemini"
        assert credential_resp.json()["configured"] is False
        assert credential_resp.json()["validation_status"] == "Unchecked"

        set_resp = c.post(
            "/novels/admin/provider-api-key",
            json={"provider_key": "gemini", "api_key": "AIza-test-key"},
        )

        assert set_resp.status_code == 200
        assert set_resp.json()["configured"] is True
        assert set_resp.json()["preferred_provider"] == "gemini"
        assert set_resp.json()["preferred_provider_key"] == "gemini"
        assert set_resp.json()["model"] == "gemini-2.5-flash"
        assert set_resp.json()["provider_model"] == "gemini-2.5-flash"
        assert set_resp.json()["validation_status"] == "working"
        assert preferences.get_api_key("gemini") == "AIza-test-key"
        assert preferences.get_preferred_provider() == "gemini"
        assert preferences.get_preferred_model() == "gemini-2.5-flash"
        assert preferences.get_llm_step_config("body_translation")["provider"] == "gemini"
        canonical_credential_resp = c.get("/api/admin/providers/gemini")
        assert canonical_credential_resp.status_code == 200
        assert canonical_credential_resp.json()["configured"] is True
        assert canonical_credential_resp.json()["is_active"] is True

        clear_resp = c.delete("/novels/admin/provider-api-key/gemini")
        assert clear_resp.status_code == 200
        assert clear_resp.json()["configured"] is False

    def test_admin_provider_api_key_validate_checks_temporary_key_without_storing(
        self,
        _no_api_key: None,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        bootstrap()
        monkeypatch.setattr(settings, "PROVIDER_GEMINI_API_KEY", None)
        monkeypatch.setattr(
            GeminiProvider,
            "_modern_client",
            staticmethod(lambda: _FakeGeminiClient),
        )
        storage = _fresh_storage()
        preferences = PreferencesService(_TMP / "prefs")
        c = _make_app(storage, preferences=preferences)

        resp = c.post(
            "/novels/admin/provider-api-key/validate",
            json={"provider_key": "gemini", "api_key": "AIza-temp-key"},
        )

        assert resp.status_code == 200
        assert resp.json()["validation_status"] == "working"
        assert preferences.get_api_key("gemini") is None
        canonical_resp = c.post(
            "/api/admin/providers/gemini/validate",
            json={"api_key": "AIza-temp-key"},
        )
        assert canonical_resp.status_code == 200
        assert canonical_resp.json()["validation_status"] == "Working"
        assert preferences.get_api_key("gemini") is None

    def test_admin_runtime_state_can_list_refresh_and_clear(self, _no_api_key: None) -> None:
        bootstrap()
        data_dir = _TMP / "runtime_state"
        shutil.rmtree(data_dir, ignore_errors=True)
        storage = _fresh_storage()
        preferences = PreferencesService(data_dir)
        cache = TranslationCache(data_dir)
        usage = UsageService(data_dir)
        preferences.set_preferred_provider("gemini")
        cache.set("source", "gemini", "gemini-2.5-flash", "translated")
        usage.record({"timestamp": "2026-06-03T00:00:00Z", "tokens": 12})
        c = _make_app(
            storage,
            preferences=preferences,
            translation_cache=cache,
            usage=usage,
        )

        list_resp = c.get("/novels/admin/runtime-state")

        assert list_resp.status_code == 200
        canonical_list_resp = c.get("/api/admin/runtime-state")
        assert canonical_list_resp.status_code == 200
        items = {item["key"]: item for item in list_resp.json()["items"]}
        canonical_items = {item["key"]: item for item in canonical_list_resp.json()["items"]}
        assert set(items) == {"preferences", "translation_cache", "usage"}
        assert set(canonical_items) == set(items)
        assert items["preferences"]["exists"] is True
        assert items["translation_cache"]["affects_process"] is True
        assert items["usage"]["affects_process"] is False

        refresh_resp = c.post("/novels/admin/runtime-state/preferences/refresh")
        assert refresh_resp.status_code == 200
        assert refresh_resp.json()["key"] == "preferences"

        clear_cache_resp = c.delete("/novels/admin/runtime-state/translation_cache")
        assert clear_cache_resp.status_code == 200
        assert cache.get("source", "gemini", "gemini-2.5-flash") is None

        clear_usage_resp = c.delete("/novels/admin/runtime-state/usage")
        assert clear_usage_resp.status_code == 200
        assert usage.summary(all_days=True)["total_requests"] == 0

        clear_preferences_resp = c.delete("/novels/admin/runtime-state/preferences")
        assert clear_preferences_resp.status_code == 200
        assert preferences.get_preferred_provider() == "dummy"


# ---------------------------------------------------------------------------
# Activity queue endpoints
# ---------------------------------------------------------------------------


class TestActivity:
    def test_create_and_list_crawl_activity(self, _no_api_key: None) -> None:
        bootstrap()
        storage = _fresh_storage()
        jobs = ActivityQueueService(_TMP / "jobs")
        c = _make_app(storage, jobs)

        create_resp = c.post(
            "/novels/activity/crawl",
            json={
                "novel_id": "test-n1",
                "source_key": "syosetu_ncode",
                "kind": "metadata",
                "source_url": "https://ncode.syosetu.com/n1234ab/",
            },
        )
        assert create_resp.status_code == 200
        created = create_resp.json()
        assert created["type"] == "crawl"
        assert created["status"] == "pending"

        activity_resp = c.get("/novels/activity", params={"activity_type": "crawl", "status": "pending"})
        assert activity_resp.status_code == 200
        activity_list = activity_resp.json()["activity"]
        assert len(activity_list) == 1
        assert activity_list[0]["id"] == created["id"]
        canonical_activity_resp = c.get("/api/admin/activity", params={"activity_type": "crawl", "status": "pending"})
        assert canonical_activity_resp.status_code == 200
        assert canonical_activity_resp.json()["activity"][0]["id"] == created["id"]

        list_resp = c.get("/novels/activity", params={"activity_type": "crawl", "status": "pending"})
        assert list_resp.status_code == 200
        listed = list_resp.json()["activity"]
        assert len(listed) == 1
        assert listed[0]["id"] == created["id"]

        alias_resp = c.get("/novels/jobs", params={"job_type": "crawl", "status": "pending"})
        assert alias_resp.status_code == 200
        assert alias_resp.json()["jobs"][0]["id"] == created["id"]

    def test_create_update_and_get_translation_activity(self, _no_api_key: None) -> None:
        bootstrap()
        storage = _fresh_storage()
        jobs = ActivityQueueService(_TMP / "jobs")
        c = _make_app(storage, jobs)

        create_resp = c.post(
            "/novels/activity/translation",
            json={
                "novel_id": "test-n1",
                "chapters": "1-2",
                "provider_key": "openai",
                "provider_model": "gpt-5.4",
            },
        )
        assert create_resp.status_code == 200
        created_payload = create_resp.json()
        job_id = created_payload["id"]
        assert created_payload["provider"] == "openai"
        assert created_payload["model"] == "gpt-5.4"
        assert created_payload["provider_key"] == "openai"
        assert created_payload["provider_model"] == "gpt-5.4"

        update_resp = c.patch(
            f"/novels/activity/{job_id}",
            json={"status": "running", "metadata": {"worker": "local"}},
        )
        assert update_resp.status_code == 200
        assert update_resp.json()["status"] == "running"
        assert update_resp.json()["started_at"] is not None

        get_resp = c.get(f"/novels/activity/{job_id}")
        assert get_resp.status_code == 200
        assert get_resp.json()["metadata"]["worker"] == "local"

    def test_activity_progress_fields_are_exposed_for_frontend(self, _no_api_key: None) -> None:
        bootstrap()
        storage = _fresh_storage()
        jobs = ActivityQueueService(_TMP / "jobs")
        created = jobs.create_translation_activity(
            novel_id="test-n1",
            chapters="all",
            provider="gemini",
            model="gemini-2.5-flash-lite",
            metadata={
                "progress": {
                    "current_stage": "TranslateStage",
                    "current_label": "Chapter 2 / Chunk 3",
                    "completed": 27,
                    "total": 100,
                    "warnings": [{"code": "model_switch_warning"}],
                    "errors": [{"code": "provider_rate_limited"}],
                    "model_states": [
                        {
                            "provider_key": "gemini",
                            "provider_model": "gemini-2.5-flash-lite",
                            "status": "cooling_down",
                            "cooldown_until": "2026-06-04T12:01:00Z",
                        }
                    ],
                }
            },
        )
        c = _make_app(storage, jobs)

        get_resp = c.get(f"/novels/activity/{created['id']}")
        list_resp = c.get("/novels/activity", params={"activity_type": "translation"})

        payload = get_resp.json()
        assert get_resp.status_code == 200
        assert payload["id"] == created["id"]
        assert payload["activity_id"] == created["id"]
        assert payload["job_id"] == created["id"]
        assert payload["provider"] == "gemini"
        assert payload["model"] == "gemini-2.5-flash-lite"
        assert payload["provider_key"] == "gemini"
        assert payload["provider_model"] == "gemini-2.5-flash-lite"
        assert payload["current_stage"] == "TranslateStage"
        assert payload["current_label"] == "Chapter 2 / Chunk 3"
        assert payload["completed"] == 27
        assert payload["total"] == 100
        assert payload["paused_reason"] is None
        assert payload["resume_after"] is None
        assert payload["warnings"][0]["code"] == "model_switch_warning"
        assert payload["errors"][0]["code"] == "provider_rate_limited"
        assert payload["model_states"][0]["status"] == "cooling_down"
        assert list_resp.json()["activity"][0]["current_stage"] == "TranslateStage"
        assert list_resp.json()["jobs"][0]["job_id"] == created["id"]

    def test_jobs_aliases_preserve_activity_identifiers_and_provider_mirrors(self, _no_api_key: None) -> None:
        bootstrap()
        storage = _fresh_storage()
        jobs = ActivityQueueService(_TMP / "jobs")
        created = jobs.create_translation_activity(
            novel_id="test-n1",
            chapters="1-2",
            provider="openai",
            model="gpt-5.4",
        )
        c = _make_app(storage, jobs)

        list_resp = c.get("/novels/jobs", params={"job_type": "translation", "status": "pending"})
        detail_resp = c.get(f"/novels/jobs/{created['id']}")

        assert list_resp.status_code == 200
        list_payload = list_resp.json()
        assert len(list_payload["activity"]) == 1
        assert len(list_payload["jobs"]) == 1
        assert list_payload["activity"][0] == list_payload["jobs"][0]
        assert detail_resp.status_code == 200
        detail_payload = detail_resp.json()
        assert detail_payload["id"] == created["id"]
        assert detail_payload["activity_id"] == created["id"]
        assert detail_payload["job_id"] == created["id"]
        assert detail_payload["provider"] == "openai"
        assert detail_payload["model"] == "gpt-5.4"
        assert detail_payload["provider_key"] == "openai"
        assert detail_payload["provider_model"] == "gpt-5.4"

    def test_activity_root_metadata_progress_fields_and_default_arrays_are_normalized(self, _no_api_key: None) -> None:
        bootstrap()
        storage = _fresh_storage()
        jobs = ActivityQueueService(_TMP / "jobs")
        created = jobs.create_crawl_activity(
            novel_id="test-n1",
            source_key="syosetu_ncode",
            kind="chapters",
            metadata={
                "current_stage": "RootStage",
                "current_label": "Root progress",
                "completed": 1,
                "total": 2,
                "paused_reason": "manual_pause",
                "resume_after": "2026-06-04T12:10:00Z",
            },
        )
        c = _make_app(storage, jobs)

        resp = c.get(f"/novels/activity/{created['id']}")

        assert resp.status_code == 200
        payload = resp.json()
        assert payload["id"] == created["id"]
        assert payload["activity_id"] == created["id"]
        assert payload["job_id"] == created["id"]
        assert payload["current_stage"] == "RootStage"
        assert payload["current_label"] == "Root progress"
        assert payload["completed"] == 1
        assert payload["total"] == 2
        assert payload["paused_reason"] == "manual_pause"
        assert payload["resume_after"] == "2026-06-04T12:10:00Z"
        assert payload["errors"] == []
        assert payload["warnings"] == []
        assert payload["model_states"] == []

    def test_delete_activity(self, _no_api_key: None) -> None:
        bootstrap()
        storage = _fresh_storage()
        jobs = ActivityQueueService(_TMP / "jobs")
        c = _make_app(storage, jobs)
        created = jobs.create_crawl_activity(novel_id="test-n1", source_key="syosetu_ncode", kind="metadata")

        delete_resp = c.delete(f"/novels/activity/{created['id']}")

        assert delete_resp.status_code == 204
        assert jobs.get_activity(str(created["id"])) is None
        assert c.delete("/novels/activity/missing").status_code == 404

    def test_invalid_activity_kind_returns_400(self, _no_api_key: None) -> None:
        bootstrap()
        storage = _fresh_storage()
        jobs = ActivityQueueService(_TMP / "jobs")
        c = _make_app(storage, jobs)

        resp = c.post(
            "/novels/activity/crawl",
            json={"novel_id": "test-n1", "source_key": "syosetu_ncode", "kind": "unknown"},
        )
        assert resp.status_code == 400

    def test_run_next_activity_executes_pending_activity(self, _no_api_key: None) -> None:
        bootstrap()
        storage = _fresh_storage()
        jobs = ActivityQueueService(_TMP / "jobs")
        orchestrator = StubJobOrchestrator(storage)
        worker = ActivityWorkerService(jobs, orchestrator)  # type: ignore[arg-type]
        c = _make_app(storage, jobs, worker)

        jobs.create_crawl_activity(novel_id="test-n1", source_key="syosetu_ncode", kind="chapters", chapters="1")

        resp = c.post("/novels/activity/run-next", params={"activity_type": "crawl"})

        assert resp.status_code == 200
        assert resp.json()["status"] == "completed"
        assert resp.json()["metadata"]["result"]["chapters"] == "1"
        assert orchestrator.calls[0][0] == "scrape_chapters"

        health_resp = c.get("/novels/activity/source-health/syosetu_ncode")
        assert health_resp.status_code == 200
        assert health_resp.json()["success_count"] == 1

        list_health_resp = c.get("/novels/activity/source-health")
        assert list_health_resp.status_code == 200
        assert list_health_resp.json()["sources"][0]["source_key"] == "syosetu_ncode"

    def test_run_activity_not_found(self, _no_api_key: None) -> None:
        bootstrap()
        storage = _fresh_storage()
        jobs = ActivityQueueService(_TMP / "jobs")
        worker = ActivityWorkerService(jobs, StubJobOrchestrator(storage))  # type: ignore[arg-type]
        c = _make_app(storage, jobs, worker)

        resp = c.post("/novels/activity/missing/run")

        assert resp.status_code == 404

    def test_run_activity_returns_completed_stored_record(self, _no_api_key: None) -> None:
        bootstrap()
        storage = _fresh_storage()
        jobs = ActivityQueueService(_TMP / "jobs")
        orchestrator = StubJobOrchestrator(storage)
        worker = ActivityWorkerService(jobs, orchestrator)  # type: ignore[arg-type]
        c = _make_app(storage, jobs, worker)
        created = jobs.create_crawl_activity(
            novel_id="test-n1",
            source_key="syosetu_ncode",
            kind="chapters",
            chapters="1",
        )

        resp = c.post(f"/novels/activity/{created['id']}/run")

        assert resp.status_code == 200
        payload = resp.json()
        stored = jobs.get_activity(str(created["id"]))
        assert stored is not None
        assert payload["status"] == "completed"
        assert payload["finished_at"] == stored["finished_at"]
        assert payload["metadata"] == stored["metadata"]


# ---------------------------------------------------------------------------
# Novel request endpoints
# ---------------------------------------------------------------------------


def _assert_request_id_mirror(payload: dict[str, object]) -> str:
    assert "id" in payload
    assert "request_id" in payload
    assert payload["request_id"] == payload["id"]
    return str(payload["id"])


def _assert_source_candidate_url_mirror(payload: dict[str, object]) -> str | None:
    assert "url" in payload
    assert "source_url" in payload
    assert payload["source_url"] == payload["url"]
    return str(payload["url"]) if payload["url"] is not None else None


class TestNovelRequests:
    def test_create_vote_and_list_request(self, _no_api_key: None) -> None:
        bootstrap()
        storage = _fresh_storage()
        requests = NovelRequestService(_TMP / "requests")
        c = _make_app(storage, requests=requests)

        create_resp = c.post(
            "/novels/requests",
            json={
                "title": "Requested Novel",
                "source_key": "syosetu_ncode",
                "source_url": "https://ncode.syosetu.com/n1234ab/",
                "requested_by": "reader-1",
            },
        )
        assert create_resp.status_code == 200
        request_id = _assert_request_id_mirror(create_resp.json())

        vote_resp = c.post(f"/novels/requests/{request_id}/vote", json={"voter": "reader-2"})
        assert vote_resp.status_code == 200
        voted = vote_resp.json()
        assert voted["vote_count"] == 1
        assert _assert_request_id_mirror(voted) == request_id

        list_resp = c.get("/novels/requests", params={"status": "pending"})
        assert list_resp.status_code == 200
        listed = list_resp.json()["requests"]
        assert len(listed) == 1
        assert listed[0]["id"] == request_id
        assert _assert_request_id_mirror(listed[0]) == request_id
        assert listed[0]["source_candidates"][0]["source_key"] == "syosetu_ncode"
        assert _assert_source_candidate_url_mirror(listed[0]["source_candidates"][0]) == "https://ncode.syosetu.com/n1234ab/"
        canonical_list_resp = c.get("/api/admin/requests", params={"status": "pending"})
        assert canonical_list_resp.status_code == 200
        assert canonical_list_resp.json()["requests"][0]["id"] == request_id

    def test_update_request_status_and_add_source_candidate(self, _no_api_key: None) -> None:
        bootstrap()
        storage = _fresh_storage()
        requests = NovelRequestService(_TMP / "requests")
        c = _make_app(storage, requests=requests)
        request_id = _assert_request_id_mirror(c.post("/novels/requests", json={"title": "Requested Novel"}).json())

        status_resp = c.patch(
            f"/novels/requests/{request_id}",
            json={"status": "approved", "reviewed_by": "admin"},
        )
        assert status_resp.status_code == 200
        status_payload = status_resp.json()
        assert status_payload["status"] == "approved"
        assert _assert_request_id_mirror(status_payload) == request_id

        candidate_resp = c.post(
            f"/novels/requests/{request_id}/source-candidates",
            json={"source_key": "kakuyomu", "source_url": "https://kakuyomu.jp/works/123"},
        )
        assert candidate_resp.status_code == 200
        candidate_payload = candidate_resp.json()
        assert candidate_payload["source_key"] == "kakuyomu"
        assert _assert_source_candidate_url_mirror(candidate_payload) == "https://kakuyomu.jp/works/123"

        get_resp = c.get(f"/novels/requests/{request_id}")
        assert get_resp.status_code == 200
        get_payload = get_resp.json()
        assert len(get_payload["source_candidates"]) == 1
        assert _assert_request_id_mirror(get_payload) == request_id
        assert _assert_source_candidate_url_mirror(get_payload["source_candidates"][0]) == "https://kakuyomu.jp/works/123"

    def test_invalid_request_status_returns_400(self, _no_api_key: None) -> None:
        bootstrap()
        storage = _fresh_storage()
        requests = NovelRequestService(_TMP / "requests")
        c = _make_app(storage, requests=requests)
        request_id = c.post("/novels/requests", json={"title": "Requested Novel"}).json()["id"]

        resp = c.patch(f"/novels/requests/{request_id}", json={"status": "not-real"})

        assert resp.status_code == 400


# ---------------------------------------------------------------------------
# Rate limiting
# ---------------------------------------------------------------------------


class TestRateLimit:
    def test_preliminary_crawl_scrapes_metadata_only(self, _no_api_key: None) -> None:
        bootstrap()
        storage = _fresh_storage()
        jobs = ActivityQueueService(_TMP / "jobs")
        orchestrator = StubJobOrchestrator(storage)
        c = _make_app(storage, activity_log=jobs, orchestrator=orchestrator)

        resp = c.post(
            "/novels/n1234ab/preliminary-crawl",
            json={"identifier": "https://ncode.syosetu.com/n1234ab/", "source_key": "syosetu_ncode"},
        )

        assert resp.status_code == 200
        assert resp.json()["chapters"] == 1
        assert resp.json()["source_key"] == "syosetu_ncode"
        assert resp.json()["translated_title"] == "Translated Title"
        assert resp.json()["translated_author"] == "Translated Author"
        assert resp.json()["translated_synopsis"] == "Translated Synopsis"
        assert resp.json()["chapter_list"][0]["translated_title"] == "Translated Chapter One"
        assert resp.json()["chapter_list"][0]["part"] == "Part One"
        assert resp.json()["chapter_list"][0]["date_added"] == "2025/01/13 20:00"
        logged_activity = jobs.list_activity(activity_type="crawl")
        assert len(logged_activity) == 1
        assert logged_activity[0]["status"] == "completed"
        assert logged_activity[0]["kind"] == "metadata"
        assert logged_activity[0]["metadata"]["activity_subtype"] == "crawling"
        assert logged_activity[0]["metadata"]["activity_phase"] == "preliminary_crawl"
        assert logged_activity[0]["metadata"]["result"]["chapter_count"] == 1
        assert resp.json()["activity_log_job_id"] == logged_activity[0]["id"]
        assert orchestrator.calls == [
            (
                "scrape_metadata",
                ("syosetu_ncode", "n1234ab"),
                {
                    "mode": "update",
                    "max_chapter": None,
                    "source_identifier": "https://ncode.syosetu.com/n1234ab/",
                },
            )
        ]

    def test_preliminary_crawl_detects_novel18_url(self, _no_api_key: None) -> None:
        bootstrap()
        storage = _fresh_storage()
        jobs = ActivityQueueService(_TMP / "jobs")
        orchestrator = StubJobOrchestrator(storage)
        c = _make_app(storage, activity_log=jobs, orchestrator=orchestrator)

        resp = c.post(
            "/novels/n1962jz/preliminary-crawl",
            json={"identifier": "https://novel18.syosetu.com/n1962jz/", "source_key": "syosetu_ncode"},
        )

        assert resp.status_code == 200
        assert resp.json()["source_key"] == "novel18_syosetu"
        assert orchestrator.calls[0] == (
            "scrape_metadata",
            ("novel18_syosetu", "n1962jz"),
            {
                "mode": "update",
                "max_chapter": None,
                "source_identifier": "https://novel18.syosetu.com/n1962jz/",
            },
        )

    def test_preliminary_crawl_prefers_novel18_for_bare_ncode_id(self, _no_api_key: None) -> None:
        bootstrap()
        storage = _fresh_storage()
        jobs = ActivityQueueService(_TMP / "jobs")
        orchestrator = FallbackPreliminaryOrchestrator(storage)
        c = _make_app(storage, activity_log=jobs, orchestrator=orchestrator)

        resp = c.post(
            "/novels/n1962jz/preliminary-crawl",
            json={"identifier": "n1962jz", "source_key": "syosetu_ncode"},
        )

        assert resp.status_code == 200
        assert resp.json()["source_key"] == "novel18_syosetu"
        assert resp.json()["chapters"] == 2
        assert [call[1][0] for call in orchestrator.calls] == ["novel18_syosetu"]

    def test_preliminary_crawl_falls_back_to_syosetu_when_novel18_empty(self, _no_api_key: None) -> None:
        bootstrap()
        storage = _fresh_storage()
        jobs = ActivityQueueService(_TMP / "jobs")
        orchestrator = SyosetuPreliminaryFallbackOrchestrator(storage)
        c = _make_app(storage, activity_log=jobs, orchestrator=orchestrator)

        resp = c.post(
            "/novels/n1962jz/preliminary-crawl",
            json={"identifier": "n1962jz", "source_key": "syosetu_ncode"},
        )

        assert resp.status_code == 200
        assert resp.json()["source_key"] == "syosetu_ncode"
        assert resp.json()["chapters"] == 1
        assert [call[1][0] for call in orchestrator.calls] == ["novel18_syosetu", "syosetu_ncode"]

    def test_preliminary_crawl_falls_back_to_syosetu_when_novel18_url_empty(self, _no_api_key: None) -> None:
        bootstrap()
        storage = _fresh_storage()
        jobs = ActivityQueueService(_TMP / "jobs")
        orchestrator = SyosetuPreliminaryFallbackOrchestrator(storage)
        c = _make_app(storage, activity_log=jobs, orchestrator=orchestrator)

        resp = c.post(
            "/novels/n1962jz/preliminary-crawl",
            json={"identifier": "https://novel18.syosetu.com/n1962jz/"},
        )

        assert resp.status_code == 200
        assert resp.json()["source_key"] == "syosetu_ncode"
        assert [call[1][0] for call in orchestrator.calls] == ["novel18_syosetu", "syosetu_ncode"]

    def test_preliminary_crawl_reports_attempt_errors_without_500(self, _no_api_key: None) -> None:
        bootstrap()
        storage = _fresh_storage()
        jobs = ActivityQueueService(_TMP / "jobs")
        orchestrator = FailingPreliminaryOrchestrator(storage)
        c = _make_app(storage, activity_log=jobs, orchestrator=orchestrator)

        resp = c.post(
            "/novels/n1962jz/preliminary-crawl",
            json={"identifier": "n1962jz", "source_key": "syosetu_ncode"},
        )

        assert resp.status_code == 502
        payload = resp.json()
        assert payload["code"] == "PRELIMINARY_CRAWL_FAILED"
        assert "novel18_syosetu" in payload["detail"]
        assert "syosetu_ncode" in payload["detail"]
        assert payload["details"]["attempted_sources"] == ["novel18_syosetu", "syosetu_ncode"]
        logged_activity = jobs.list_activity(activity_type="crawl")
        assert len(logged_activity) == 1
        assert logged_activity[0]["status"] == "failed"
        assert logged_activity[0]["kind"] == "metadata"
        assert logged_activity[0]["metadata"]["preliminary_crawl"] is True
        assert logged_activity[0]["metadata"]["attempted_sources"] == ["novel18_syosetu", "syosetu_ncode"]

    def test_preliminary_crawl_reports_partial_timeout_code(self, _no_api_key: None) -> None:
        bootstrap()
        storage = _fresh_storage()
        jobs = ActivityQueueService(_TMP / "jobs")
        orchestrator = TimeoutThenEmptyPreliminaryOrchestrator(storage)
        c = _make_app(storage, activity_log=jobs, orchestrator=orchestrator)

        resp = c.post(
            "/novels/n1962jz/preliminary-crawl",
            json={"identifier": "n1962jz", "source_key": "novel18_syosetu"},
        )

        assert resp.status_code == 502
        payload = resp.json()
        assert payload["code"] == "PRELIMINARY_CRAWL_PARTIAL_TIMEOUT"
        assert payload["details"]["attempted_sources"] == ["novel18_syosetu", "syosetu_ncode"]
        logged_activity = jobs.list_activity(activity_type="crawl")
        assert logged_activity[0]["metadata"]["failure_code"] == "PRELIMINARY_CRAWL_PARTIAL_TIMEOUT"
        assert logged_activity[0]["metadata"]["failure_category"] == "crawler"
        assert "fallback source" in logged_activity[0]["metadata"]["failure_explanation"]

    def test_scrape_rate_limit(self, _no_api_key: None) -> None:
        """Scrape endpoint should reject after exceeding rate limit."""
        bootstrap()
        storage = _fresh_storage()
        _seed_novel(storage)
        app = create_app()
        app.dependency_overrides[get_current_user] = lambda: OWNER_USER
        app.dependency_overrides[get_storage] = lambda: storage

        mock_orch = AsyncMock()
        mock_orch.scrape_metadata = AsyncMock(return_value={"chapters": []})
        mock_orch.scrape_chapters = AsyncMock()
        app.dependency_overrides[get_orchestrator] = lambda: mock_orch

        with patch("novelai.api.routers.novels._hits", defaultdict(list)):
            c = TestClient(app)
            body = {"url": "https://example.com/n1", "source_key": "dummy"}
            for _ in range(5):
                resp = c.post("/novels/test-n1/scrape", json=body)
                assert resp.status_code == 200
            # 6th should be rate-limited
            resp = c.post("/novels/test-n1/scrape", json=body)
            assert resp.status_code == 429
