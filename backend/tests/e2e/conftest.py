"""Shared fixtures for end-to-end integration tests.

Provides a fully wired FastAPI TestClient with:
- In-memory SQLite database (all tables created)
- Temp-directory storage (isolated per session)
- DummySource registered in the source adapter registry
- MockGeminiProvider registered as the "dummy" provider
- Owner session user for authenticated admin requests
- CSRF token helper for unsafe methods

Architecture:
    Uses ``create_app()`` from ``novelai.api.app`` with dependency
    overrides for storage, DB session, and current user. The source
    and provider registries are patched at session scope so the
    orchestrator discovers the test fixtures automatically.

    Additionally patches ``novelai.db.engine.session_scope`` so that
    CatalogService and other internal services use the same in-memory
    SQLite database instead of connecting to PostgreSQL.

IMPORTANT:
    All ``novelai.*`` and ``tests.*`` imports are lazy (inside
    fixtures) to prevent PostgreSQL connection attempts at module
    import time.  ``catalog_service`` captures ``session_scope`` as a
    default parameter — import order matters.
"""

from __future__ import annotations

from contextlib import contextmanager
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

# Module-level ref to the TranslationCache so per-test fixtures can clear it
_translation_cache: Any = None

# ---------------------------------------------------------------------------
# Session-scoped fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def mock_provider():
    """Session-scoped mock provider with call tracking and failure injection."""
    from tests.fixtures.e2e.mock_provider import MockGeminiProvider

    return MockGeminiProvider()


@pytest.fixture(scope="session")
def e2e_db_session_factory():
    """Create in-memory SQLite engine with all tables, return a session factory."""
    from novelai.db.base import Base

    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine)


@pytest.fixture(scope="session")
def e2e_storage_dir(tmp_path_factory):
    """Session-scoped temp directory for isolated storage."""
    return tmp_path_factory.mktemp("e2e_storage")


