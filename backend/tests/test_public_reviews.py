"""Contract tests for public review listing endpoint."""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from novelai.api.auth.session import SessionUser, get_current_user
from novelai.api.routers.dependencies import get_db_session, get_public_catalog_service
from novelai.api.routers.public_novel import router as public_novel_router
from novelai.db.base import Base
from novelai.db.models.novel import Novel
from novelai.db.models.users import Review

_SQLITE = "sqlite:///:memory:"


@pytest.fixture()
def db_session():
    engine = create_engine(_SQLITE, connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, autocommit=False, autoflush=True)
    sess = Session()
    yield sess
    sess.close()
    Base.metadata.drop_all(engine)


@pytest.fixture()
def novel(db_session):
    n = Novel(slug="test-novel", title="Test Novel", language="ja", publication_status="ongoing")
    db_session.add(n)
    db_session.commit()
    return n


class FakeCatalogService:
    """Minimal stub for PublicCatalogService._resolve_public_novel."""

    def __init__(self, db_session):
        self._db = db_session

    def _resolve_public_novel(self, slug: str):
        novel = self._db.query(Novel).filter_by(slug=slug).one_or_none()
        if novel is None:
            return None
        return novel.id, {}, slug

    def get_public_novel_summary(self, slug: str, *, include_adult: bool = False):
        del include_adult
        resolved = self._resolve_public_novel(slug)
        if resolved is None:
            return None, None
        novel_id, _metadata, public_slug = resolved
        return {"novel_id": str(novel_id), "slug": public_slug}, str(novel_id)


@pytest.fixture()
def app(db_session):
    _app = FastAPI()
    _app.include_router(public_novel_router)

    def _db_override():
        yield db_session
        db_session.commit()

    _app.dependency_overrides[get_db_session] = _db_override
    _app.dependency_overrides[get_current_user] = lambda: SessionUser(user_id=None, email=None, role="guest")
    _app.dependency_overrides[get_public_catalog_service] = lambda: FakeCatalogService(db_session)
    return _app


@pytest.fixture()
def client(app):
    return TestClient(app, raise_server_exceptions=True)


def _seed_review(db_session, novel, user_id: int, rating: int, status: str = "published") -> Review:
    r = Review(user_id=user_id, novel_id=novel.id, rating=rating, body=f"Review by {user_id}", status=status)
    db_session.add(r)
    db_session.flush()
    return r


class TestPublicReviewListing:
    def test_only_published_reviews_visible(self, client, novel, db_session) -> None:
        _seed_review(db_session, novel, 1, 5, "published")
        _seed_review(db_session, novel, 2, 3, "pending")
        _seed_review(db_session, novel, 3, 1, "rejected")
        db_session.commit()

        resp = client.get("/api/public/novels/test-novel/reviews")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["items"]) == 1
        assert data["items"][0]["rating"] == 5

    def test_no_user_id_in_public_items(self, client, novel, db_session) -> None:
        _seed_review(db_session, novel, 1, 5)
        db_session.commit()

        resp = client.get("/api/public/novels/test-novel/reviews")
        item = resp.json()["items"][0]
        assert "user_id" not in item
        assert "status" not in item

    def test_pagination_shape(self, client, novel, db_session) -> None:
        for i in range(5):
            _seed_review(db_session, novel, 100 + i, 3 + (i % 3))
        db_session.commit()

        resp1 = client.get("/api/public/novels/test-novel/reviews?limit=2")
        data1 = resp1.json()
        assert len(data1["items"]) == 2
        assert data1["next_cursor"] is not None

        resp2 = client.get(f"/api/public/novels/test-novel/reviews?limit=2&cursor={data1['next_cursor']}")
        data2 = resp2.json()
        assert len(data2["items"]) == 2

        resp3 = client.get(f"/api/public/novels/test-novel/reviews?limit=2&cursor={data2['next_cursor']}")
        data3 = resp3.json()
        assert len(data3["items"]) == 1
        assert data3["next_cursor"] is None

    def test_404_unknown_novel(self, client) -> None:
        assert client.get("/api/public/novels/nonexistent/reviews").status_code == 404

    def test_guest_access_allowed(self, client, novel, db_session) -> None:
        _seed_review(db_session, novel, 1, 5)
        db_session.commit()
        resp = client.get("/api/public/novels/test-novel/reviews")
        assert resp.status_code == 200

    def test_cache_control_header(self, client, novel, db_session) -> None:
        _seed_review(db_session, novel, 1, 5)
        db_session.commit()
        resp = client.get("/api/public/novels/test-novel/reviews")
        assert "public" in resp.headers.get("cache-control", "")
