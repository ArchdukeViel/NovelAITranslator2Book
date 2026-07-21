"""Tests for the FastAPI web API (auth, CORS, rate limiting, endpoints)."""

from __future__ import annotations

import json
import shutil
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient
from pydantic import BaseModel, SecretStr
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

# ORM models are registered by the session-scoped autouse fixture in conftest.py.
from novelai.activity.queue import ActivityQueueService
from novelai.activity.runner import BackgroundActivityRunner
from novelai.activity.worker import ActivityWorkerService
from novelai.api import error_handlers as error_handler_module
from novelai.api.app import create_app
from novelai.api.auth.session import GUEST, SessionUser, get_current_user
from novelai.api.routers import novels
from novelai.api.routers.dependencies import get_db_session
from novelai.api.routers.novels import (
    get_activity_log,
    get_activity_runner,
    get_activity_worker,
    get_orchestrator,
    get_preferences,
    get_storage,
    get_translation_cache,
    get_usage,
)
from novelai.config.settings import settings
from novelai.core.errors import (
    ConfigError,
    ExportError,
    NovelAIError,
    PipelineError,
    ProviderError,
    ProviderErrorCode,
    StorageError,
)
from novelai.db.base import Base
from novelai.db.models.genre import Genre
from novelai.db.models.novel import Novel
from novelai.db.models.system import ProviderCredential
from novelai.db.models.users import NovelRequest
from novelai.providers.gemini_provider import GeminiProvider
from novelai.runtime.bootstrap import bootstrap
from novelai.services.preferences_service import PreferencesService
from novelai.services.provider_credentials import ProviderCredentialService
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
    storage.save_metadata(
        novel_id,
        {
            "novel_id": novel_id,
            "title": "Test Novel",
            "author": "Author",
            "chapters": [{"id": "1", "title": "Ch1"}, {"id": "2", "title": "Ch2"}],
        },
    )
    storage.save_chapter(novel_id, "1", "Raw text ch1", source_key="dummy", source_url="http://example.com/1")
    storage.save_translated_chapter(novel_id, "1", "Translated ch1", provider="dummy", model="dummy")


def _seed_db_novel(
    session: Session,
    slug: str,
    *,
    title: str | None = None,
    author: str | None = None,
    source_site: str | None = None,
    source_url: str | None = None,
    publication_status: str = "unknown",
    chapter_count: int = 0,
    translated_count: int = 0,
    updated_at: datetime | None = None,
    is_published: bool = False,
) -> Novel:
    novel = Novel(
        slug=slug,
        title=title or f"Title {slug}",
        author=author,
        source_site=source_site,
        source_url=source_url,
        language="ja",
        publication_status=publication_status,
        chapter_count=chapter_count,
        translated_count=translated_count,
        updated_at=updated_at or datetime(2024, 1, 1, tzinfo=UTC),
        is_published=is_published,
    )
    session.add(novel)
    session.commit()
    return novel


def _seed_storage_catalog_metadata(
    storage: StorageService,
    novel_id: str,
    *,
    translated: bool = True,
    translated_title: str = "Translated Public Title",
    translated_synopsis: str = "Translated public synopsis.",
    latest_title: str = "Translated Chapter One",
) -> None:
    storage.save_metadata(
        novel_id,
        {
            "novel_id": novel_id,
            "title": "原題",
            "translated_title": translated_title,
            "author": "Source Author",
            "translated_author": "Translated Author",
            "synopsis": "Source synopsis.",
            "translated_synopsis": translated_synopsis,
            "publication_status": "ongoing",
            "chapters": [
                {
                    "id": "1",
                    "num": 1,
                    "title": "第一話",
                    "translated_title": latest_title,
                },
                {"id": "2", "num": 2, "title": "第二話"},
            ],
        },
    )
    storage.save_chapter(novel_id, "1", "Raw text ch1", source_key="dummy", source_url="https://example.com/1")
    if translated:
        storage.save_translated_chapter(novel_id, "1", "Translated chapter one.", provider="dummy", model="dummy")


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
    orchestrator: object | None = None,
    preferences: PreferencesService | None = None,
    translation_cache: TranslationCache | None = None,
    usage: UsageService | None = None,
    session_user: SessionUser | None = OWNER_USER,
    db_session: Session | None = None,
) -> TestClient:
    """Create a TestClient with storage dependency overridden."""
    app = create_app()
    resolved_session_user = session_user if session_user is not None else GUEST
    app.dependency_overrides[get_current_user] = lambda: resolved_session_user
    app.dependency_overrides[get_storage] = lambda: storage
    if db_session is None:
        app.dependency_overrides[get_db_session] = lambda: None
    else:

        def _db_override():
            yield db_session
            db_session.commit()

        app.dependency_overrides[get_db_session] = _db_override
    if activity_log is not None:
        app.dependency_overrides[get_activity_log] = lambda: activity_log
    if worker is not None:
        app.dependency_overrides[get_activity_worker] = lambda: worker
    if runner is not None:
        app.dependency_overrides[get_activity_runner] = lambda: runner
    if orchestrator is not None:
        app.dependency_overrides[get_orchestrator] = lambda: orchestrator
    if preferences is not None:
        app.dependency_overrides[get_preferences] = lambda: preferences
    if translation_cache is not None:
        app.dependency_overrides[get_translation_cache] = lambda: translation_cache
    if usage is not None:
        app.dependency_overrides[get_usage] = lambda: usage
    return TestClient(app)


def _csrf_headers(client: TestClient) -> dict[str, str]:
    resp = client.get("/api/auth/csrf")
    assert resp.status_code == 200
    return {"X-CSRF-Token": resp.json()["csrf_token"]}


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
        (("GET",), "/catalog-health"),
        (("GET",), "/activity"),
        (("GET",), "/activity/source-health"),
        (("GET",), "/activity/source-health/{source_key}"),
        (("GET",), "/activity/{activity_id}"),
        (("GET",), "/admin"),
        (("GET",), "/admin/providers"),
        (("GET",), "/admin/providers/credentials"),
        (("GET",), "/admin/providers/fallback-policy"),
        (("GET",), "/admin/providers/models"),
        (("GET",), "/admin/providers/{provider_key}"),
        (("GET",), "/admin/provider-api-key/{provider_key}"),
        (("GET",), "/admin/runtime-state"),
        (("GET",), "/admin/worker"),
        (("GET",), "/admin/translation/scheduler-health"),
        (("GET",), "/admin/health/errors"),
        (("GET",), "/admin/novels/{novel_id}/exports/latest/{export_format}"),
        (("GET",), "/admin/novels/{novel_id}/exports"),
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
        (("GET",), "/{novel_id}/checkpoints"),
        (("GET",), "/{novel_id}/translate-status"),
        (("GET",), "/{novel_id}/reader"),
        (("GET",), "/{novel_id}/reader/chapters/{chapter_id}"),
        (("GET",), "/{novel_id}/catalog-projection-health"),
        (("GET",), "/{novel_id}/source-metadata"),
        (("GET",), "/{novel_id}/source-metadata/history"),
        (("GET",), "/{novel_id}/source-metadata/history/diff"),
        (("GET",), "/{novel_id}/source-metadata/history/{snapshot_id}"),
        (("PATCH",), "/activity/{activity_id}"),
        (("PATCH",), "/jobs/{activity_id}"),
        (("PATCH",), "/requests/{request_id}"),
        (("POST",), "/admin/worker/run-once"),
        (("POST",), "/admin/worker/start"),
        (("POST",), "/admin/worker/stop"),
        (("POST",), "/admin/providers"),
        (("POST",), "/admin/providers/credentials"),
        (("POST",), "/admin/providers/credentials/{credential_id}/test"),
        (("POST",), "/admin/providers/{provider_key}/validate"),
        (("POST",), "/admin/provider-api-key"),
        (("POST",), "/admin/provider-api-key/validate"),
        (("POST",), "/admin/runtime-state/{state_key}/refresh"),
        (("POST",), "/admin/runtime-state/cleanup"),
        (("POST",), "/admin/novels/{novel_id}/cache/invalidate"),
        (("POST",), "/activity/crawl"),
        (("POST",), "/activity/run-next"),
        (("POST",), "/activity/translation"),
        (("POST",), "/activity/{activity_id}/retry"),
        (("POST",), "/activity/{activity_id}/run"),
        (("POST",), "/jobs/crawl"),
        (("POST",), "/jobs/run-next"),
        (("POST",), "/jobs/translation"),
        (("POST",), "/jobs/{activity_id}/retry"),
        (("POST",), "/jobs/{activity_id}/run"),
        (("POST",), "/refresh-catalog-projections"),
        (("POST",), "/"),
        (("POST",), "/requests"),
        (("POST",), "/requests/{request_id}/source-candidates"),
        (("POST",), "/requests/{request_id}/vote"),
        (("POST",), "/{novel_id}/chapters/{chapter_id}/translated/rollback"),
        (("POST",), "/{novel_id}/export"),
        (("POST",), "/{novel_id}/import"),
        (("POST",), "/{novel_id}/preliminary-crawl"),
        (("POST",), "/{novel_id}/publish"),
        (("POST",), "/{novel_id}/refresh-catalog-projection"),
        (("POST",), "/{novel_id}/scrape"),
        (("POST",), "/{novel_id}/translate"),
        (("POST",), "/{novel_id}/unpublish"),
        (("POST",), "/{novel_id}/onboarding/cancel"),
        (("POST",), "/{novel_id}/onboarding/resume"),
        (("POST",), "/{novel_id}/retranslate-stale"),
        (("POST",), "/{novel_id}/chapters/{chapter_id}/translated/lint"),
        (("PUT",), "/{novel_id}/chapters/{chapter_id}/translated"),
        (("PUT",), "/admin/providers/fallback-policy"),
        (("PATCH",), "/admin/providers/credentials/{credential_id}"),
        (("DELETE",), "/admin/providers/credentials/{credential_id}"),
        (("DELETE",), "/admin/providers/{provider_key}"),
        (("DELETE",), "/admin/provider-api-key/{provider_key}"),
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

    payload = json.loads(bytes(response.body).decode("utf-8"))

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

    async def scrape_chapters(self, *args: object, **kwargs: object) -> dict[str, object]:
        self.calls.append(("scrape_chapters", args, kwargs))
        return {
            "succeeded": 1,
            "skipped": 0,
            "failed": 0,
            "failures": [],
            "image_download_failures": 0,
        }

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
    old_gemini_key = settings.PROVIDER_GEMINI_API_KEY
    old_provider_credential_key = settings.PROVIDER_CREDENTIAL_ENCRYPTION_KEY
    novels._hits.clear()
    if _TMP.exists():
        shutil.rmtree(_TMP, ignore_errors=True)
    _TMP.mkdir(parents=True, exist_ok=True)
    yield
    settings.PROVIDER_GEMINI_API_KEY = old_gemini_key
    settings.PROVIDER_CREDENTIAL_ENCRYPTION_KEY = old_provider_credential_key
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
def isolated_db_session():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=True)
    session = SessionLocal()
    yield session
    session.close()
    Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture()
