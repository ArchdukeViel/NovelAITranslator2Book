"""Session-scoped in-app notification endpoints."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from novelai.api.auth.roles import require_role
from novelai.api.auth.security import require_csrf_token
from novelai.api.auth.session import SessionUser
from novelai.api.routers.dependencies import get_db_session, get_notification_persistence_service
from novelai.services.analytics_service import AnalyticsService
from novelai.services.notification_service import NotificationPersistenceService

router = APIRouter(prefix="/api/user/notifications", tags=["notifications"])

EventType = Literal["translation.completed", "translation.failed", "translation.requires_review"]
Status = Literal["unread", "read", "archived"]
Channel = Literal["in_app", "email"]


class NotificationResponse(BaseModel):
    id: int
    event_type: EventType
    title: str
    body: str
    severity: Literal["info", "success", "warning", "error"]
    status: Status
    action_url: str | None
    created_at: datetime
    read_at: datetime | None


class NotificationListResponse(BaseModel):
    items: list[NotificationResponse]
    page: int
    page_size: int
    total: int


class UnreadCountResponse(BaseModel):
    unread_count: int


class UpdatedCountResponse(BaseModel):
    updated: int


class PreferenceResponse(BaseModel):
    event_type: EventType
    channel: Channel
    enabled: bool


class PreferenceUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event_type: EventType
    channel: Channel
    enabled: bool


def _user_id(user: SessionUser) -> int:
    assert user.user_id is not None, "Authenticated route requires user_id"
    return user.user_id


@router.get("", response_model=NotificationListResponse)
def list_notifications(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
    status: Status | None = None,
    event_type: EventType | None = None,
    channel: Channel | None = None,
    user: SessionUser = Depends(require_role("user")),
    service: NotificationPersistenceService = Depends(get_notification_persistence_service),
) -> NotificationListResponse:
    if channel == "email":  # Email has delivery records, not recipient-visible notification rows.
        return NotificationListResponse(items=[], page=page, page_size=page_size, total=0)
    return NotificationListResponse.model_validate(
        service.list(
            requesting_user_id=_user_id(user), page=page, page_size=page_size, status=status, event_type=event_type
        )
    )


@router.get("/unread-count", response_model=UnreadCountResponse)
def unread_count(
    user: SessionUser = Depends(require_role("user")),
    service: NotificationPersistenceService = Depends(get_notification_persistence_service),
) -> UnreadCountResponse:
    return UnreadCountResponse(unread_count=service.unread_count(requesting_user_id=_user_id(user)))


@router.post("/read-all", response_model=UpdatedCountResponse, dependencies=[Depends(require_csrf_token)])
def read_all_notifications(
    user: SessionUser = Depends(require_role("user")),
    service: NotificationPersistenceService = Depends(get_notification_persistence_service),
) -> UpdatedCountResponse:
    return UpdatedCountResponse(updated=service.mark_all_read(requesting_user_id=_user_id(user)))


@router.post("/{notification_id}/archive", status_code=204, dependencies=[Depends(require_csrf_token)])
def archive_notification(
    notification_id: int,
    user: SessionUser = Depends(require_role("user")),
    service: NotificationPersistenceService = Depends(get_notification_persistence_service),
) -> None:
    if not service.archive(requesting_user_id=_user_id(user), notification_id=notification_id):
        raise HTTPException(status_code=404, detail="Notification not found.")


@router.get("/preferences", response_model=list[PreferenceResponse])
def get_preferences(
    user: SessionUser = Depends(require_role("user")),
    service: NotificationPersistenceService = Depends(get_notification_persistence_service),
) -> list[PreferenceResponse]:
    return [
        PreferenceResponse.model_validate(item) for item in service.get_preferences(requesting_user_id=_user_id(user))
    ]


@router.put("/preferences", response_model=PreferenceResponse, dependencies=[Depends(require_csrf_token)])
def update_preferences(
    payload: PreferenceUpdate,
    user: SessionUser = Depends(require_role("user")),
    service: NotificationPersistenceService = Depends(get_notification_persistence_service),
) -> PreferenceResponse:
    return PreferenceResponse.model_validate(
        service.update_preference(requesting_user_id=_user_id(user), **payload.model_dump())
    )


@router.post("/{notification_id}/read", status_code=204, dependencies=[Depends(require_csrf_token)])
def read_notification(
    notification_id: int,
    user: SessionUser = Depends(require_role("user")),
    service: NotificationPersistenceService = Depends(get_notification_persistence_service),
    db_session: Session = Depends(get_db_session),
) -> None:
    notification = service.get(requesting_user_id=_user_id(user), notification_id=notification_id)
    if notification is None or not service.mark_read(
        requesting_user_id=_user_id(user), notification_id=notification_id
    ):
        raise HTTPException(status_code=404, detail="Notification not found.")
    AnalyticsService().record_event(
        db_session,
        "notification.opened",
        user_id=_user_id(user),
        metadata={"event_type": notification["event_type"], "severity": notification["severity"], "channel": "in_app"},
    )
