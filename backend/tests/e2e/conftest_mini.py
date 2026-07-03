"""Minimal conftest to isolate hang cause."""
from __future__ import annotations
import sys
from contextlib import contextmanager
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

print("=== conftest start ===", flush=True)

@pytest.fixture(scope="session")
def mp_session():
    mp = pytest.MonkeyPatch()
    yield mp
    mp.undo()

@pytest.fixture(scope="session")
def db():
    from novelai.db.base import Base
    import novelai.db.models
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine)

@pytest.fixture(scope="session")
def test_client(db, mp_session):
    print("=== fixture start ===", flush=True)

    # Patch session_scope
    import novelai.db.engine as _db_engine
    import novelai.services.catalog_service as _catalog_svc

    @contextmanager
    def _patched(url=None):
        s = db()
        try:
            yield s
            s.commit()
        except Exception:
            s.rollback()
            raise
        finally:
            s.close()

    mp_session.setattr(_db_engine, "session_scope", _patched)
    mp_session.setattr(_catalog_svc, "session_scope", _patched)

    print("=== session_scope patched ===", flush=True)

    # Set up storage + orchestrator
    import tempfile
    from pathlib import Path
    from novelai.storage.service import StorageService
    from novelai.runtime.container import container
    tmp = Path(tempfile.mkdtemp("e2e_test"))
    storage = StorageService(tmp)
    print("=== about to access orchestrator ===", flush=True)
    container.orchestrator.storage = storage
    print("=== orchestrator set ===", flush=True)

    # Patch catalog refresh in 3 modules
    import novelai.services.catalog_service as _cat
    import novelai.services.orchestration.crawler as _cr
    import novelai.services.orchestration.translation as _tr
    def _noop(*a, **kw):
        return True
    for _mod in (_cat, _cr, _tr):
        mp_session.setattr(_mod, "safely_refresh_catalog_projection_after_storage_write", _noop)
    print("=== catalog refresh noop'd ===", flush=True)

    # create_app
    from novelai.api.app import create_app
    from novelai.api.auth.session import SessionUser, get_current_user
    from novelai.api.routers.dependencies import get_db_session, get_orchestrator, get_storage
    from novelai.providers.registry import register_provider
    from novelai.sources.registry import register_source
    from tests.fixtures.e2e.dummy_source import DummySource
    from tests.fixtures.e2e.mock_provider import MockGeminiProvider

    register_source("dummy-e2e", lambda: DummySource())
    register_provider("dummy", lambda: MockGeminiProvider())

    print("=== about to create_app ===", flush=True)
    app = create_app()
    print("=== app created ===", flush=True)

    OWNER_USER = SessionUser(user_id=1, email="owner@e2e.local", role="owner")
    app.dependency_overrides[get_storage] = lambda: storage
    app.dependency_overrides[get_orchestrator] = lambda: container.orchestrator
    def _db_override():
        s = db()
        try:
            yield s
            s.commit()
        finally:
            s.close()
    app.dependency_overrides[get_db_session] = _db_override
    app.dependency_overrides[get_current_user] = lambda: OWNER_USER

    print("=== about to create TestClient ===", flush=True)
    with TestClient(app, raise_server_exceptions=False) as client:
        print("=== TestClient ready ===", flush=True)
        yield client

    app.dependency_overrides.clear()
    print("=== fixture done ===", flush=True)

@pytest.fixture
def auth(test_client):
    resp = test_client.get("/api/auth/csrf")
    csrf = resp.json()["csrf_token"]
    return {"X-CSRF-Token": csrf}