def client(_no_api_key: None, isolated_db_session: Session) -> TestClient:
    """Owner-authenticated client."""
    bootstrap()
    return _make_app(_fresh_storage(), db_session=isolated_db_session)


@pytest.fixture()
def seeded_client(_no_api_key: None, isolated_db_session: Session) -> TestClient:
    """Client with a pre-seeded novel."""
    bootstrap()
    storage = _fresh_storage()
    _seed_novel(storage)
    return _make_app(storage, db_session=isolated_db_session)


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
            ("POST", "/novels/activity/activity-1/retry", None),
            ("PATCH", "/novels/activity/activity-1", {"status": "failed"}),
            ("DELETE", "/novels/activity/activity-1", None),
            ("POST", "/novels/test-n1/scrape", {"source_key": "dummy", "url": "https://example.com/n1"}),
            ("POST", "/novels/test-n1/publish", None),
            ("POST", "/novels/test-n1/refresh-catalog-projection", None),
            ("POST", "/novels/test-n1/unpublish", None),
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
            ("POST", "/api/admin/activity/activity-1/retry", None),
            ("PATCH", "/api/admin/activity/activity-1", {"status": "failed"}),
            ("DELETE", "/api/admin/activity/activity-1", None),
            ("POST", "/api/admin/novels/test-n1/scrape", {"source_key": "dummy", "url": "https://example.com/n1"}),
            ("POST", "/api/admin/novels/test-n1/publish", None),
            ("POST", "/api/admin/novels/test-n1/refresh-catalog-projection", None),
            ("POST", "/api/admin/novels/test-n1/unpublish", None),
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


