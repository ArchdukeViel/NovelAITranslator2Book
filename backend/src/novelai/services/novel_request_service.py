"""Novel request moderation — list, get, update status.

Separated from the HTTP adapter to keep moderation logic testable
without a running server.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy.orm import Session

from novelai.core.platform import NovelRequestStatus
from novelai.db.models.chapter import Chapter as ChapterModel
from novelai.db.models.novel import Novel
from novelai.db.models.users import NovelRequest


class NovelRequestService:
    """Business logic for novel request moderation."""

    def __init__(self, *, db_session: Session) -> None:
        self.db_session = db_session

    # -- constants --------------------------------------------------------------

    _VALID_STATUSES = {item.value for item in NovelRequestStatus}
    _RESOLVED_STATUSES = {
        NovelRequestStatus.APPROVED.value,
        NovelRequestStatus.REJECTED.value,
        NovelRequestStatus.RELEASED.value,
    }

    # -- helpers ----------------------------------------------------------------

    @staticmethod
    def _utcnow() -> datetime:
        return datetime.now(UTC)

    def _normalize_status(self, status: str | None) -> str | None:
        if status is None:
            return None
        normalized = status.strip().lower()
        if normalized not in self._VALID_STATUSES:
            raise ValueError("Invalid request status")
        return normalized

    @staticmethod
    def _request_pk(request_id: str) -> int:
        try:
            return int(request_id)
        except ValueError as exc:
            raise ValueError("Novel request not found") from exc

    def _novel_slug(self, novel_id: int | None) -> str | None:
        if novel_id is None:
            return None
        novel = self.db_session.query(Novel).filter_by(id=novel_id).one_or_none()
        return novel.slug if novel else None

    def _get_novel_by_id(self, novel_id: int) -> Novel:
        novel = self.db_session.get(Novel, novel_id)
        if novel is None:
            raise ValueError("Approved novel not found")
        return novel

    def _request_response(self, item: NovelRequest) -> dict[str, Any]:
        request_id = str(item.id)
        return {
            "id": request_id,
            "request_id": request_id,
            "db_id": item.id,
            "user_id": item.user_id,
            "request_type": item.request_type,
            "status": item.status,
            "source_url": item.source_url,
            "slug": self._novel_slug(item.novel_id),
            "chapter_id": None,
            "created_at": item.created_at,
            "updated_at": item.updated_at,
            "resolved_at": item.resolved_at,
            "rejection_reason": item.rejection_reason,
            "approved_novel_id": item.approved_novel_id,
            "approved_slug": self._novel_slug(item.approved_novel_id),
        }

    def _get_request(self, request_id: str) -> NovelRequest:
        item = self.db_session.get(NovelRequest, self._request_pk(request_id))
        if item is None:
            raise ValueError("Novel request not found")
        return item

    # -- public API -------------------------------------------------------------

    def list_requests(self, *, status: str | None = None, limit: int = 50) -> list[dict[str, Any]]:
        normalized_status = self._normalize_status(status)
        query = self.db_session.query(NovelRequest)
        if normalized_status is not None:
            query = query.filter(NovelRequest.status == normalized_status)
        items = query.order_by(NovelRequest.created_at.desc()).limit(limit).all()
        return [self._request_response(item) for item in items]

    def get_request(self, request_id: str) -> dict[str, Any]:
        return self._request_response(self._get_request(request_id))

    def update_request_status(
        self,
        request_id: str,
        status: str,
        rejection_reason: str | None = None,
        approved_novel_id: int | None = None,
    ) -> dict[str, Any]:
        normalized_status = status.strip().lower()
        item = self._get_request(request_id)
        item.status = status
        if status == NovelRequestStatus.PENDING.value:
            item.resolved_at = None
            item.rejection_reason = None
            item.approved_novel_id = None
        elif status in self._RESOLVED_STATUSES:
            item.resolved_at = item.resolved_at or self._utcnow()
            if normalized_status == NovelRequestStatus.REJECTED.value:
                item.rejection_reason = rejection_reason.strip() if rejection_reason else None
                item.approved_novel_id = None
            elif normalized_status in (
                NovelRequestStatus.APPROVED.value,
                NovelRequestStatus.RELEASED.value,
            ):
                item.rejection_reason = None
                if approved_novel_id is not None:
                    item.approved_novel_id = self._get_novel_by_id(approved_novel_id).id
        item.updated_at = self._utcnow()
        self.db_session.flush()
        return self._request_response(item)

    # -- user-facing -----------------------------------------------------------

    def create_user_request(
        self,
        user_id: int,
        request_type: str,
        source_url: str | None = None,
        slug: str | None = None,
        chapter_id: str | None = None,
    ) -> dict[str, Any]:
        if request_type not in {"novel", "chapter"}:
            raise ValueError("request_type must be 'novel' or 'chapter'")
        if request_type == "novel" and source_url is None:
            raise ValueError("source_url is required for novel requests")
        if request_type == "chapter" and slug is None:
            raise ValueError("slug is required for chapter requests")

        novel_id = None
        if slug is not None:
            novel = self.db_session.query(Novel).filter_by(slug=slug).one_or_none()
            if novel is None:
                raise ValueError("Novel not found")
            novel_id = novel.id

        # Validate chapter_id belongs to the novel
        if chapter_id is not None:
            try:
                _cid = int(chapter_id)
            except ValueError:
                raise ValueError("Chapter not found") from None
            ch = self.db_session.query(ChapterModel).filter_by(id=_cid, novel_id=novel_id).one_or_none()
            if ch is None:
                raise ValueError("Chapter not found")

        existing = self.db_session.query(NovelRequest).filter_by(
            user_id=user_id,
            request_type=request_type,
            novel_id=novel_id,
            source_url=source_url,
            status="pending",
        ).one_or_none()
        if existing is not None:
            return self._request_response(existing)

        req = NovelRequest(
            user_id=user_id,
            request_type=request_type,
            novel_id=novel_id,
            source_url=source_url,
            status="pending",
        )
        self.db_session.add(req)
        self.db_session.flush()
        return self._request_response(req)

    def list_user_requests(self, user_id: int, limit: int = 50) -> list[dict[str, Any]]:
        reqs = (
            self.db_session.query(NovelRequest)
            .filter_by(user_id=user_id)
            .order_by(NovelRequest.created_at.desc())
            .limit(limit)
            .all()
        )
        return [self._request_response(req) for req in reqs]
