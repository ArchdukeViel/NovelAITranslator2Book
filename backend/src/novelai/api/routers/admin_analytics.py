"""Admin analytics summary and ingestion endpoints (DEBT-009).

Owner-only summary endpoint with time-window aggregation. Public-safe batch
ingestion endpoint for approved frontend events with metadata sanitization.
"""

from __future__ import annotations

import hashlib
import hmac
from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, ConfigDict, field_validator
from sqlalchemy.orm import Session

from novelai.api.auth.roles import require_role
from novelai.api.auth.security import require_csrf_for_unsafe_methods
from novelai.api.auth.session import SessionUser, get_current_user
from novelai.api.routers.dependencies import _rate_limit, get_db_session
from novelai.config.settings import settings
from novelai.services.analytics_service import AnalyticsService, validate_event_name

router = APIRouter(
    prefix="/api/admin/analytics",
    tags=["admin-api"],
    dependencies=[Depends(require_csrf_for_unsafe_methods)],
)

# ---------------------------------------------------------------------------
# Internal ingestion router (no CSRF for public POST)
# ---------------------------------------------------------------------------
ingestion_router = APIRouter(prefix="/api/public/analytics", tags=["public"])


class AnalyticsEventPayload(BaseModel):
    """Single analytics event from frontend."""

    model_config = ConfigDict(extra="forbid")

    event_name: str
    event_timestamp: datetime | None = None
    novel_id: str | None = None
    chapter_id: str | None = None
    metadata: dict[str, Any] | None = None

    @field_validator("event_name")
    @classmethod
    def _validate_event_name(cls, v: str) -> str:
        if not validate_event_name(v):
            raise ValueError(f"Unknown analytics event: {v}")
        return v

    @field_validator("event_timestamp")
    @classmethod
    def _validate_event_timestamp(cls, value: datetime | None) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("event_timestamp must include a timezone")
        timestamp = value.astimezone(UTC)
        now = datetime.now(UTC)
        if timestamp > now + timedelta(minutes=5):
            raise ValueError("event_timestamp is too far in the future")
        if timestamp < now - timedelta(days=settings.ANALYTICS_RETENTION_DAYS):
            raise ValueError("event_timestamp is older than analytics retention")
        return timestamp


class AnalyticsBatchPayload(BaseModel):
    """Batch analytics events from frontend."""

    model_config = ConfigDict(extra="forbid")

    events: list[AnalyticsEventPayload]

    @field_validator("events")
    @classmethod
    def _limit_batch_size(cls, v: list[AnalyticsEventPayload]) -> list[AnalyticsEventPayload]:
        if len(v) > settings.ANALYTICS_INGEST_MAX_BATCH:
            raise ValueError(f"Batch exceeds maximum of {settings.ANALYTICS_INGEST_MAX_BATCH} events")
        return v


_SUMMARY_WINDOWS = "^(5m|15m|1h|24h|7d|30d)$"


def _get_service() -> AnalyticsService:
    return AnalyticsService()


# ---------------------------------------------------------------------------
# Summary endpoint (owner-only)
# ---------------------------------------------------------------------------


@router.get("/summary", dependencies=[Depends(require_role("owner"))])
def analytics_summary(
    window: str = Query("24h", pattern=_SUMMARY_WINDOWS),
    timezone: str = Query(
        "UTC",
        pattern="^(UTC|America/New_York|America/Chicago|America/Denver|America/Los_Angeles|Europe/London|Europe/Berlin|Europe/Moscow|Asia/Tokyo|Asia/Shanghai|Asia/Kolkata|Australia/Sydney|Pacific/Auckland)$",
    ),
    db_session: Session = Depends(get_db_session),
    svc: AnalyticsService = Depends(_get_service),
) -> dict[str, Any]:
    """Return aggregate analytics summary for the window (owner only)."""
    return svc.summary(db_session=db_session, window=window, timezone=timezone)


# ---------------------------------------------------------------------------
# Ingestion endpoint (public, rate-limited, fails closed when disabled)
# ---------------------------------------------------------------------------


@ingestion_router.post("/events")
async def ingest_analytics_events(
    body: AnalyticsBatchPayload,
    request: Request,
    db_session: Session = Depends(get_db_session),
    svc: AnalyticsService = Depends(_get_service),
    user: SessionUser = Depends(get_current_user),
) -> dict[str, Any]:
    """Record analytics events from frontend.

    Returns 503 when analytics are disabled. Rate-limited per client.
    Invalid events in the batch are dropped silently.
    """
    if user.is_authenticated:
        _rate_limit(request, "analytics", client_id=f"user:{user.user_id}")
    else:
        _rate_limit(request, "analytics", key_transform=_anonymous_analytics_limiter_key)

    if len(await request.body()) > settings.ANALYTICS_INGEST_MAX_BODY_BYTES:
        raise HTTPException(status_code=413, detail="Analytics request body too large")

    if not settings.ANALYTICS_ENABLED or not settings.ANALYTICS_PUBLIC_INGESTION_ENABLED:
        raise HTTPException(status_code=503, detail="Analytics are disabled")

    if not body.events:
        return {"recorded": 0, "dropped": 0}

    recorded = 0
    dropped = 0
    for event in body.events:
        try:
            svc.record_event(
                db_session,
                event.event_name,
                user_id=user.user_id,
                novel_id=event.novel_id,
                chapter_id=event.chapter_id,
                metadata=event.metadata,
                created_at=event.event_timestamp,
            )
            recorded += 1
        except Exception:
            dropped += 1

    return {"recorded": recorded, "dropped": dropped}


def _anonymous_analytics_limiter_key(client_id: str) -> str:
    """Return non-reversible limiter identity; raw client IP never reaches limiter storage."""
    digest = hmac.new(
        settings.SESSION_SECRET_KEY.encode("utf-8"), client_id.encode("utf-8"), hashlib.sha256
    ).hexdigest()
    return f"anonymous:{digest}"