@pytest.fixture(scope="session")
def e2e_test_client(
    e2e_db_session_factory,
    e2e_storage_dir,
    mock_provider,
    monkeypatch_session,
):
    """Session-scoped FastAPI TestClient with all dependencies overridden.

    Registers DummySource and MockGeminiProvider so the orchestrator
    discovers them automatically. Overrides storage, DB session, and
    current user to isolate tests from the real runtime.

    Patches ``novelai.db.engine.session_scope`` so CatalogService and
    other internal services use the in-memory SQLite database.
    """
    # ---- lazy imports (avoids PostgreSQL at module load) ----

    # Step 1: Patch session_scope on db.engine FIRST, before any other
    # module imports it.  Subsequent modules that do
    # ``from novelai.db.engine import session_scope`` will get the
    # patched version from the cached sys.modules entry.
    import novelai.db.engine as _db_engine

    @contextmanager
    def _patched_session_scope(url=None):
        session: Session = e2e_db_session_factory()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    monkeypatch_session.setattr(_db_engine, "session_scope", _patched_session_scope)

    # Step 2: Now import every module that binds session_scope at
    # module level.  Because ``novelai.db.engine`` is already cached
    # and patched, their ``from novelai.db.engine import session_scope``
    # resolves to the patched version.  We also patch their local name
    # to guard against any edge case where Python cached the attr
    # lookup before the monkeypatch took effect.
    import novelai.services.catalog_service as _catalog_svc
    import novelai.services.orchestration.crawler as _crawler
    import novelai.services.orchestration.glossary as _glossary_svc
    import novelai.services.orchestration.translation as _translation_svc

    for _mod in (_catalog_svc, _crawler, _translation_svc):
        monkeypatch_session.setattr(_mod, "session_scope", _patched_session_scope)
    # glossary.py aliases it as ``_session_scope``
    monkeypatch_session.setattr(_glossary_svc, "_session_scope", _patched_session_scope)

    # Step 3: Build the noop refresh and patch on catalog_service
    # BEFORE any module that imports it from module level.
    def _noop_refresh(*args, **kwargs):
        return True

    monkeypatch_session.setattr(
        _catalog_svc,
        "safely_refresh_catalog_projection_after_storage_write",
        _noop_refresh,
    )

    # Step 4: Import novel_orchestration_service — its module-level
    # ``from catalog_service import safely_refresh…`` catches the noop.
    import novelai.services.novel_orchestration_service as _orch_svc
    monkeypatch_session.setattr(
        _orch_svc,
        "safely_refresh_catalog_projection_after_storage_write",
        _noop_refresh,
    )

    # Step 5: Propagate the safely_refresh noop to every other module
    # that imports it (crawler, translation already done via noop above
    # but we re-assert here).
    import novelai.services.backup_manager as _backup
    import novelai.services.checkpoint_manager as _checkpoint
    import novelai.services.editor_service as _editor_service
    import novelai.services.orchestration.importer as _importer

    for _mod in (
        _crawler,
        _glossary_svc,
        _translation_svc,
        _editor_service,
        _backup,
        _checkpoint,
        _importer,
    ):
        monkeypatch_session.setattr(
            _mod,
            "safely_refresh_catalog_projection_after_storage_write",
            _noop_refresh,
        )

    # Step 6: Patch translation model policy to include the mock provider.
    # Without this the scheduler sees no configs → SchedulerPausedError
    # because no gemini-compatible policy exists for the "dummy" provider.
    from novelai.config.settings import settings as _app_settings
    monkeypatch_session.setattr(
        _app_settings,
        "TRANSLATION_MODEL_POLICY",
        [
            {
                "provider_key": "dummy",
                "provider_model": "mock-gemini-default",
                "priority_order": 0,
            },
        ],
    )

    # Step 7: Disable rate limiter to avoid 429 on sequential translate calls
    def _noop_rate_limit(request, action):
        pass

    monkeypatch_session.setattr(
        "novelai.api.routers.operations._rate_limit",
        _noop_rate_limit,
    )

    # Step 8: Now it's safe to import container (all its dependencies
    # already have patched session_scope and noop refresh).
    from novelai.runtime.container import container

    # Clear stale asyncio locks from previous aborted runs (module-level state)
    _translation_svc._translation_locks.clear()
    from novelai.services.orchestration.operations_helpers import _novel_translation_locks
    _novel_translation_locks.clear()

    # Step 8b: Disable translation cache to prevent cross-test cache hits
    # (identical chunk text across different novels hits the same cache key).
    monkeypatch_session.setattr(
        _app_settings,
        "TRANSLATION_CACHE_ENABLED",
        False,
    )

    # Step 8c: Snapshot the old TranslationCache ref so per-test fixtures
    # can clear it (the TranslateStage ALWAYS checks this cache).
    global _translation_cache
    _translation_cache = container.translation_cache

    from novelai.api.auth.session import SessionUser, get_current_user
    from novelai.api.routers.dependencies import (
        get_db_session,
        get_orchestrator,
        get_storage,
    )
    from novelai.providers.registry import register_provider
    from novelai.sources.registry import get_registry
    from novelai.storage.service import StorageService
    from tests.fixtures.e2e.dummy_source import DummySource

    OWNER_USER = SessionUser(user_id=1, email="owner@e2e.local", role="owner")

    # Temp storage
    storage = StorageService(e2e_storage_dir)
    # Rebuild the storage-dependent service graph against the isolated root.
    # Reassigning only ``orchestrator.storage`` leaves TranslateStage writing
    # chunk lineage through the container's default StorageService.
    monkeypatch_session.setattr(container, "_storage", storage)
    monkeypatch_session.setattr(container, "_translation", None)
    monkeypatch_session.setattr(container, "_orchestrator", None)
    container.orchestrator.storage = storage

    from novelai.api.app import create_app
    app = create_app()

    # MUST register test adapters AFTER create_app() — bootstrap() inside
    # create_app() calls register_provider("dummy", DummyProvider) which
    # would overwrite our mock if we registered first.
    get_registry().register(DummySource)
    register_provider("dummy", lambda: mock_provider)

    app.dependency_overrides[get_storage] = lambda: storage
    app.dependency_overrides[get_orchestrator] = lambda: container.orchestrator

    def _db_override():
        s: Session = e2e_db_session_factory()
        try:
            yield s
            s.commit()
        finally:
            s.close()

    app.dependency_overrides[get_db_session] = _db_override
    app.dependency_overrides[get_current_user] = lambda: OWNER_USER

    with TestClient(app, raise_server_exceptions=False) as client:
        yield client

    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Per-test fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def owner_auth(e2e_test_client: TestClient) -> dict[str, str]:
    """Return auth headers for an owner-authenticated request.

    Fetches a CSRF token and returns both the session cookie and
    X-CSRF-Token header needed for unsafe methods (POST/PUT/DELETE).
    """
    resp = e2e_test_client.get("/api/auth/csrf")
    assert resp.status_code == 200, f"CSRF token fetch failed: {resp.text}"
    csrf_token = resp.json()["csrf_token"]
    return {"X-CSRF-Token": csrf_token}


@pytest.fixture
def fresh_db(e2e_test_client: TestClient) -> Session:
    """Return a fresh DB session for direct DB assertions."""
    from novelai.api.routers.dependencies import get_db_session as _get_db

    gen = e2e_test_client.app.dependency_overrides[_get_db]()  # type: ignore[attr-defined]
    session = next(gen)
    return session


@pytest.fixture(scope="session")
def monkeypatch_session():
    """Session-scoped monkeypatch for patching module-level globals."""
    mp = pytest.MonkeyPatch()
    yield mp
    mp.undo()


@pytest.fixture(autouse=True)
def _reset_mock_provider(mock_provider) -> None:
    """Reset mock provider state and clear translation cache before each test."""
    mock_provider.reset()
    # Clear the old TranslationCache to prevent cross-test cache hits
    # (TranslateStage._cached_translation always checks this cache).
    global _translation_cache
    if _translation_cache is not None:
        _translation_cache._data.clear()
