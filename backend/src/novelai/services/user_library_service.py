"""User library service — add/remove/list library items."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy.orm import Session

from novelai.db.models.novel import Novel
from novelai.db.models.users import LibraryItem


class UserLibraryService:
    """Business logic for user library management."""

    def __init__(self, *, db_session: Session) -> None:
        self.db_session = db_session

    def _get_novel(self, slug: str) -> Novel:
        novel = self.db_session.query(Novel).filter_by(slug=slug).one_or_none()
        if novel is None:
            raise ValueError("Novel not found")
        return novel

    def _library_response(self, item: LibraryItem, slug: str) -> dict[str, Any]:
        return {"slug": slug, "status": item.status, "added_at": item.added_at}

    def add_to_library(self, user_id: int, slug: str) -> dict[str, Any]:
        novel = self._get_novel(slug)
        existing = (
            self.db_session.query(LibraryItem)
            .filter_by(user_id=user_id, novel_id=novel.id)
            .one_or_none()
        )
        if existing:
            return self._library_response(existing, slug)
        item = LibraryItem(user_id=user_id, novel_id=novel.id)
        self.db_session.add(item)
        self.db_session.flush()
        return self._library_response(item, slug)

    def list_library(self, user_id: int) -> list[dict[str, Any]]:
        items = self.db_session.query(LibraryItem).filter_by(user_id=user_id).all()
        result: list[dict[str, Any]] = []
        for item in items:
            novel = self.db_session.query(Novel).filter_by(id=item.novel_id).one_or_none()
            slug = novel.slug if novel else str(item.novel_id)
            result.append(self._library_response(item, slug))
        return result

    def get_library_item(self, user_id: int, slug: str) -> dict[str, Any]:
        novel = self._get_novel(slug)
        item = (
            self.db_session.query(LibraryItem)
            .filter_by(user_id=user_id, novel_id=novel.id)
            .one_or_none()
        )
        if item is None:
            raise ValueError("Library item not found")
        return self._library_response(item, slug)

    def remove_from_library(self, user_id: int, slug: str) -> None:
        novel = self._get_novel(slug)
        item = (
            self.db_session.query(LibraryItem)
            .filter_by(user_id=user_id, novel_id=novel.id)
            .one_or_none()
        )
        if item:
            self.db_session.delete(item)