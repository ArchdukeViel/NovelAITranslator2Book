"""Review service — upsert, get, list, moderate reviews."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import asc, desc
from sqlalchemy.orm import Session

from novelai.db.models.novel import Novel
from novelai.db.models.users import Review

REVIEW_MODERATION_STATUSES = frozenset({"published", "rejected"})
DEFAULT_PAGE_SIZE = 20


class ReviewService:
    """Business logic for reviews."""

    def __init__(self, *, db_session: Session) -> None:
        self.db_session = db_session

    def _get_novel(self, slug: str) -> Novel:
        novel = self.db_session.query(Novel).filter_by(slug=slug).one_or_none()
        if novel is None:
            raise ValueError("Novel not found")
        return novel

    def _utcnow(self) -> datetime:
        return datetime.now(UTC)

    def _review_response(self, review: Review, slug: str) -> dict[str, Any]:
        return {
            "id": review.id,
            "slug": slug,
            "rating": review.rating,
            "body": review.body,
            "status": review.status,
            "created_at": review.created_at,
            "updated_at": review.updated_at,
        }

    # ------------------------------------------------------------------
    # User-facing CRUD
    # ------------------------------------------------------------------

    def upsert_review(self, user_id: int, slug: str, rating: int, review_text: str | None) -> dict[str, Any]:
        novel = self._get_novel(slug)
        review = self.db_session.query(Review).filter_by(user_id=user_id, novel_id=novel.id).one_or_none()
        if review is None:
            review = Review(user_id=user_id, novel_id=novel.id)
            self.db_session.add(review)
        review.rating = rating
        review.body = review_text
        # Content change resets moderation state.
        review.status = "pending"
        review.updated_at = self._utcnow()
        review.moderated_at = None
        review.reviewer_notes = None
        self.db_session.flush()
        return self._review_response(review, slug)

    def get_review(self, user_id: int, slug: str) -> dict[str, Any] | None:
        novel = self._get_novel(slug)
        review = self.db_session.query(Review).filter_by(user_id=user_id, novel_id=novel.id).one_or_none()
        if review is None:
            return None
        return self._review_response(review, slug)

    def list_reviews(self, slug: str) -> list[dict[str, Any]]:
        novel = self._get_novel(slug)
        reviews = self.db_session.query(Review).filter_by(novel_id=novel.id).all()
        return [self._review_response(review, slug) for review in reviews]

    def list_user_reviews(self, user_id: int, limit: int = 100) -> list[dict[str, Any]]:
        """List reviews authored by one user, newest first, with novel metadata."""
        rows = (
            self.db_session.query(Review, Novel.slug, Novel.title)
            .join(Novel, Review.novel_id == Novel.id)
            .filter(Review.user_id == user_id)
            .order_by(Review.created_at.desc())
            .limit(limit)
            .all()
        )
        return [
            {
                "slug": slug,
                "title": title,
                "rating": review.rating,
                "body": review.body,
                "status": review.status,
                "created_at": review.created_at,
                "updated_at": review.updated_at,
            }
            for review, slug, title in rows
        ]

    def delete_review(self, user_id: int, slug: str) -> int | None:
        """Delete user review. Returns review id if deleted, else None."""
        novel = self._get_novel(slug)
        review = self.db_session.query(Review).filter_by(user_id=user_id, novel_id=novel.id).one_or_none()
        if review is not None:
            review_id = review.id
            self.db_session.delete(review)
            return review_id
        return None

    # ------------------------------------------------------------------
    # Public listing (published only, cursor pagination)
    # ------------------------------------------------------------------

    def list_published_reviews(
        self, slug: str, limit: int = 20, cursor: str | None = None
    ) -> tuple[list[dict[str, Any]], str | None]:
        """Return published reviews for a novel with keyset pagination.

        Cursor format: ``ISO-timestamp|review-id``.
        """
        novel = self._get_novel(slug)
        query = (
            self.db_session.query(Review)
            .filter(Review.novel_id == novel.id, Review.status == "published")
            .order_by(Review.created_at.desc(), Review.id.desc())
        )

        if cursor:
            cursor_ts, cursor_id = _parse_cursor(cursor)
            if cursor_ts is not None and cursor_id is not None:
                query = query.filter(
                    (Review.created_at < cursor_ts) | ((Review.created_at == cursor_ts) & (Review.id < cursor_id))
                )

        rows = query.limit(limit + 1).all()
        has_next = len(rows) > limit
        items = rows[:limit]

        next_cursor: str | None = None
        if has_next and items:
            last = items[-1]
            next_cursor = f"{last.created_at.isoformat()}|{last.id}"

        return [
            {
                "id": r.id,
                "rating": r.rating,
                "body": r.body,
                "created_at": r.created_at,
            }
            for r in items
        ], next_cursor

    # ------------------------------------------------------------------
    # Admin listing + moderation
    # ------------------------------------------------------------------

    def list_all_reviews(
        self,
        status: str | None = None,
        page: int = 1,
        page_size: int = DEFAULT_PAGE_SIZE,
        sort_by: str = "created_at",
        order: str = "desc",
    ) -> tuple[list[dict[str, Any]], int]:
        """Admin list: all reviews with novel metadata, page/total."""
        query = self.db_session.query(Review, Novel.slug, Novel.title).join(Novel, Review.novel_id == Novel.id)
        if status and status in {"pending", "published", "rejected"}:
            query = query.filter(Review.status == status)

        total = query.count()
        order_col = getattr(Review, sort_by, Review.created_at)
        order_fn = desc if order == "desc" else asc
        rows = query.order_by(order_fn(order_col)).offset((page - 1) * page_size).limit(page_size).all()
        items = [
            {
                "id": review.id,
                "user_id": review.user_id,
                "slug": slug,
                "title": title,
                "rating": review.rating,
                "body": review.body,
                "status": review.status,
                "created_at": review.created_at,
                "updated_at": review.updated_at,
                "moderated_at": review.moderated_at,
                "reviewer_notes": review.reviewer_notes,
                "reviewed_by_user_id": review.reviewed_by_user_id,
            }
            for review, slug, title in rows
        ]
        return items, total

    def moderate_review(
        self,
        review_id: int,
        status: str,
        reviewer_notes: str | None = None,
        reviewed_by_user_id: int | None = None,
    ) -> Review | None:
        """Set review status to published or rejected."""
        if status not in REVIEW_MODERATION_STATUSES:
            raise ValueError(f"Invalid status: {status}. Valid: {sorted(REVIEW_MODERATION_STATUSES)}")
        review = self.db_session.query(Review).filter(Review.id == review_id).first()
        if not review:
            return None
        review.status = status
        review.moderated_at = self._utcnow()
        review.reviewer_notes = reviewer_notes
        review.reviewed_by_user_id = reviewed_by_user_id
        self.db_session.flush()
        return review


def _parse_cursor(cursor: str) -> tuple[datetime | None, int | None]:
    """Parse ``ISO-timestamp|id`` cursor. Returns (None, None) on garbage."""
    try:
        ts_str, id_str = cursor.rsplit("|", 1)
        return datetime.fromisoformat(ts_str), int(id_str)
    except (ValueError, TypeError):
        return None, None
