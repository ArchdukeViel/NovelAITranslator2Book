"""Review service — upsert, get, list reviews."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy.orm import Session

from novelai.db.models.novel import Novel
from novelai.db.models.users import Review


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
            "slug": slug,
            "rating": review.rating,
            "review_text": review.body,
            "created_at": review.created_at,
            "updated_at": review.updated_at,
        }

    def upsert_review(
        self, user_id: int, slug: str, rating: int, review_text: str | None
    ) -> dict[str, Any]:
        novel = self._get_novel(slug)
        review = (
            self.db_session.query(Review)
            .filter_by(user_id=user_id, novel_id=novel.id)
            .one_or_none()
        )
        if review is None:
            review = Review(user_id=user_id, novel_id=novel.id)
            self.db_session.add(review)
        review.rating = rating
        review.body = review_text
        review.updated_at = self._utcnow()
        self.db_session.flush()
        return self._review_response(review, slug)

    def get_review(self, user_id: int, slug: str) -> dict[str, Any] | None:
        novel = self._get_novel(slug)
        review = (
            self.db_session.query(Review)
            .filter_by(user_id=user_id, novel_id=novel.id)
            .one_or_none()
        )
        if review is None:
            return None
        return self._review_response(review, slug)

    def list_reviews(self, slug: str) -> list[dict[str, Any]]:
        novel = self._get_novel(slug)
        reviews = self.db_session.query(Review).filter_by(novel_id=novel.id).all()
        return [self._review_response(review, slug) for review in reviews]