class TestAdminCsrf:
    def test_provider_credential_mutation_requires_and_accepts_csrf(
        self,
        _no_api_key: None,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        bootstrap()
        monkeypatch.setattr(settings, "PROVIDER_GEMINI_API_KEY", None)
        storage = _fresh_storage()
        preferences = PreferencesService(_TMP / "prefs")
        c = _make_app(storage, preferences=preferences)
        body = {
            "provider_key": "gemini",
            "api_key": "AIza-test-key",
            "validate_connection": False,
        }

        assert c.post("/api/admin/provider-api-key", json=body).status_code == 403
        assert (
            c.post(
                "/api/admin/provider-api-key",
                json=body,
                headers={"X-CSRF-Token": "bad"},
            ).status_code
            == 403
        )
        accepted = c.post("/api/admin/provider-api-key", json=body, headers=_csrf_headers(c))

        assert accepted.status_code == 200
        assert preferences.get_api_key("gemini") == "AIza-test-key"

    def test_representative_admin_mutations_reject_missing_csrf(self, _no_api_key: None) -> None:
        bootstrap()
        storage = _fresh_storage()
        _seed_novel(storage)
        jobs = ActivityQueueService(_TMP / "jobs")
        c = _make_app(storage, activity_log=jobs)

        assert (
            c.post(
                "/api/admin/novels/test-n1/scrape",
                json={"source_key": "dummy", "url": "https://example.com/n1"},
            ).status_code
            == 403
        )
        assert (
            c.put(
                "/api/admin/novels/test-n1/chapters/1/translated",
                json={"text": "Edited"},
            ).status_code
            == 403
        )
        assert (
            c.post(
                "/api/admin/activity/crawl",
                json={"novel_id": "test-n1", "source_key": "dummy", "kind": "chapters"},
            ).status_code
            == 403
        )
        assert c.post("/api/admin/novels/test-n1/publish").status_code == 403
        assert c.post("/api/admin/novels/test-n1/refresh-catalog-projection").status_code == 403
        assert (
            c.put(
                "/api/admin/novels/test-n1/taxonomy",
                json={"genre_slugs": [], "tags": []},
            ).status_code
            == 403
        )

    def test_admin_read_only_get_does_not_require_csrf(self, seeded_client: TestClient) -> None:
        resp = seeded_client.get("/api/admin/novels")

        assert resp.status_code == 200

    def test_legacy_alias_mutation_requires_csrf(self, seeded_client: TestClient) -> None:
        resp = seeded_client.post(
            "/novels/test-n1/scrape",
            json={"source_key": "dummy", "url": "https://example.com/n1"},
        )

        assert resp.status_code == 403

    def test_non_owner_with_csrf_still_cannot_mutate_admin_routes(self, _no_api_key: None) -> None:
        bootstrap()
        c = _make_app(_fresh_storage(), session_user=REGULAR_USER)
        resp = c.post(
            "/api/admin/activity/crawl",
            json={"novel_id": "test-n1", "source_key": "dummy", "kind": "chapters"},
            headers=_csrf_headers(c),
        )

        assert resp.status_code == 403

    def test_bearer_api_key_still_does_not_grant_admin_mutation_access(
        self,
        _with_api_key: None,
    ) -> None:
        bootstrap()
        c = _make_app(_fresh_storage(), session_user=None)
        resp = c.post(
            "/api/admin/activity/crawl",
            json={"novel_id": "test-n1", "source_key": "dummy", "kind": "chapters"},
            headers={"Authorization": "Bearer test-secret"},
        )

        assert resp.status_code == 401

    def test_public_guest_route_still_works(self, _no_api_key: None, isolated_db_session: Session) -> None:
        bootstrap()
        storage = _fresh_storage()
        _seed_novel(storage)
        c = _make_app(storage, session_user=None, db_session=isolated_db_session)

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
    def test_api_prefixed_novels_route(self, seeded_client: TestClient) -> None:
        resp = seeded_client.get("/api/novels/")
        assert resp.status_code == 200
        assert resp.json()[0]["novel_id"] == "test-n1"

    def test_api_prefixed_novels_route_without_trailing_slash_does_not_redirect(
        self, seeded_client: TestClient
    ) -> None:
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
        assert data[0]["publication_status"] == "unknown"

    def test_admin_list_uses_db_rows_without_storage_scan(
        self,
        _no_api_key: None,
        isolated_db_session: Session,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        storage = _fresh_storage()
        _seed_db_novel(
            isolated_db_session,
            "old-db",
            title="Old DB Novel",
            updated_at=datetime(2024, 1, 1, tzinfo=UTC),
        )
        new_db = _seed_db_novel(
            isolated_db_session,
            "new-db",
            title="New DB Novel",
            author="DB Author",
            source_site="syosetu_ncode",
            source_url="https://ncode.syosetu.com/n1234ab/",
            publication_status="completed",
            chapter_count=12,
            translated_count=4,
            is_published=True,
            updated_at=datetime(2024, 6, 1, tzinfo=UTC),
        )
        new_db.original_title = "新しいDB小説"
        new_db.latest_chapter_id = "4"
        new_db.latest_chapter_number = 4
        new_db.latest_chapter_title = "Fourth Chapter"
        isolated_db_session.commit()
        monkeypatch.setattr(
            storage,
            "list_novels",
            lambda: (_ for _ in ()).throw(AssertionError("storage scan should not run")),
        )
        c = _make_app(storage, db_session=isolated_db_session)

        resp = c.get("/api/admin/novels")
        data = resp.json()

        assert resp.status_code == 200
        assert [novel["novel_id"] for novel in data] == ["new-db", "old-db"]
        expected_summary = {
            "novel_id": "new-db",
            "title": "New DB Novel",
            "source_title": "新しいDB小説",
            "author": "DB Author",
            "source_key": "syosetu_ncode",
            "source_url": "https://ncode.syosetu.com/n1234ab/",
            "publication_status": "completed",
            "chapter_count": 12,
            "scraped_count": 12,
            "translated_count": 4,
            "is_published": True,
            "latest_chapter_id": "4",
            "latest_chapter_number": 4,
            "latest_chapter_title": "Fourth Chapter",
        }
        assert {key: data[0][key] for key in expected_summary} == expected_summary

    def test_admin_list_limit_offset_use_db_pagination(
        self,
        _no_api_key: None,
        isolated_db_session: Session,
    ) -> None:
        storage = _fresh_storage()
        _seed_db_novel(isolated_db_session, "first", updated_at=datetime(2024, 3, 1, tzinfo=UTC))
        _seed_db_novel(isolated_db_session, "second", updated_at=datetime(2024, 2, 1, tzinfo=UTC))
        _seed_db_novel(isolated_db_session, "third", updated_at=datetime(2024, 1, 1, tzinfo=UTC))
        c = _make_app(storage, db_session=isolated_db_session)

        resp = c.get("/api/admin/novels?limit=1&offset=1")

        assert resp.status_code == 200
        assert [novel["novel_id"] for novel in resp.json()] == ["second"]

    def test_admin_list_legacy_aliases_use_db_listing(
        self,
        _no_api_key: None,
        isolated_db_session: Session,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        storage = _fresh_storage()
        _seed_db_novel(isolated_db_session, "db-alias", title="DB Alias")
        monkeypatch.setattr(
            storage,
            "list_novels",
            lambda: (_ for _ in ()).throw(AssertionError("storage scan should not run")),
        )
        c = _make_app(storage, db_session=isolated_db_session)

        legacy = c.get("/novels/")
        api_legacy = c.get("/api/novels/")

        assert legacy.status_code == 200
        assert api_legacy.status_code == 200
        assert legacy.json()[0]["novel_id"] == "db-alias"
        assert api_legacy.json()[0]["novel_id"] == "db-alias"

    def test_admin_list_does_not_duplicate_storage_rows_when_db_exists(
        self,
        _no_api_key: None,
        isolated_db_session: Session,
    ) -> None:
        storage = _fresh_storage()
        _seed_novel(storage, "same-id")
        _seed_novel(storage, "storage-only")
        _seed_db_novel(isolated_db_session, "same-id", title="DB Canonical")
        c = _make_app(storage, db_session=isolated_db_session)

        resp = c.get("/novels/")

        assert resp.status_code == 200
        assert [novel["novel_id"] for novel in resp.json()] == ["same-id"]

    def test_list_novels_ignores_noncanonical_syosetu_folder_without_metadata(
        self,
        _no_api_key: None,
        isolated_db_session: Session,
    ) -> None:
        bootstrap()
        storage = _fresh_storage()
        novel_dir = storage.novels_dir / "0813kx"
        chapter_dir = novel_dir / "chapters"
        chapter_dir.mkdir(parents=True)
        (chapter_dir / "1.json").write_text(
            json.dumps({"id": "1", "raw": {"text": "raw chapter"}}, ensure_ascii=False),
            encoding="utf-8",
        )
        c = _make_app(storage, db_session=isolated_db_session)

        resp = c.get("/novels/")
        assert resp.status_code == 200
        data = resp.json()

        assert data == []

    def test_get_novel(self, seeded_client: TestClient) -> None:
        resp = seeded_client.get("/novels/test-n1")
        assert resp.status_code == 200
        assert resp.json()["title"] == "Test Novel"

    def test_get_novel_not_found(self, client: TestClient) -> None:
        resp = client.get("/novels/does-not-exist")
        assert resp.status_code in {404, 405}

    def test_owner_can_inspect_source_metadata(self, _no_api_key: None) -> None:
        bootstrap()
        storage = _fresh_storage()
        storage.save_metadata(
            "inspect-n1",
            {
                "title": "Source Title",
                "translated_title": "Translated Title",
                "author": "Source Author",
                "source_key": "syosetu_ncode",
                "source_url": "https://ncode.syosetu.com/n1234ab/",
                "publication_status": "完結済",
                "source_publication_status": "完結済",
                "description": "A stored synopsis.",
                "language": "ja",
                "chapters": [{"id": "1", "title": "Chapter 1"}],
                "raw_html": "<html>secret source page</html>",
                "api_key": "secret-key",
                "authorization_header": "Bearer secret",
            },
        )
        c = _make_app(storage)

        resp = c.get("/api/admin/novels/inspect-n1/source-metadata")
        payload = resp.json()

        assert resp.status_code == 200
        assert payload["novel_id"] == "inspect-n1"
        assert payload["title"] == "Translated Title"
        assert payload["source_title"] == "Source Title"
        assert payload["author"] == "Source Author"
        assert payload["source_key"] == "syosetu_ncode"
        assert payload["source_url"] == "https://ncode.syosetu.com/n1234ab/"
        assert payload["publication_status"] == "completed"
        assert payload["raw_status"] == "完結済"
        assert payload["synopsis"] == "A stored synopsis."
        assert payload["language"] == "ja"
        assert payload["chapter_count"] == 1
        assert payload["extraction"] == {
            "publication_status": "completed",
            "source_title": "Source Title",
            "synopsis_present": True,
            "author_present": True,
        }
        assert payload["warnings"] == []
        assert "raw_html" not in payload["source_metadata_keys"]
        assert "api_key" not in payload["source_metadata_keys"]
        assert "authorization_header" not in payload["source_metadata_keys"]
        encoded = json.dumps(payload, ensure_ascii=False)
        assert "<html>" not in encoded
        assert "secret-key" not in encoded
        assert "Bearer secret" not in encoded

    def test_owner_can_inspect_source_metadata_history(self, _no_api_key: None) -> None:
        bootstrap()
        storage = _fresh_storage()
        storage.save_metadata(
            "history-n1",
            {
                "title": "Version 0",
                "author": "Original Author",
                "publication_status": "ongoing",
                "raw_html": "<html>secret source page</html>",
                "api_key": "secret-key",
                "authorization_header": "Bearer secret",
            },
        )
        storage.save_metadata(
            "history-n1",
            {
                "title": "Version 1",
                "translated_title": "Translated Version 1",
                "author": "Updated Author",
                "publication_status": "completed",
            },
        )
        c = _make_app(storage)

        resp = c.get("/api/admin/novels/history-n1/source-metadata/history")
        payload = resp.json()

        assert resp.status_code == 200
        assert payload["novel_id"] == "history-n1"
        assert payload["limit"] == 10
        assert len(payload["entries"]) == 2
        assert payload["entries"][0]["snapshot_id"] == "current"
        assert payload["entries"][0]["is_current"] is True
        assert payload["entries"][0]["publication_status"] == "completed"
        assert payload["entries"][0]["title"] == "Translated Version 1"
        assert payload["entries"][0]["source_title"] == "Version 1"
        assert payload["entries"][1]["is_current"] is False
        assert payload["entries"][1]["publication_status"] == "ongoing"
        encoded = json.dumps(payload, ensure_ascii=False)
        assert "<html>" not in encoded
        assert "secret-key" not in encoded
        assert "Bearer secret" not in encoded

    def test_source_metadata_history_limit_bounds_entries(self, _no_api_key: None) -> None:
        bootstrap()
        storage = _fresh_storage()
        storage.save_metadata("history-limit", {"title": "Version 0"})
        for index in range(1, 4):
            storage.save_metadata("history-limit", {"title": f"Version {index}"})
        c = _make_app(storage)

        resp = c.get("/api/admin/novels/history-limit/source-metadata/history?limit=1")

        assert resp.status_code == 200
        payload = resp.json()
        assert payload["limit"] == 1
        assert len(payload["entries"]) == 1
        assert payload["entries"][0]["snapshot_id"] == "current"

    def test_owner_can_diff_source_metadata_backup_to_current(self, _no_api_key: None) -> None:
        bootstrap()
        storage = _fresh_storage()
        storage.save_metadata(
            "diff-n1",
            {
                "title": "Version 0",
                "author": "Stable Author",
                "publication_status": "ongoing",
                "removed_field": "old-only",
                "api_key": "secret-key",
                "raw_html": "<html>secret source page</html>",
            },
        )
        storage.save_metadata(
            "diff-n1",
            {
                "title": "Version 1",
                "author": "Stable Author",
                "publication_status": "completed",
                "added_field": "new-only",
            },
        )
        metadata_path = storage._novel_dir("diff-n1") / "metadata.json"
        current_payload = json.loads(metadata_path.read_text(encoding="utf-8"))
        current_payload.pop("removed_field", None)
        metadata_path.write_text(json.dumps(current_payload, ensure_ascii=False), encoding="utf-8")
        backup_id = storage.list_metadata_history("diff-n1")[1]["snapshot_id"]
        c = _make_app(storage)

        resp = c.get(
            "/api/admin/novels/diff-n1/source-metadata/history/diff",
            params={"from_snapshot": backup_id},
        )
        payload = resp.json()
        changed = {item["key"]: item for item in payload["changed"]}

        assert resp.status_code == 200
        assert payload["novel_id"] == "diff-n1"
        assert payload["from_snapshot"] == backup_id
        assert payload["to_snapshot"] == "current"
        assert "added_field" in payload["added_keys"]
        assert "removed_field" in payload["removed_keys"]
        assert changed["title"]["before"] == "Version 0"
        assert changed["title"]["after"] == "Version 1"
        assert changed["publication_status"]["before"] == "ongoing"
        assert changed["publication_status"]["after"] == "completed"
        assert payload["unchanged_count"] > 0
        assert payload["truncated"] is False
        encoded = json.dumps(payload, ensure_ascii=False)
        assert "secret-key" not in encoded
        assert "<html>" not in encoded
        assert "api_key" not in encoded
        assert "raw_html" not in encoded

    def test_owner_can_diff_current_to_backup_snapshot(self, _no_api_key: None) -> None:
        bootstrap()
        storage = _fresh_storage()
        storage.save_metadata("diff-reverse", {"title": "Version 0", "legacy_key": "backup-only"})
        storage.save_metadata("diff-reverse", {"title": "Version 1", "new_key": "current-only"})
        metadata_path = storage._novel_dir("diff-reverse") / "metadata.json"
        current_payload = json.loads(metadata_path.read_text(encoding="utf-8"))
        current_payload.pop("legacy_key", None)
        metadata_path.write_text(json.dumps(current_payload, ensure_ascii=False), encoding="utf-8")
        backup_id = storage.list_metadata_history("diff-reverse")[1]["snapshot_id"]
        c = _make_app(storage)

        resp = c.get(
            "/api/admin/novels/diff-reverse/source-metadata/history/diff",
            params={"from_snapshot": "current", "to_snapshot": backup_id},
        )
        payload = resp.json()
        changed = {item["key"]: item for item in payload["changed"]}

        assert resp.status_code == 200
        assert payload["from_snapshot"] == "current"
        assert payload["to_snapshot"] == backup_id
        assert "legacy_key" in payload["added_keys"]
        assert "new_key" in payload["removed_keys"]
        assert changed["title"]["before"] == "Version 1"
        assert changed["title"]["after"] == "Version 0"

    def test_source_metadata_diff_caps_changed_entries_and_truncates_values(self, _no_api_key: None) -> None:
        bootstrap()
        storage = _fresh_storage()
        original = {f"field_{index:02d}": f"old-{index}" for index in range(55)}
        original["huge_text"] = "a" * 1500
        storage.save_metadata("diff-capped", original)
        updated = {f"field_{index:02d}": f"new-{index}" for index in range(55)}
        updated["huge_text"] = "b" * 1500
        storage.save_metadata("diff-capped", updated)
        backup_id = storage.list_metadata_history("diff-capped")[1]["snapshot_id"]
        c = _make_app(storage)

        resp = c.get(
            "/api/admin/novels/diff-capped/source-metadata/history/diff",
            params={"from_snapshot": backup_id},
        )
        payload = resp.json()
        encoded = json.dumps(payload, ensure_ascii=False)

        assert resp.status_code == 200
        assert payload["truncated"] is True
        assert len(payload["changed"]) == 50
        assert "truncated:changed_fields" in payload["warnings"]
        assert "truncated:huge_text" in payload["warnings"]
        assert "a" * 1200 not in encoded
        assert "b" * 1200 not in encoded

    def test_source_metadata_diff_missing_snapshot_returns_404(self, _no_api_key: None) -> None:
        bootstrap()
        storage = _fresh_storage()
        _seed_novel(storage, "diff-missing")
        c = _make_app(storage)

        resp = c.get(
            "/api/admin/novels/diff-missing/source-metadata/history/diff",
            params={"from_snapshot": "missing.json"},
        )

        assert resp.status_code == 404

    def test_source_metadata_diff_rejects_path_traversal(self, _no_api_key: None) -> None:
        bootstrap()
        storage = _fresh_storage()
        _seed_novel(storage, "diff-traversal")
        c = _make_app(storage)

        resp = c.get(
            "/api/admin/novels/diff-traversal/source-metadata/history/diff",
            params={"from_snapshot": "..\\metadata.json"},
        )

        assert resp.status_code == 400

    def test_non_owner_cannot_diff_source_metadata_snapshots(self, _no_api_key: None) -> None:
        bootstrap()
        storage = _fresh_storage()
        _seed_novel(storage)
        guest = _make_app(storage, session_user=None)
        user = _make_app(storage, session_user=REGULAR_USER)

        guest_resp = guest.get(
            "/api/admin/novels/test-n1/source-metadata/history/diff",
            params={"from_snapshot": "current"},
        )
        user_resp = user.get(
            "/api/admin/novels/test-n1/source-metadata/history/diff",
            params={"from_snapshot": "current"},
        )

        assert guest_resp.status_code == 401
        assert user_resp.status_code == 403

    def test_source_metadata_diff_get_does_not_require_csrf(self, _no_api_key: None) -> None:
        bootstrap()
        storage = _fresh_storage()
        _seed_novel(storage)
        c = _make_app(storage)

        resp = c.get(
            "/api/admin/novels/test-n1/source-metadata/history/diff",
            params={"from_snapshot": "current"},
        )

        assert resp.status_code == 200

    def test_public_routes_do_not_expose_source_metadata_diff(
        self,
        _no_api_key: None,
        isolated_db_session: Session,
    ) -> None:
        bootstrap()
        storage = _fresh_storage()
        _seed_novel(storage)
        c = _make_app(storage, session_user=None, db_session=isolated_db_session)

        resp = c.get(
            "/api/public/novels/test-n1/source-metadata/history/diff",
            params={"from_snapshot": "current"},
        )

        assert resp.status_code == 404

    def test_owner_can_inspect_current_source_metadata_snapshot_detail(self, _no_api_key: None) -> None:
        bootstrap()
        storage = _fresh_storage()
        huge_text = "x" * 1500
        storage.save_metadata(
            "snapshot-current",
            {
                "title": "Source Title",
                "translated_title": "Translated Title",
                "author": "Source Author",
                "publication_status": "completed",
                "description": "A stored synopsis.",
                "chapters": [{"id": "1", "title": "Chapter 1"}],
                "api_key": "secret-key",
                "authorization_header": "Bearer secret",
                "raw_html": "<html>secret source page</html>",
                "large_text": huge_text,
            },
        )
        c = _make_app(storage)

        resp = c.get("/api/admin/novels/snapshot-current/source-metadata/history/current")
        payload = resp.json()

        assert resp.status_code == 200
        assert payload["novel_id"] == "snapshot-current"
        assert payload["snapshot_id"] == "current"
        assert payload["is_current"] is True
        assert payload["size_bytes"] > 0
        assert payload["metadata"]["title"] == "Source Title"
        assert payload["metadata"]["translated_title"] == "Translated Title"
        assert payload["metadata"]["publication_status"] == "completed"
        assert payload["metadata"]["large_text"].endswith("... [truncated]")
        assert len(payload["metadata"]["large_text"]) < len(huge_text)
        assert "api_key" not in payload["metadata"]
        assert "authorization_header" not in payload["metadata"]
        assert "raw_html" not in payload["metadata"]
        assert "api_key" not in payload["metadata_keys"]
        assert "authorization_header" not in payload["metadata_keys"]
        assert "raw_html" not in payload["metadata_keys"]
        assert "truncated:large_text" in payload["warnings"]
        assert "omitted_raw_payload:raw_html" in payload["warnings"]
        encoded = json.dumps(payload, ensure_ascii=False)
        assert "secret-key" not in encoded
        assert "Bearer secret" not in encoded
        assert "<html>" not in encoded

    def test_owner_can_inspect_backup_source_metadata_snapshot_detail(self, _no_api_key: None) -> None:
        bootstrap()
        storage = _fresh_storage()
        storage.save_metadata(
            "snapshot-backup",
            {
                "title": "Version 0",
                "publication_status": "ongoing",
                "source_payload": {"html": "<html>source dump</html>"},
                "session_cookie": "cookie-secret",
            },
        )
        storage.save_metadata(
            "snapshot-backup",
            {
                "title": "Version 1",
                "publication_status": "completed",
            },
        )
        history = storage.list_metadata_history("snapshot-backup")
        backup_id = history[1]["snapshot_id"]
        c = _make_app(storage)

        resp = c.get(f"/api/admin/novels/snapshot-backup/source-metadata/history/{backup_id}")
        payload = resp.json()

        assert resp.status_code == 200
        assert payload["snapshot_id"] == backup_id
        assert payload["is_current"] is False
        assert payload["metadata"]["title"] == "Version 0"
        assert payload["metadata"]["publication_status"] == "ongoing"
        assert "source_payload" not in payload["metadata"]
        assert "session_cookie" not in payload["metadata"]
        encoded = json.dumps(payload, ensure_ascii=False)
        assert "<html>" not in encoded
        assert "cookie-secret" not in encoded

    def test_source_metadata_snapshot_detail_missing_snapshot_returns_404(self, _no_api_key: None) -> None:
        bootstrap()
        storage = _fresh_storage()
        _seed_novel(storage, "snapshot-missing")
        c = _make_app(storage)

        resp = c.get("/api/admin/novels/snapshot-missing/source-metadata/history/missing.json")

        assert resp.status_code == 404

    def test_source_metadata_snapshot_detail_rejects_path_traversal(self, _no_api_key: None) -> None:
        bootstrap()
        storage = _fresh_storage()
        _seed_novel(storage, "snapshot-traversal")
        c = _make_app(storage)

        resp = c.get("/api/admin/novels/snapshot-traversal/source-metadata/history/..%5Cmetadata.json")

        assert resp.status_code == 400

    def test_non_owner_cannot_inspect_source_metadata_snapshot_detail(self, _no_api_key: None) -> None:
        bootstrap()
        storage = _fresh_storage()
        _seed_novel(storage)
        guest = _make_app(storage, session_user=None)
        user = _make_app(storage, session_user=REGULAR_USER)

        guest_resp = guest.get("/api/admin/novels/test-n1/source-metadata/history/current")
        user_resp = user.get("/api/admin/novels/test-n1/source-metadata/history/current")

        assert guest_resp.status_code == 401
        assert user_resp.status_code == 403

    def test_source_metadata_snapshot_detail_get_does_not_require_csrf(self, _no_api_key: None) -> None:
        bootstrap()
        storage = _fresh_storage()
        _seed_novel(storage)
        c = _make_app(storage)

        resp = c.get("/api/admin/novels/test-n1/source-metadata/history/current")

        assert resp.status_code == 200

    def test_public_routes_do_not_expose_source_metadata_snapshot_detail(
        self,
        _no_api_key: None,
        isolated_db_session: Session,
    ) -> None:
        bootstrap()
        storage = _fresh_storage()
        _seed_novel(storage)
        c = _make_app(storage, session_user=None, db_session=isolated_db_session)

        resp = c.get("/api/public/novels/test-n1/source-metadata/history/current")

        assert resp.status_code == 404

    def test_non_owner_cannot_inspect_source_metadata_history(self, _no_api_key: None) -> None:
        bootstrap()
        storage = _fresh_storage()
        _seed_novel(storage)
        guest = _make_app(storage, session_user=None)
        user = _make_app(storage, session_user=REGULAR_USER)

        guest_resp = guest.get("/api/admin/novels/test-n1/source-metadata/history")
        user_resp = user.get("/api/admin/novels/test-n1/source-metadata/history")

        assert guest_resp.status_code == 401
        assert user_resp.status_code == 403

    def test_source_metadata_history_get_does_not_require_csrf(self, _no_api_key: None) -> None:
        bootstrap()
        storage = _fresh_storage()
        _seed_novel(storage)
        c = _make_app(storage)

        resp = c.get("/api/admin/novels/test-n1/source-metadata/history")

        assert resp.status_code == 200

    def test_source_metadata_history_missing_novel_returns_404(self, _no_api_key: None) -> None:
        bootstrap()
        c = _make_app(_fresh_storage())

        resp = c.get("/api/admin/novels/missing/source-metadata/history")

        assert resp.status_code == 404

    def test_public_routes_do_not_expose_source_metadata_history(
        self,
        _no_api_key: None,
        isolated_db_session: Session,
    ) -> None:
        bootstrap()
        storage = _fresh_storage()
        _seed_novel(storage)
        c = _make_app(storage, session_user=None, db_session=isolated_db_session)

        resp = c.get("/api/public/novels/test-n1/source-metadata/history")

        assert resp.status_code == 404

    def test_non_owner_cannot_inspect_source_metadata(self, _no_api_key: None) -> None:
        bootstrap()
        storage = _fresh_storage()
        _seed_novel(storage)
        guest = _make_app(storage, session_user=None)
        user = _make_app(storage, session_user=REGULAR_USER)

        guest_resp = guest.get("/api/admin/novels/test-n1/source-metadata")
        user_resp = user.get("/api/admin/novels/test-n1/source-metadata")

        assert guest_resp.status_code == 401
        assert user_resp.status_code == 403

    def test_source_metadata_inspection_missing_novel_returns_404(self, client: TestClient) -> None:
        resp = client.get("/api/admin/novels/missing/source-metadata")

        assert resp.status_code in {404, 405}

    def test_source_metadata_inspection_rejects_noncanonical_folder(self, _no_api_key: None) -> None:
        bootstrap()
        storage = _fresh_storage()
        chapter_dir = storage.novels_dir / "0813kx" / "chapters"
        chapter_dir.mkdir(parents=True)
        (chapter_dir / "1.json").write_text(
            json.dumps({"id": "1", "raw": {"text": "raw chapter"}}, ensure_ascii=False),
            encoding="utf-8",
        )
        c = _make_app(storage)

        resp = c.get("/api/admin/novels/n0813kx/source-metadata")
        payload = resp.json()

        assert resp.status_code == 404
        assert payload["detail"] == "Novel not found"

    def test_source_metadata_inspection_unknown_status_warns(self, _no_api_key: None) -> None:
        bootstrap()
        storage = _fresh_storage()
        storage.save_metadata(
            "unknown-status",
            {
                "title": "Unknown Status",
                "source_url": "https://example.com/novel",
                "chapters": [{"id": "1"}],
            },
        )
        c = _make_app(storage)

        resp = c.get("/api/admin/novels/unknown-status/source-metadata")
        payload = resp.json()

        assert resp.status_code == 200
        assert payload["publication_status"] == "unknown"
        assert "unknown_publication_status" in payload["warnings"]
        assert "missing_synopsis" in payload["warnings"]
        assert "missing_source_url" not in payload["warnings"]
        assert "no_chapters" not in payload["warnings"]

    def test_public_routes_do_not_expose_source_metadata_inspection(
        self,
        _no_api_key: None,
        isolated_db_session: Session,
    ) -> None:
        bootstrap()
        storage = _fresh_storage()
        _seed_novel(storage)
        c = _make_app(storage, session_user=None, db_session=isolated_db_session)

        resp = c.get("/api/public/novels/test-n1/source-metadata")

        assert resp.status_code == 404

    def test_refresh_catalog_projection_endpoint_repairs_stale_db_fields(
        self,
        _no_api_key: None,
        isolated_db_session: Session,
    ) -> None:
        bootstrap()
        storage = _fresh_storage()
        storage.save_metadata(
            "repair-n1",
            {
                "title": "Repair Novel",
                "publication_status": "completed",
                "chapters": [
                    {"id": "1", "num": 1, "title": "Chapter One"},
                    {"id": "2", "num": 2, "title": "Chapter Two"},
                ],
            },
        )
        storage.save_translated_chapter("repair-n1", "2", "Translated chapter two")
        isolated_db_session.add(
            Novel(
                slug="repair-n1",
                title="Repair Novel",
                language="ja",
                publication_status="unknown",
                chapter_count=0,
                translated_count=0,
            )
        )
        isolated_db_session.commit()
        c = _make_app(storage, db_session=isolated_db_session)

        resp = c.post(
            "/api/admin/novels/repair-n1/refresh-catalog-projection",
            headers=_csrf_headers(c),
        )
        payload = resp.json()

        assert resp.status_code == 200
        assert payload["novel_id"] == "repair-n1"
        assert payload["created"] is False
        assert payload["before"]["chapter_count"] == 0
        assert payload["after"]["chapter_count"] == 2
        assert payload["after"]["translated_count"] == 1
        assert payload["after"]["publication_status"] == "completed"
        assert payload["after"]["latest_chapter_id"] == "2"
        assert payload["after"]["latest_chapter_number"] == 2
        assert payload["after"]["latest_chapter_title"] == "Chapter Two"
        assert "chapter_count" in payload["changed_fields"]
        assert "latest_chapter_id" in payload["changed_fields"]
        repaired = isolated_db_session.query(Novel).filter_by(slug="repair-n1").one()
        assert repaired.chapter_count == 2
        assert repaired.translated_count == 1
        assert repaired.latest_chapter_id == "2"

    def test_refresh_catalog_projection_endpoint_creates_db_row_from_storage_metadata(
        self,
        _no_api_key: None,
        isolated_db_session: Session,
    ) -> None:
        bootstrap()
        storage = _fresh_storage()
        storage.save_metadata(
            "storage-only-repair",
            {
                "title": "Storage Only Repair",
                "publication_status": "ongoing",
                "chapters": [{"id": "1", "num": 1, "title": "Chapter One"}],
            },
        )
        c = _make_app(storage, db_session=isolated_db_session)

        resp = c.post(
            "/api/admin/novels/storage-only-repair/refresh-catalog-projection",
            headers=_csrf_headers(c),
        )
        payload = resp.json()

        assert resp.status_code == 200
        assert payload["created"] is True
        assert payload["before"] is None
        assert payload["after"]["chapter_count"] == 1
        repaired = isolated_db_session.query(Novel).filter_by(slug="storage-only-repair").one()
        assert repaired.title == "Storage Only Repair"

    def test_refresh_catalog_projection_endpoint_missing_novel_returns_404(
        self,
        _no_api_key: None,
        isolated_db_session: Session,
    ) -> None:
        bootstrap()
        c = _make_app(_fresh_storage(), db_session=isolated_db_session)

        resp = c.post(
            "/api/admin/novels/missing/refresh-catalog-projection",
            headers=_csrf_headers(c),
        )

        assert resp.status_code == 404

    def test_bulk_refresh_catalog_projections_dry_run_reports_without_commit(
        self,
        _no_api_key: None,
        isolated_db_session: Session,
    ) -> None:
        bootstrap()
        storage = _fresh_storage()
        storage.save_metadata(
            "bulk-stale",
            {
                "title": "Bulk Stale",
                "publication_status": "completed",
                "chapters": [{"id": "1", "num": 1}],
            },
        )
        _seed_db_novel(
            isolated_db_session,
            "bulk-stale",
            publication_status="unknown",
            chapter_count=0,
        )
        c = _make_app(storage, db_session=isolated_db_session)

        resp = c.post(
            "/api/admin/novels/refresh-catalog-projections",
            headers=_csrf_headers(c),
        )
        payload = resp.json()

        assert resp.status_code == 200
        assert payload["dry_run"] is True
        assert payload["scanned"] == 1
        assert payload["updated"] == 1
        assert payload["created"] == 0
        assert payload["failed"] == 0
        assert payload["changed"][0]["novel_id"] == "bulk-stale"
        isolated_db_session.expire_all()
        stale = isolated_db_session.query(Novel).filter_by(slug="bulk-stale").one()
        assert stale.publication_status == "unknown"
        assert stale.chapter_count == 0

    def test_bulk_refresh_catalog_projections_apply_updates_and_creates(
        self,
        _no_api_key: None,
        isolated_db_session: Session,
    ) -> None:
        bootstrap()
        storage = _fresh_storage()
        storage.save_metadata(
            "bulk-stale",
            {
                "title": "Bulk Stale",
                "publication_status": "completed",
                "chapters": [{"id": "1", "num": 1}, {"id": "2", "num": 2}],
            },
        )
        storage.save_metadata(
            "bulk-created",
            {
                "title": "Bulk Created",
                "publication_status": "ongoing",
                "chapters": [{"id": "1", "num": 1}],
            },
        )
        _seed_db_novel(
            isolated_db_session,
            "bulk-stale",
            publication_status="unknown",
            chapter_count=0,
        )
        c = _make_app(storage, db_session=isolated_db_session)

        resp = c.post(
            "/api/admin/novels/refresh-catalog-projections?dry_run=false",
            headers=_csrf_headers(c),
        )
        payload = resp.json()

        assert resp.status_code == 200
        assert payload["dry_run"] is False
        assert payload["created"] == 1
        assert payload["updated"] == 1
        repaired = isolated_db_session.query(Novel).filter_by(slug="bulk-stale").one()
        created = isolated_db_session.query(Novel).filter_by(slug="bulk-created").one()
        assert repaired.publication_status == "completed"
        assert repaired.chapter_count == 2
        assert created.title == "Bulk Created"
        assert created.chapter_count == 1

    def test_bulk_refresh_catalog_projections_requires_owner_and_csrf(
        self,
        _no_api_key: None,
        isolated_db_session: Session,
    ) -> None:
        bootstrap()
        storage = _fresh_storage()
        owner = _make_app(storage, db_session=isolated_db_session)
        guest = _make_app(storage, session_user=None, db_session=isolated_db_session)
        user = _make_app(storage, session_user=REGULAR_USER, db_session=isolated_db_session)

        assert owner.post("/api/admin/novels/refresh-catalog-projections").status_code == 403
        assert (
            guest.post(
                "/api/admin/novels/refresh-catalog-projections",
                headers=_csrf_headers(guest),
            ).status_code
            == 401
        )
        assert (
            user.post(
                "/api/admin/novels/refresh-catalog-projections",
                headers=_csrf_headers(user),
            ).status_code
            == 403
        )

    def test_bulk_refresh_catalog_projections_static_route_not_swallowed(
        self,
        _no_api_key: None,
        isolated_db_session: Session,
    ) -> None:
        bootstrap()
        c = _make_app(_fresh_storage(), db_session=isolated_db_session)

        resp = c.post(
            "/api/admin/novels/refresh-catalog-projections?limit=1&offset=0",
            headers=_csrf_headers(c),
        )

        assert resp.status_code == 200
        assert resp.json()["scanned"] == 0

    def test_bulk_refresh_catalog_projections_public_route_not_exposed(
        self,
        _no_api_key: None,
        isolated_db_session: Session,
    ) -> None:
        bootstrap()
        c = _make_app(_fresh_storage(), session_user=None, db_session=isolated_db_session)

        resp = c.post(
            "/api/public/novels/refresh-catalog-projections",
            headers=_csrf_headers(c),
        )

        assert resp.status_code in {404, 405}

    def test_bulk_refresh_catalog_projections_limit_offset(
        self,
        _no_api_key: None,
        isolated_db_session: Session,
    ) -> None:
        bootstrap()
        storage = _fresh_storage()
        _seed_db_novel(isolated_db_session, "a-novel", publication_status="unknown")
        _seed_db_novel(isolated_db_session, "b-novel", publication_status="strange")
        _seed_db_novel(isolated_db_session, "c-novel", publication_status="unknown")
        c = _make_app(storage, db_session=isolated_db_session)

        resp = c.post(
            "/api/admin/novels/refresh-catalog-projections?limit=1&offset=1",
            headers=_csrf_headers(c),
        )
        payload = resp.json()

        assert resp.status_code == 200
        assert payload["scanned"] == 1
        assert payload["changed"][0]["novel_id"] == "b-novel"

    def test_public_routes_do_not_expose_catalog_projection_repair(
        self,
        _no_api_key: None,
        isolated_db_session: Session,
    ) -> None:
        bootstrap()
        storage = _fresh_storage()
        _seed_novel(storage)
        c = _make_app(storage, session_user=None, db_session=isolated_db_session)

        resp = c.post(
            "/api/public/novels/test-n1/refresh-catalog-projection",
            headers=_csrf_headers(c),
        )

        assert resp.status_code == 404


class TestAdminNovelPublish:
    def test_publish_requires_owner_and_csrf(
        self,
        _no_api_key: None,
        isolated_db_session: Session,
    ) -> None:
        bootstrap()
        storage = _fresh_storage()
        _seed_storage_catalog_metadata(storage, "publish-auth")
        owner = _make_app(storage, db_session=isolated_db_session)
        guest = _make_app(storage, session_user=None, db_session=isolated_db_session)
        user = _make_app(storage, session_user=REGULAR_USER, db_session=isolated_db_session)

        assert owner.post("/api/admin/novels/publish-auth/publish").status_code == 403
        assert (
            guest.post(
                "/api/admin/novels/publish-auth/publish",
                headers=_csrf_headers(guest),
            ).status_code
            == 401
        )
        assert (
            user.post(
                "/api/admin/novels/publish-auth/publish",
                headers=_csrf_headers(user),
            ).status_code
            == 403
        )

    def test_publish_fails_without_translated_chapter(
        self,
        _no_api_key: None,
        isolated_db_session: Session,
    ) -> None:
        bootstrap()
        storage = _fresh_storage()
        _seed_storage_catalog_metadata(storage, "draft-only", translated=False)
        c = _make_app(storage, db_session=isolated_db_session)

        resp = c.post("/api/admin/novels/draft-only/publish", headers=_csrf_headers(c))

        assert resp.status_code == 400
        assert "translated chapters" in resp.json()["detail"]
        novel = isolated_db_session.query(Novel).filter_by(slug="draft-only").one()
        assert novel.is_published is False
        assert novel.translated_count == 0

    def test_publish_refreshes_projection_and_exposes_safe_summary(
        self,
        _no_api_key: None,
        isolated_db_session: Session,
    ) -> None:
        bootstrap()
        storage = _fresh_storage()
        _seed_storage_catalog_metadata(
            storage,
            "publish-n1",
            translated_title="The Translated Title",
            translated_synopsis="A translated synopsis.",
            latest_title="Translated Latest Chapter",
        )
        _seed_db_novel(
            isolated_db_session,
            "publish-n1",
            title="Stale Title",
            publication_status="unknown",
            translated_count=0,
            is_published=False,
        )
        c = _make_app(storage, session_user=OWNER_USER, db_session=isolated_db_session)

        before_catalog = c.get("/api/public/catalog").json()
        resp = c.post("/api/admin/novels/publish-n1/publish", headers=_csrf_headers(c))
        payload = resp.json()
        after_catalog = c.get("/api/public/catalog").json()
        detail = c.get("/api/public/novels/publish-n1").json()
        reader = c.get("/api/public/novels/publish-n1/chapters/1")

        assert resp.status_code == 200
        assert before_catalog["novels"] == []
        assert payload == {
            "novel_id": "publish-n1",
            "title": "The Translated Title",
            "source_title": "原題",
            "is_published": True,
            "chapter_count": 2,
            "translated_count": 1,
            "latest_chapter_id": "1",
            "latest_chapter_number": 1,
            "latest_chapter_title": "Translated Latest Chapter",
            "publication_status": "ongoing",
            "visibility_warnings": [],
        }
        assert "synopsis" not in payload
        assert "source_url" not in payload
        assert [novel["novel_id"] for novel in after_catalog["novels"]] == ["publish-n1"]
        assert after_catalog["novels"][0]["title"] == "The Translated Title"
        assert after_catalog["novels"][0]["latest_chapter_title"] == "Translated Latest Chapter"
        assert detail["synopsis"] == "A translated synopsis."
        assert reader.status_code == 200

    def test_unpublish_removes_novel_from_default_public_catalog(
        self,
        _no_api_key: None,
        isolated_db_session: Session,
    ) -> None:
        bootstrap()
        storage = _fresh_storage()
        _seed_storage_catalog_metadata(storage, "unpublish-n1")
        c = _make_app(storage, db_session=isolated_db_session)

        publish_resp = c.post("/api/admin/novels/unpublish-n1/publish", headers=_csrf_headers(c))
        visible = c.get("/api/public/catalog").json()
        unpublish_resp = c.post("/api/admin/novels/unpublish-n1/unpublish", headers=_csrf_headers(c))
        hidden = c.get("/api/public/catalog").json()

        assert publish_resp.status_code == 200
        assert [novel["novel_id"] for novel in visible["novels"]] == ["unpublish-n1"]
        assert unpublish_resp.status_code == 200
        assert unpublish_resp.json()["is_published"] is False
        assert hidden["novels"] == []
        novel = isolated_db_session.query(Novel).filter_by(slug="unpublish-n1").one()
        assert novel.is_published is False

    def test_published_adult_novel_stays_hidden_by_default(
        self,
        _no_api_key: None,
        isolated_db_session: Session,
    ) -> None:
        bootstrap()
        storage = _fresh_storage()
        _seed_storage_catalog_metadata(storage, "adult-publish")
        novel = _seed_db_novel(
            isolated_db_session,
            "adult-publish",
            title="Stale Adult Title",
            is_published=False,
        )
        adult_genre = Genre(
            slug="adult-romance",
            name_ja="大人向け恋愛",
            name_en="Adult Romance",
            is_adult=True,
            display_order=100,
            is_active=True,
        )
        novel.genres.append(adult_genre)
        isolated_db_session.add(adult_genre)
        isolated_db_session.commit()
        c = _make_app(storage, db_session=isolated_db_session)

        publish_resp = c.post("/api/admin/novels/adult-publish/publish", headers=_csrf_headers(c))
        default_catalog = c.get("/api/public/catalog").json()
        adult_catalog = c.get("/api/public/catalog?include_adult=true").json()

        assert publish_resp.status_code == 200
        assert publish_resp.json()["visibility_warnings"] == ["adult_hidden_by_default"]
        assert default_catalog["novels"] == []
        assert [novel["novel_id"] for novel in adult_catalog["novels"]] == ["adult-publish"]

    def test_public_route_does_not_expose_publish_operation(
        self,
        _no_api_key: None,
        isolated_db_session: Session,
    ) -> None:
        bootstrap()
        c = _make_app(_fresh_storage(), session_user=None, db_session=isolated_db_session)

        resp = c.post(
            "/api/public/novels/publish-n1/publish",
            headers=_csrf_headers(c),
        )

        assert resp.status_code in {404, 405}


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

    def test_update_translated_chapter_creates_edit_history(
        self,
        seeded_client: TestClient,
        isolated_db_session: Session,
    ) -> None:
        resp = seeded_client.put(
            "/novels/test-n1/chapters/1/translated",
            json={"text": "Edited ch1", "editor": "admin", "note": "line edit"},
            headers=_csrf_headers(seeded_client),
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

        novel = isolated_db_session.query(Novel).filter_by(slug="test-n1").one()
        assert novel.chapter_count == 2
        assert novel.translated_count == 1
        assert novel.latest_chapter_id == "1"
        assert novel.latest_chapter_updated_at is not None

    def test_rollback_translated_chapter_version(
        self,
        seeded_client: TestClient,
        isolated_db_session: Session,
    ) -> None:
        edit_resp = seeded_client.put(
            "/novels/test-n1/chapters/1/translated",
            json={"text": "Edited ch1", "editor": "admin"},
            headers=_csrf_headers(seeded_client),
        )
        assert edit_resp.status_code == 200

        rollback_resp = seeded_client.post(
            "/novels/test-n1/chapters/1/translated/rollback",
            json={"version_id": "v1", "editor": "admin", "note": "restore original"},
            headers=_csrf_headers(seeded_client),
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

        novel = isolated_db_session.query(Novel).filter_by(slug="test-n1").one()
        assert novel.chapter_count == 2
        assert novel.translated_count == 1
        assert novel.latest_chapter_id == "1"
        assert novel.latest_chapter_updated_at is not None


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
        resp = seeded_client.delete("/novels/test-n1", headers=_csrf_headers(seeded_client))
        assert resp.status_code == 204
        # Verify gone
        resp2 = seeded_client.get("/novels/test-n1")
        assert resp2.status_code == 404

    def test_delete_novel_not_found(self, client: TestClient) -> None:
        resp = client.delete("/novels/does-not-exist", headers=_csrf_headers(client))
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

        headers = _csrf_headers(c)
        start_resp = c.post("/novels/admin/worker/start", headers=headers)
        assert start_resp.status_code == 200
        assert start_resp.json()["running"] is True

        run_once_resp = c.post("/novels/admin/worker/run-once", headers=headers)
        assert run_once_resp.status_code == 200
        assert run_once_resp.json()["activity"]["id"] == "activity-1"
        assert run_once_resp.json()["job"]["id"] == "activity-1"
        assert run_once_resp.json()["worker"]["activity_processed"] == 1

        stop_resp = c.post("/novels/admin/worker/stop", headers=headers)
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
        assert status_resp.json()["provider_model"] == "gemini-3.1-flash-lite"
        canonical_status_resp = c.get("/api/admin/provider-api-key/gemini")
        assert canonical_status_resp.status_code == 200
        assert canonical_status_resp.json()["provider_key"] == "gemini"
        credential_resp = c.get("/api/admin/providers/gemini")
        assert credential_resp.status_code == 200
        assert credential_resp.json()["provider_key"] == "gemini"
        assert credential_resp.json()["configured"] is False
        assert credential_resp.json()["validation_status"] == "Unchecked"

        set_resp = c.post(
            "/novels/admin/provider-api-key",
            json={"provider_key": "gemini", "api_key": "AIza-test-key"},
            headers=_csrf_headers(c),
        )

        assert set_resp.status_code == 200
        assert set_resp.json()["configured"] is True
        assert set_resp.json()["preferred_provider_key"] == "gemini"
        assert set_resp.json()["provider_model"] == "gemini-3.1-flash-lite"
        assert set_resp.json()["validation_status"] == "working"
        assert preferences.get_api_key("gemini") == "AIza-test-key"
        assert preferences.get_preferred_provider() == "gemini"
        assert preferences.get_preferred_model() == "gemini-3.1-flash-lite"
        assert preferences.get_llm_step_config("body_translation")["provider"] == "gemini"
        canonical_credential_resp = c.get("/api/admin/providers/gemini")
        assert canonical_credential_resp.status_code == 200
        assert canonical_credential_resp.json()["configured"] is True
        assert canonical_credential_resp.json()["is_active"] is True

        clear_resp = c.delete("/novels/admin/provider-api-key/gemini", headers=_csrf_headers(c))
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
            headers=_csrf_headers(c),
        )

        assert resp.status_code == 200
        assert resp.json()["validation_status"] == "working"
        assert preferences.get_api_key("gemini") is None
        canonical_resp = c.post(
            "/api/admin/providers/gemini/validate",
            json={"api_key": "AIza-temp-key"},
            headers=_csrf_headers(c),
        )
        assert canonical_resp.status_code == 200
        assert canonical_resp.json()["validation_status"] == "Working"
        assert preferences.get_api_key("gemini") is None

    def test_admin_provider_api_rejects_openai(
        self,
        _no_api_key: None,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        bootstrap()
        storage = _fresh_storage()
        preferences = PreferencesService(_TMP / "prefs")
        c = _make_app(storage, preferences=preferences)

        openai_resp = c.get("/api/admin/provider-api-key/openai")
        assert openai_resp.status_code == 400
        assert "must be: gemini" in openai_resp.json()["detail"]

    def test_provider_management_requires_owner_and_returns_safe_metadata(
        self,
        _no_api_key: None,
        isolated_db_session: Session,
    ) -> None:
        bootstrap()
        settings.PROVIDER_CREDENTIAL_ENCRYPTION_KEY = SecretStr("test-provider-credential-encryption-key")
        storage = _fresh_storage()
        owner_preferences = PreferencesService(_TMP / "prefs-owner")
        user_preferences = PreferencesService(_TMP / "prefs-user")
        owner = _make_app(storage, preferences=owner_preferences, db_session=isolated_db_session)
        user = _make_app(
            storage, preferences=user_preferences, session_user=REGULAR_USER, db_session=isolated_db_session
        )

        assert user.get("/api/admin/providers").status_code == 403
        assert user.get("/api/admin/providers/credentials").status_code == 403
        assert user.get("/api/admin/providers/fallback-policy").status_code == 403

        created = owner.post(
            "/api/admin/providers/credentials",
            json={
                "provider_key": "gemini",
                "api_key": "AIza-admin-safe-key",
                "label": "Primary Gemini",
                "provider_model": "gemini-3.1-flash-lite",
                "is_active": True,
            },
            headers=_csrf_headers(owner),
        )
        assert created.status_code == 200
        payload = created.json()
        encoded = json.dumps(payload)
        assert payload["provider_key"] == "gemini"
        assert payload["label"] == "Primary Gemini"
        assert payload["last4"] == "-key"
        assert "AIza-admin-safe-key" not in encoded
        assert "api_key" not in payload
        row = isolated_db_session.query(ProviderCredential).filter_by(provider="gemini").one()
        assert row.encrypted_api_key != "AIza-admin-safe-key"
        assert "AIza-admin-safe-key" not in row.encrypted_api_key
        assert ProviderCredentialService(isolated_db_session).decrypt_api_key(row) == "AIza-admin-safe-key"

        listed = owner.get("/api/admin/providers/credentials")
        assert listed.status_code == 200
        assert "AIza-admin-safe-key" not in json.dumps(listed.json())
        assert listed.json()["credentials"][0]["configured"] is True

    def test_provider_management_model_registry_keeps_provider_ids_separate(
        self,
        _no_api_key: None,
        isolated_db_session: Session,
    ) -> None:
        bootstrap()
        settings.PROVIDER_CREDENTIAL_ENCRYPTION_KEY = SecretStr("test-provider-credential-encryption-key")
        c = _make_app(
            _fresh_storage(),
            preferences=PreferencesService(_TMP / "prefs-models"),
            db_session=isolated_db_session,
        )

        models_resp = c.get("/api/admin/providers/models")
        assert models_resp.status_code == 200
        models = {(item["provider"], item["model"]) for item in models_resp.json()["models"]}
        assert ("gemini", "gemma-4-31b-it") in models
        assert ("gemini", "google/gemma-4-31b-it") not in models

        rejected = c.put(
            "/api/admin/providers/fallback-policy",
            json={
                "default_provider": "gemini",
                "default_model": "google/gemma-4-31b-it",
                "candidates": [
                    {"provider": "gemini", "model": "google/gemma-4-31b-it", "credential_id": "gemini"},
                ],
            },
            headers=_csrf_headers(c),
        )
        assert rejected.status_code == 400

    def test_provider_management_requires_encryption_key_for_storage(
        self,
        _no_api_key: None,
        isolated_db_session: Session,
    ) -> None:
        bootstrap()
        settings.PROVIDER_CREDENTIAL_ENCRYPTION_KEY = None
        c = _make_app(
            _fresh_storage(),
            preferences=PreferencesService(_TMP / "prefs-missing-encryption"),
            db_session=isolated_db_session,
        )

        resp = c.post(
            "/api/admin/providers/credentials",
            json={"provider_key": "gemini", "api_key": "AIza-should-not-store"},
            headers=_csrf_headers(c),
        )

        assert resp.status_code == 400
        assert "PROVIDER_CREDENTIAL_ENCRYPTION_KEY" in resp.json()["detail"]
        assert isolated_db_session.query(ProviderCredential).count() == 0

    def test_provider_management_fallback_policy_order_and_safe_defaults(
        self,
        _no_api_key: None,
        isolated_db_session: Session,
    ) -> None:
        bootstrap()
        settings.PROVIDER_CREDENTIAL_ENCRYPTION_KEY = SecretStr("test-provider-credential-encryption-key")
        preferences = PreferencesService(_TMP / "prefs-policy")
        c = _make_app(_fresh_storage(), preferences=preferences, db_session=isolated_db_session)
        headers = _csrf_headers(c)
        resp = c.post(
            "/api/admin/providers/credentials",
            json={
                "provider_key": "gemini",
                "api_key": "AIza-policy-key",
                "provider_model": "gemma-4-31b-it",
                "is_active": True,
            },
            headers=headers,
        )
        assert resp.status_code == 200

        policy_resp = c.put(
            "/api/admin/providers/fallback-policy",
            json={
                "default_provider": "gemini",
                "default_model": "gemma-4-31b-it",
                "default_credential_id": "gemini",
                "allow_cross_provider_fallback": False,
                "fallback_on_qa_failure": False,
                "candidates": [
                    {
                        "priority_order": 0,
                        "provider_key": "gemini",
                        "provider_model": "gemma-4-31b-it",
                        "credential_id": "gemini",
                        "enabled": True,
                    },
                ],
            },
            headers=headers,
        )
        assert policy_resp.status_code == 200
        policy = policy_resp.json()
        assert policy["default_provider"] == "gemini"
        assert policy["default_model"] == "gemma-4-31b-it"
        assert policy["allow_cross_provider_fallback"] is False
        assert policy["fallback_on_qa_failure"] is False
        assert "qa_failure" in policy["disallowed_failure_reasons"]
        assert [(item["provider_key"], item["provider_model"]) for item in policy["candidates"]] == [
            ("gemini", "gemma-4-31b-it"),
        ]

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
        assert {"preferences", "translation_cache", "usage"} <= set(items)
        assert set(canonical_items) == set(items)
        assert items["preferences"]["exists"] is True
        assert items["translation_cache"]["affects_process"] is True
        assert items["usage"]["affects_process"] is False

        headers = _csrf_headers(c)
        refresh_resp = c.post("/novels/admin/runtime-state/preferences/refresh", headers=headers)
        assert refresh_resp.status_code == 200
        assert refresh_resp.json()["key"] == "preferences"

        clear_cache_resp = c.delete("/novels/admin/runtime-state/translation_cache", headers=headers)
        assert clear_cache_resp.status_code == 200
        assert cache.get("source", "gemini", "gemini-2.5-flash") is None

        clear_usage_resp = c.delete("/novels/admin/runtime-state/usage", headers=headers)
        assert clear_usage_resp.status_code == 200
        assert usage.summary(all_days=True)["total_requests"] == 0

        clear_preferences_resp = c.delete("/novels/admin/runtime-state/preferences", headers=headers)
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
            headers=_csrf_headers(c),
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
                "provider_key": "gemini",
                "provider_model": "gemini-2.5-flash-lite",
            },
            headers=_csrf_headers(c),
        )
        assert create_resp.status_code == 200
        created_payload = create_resp.json()
        job_id = created_payload["id"]
        assert "provider" not in created_payload
        assert "model" not in created_payload
        assert created_payload["provider_key"] == "gemini"
        assert created_payload["provider_model"] == "gemini-2.5-flash-lite"

        update_resp = c.patch(
            f"/novels/activity/{job_id}",
            json={"status": "failed", "error": "worker failed", "metadata": {"worker": "local"}},
            headers=_csrf_headers(c),
        )
        assert update_resp.status_code == 200
        assert update_resp.json()["status"] == "failed"
        assert update_resp.json()["finished_at"] is not None
        assert update_resp.json()["error"] == "worker failed"

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
            provider_key="gemini",
            provider_model="gemini-2.5-flash-lite",
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
        assert "provider" not in payload
        assert "model" not in payload
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

    def test_jobs_routes_preserve_activity_identifiers_and_canonical_provider_fields(self, _no_api_key: None) -> None:
        bootstrap()
        storage = _fresh_storage()
        jobs = ActivityQueueService(_TMP / "jobs")
        created = jobs.create_translation_activity(
            novel_id="test-n1",
            chapters="1-2",
            provider_key="gemini",
            provider_model="gemini-2.5-flash-lite",
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
        assert "provider" not in detail_payload
        assert "model" not in detail_payload
        assert detail_payload["provider_key"] == "gemini"
        assert detail_payload["provider_model"] == "gemini-2.5-flash-lite"

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

        headers = _csrf_headers(c)
        delete_resp = c.delete(f"/novels/activity/{created['id']}", headers=headers)

        assert delete_resp.status_code == 204
        assert jobs.get_activity(str(created["id"])) is None
        assert c.delete("/novels/activity/missing", headers=headers).status_code == 404

    def test_invalid_activity_kind_returns_400(self, _no_api_key: None) -> None:
        bootstrap()
        storage = _fresh_storage()
        jobs = ActivityQueueService(_TMP / "jobs")
        c = _make_app(storage, jobs)

        resp = c.post(
            "/novels/activity/crawl",
            json={"novel_id": "test-n1", "source_key": "syosetu_ncode", "kind": "unknown"},
            headers=_csrf_headers(c),
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

        resp = c.post("/novels/activity/run-next", params={"activity_type": "crawl"}, headers=_csrf_headers(c))

        assert resp.status_code == 200
        assert resp.json()["status"] == "completed", resp.json().get("error")
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

        resp = c.post("/novels/activity/missing/run", headers=_csrf_headers(c))

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

        resp = c.post(f"/novels/activity/{created['id']}/run", headers=_csrf_headers(c))

        assert resp.status_code == 200
        payload = resp.json()
        stored = jobs.get_activity(str(created["id"]))
        assert stored is not None
        assert payload["status"] == "completed", payload.get("error")
        assert payload["finished_at"] == stored["finished_at"]
        assert payload["metadata"] == stored["metadata"]

    def test_run_activity_rejects_failed_activity_use_retry(self, _no_api_key: None) -> None:
        bootstrap()
        storage = _fresh_storage()
        jobs = ActivityQueueService(_TMP / "jobs")
        worker = ActivityWorkerService(jobs, StubJobOrchestrator(storage))  # type: ignore[arg-type]
        c = _make_app(storage, jobs, worker)
        created = jobs.create_crawl_activity(novel_id="test-n1", source_key="syosetu_ncode", kind="chapters")
        jobs.update_activity_status(str(created["id"]), "failed", error="source timeout")

        resp = c.post(f"/novels/activity/{created['id']}/run", headers=_csrf_headers(c))

        assert resp.status_code == 400
        assert "cannot be run from status: failed" in resp.text

    def test_retry_failed_activity_resets_to_pending(self, _no_api_key: None) -> None:
        bootstrap()
        storage = _fresh_storage()
        jobs = ActivityQueueService(_TMP / "jobs")
        worker = ActivityWorkerService(jobs, StubJobOrchestrator(storage))  # type: ignore[arg-type]
        c = _make_app(storage, jobs, worker)
        created = jobs.create_crawl_activity(novel_id="test-n1", source_key="syosetu_ncode", kind="chapters")
        failed = jobs.update_activity_status(str(created["id"]), "failed", error="source timeout")
        assert failed is not None

        resp = c.post(f"/api/admin/activity/{created['id']}/retry", headers=_csrf_headers(c))

        assert resp.status_code == 200
        payload = resp.json()
        assert payload["status"] == "pending"
        assert payload["started_at"] is None
        assert payload["finished_at"] is None
        assert payload["error"] is None
        assert payload["retry_count"] == 2
        assert payload["metadata"]["retry_history"][0]["status"] == "failed"
        assert payload["metadata"]["retry_history"][0]["error"] == "source timeout"

    @pytest.mark.parametrize("status", ["pending", "running", "completed"])
    def test_retry_rejects_non_retryable_statuses(self, _no_api_key: None, status: str) -> None:
        bootstrap()
        storage = _fresh_storage()
        jobs = ActivityQueueService(_TMP / "jobs")
        worker = ActivityWorkerService(jobs, StubJobOrchestrator(storage))  # type: ignore[arg-type]
        c = _make_app(storage, jobs, worker)
        created = jobs.create_crawl_activity(novel_id="test-n1", source_key="syosetu_ncode", kind="chapters")
        if status != "pending":
            jobs.update_activity_status(str(created["id"]), status)

        resp = c.post(f"/api/admin/activity/{created['id']}/retry", headers=_csrf_headers(c))

        assert resp.status_code == 400
        assert f"cannot be retried from status: {status}" in resp.text

    def test_retry_missing_activity_returns_404(self, _no_api_key: None) -> None:
        bootstrap()
        storage = _fresh_storage()
        jobs = ActivityQueueService(_TMP / "jobs")
        worker = ActivityWorkerService(jobs, StubJobOrchestrator(storage))  # type: ignore[arg-type]
        c = _make_app(storage, jobs, worker)

        resp = c.post("/api/admin/activity/missing/retry", headers=_csrf_headers(c))

        assert resp.status_code == 404

    def test_retry_requires_owner_and_csrf(self, _no_api_key: None) -> None:
        bootstrap()
        storage = _fresh_storage()
        jobs = ActivityQueueService(_TMP / "jobs")
        worker = ActivityWorkerService(jobs, StubJobOrchestrator(storage))  # type: ignore[arg-type]
        owner = _make_app(storage, jobs, worker)
        user = _make_app(storage, jobs, worker, session_user=REGULAR_USER)
        created = jobs.create_crawl_activity(novel_id="test-n1", source_key="syosetu_ncode", kind="chapters")
        jobs.update_activity_status(str(created["id"]), "failed", error="source timeout")

        missing_csrf = owner.post(f"/api/admin/activity/{created['id']}/retry")
        non_owner = user.post(f"/api/admin/activity/{created['id']}/retry", headers=_csrf_headers(user))
        legacy_alias = owner.post(f"/novels/activity/{created['id']}/retry", headers=_csrf_headers(owner))

        assert missing_csrf.status_code == 403
        assert non_owner.status_code == 403
        assert legacy_alias.status_code == 200
        assert legacy_alias.json()["status"] == "pending"

    def test_manual_status_patch_rejects_running_transition(self, _no_api_key: None) -> None:
        bootstrap()
        storage = _fresh_storage()
        jobs = ActivityQueueService(_TMP / "jobs")
        c = _make_app(storage, jobs)
        created = jobs.create_crawl_activity(novel_id="test-n1", source_key="syosetu_ncode", kind="chapters")

        resp = c.patch(
            f"/api/admin/activity/{created['id']}",
            json={"status": "running"},
            headers=_csrf_headers(c),
        )

        assert resp.status_code == 400
        assert "Use the activity run endpoint" in resp.text


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
    def test_list_db_backed_request(self, _no_api_key: None, isolated_db_session: Session) -> None:
        bootstrap()
        storage = _fresh_storage()
        req = NovelRequest(
            user_id=2,
            request_type="novel",
            source_url="https://ncode.syosetu.com/n1234ab/",
            status="pending",
        )
        isolated_db_session.add(req)
        isolated_db_session.commit()
        c = _make_app(storage, db_session=isolated_db_session)

        list_resp = c.get("/novels/requests", params={"status": "pending"})
        assert list_resp.status_code == 200
        listed = list_resp.json()["requests"]
        assert len(listed) == 1
        assert listed[0]["id"] == str(req.id)
        assert listed[0]["request_id"] == str(req.id)
        assert listed[0]["source_url"] == "https://ncode.syosetu.com/n1234ab/"
        canonical_list_resp = c.get("/api/admin/requests", params={"status": "pending"})
        assert canonical_list_resp.status_code == 200
        assert canonical_list_resp.json()["requests"][0]["id"] == str(req.id)

    def test_update_db_backed_request_status(self, _no_api_key: None, isolated_db_session: Session) -> None:
        bootstrap()
        storage = _fresh_storage()
        req = NovelRequest(user_id=2, request_type="novel", source_url="https://example.com/novel", status="pending")
        isolated_db_session.add(req)
        isolated_db_session.commit()
        c = _make_app(storage, db_session=isolated_db_session)

        status_resp = c.patch(
            f"/novels/requests/{req.id}",
            json={"status": "approved", "reviewed_by": "admin"},
            headers=_csrf_headers(c),
        )
        assert status_resp.status_code == 200
        status_payload = status_resp.json()
        assert status_payload["status"] == "approved"
        assert status_payload["request_id"] == str(req.id)
        assert status_payload["resolved_at"] is not None

        get_resp = c.get(f"/novels/requests/{req.id}")
        assert get_resp.status_code == 200
        get_payload = get_resp.json()
        assert get_payload["status"] == "approved"
        assert get_payload["request_id"] == str(req.id)

    def test_invalid_request_status_returns_400(self, _no_api_key: None, isolated_db_session: Session) -> None:
        bootstrap()
        storage = _fresh_storage()
        req = NovelRequest(user_id=2, request_type="novel", source_url="https://example.com/novel", status="pending")
        isolated_db_session.add(req)
        isolated_db_session.commit()
        c = _make_app(storage, db_session=isolated_db_session)

        resp = c.patch(f"/novels/requests/{req.id}", json={"status": "not-real"}, headers=_csrf_headers(c))

        assert resp.status_code == 400

    def test_legacy_request_actions_return_gone(self, _no_api_key: None, isolated_db_session: Session) -> None:
        bootstrap()
        c = _make_app(_fresh_storage(), db_session=isolated_db_session)

        headers = _csrf_headers(c)
        assert c.post("/novels/requests", json={"title": "Requested Novel"}, headers=headers).status_code == 410
        assert c.post("/novels/requests/1/vote", json={"voter": "reader-2"}, headers=headers).status_code == 410
        assert (
            c.post(
                "/novels/requests/1/source-candidates",
                json={"source_key": "kakuyomu", "source_url": "https://kakuyomu.jp/works/123"},
                headers=headers,
            ).status_code
            == 410
        )


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
            headers=_csrf_headers(c),
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
            headers=_csrf_headers(c),
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
            headers=_csrf_headers(c),
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
            headers=_csrf_headers(c),
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
            headers=_csrf_headers(c),
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
            headers=_csrf_headers(c),
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
            headers=_csrf_headers(c),
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
            headers = _csrf_headers(c)
            for _ in range(5):
                resp = c.post("/novels/test-n1/scrape", json=body, headers=headers)
                assert resp.status_code == 200
            # 6th should be rate-limited
            resp = c.post("/novels/test-n1/scrape", json=body, headers=headers)
            assert resp.status_code == 429
