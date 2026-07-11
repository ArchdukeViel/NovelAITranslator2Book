"""Optional property coverage for the admin novel detail payload."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient
from hypothesis import given, settings
from hypothesis import strategies as st
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from starlette.middleware.sessions import SessionMiddleware

from novelai.api.auth.session import SessionUser, get_current_user
from novelai.api.routers.dependencies import get_db_session, get_storage
from novelai.api.routers.library import router as library_router
from novelai.db.base import Base
from novelai.db.models.glossary import NovelGlossaryEntry
from novelai.db.models.novel import Novel


@settings(deadline=None)
@given(
    st.sampled_from(["glossary_pending", "glossary_ready", "glossary_skipped"]),
    st.integers(min_value=0, max_value=10),
)
def test_admin_novel_detail_api_returns_glossary_fields(glossary_status: str, glossary_revision: int) -> None:
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, autocommit=False, autoflush=True)
    db_session = Session()
    storage = _NovelDetailStorage()

    try:
        app = FastAPI()
        app.add_middleware(SessionMiddleware, secret_key="test", https_only=False)
        current = {"user": SessionUser(user_id=1, email="owner@example.com", role="owner")}

        def _user_override():
            return current["user"]

        def _db_override():
            yield db_session

        app.dependency_overrides[get_current_user] = _user_override
        app.dependency_overrides[get_db_session] = _db_override
        app.dependency_overrides[get_storage] = lambda: storage
        app.include_router(library_router, prefix="/api/admin/novels")

        novel = Novel(
            slug="detail-novel",
            title="Detail Novel",
            language="ja",
            status="ongoing",
            glossary_status=glossary_status,
            glossary_revision=glossary_revision,
        )
        db_session.add(novel)
        db_session.flush()
        for index in range(glossary_revision % 3):
            db_session.add(
                NovelGlossaryEntry(
                    novel_id=novel.id,
                    canonical_term=f"Term {index}",
                    term_type="other",
                    status="candidate" if index % 2 == 0 else "recommended",
                )
            )
        db_session.commit()

        client = TestClient(app, raise_server_exceptions=True)
        response = client.get("/api/admin/novels/detail-novel")

        assert response.status_code == 200
        payload = response.json()
        assert payload["glossary_status"] == glossary_status
        assert payload["glossary_revision"] == glossary_revision
        assert payload["glossary_pending_count"] == glossary_revision % 3
    finally:
        db_session.close()
        Base.metadata.drop_all(engine)


class _NovelDetailStorage:
    def load_metadata(self, novel_id: str):
        return {"title": "Detail Novel", "chapters": []}
