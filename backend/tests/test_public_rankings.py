"""Distinct-view ranking and anonymous viewer identity coverage."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any, cast
from unittest.mock import Mock

import pytest
from fastapi import Request
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from starlette.responses import Response

from novelai.config.settings import settings
from novelai.db.base import Base
from novelai.db.models.analytics_event import AnalyticsEvent
from novelai.db.models.novel import Novel
from novelai.services.analytics_service import anonymous_viewer_identity
from novelai.services.public_ranking_service import PublicRankingService


@pytest.fixture()
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    yield session
    session.close()
    Base.metadata.drop_all(engine)


def _request(cookie: str | None = None) -> Request:
    headers = [(b"cookie", cookie.encode("utf-8"))] if cookie is not None else []
    return Request({"type": "http", "headers": headers})


def test_anonymous_viewer_identity_is_signed_opaque_and_does_not_use_ip(monkeypatch) -> None:
    monkeypatch.setattr(settings, "SESSION_SECRET_KEY", "ranking-test-secret")
    first_response = Response()
    first_digest, created = anonymous_viewer_identity(_request(), first_response)
    assert created
    assert len(first_digest) == 64
    set_cookie = first_response.headers["set-cookie"]
    signed_value = set_cookie.split("novelai_viewer=", 1)[1].split(";", 1)[0]
    assert "127.0.0.1" not in set_cookie

    second_response = Response()
    second_digest, created = anonymous_viewer_identity(_request(f"novelai_viewer={signed_value}"), second_response)
    assert not created
    assert second_digest == first_digest
    tampered_response = Response()
    _, tampered_created = anonymous_viewer_identity(
        _request(f"novelai_viewer={signed_value}tampered"), tampered_response
    )
    assert tampered_created


def test_rankings_count_distinct_novel_detail_viewers_and_periods(db_session, monkeypatch) -> None:
    monkeypatch.setattr(settings, "ANALYTICS_ENABLED", True)
    now = datetime.now(UTC)
    alpha = Novel(slug="alpha", title="Alpha", language="ja", is_published=True)
    beta = Novel(slug="beta", title="Beta", language="ja", is_published=True)
    hidden = Novel(slug="hidden", title="Hidden", language="ja", is_published=False)
    db_session.add_all([alpha, beta, hidden])
    db_session.flush()
    events = [
        AnalyticsEvent(event_name="public_novel.view", novel_id="alpha", user_id=1, created_at=now),
        AnalyticsEvent(event_name="public_novel.view", novel_id="alpha", user_id=1, created_at=now),
        AnalyticsEvent(event_name="public_novel.view", novel_id="alpha", user_id=2, created_at=now),
        AnalyticsEvent(event_name="public_novel.view", novel_id="alpha", session_id="anon-a", created_at=now),
        AnalyticsEvent(event_name="public_novel.view", novel_id="alpha", session_id="anon-a", created_at=now),
        AnalyticsEvent(event_name="public_novel.view", novel_id="beta", user_id=1, created_at=now),
        AnalyticsEvent(event_name="public_novel.view", novel_id="beta", session_id="anon-b", created_at=now),
        AnalyticsEvent(event_name="public_chapter.view", novel_id="beta", user_id=2, created_at=now),
        AnalyticsEvent(event_name="public_novel.view", novel_id="alpha", user_id=9, created_at=now - timedelta(days=8)),
        AnalyticsEvent(
            event_name="public_novel.view", novel_id="alpha", user_id=10, created_at=now - timedelta(days=31)
        ),
        AnalyticsEvent(event_name="public_novel.view", novel_id="hidden", user_id=11, created_at=now),
    ]
    db_session.add_all(events)
    db_session.commit()

    catalog = Mock()
    catalog.get_public_novel_summary.side_effect = lambda slug, include_adult=False: (
        {"novel_id": slug, "slug": slug, "title": slug.title()},
        slug,
    )
    service = PublicRankingService(db_session=db_session, catalog_service=catalog)

    weekly = cast(dict[str, Any], service.list_rankings(period="weekly", limit=10))
    weekly_items = cast(list[dict[str, Any]], weekly["items"])
    assert weekly["available"] is True
    assert [item["novel"]["slug"] for item in weekly_items] == ["alpha", "beta"]
    assert [item["unique_views"] for item in weekly_items] == [3, 2]

    daily = cast(dict[str, Any], service.list_rankings(period="daily", limit=10))
    assert [item["unique_views"] for item in cast(list[dict[str, Any]], daily["items"])] == [3, 2]
    monthly = cast(dict[str, Any], service.list_rankings(period="monthly", limit=10))
    monthly_items = cast(list[dict[str, Any]], monthly["items"])
    assert monthly_items[0]["unique_views"] == 4
    assert monthly_items[1]["unique_views"] == 2


def test_rankings_report_disabled_and_empty_states(db_session, monkeypatch) -> None:
    catalog = Mock()
    service = PublicRankingService(db_session=db_session, catalog_service=catalog)
    monkeypatch.setattr(settings, "ANALYTICS_ENABLED", False)
    disabled = service.list_rankings(period="weekly", limit=5)
    assert disabled == {
        "period": "weekly",
        "metric": "unique_novel_views",
        "available": False,
        "reason": "analytics_disabled",
        "retention_days": settings.ANALYTICS_RETENTION_DAYS,
        "generated_at": disabled["generated_at"],
        "items": [],
    }
    monkeypatch.setattr(settings, "ANALYTICS_ENABLED", True)
    empty = service.list_rankings(period="monthly", limit=5)
    assert empty["available"] is False
    assert empty["reason"] == "no_data"
