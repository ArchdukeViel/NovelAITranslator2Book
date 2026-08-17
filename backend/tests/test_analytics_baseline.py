"""Focused privacy, retention, and API tests for analytics baseline."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from typing import Any, cast

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import DateTime, create_engine, inspect
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from starlette.middleware.sessions import SessionMiddleware

from novelai.api.auth.session import SessionUser, get_current_user
from novelai.api.routers.admin_analytics import ingestion_router, router
from novelai.api.routers.dependencies import get_db_session
from novelai.api.routers.public_novel import get_novel
from novelai.config.settings import settings
from novelai.db.base import Base
from novelai.db.models.analytics_event import AnalyticsEvent
from novelai.services.analytics_service import AnalyticsService, sanitize_metadata
from novelai.services.maintenance_service import TASK_ANALYTICS_EVENTS, MaintenanceService


@pytest.fixture()
def db_session():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    yield session
    session.close()
    Base.metadata.drop_all(engine)


@pytest.fixture()
def client(db_session):
    app = FastAPI()
    app.add_middleware(SessionMiddleware, secret_key="test", https_only=False)
    current: dict[str, SessionUser] = {"user": SessionUser(user_id=None, email=None, role="guest")}

    def db_override():
        yield db_session
        db_session.commit()

    app.dependency_overrides[get_db_session] = db_override
    app.dependency_overrides[get_current_user] = lambda: current["user"]
    app.include_router(router)
    app.include_router(ingestion_router)
    app.state.current_user = current
    return TestClient(app)


def test_metadata_drops_private_values() -> None:
    metadata = sanitize_metadata(
        "search.performed",
        {"scope": "catalog", "query": "private text", "prompt": "secret", "result_count": 3},
    )
    assert json.loads(metadata or "{}") == {"scope": "catalog", "result_count": "3"}


def test_recording_disabled_and_invalid_events_do_not_store(db_session, monkeypatch) -> None:
    monkeypatch.setattr(settings, "ANALYTICS_ENABLED", False)
    AnalyticsService().record_event(db_session, "public_novel.view", novel_id="n1")
    monkeypatch.setattr(settings, "ANALYTICS_ENABLED", True)
    AnalyticsService().record_event(db_session, "unknown.event", novel_id="n1")
    assert db_session.query(AnalyticsEvent).count() == 0


def test_analytics_event_created_at_is_timezone_aware_and_indexed(db_session) -> None:
    created_at = datetime.now(UTC)
    db_session.add(AnalyticsEvent(event_name="public_novel.view", created_at=created_at))
    db_session.flush()

    column = next(column for column in AnalyticsEvent.__table__.columns if column.name == "created_at")
    assert isinstance(column.type, DateTime) and column.type.timezone is True
    assert "ix_analytics_events_created_at" in {
        index["name"] for index in inspect(db_session.bind).get_indexes("analytics_events")
    }


def test_ingestion_limits_and_disabled_behavior(client, monkeypatch) -> None:
    monkeypatch.setattr(settings, "ANALYTICS_ENABLED", False)
    assert client.post("/api/public/analytics/events", json={"events": []}).status_code == 503

    monkeypatch.setattr(settings, "ANALYTICS_ENABLED", True)
    monkeypatch.setattr(settings, "ANALYTICS_PUBLIC_INGESTION_ENABLED", False)
    assert client.post("/api/public/analytics/events", json={"events": []}).status_code == 503

    monkeypatch.setattr(settings, "ANALYTICS_PUBLIC_INGESTION_ENABLED", True)
    monkeypatch.setattr(settings, "ANALYTICS_INGEST_MAX_BATCH", 1)
    assert (
        client.post(
            "/api/public/analytics/events", json={"events": [{"event_name": "public_novel.view"}] * 2}
        ).status_code
        == 422
    )
    assert (
        client.post("/api/public/analytics/events", json={"events": [{"event_name": "unknown.event"}]}).status_code
        == 422
    )

    monkeypatch.setattr(settings, "ANALYTICS_INGEST_MAX_BODY_BYTES", 1024)
    response = client.post(
        "/api/public/analytics/events",
        content=json.dumps({"events": [{"event_name": "public_novel.view", "metadata": {"novel_id": "x" * 2000}}]}),
        headers={"content-type": "application/json"},
    )
    assert response.status_code == 413


def test_public_ingestion_uses_accepted_timestamp_and_server_identity(client, db_session, monkeypatch) -> None:
    monkeypatch.setattr(settings, "ANALYTICS_ENABLED", True)
    monkeypatch.setattr(settings, "ANALYTICS_PUBLIC_INGESTION_ENABLED", True)
    client.app.state.current_user["user"] = SessionUser(user_id=42, email="reader@example.test", role="user")
    timestamp = datetime.now(UTC) - timedelta(minutes=1)

    response = client.post(
        "/api/public/analytics/events",
        json={
            "events": [
                {
                    "event_name": "public_chapter.view",
                    "event_timestamp": timestamp.isoformat(),
                    "novel_id": "novel-1",
                    "chapter_id": "chapter-1",
                    "metadata": {"user_id": "attacker", "session_id": "attacker", "chapter_id": "chapter-1"},
                }
            ]
        },
    )

    assert response.json() == {"recorded": 1, "dropped": 0}
    event = db_session.query(AnalyticsEvent).one()
    assert event.user_id == 42
    assert event.session_id is None
    assert event.novel_id == "novel-1"
    assert event.chapter_id == "chapter-1"
    assert event.metadata_json == '{"chapter_id": "chapter-1"}'
    assert event.created_at.replace(tzinfo=UTC) == timestamp.replace(microsecond=timestamp.microsecond)


@pytest.mark.parametrize(
    "case",
    ["future", "past"],
)
def test_public_ingestion_rejects_out_of_bounds_or_naive_timestamps(client, monkeypatch, case) -> None:
    monkeypatch.setattr(settings, "ANALYTICS_ENABLED", True)
    monkeypatch.setattr(settings, "ANALYTICS_PUBLIC_INGESTION_ENABLED", True)
    monkeypatch.setattr(settings, "ANALYTICS_RETENTION_DAYS", 365)
    if case == "future":
        timestamp = datetime.now(UTC) + timedelta(minutes=6)
    else:
        timestamp = datetime.now(UTC) - timedelta(days=366)
    response = client.post(
        "/api/public/analytics/events",
        json={"events": [{"event_name": "public_novel.view", "event_timestamp": timestamp.isoformat()}]},
    )
    assert response.status_code == 422

    naive_response = client.post(
        "/api/public/analytics/events",
        json={"events": [{"event_name": "public_novel.view", "event_timestamp": datetime.now().isoformat()}]},
    )
    assert naive_response.status_code == 422


def test_anonymous_ingestion_hashes_limiter_key_and_never_stores_ip(client, db_session, monkeypatch) -> None:
    monkeypatch.setattr(settings, "ANALYTICS_ENABLED", True)
    monkeypatch.setattr(settings, "ANALYTICS_PUBLIC_INGESTION_ENABLED", True)
    limiter_keys: list[str] = []

    def capture_limiter(_request, _action, **kwargs) -> None:
        limiter_keys.append(kwargs["key_transform"]("127.0.0.1"))

    monkeypatch.setattr("novelai.api.routers.admin_analytics._rate_limit", capture_limiter)

    response = client.post("/api/public/analytics/events", json={"events": [{"event_name": "public_novel.view"}]})

    assert response.status_code == 200
    assert limiter_keys[0].startswith("anonymous:")
    assert len(limiter_keys[0].removeprefix("anonymous:")) == 64
    assert "127.0.0.1" not in limiter_keys[0]
    event = db_session.query(AnalyticsEvent).one()
    assert event.user_id is None
    assert event.session_id is None
    assert "127.0.0.1" not in repr(event)
    assert "127.0.0.1" not in (event.metadata_json or "")


def test_trusted_server_recording_needs_only_global_flag(db_session, monkeypatch) -> None:
    monkeypatch.setattr(settings, "ANALYTICS_ENABLED", True)
    monkeypatch.setattr(settings, "ANALYTICS_PUBLIC_INGESTION_ENABLED", False)

    AnalyticsService().record_event(db_session, "public_novel.view", novel_id="novel-1")

    assert db_session.query(AnalyticsEvent).count() == 1


def test_summary_auth_and_aggregate_timezones(client, db_session, monkeypatch) -> None:
    monkeypatch.setattr(settings, "ANALYTICS_ENABLED", True)
    AnalyticsService().record_event(db_session, "public_novel.view", novel_id="n1")
    db_session.commit()
    assert client.get("/api/admin/analytics/summary").status_code == 401
    client.app.state.current_user["user"] = SessionUser(user_id=2, email="user@example.test", role="user")
    assert client.get("/api/admin/analytics/summary").status_code == 403
    client.app.state.current_user["user"] = SessionUser(user_id=1, email="owner@example.test", role="owner")
    response = client.get("/api/admin/analytics/summary?window=24h&timezone=Asia/Tokyo")
    assert response.status_code == 200
    payload = response.json()
    assert payload["groups"]["views"]["public_novel.view"] == 1
    assert "+09:00" in payload["generated_at"]


def test_summary_excludes_events_outside_window(db_session, monkeypatch) -> None:
    monkeypatch.setattr(settings, "ANALYTICS_ENABLED", True)
    db_session.add_all(
        [
            AnalyticsEvent(event_name="public_novel.view", created_at=datetime.now(UTC)),
            AnalyticsEvent(event_name="public_novel.view", created_at=datetime.now(UTC) - timedelta(hours=2)),
        ]
    )
    db_session.commit()
    summary = AnalyticsService().summary(db_session, window="1h", timezone="UTC")
    assert summary["groups"]["views"]["public_novel.view"] == 1


def test_retention_cleanup_is_bounded_and_maintenance_safe(db_session, monkeypatch) -> None:
    monkeypatch.setattr(settings, "ANALYTICS_ENABLED", True)
    old = AnalyticsEvent(event_name="public_novel.view", created_at=datetime.now(UTC) - timedelta(days=2))
    recent = AnalyticsEvent(event_name="public_novel.view", created_at=datetime.now(UTC))
    db_session.add_all([old, recent])
    db_session.commit()
    assert AnalyticsService().cleanup_old_events(db_session, ttl_days=1, batch_size=1) == 1
    assert db_session.query(AnalyticsEvent).count() == 1

    class AnalyticsStub:
        def cleanup_old_events(self, *, ttl_days: int) -> int:
            assert ttl_days == settings.ANALYTICS_RETENTION_DAYS
            return 1

    service = MaintenanceService(storage=object(), analytics_service=AnalyticsStub())
    assert service.run_maintenance(dry_run=True, tasks=[TASK_ANALYTICS_EVENTS])["tasks"][0]["dry_run"] is True
    assert service.run_maintenance(tasks=[TASK_ANALYTICS_EVENTS])["tasks"][0]["items_deleted"] == 1


def test_best_effort_recording_failure_isolated(monkeypatch) -> None:
    monkeypatch.setattr(settings, "ANALYTICS_ENABLED", True)
    monkeypatch.setattr("novelai.db.engine.session_scope", lambda: (_ for _ in ()).throw(RuntimeError("down")))
    AnalyticsService().record_event_best_effort("public_novel.view", novel_id="n1")


@pytest.mark.asyncio
async def test_public_novel_hook_does_not_break_response(monkeypatch) -> None:
    monkeypatch.setattr(settings, "ANALYTICS_ENABLED", True)
    monkeypatch.setattr(
        AnalyticsService,
        "record_event_best_effort",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("down")),
    )

    class Service:
        def get_public_novel_summary(self, _slug: str, *, include_adult: bool = False):
            assert include_adult is False
            return {"novel_id": "n1"}, "n1"

    result = await get_novel(
        "novel",
        False,
        cast(Any, Service()),
        SessionUser(user_id=None, email=None, role="guest"),
    )
    assert result == {"novel_id": "n1"}
