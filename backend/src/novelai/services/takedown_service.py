"""Takedown-request service for DMCA / copyright intake and review."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from urllib.parse import unquote, urlsplit

from sqlalchemy import asc, desc
from sqlalchemy.orm import Session

from novelai.db.models.takedown import TakedownRequest

logger = logging.getLogger(__name__)

VALID_STATUSES = frozenset({"pending", "reviewing", "approved", "rejected", "expired"})
DEFAULT_PAGE_SIZE = 20


class TakedownService:
    """Bundles DMCA intake, admin review, and tombstone checks."""

    def __init__(self, db: Session) -> None:
        self.db = db

    # ------------------------------------------------------------------
    # Public intake
    # ------------------------------------------------------------------

    def submit(
        self,
        complainant_name: str,
        complainant_email: str,
        infringing_url: str,
        description: str,
        signature: str,
        *,
        complainant_phone: str | None = None,
        original_work_url: str | None = None,
        original_work_description: str | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> TakedownRequest:
        req = TakedownRequest(
            complainant_name=complainant_name,
            complainant_email=complainant_email,
            complainant_phone=complainant_phone,
            infringing_url=infringing_url,
            description=description,
            original_work_url=original_work_url,
            original_work_description=original_work_description,
            signature=signature,
            ip_address=ip_address,
            user_agent=user_agent,
            status="pending",
        )
        self.db.add(req)
        self.db.flush()
        logger.info("TakedownRequest #%s submitted", req.id)
        return req

    # ------------------------------------------------------------------
    # Admin review
    # ------------------------------------------------------------------

    def list_requests(
        self,
        status: str | None = None,
        page: int = 1,
        page_size: int = DEFAULT_PAGE_SIZE,
        sort_by: str = "created_at",
        order: str = "desc",
    ) -> tuple[list[TakedownRequest], int]:
        query = self.db.query(TakedownRequest)
        if status and status in VALID_STATUSES:
            query = query.filter(TakedownRequest.status == status)

        total = query.count()
        order_col = getattr(TakedownRequest, sort_by, TakedownRequest.created_at)
        order_fn = desc if order == "desc" else asc
        rows = query.order_by(order_fn(order_col)).offset((page - 1) * page_size).limit(page_size).all()
        return list(rows), total

    def get_request(self, request_id: int) -> TakedownRequest | None:
        return self.db.query(TakedownRequest).filter(TakedownRequest.id == request_id).first()

    def review(
        self,
        request_id: int,
        status: str,
        reviewer_notes: str | None = None,
        reviewed_by_user_id: int | None = None,
    ) -> TakedownRequest | None:
        if status not in VALID_STATUSES:
            raise ValueError(f"Invalid status: {status}. Valid: {sorted(VALID_STATUSES)}")
        req = self.get_request(request_id)
        if not req:
            return None
        req.status = status
        req.reviewer_notes = reviewer_notes
        req.reviewed_at = datetime.now(UTC)
        req.reviewed_by_user_id = reviewed_by_user_id
        self.db.flush()
        from novelai.services.public_projection_cache import invalidate_public_projection_cache

        invalidate_public_projection_cache()
        logger.info("TakedownRequest #%s → %s", request_id, status)
        return req

    # ------------------------------------------------------------------
    # HTTP 451 tombstone check
    # ------------------------------------------------------------------

    def has_active_takedown(self, url: str) -> bool:
        """Return True if *url* is under an active (approved) takedown."""
        return (
            self.db.query(TakedownRequest.id)
            .filter(
                TakedownRequest.infringing_url == url,
                TakedownRequest.status == "approved",
            )
            .first()
            is not None
        )

    def has_active_takedown_for_slug(self, slug: str) -> bool:
        """Return whether an approved notice targets *slug* as an exact path segment."""
        return slug.casefold() in self.active_takedown_slugs([slug])

    def active_takedown_slugs(self, slugs: list[str]) -> set[str]:
        """Return requested slugs targeted by approved notices using one query."""
        normalized = {unquote(slug).strip("/").casefold() for slug in slugs if slug.strip("/")}
        if not normalized:
            return set()
        urls = self.db.query(TakedownRequest.infringing_url).filter(TakedownRequest.status == "approved").all()
        targeted = {
            unquote(segment).casefold() for (url,) in urls for segment in urlsplit(url).path.split("/") if segment
        }
        return normalized & targeted
