"""Reading service — progress, history."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy.orm import Session

from novelai.db.models.chapter import Chapter
from novelai.db.models.novel import Novel
from novelai.db.models.users import ReadingHistory, ReadingProgress


class ReadingService:
    """Business logic for reading progress and history."""

    def __init__(self, *, db_session: Session) -> None:
        self.db_session = db_session

    def _get_novel(self, slug: str) -> Novel:
        novel = self.db_session.query(Novel).filter_by(slug=slug).one_or_none()
        if novel is None:
            raise ValueError("Novel not found")
        return novel

    def _get_chapter(self, chapter_id: str | None, novel_id: int) -> int | None:
        if chapter_id is None:
            return None
        try:
            chapter_db_id = int(chapter_id)
        except ValueError as exc:
            raise ValueError("Chapter not found") from exc
        chapter = (
            self.db_session.query(Chapter)
            .filter_by(id=chapter_db_id, novel_id=novel_id)
            .one_or_none()
        )
        if chapter is None:
            raise ValueError("Chapter not found")
        return chapter.id

    def _utcnow(self) -> datetime:
        return datetime.now(UTC)

    def _progress_response(
        self, slug: str, rp: ReadingProgress | None, chapter_number: int | None
    ) -> dict[str, Any]:
        if rp is None:
            return {
                "slug": slug,
                "progress_percent": 0.0,
                "chapter_id": None,
                "chapter_number": None,
                "updated_at": self._utcnow(),
            }
        return {
            "slug": slug,
            "progress_percent": rp.progress_percent,
            "chapter_id": str(rp.chapter_id) if rp.chapter_id is not None else None,
            "chapter_number": chapter_number,
            "updated_at": rp.updated_at,
        }

    def get_progress(self, user_id: int, slug: str) -> dict[str, Any]:
        novel = self._get_novel(slug)
        rp = (
            self.db_session.query(ReadingProgress)
            .filter_by(user_id=user_id, novel_id=novel.id)
            .one_or_none()
        )
        chapter_number: int | None = None
        if rp is not None and rp.chapter_id is not None:
            ch = (
                self.db_session.query(Chapter.chapter_number)
                .filter_by(id=rp.chapter_id)
                .one_or_none()
            )
            if ch:
                chapter_number = ch[0]
        return self._progress_response(slug, rp, chapter_number)

    def update_progress(
        self, user_id: int, slug: str, chapter_id: str | None, progress_percent: float
    ) -> dict[str, Any]:
        novel = self._get_novel(slug)
        chapter_db_id = self._get_chapter(chapter_id, novel.id)
        rp = (
            self.db_session.query(ReadingProgress)
            .filter_by(user_id=user_id, novel_id=novel.id)
            .one_or_none()
        )
        if rp is None:
            rp = ReadingProgress(user_id=user_id, novel_id=novel.id)
            self.db_session.add(rp)
        rp.progress_percent = progress_percent
        rp.chapter_id = chapter_db_id
        rp.updated_at = self._utcnow()
        self.db_session.flush()
        chapter_number: int | None = None
        if rp.chapter_id is not None:
            ch = (
                self.db_session.query(Chapter.chapter_number)
                .filter_by(id=rp.chapter_id)
                .one_or_none()
            )
            if ch:
                chapter_number = ch[0]
        return self._progress_response(slug, rp, chapter_number)

    def record_history(
        self, user_id: int, slug: str, chapter_id: str | None
    ) -> dict[str, Any]:
        novel = self._get_novel(slug)
        chapter_db_id = self._get_chapter(chapter_id, novel.id)
        entry = ReadingHistory(user_id=user_id, novel_id=novel.id, chapter_id=chapter_db_id)
        self.db_session.add(entry)
        self.db_session.flush()
        chapter_number: int | None = None
        if entry.chapter_id is not None:
            ch = (
                self.db_session.query(Chapter.chapter_number)
                .filter_by(id=entry.chapter_id)
                .one_or_none()
            )
            if ch:
                chapter_number = ch[0]
        return {
            "id": entry.id,
            "slug": slug,
            "chapter_id": str(entry.chapter_id) if entry.chapter_id is not None else None,
            "chapter_number": chapter_number,
            "read_at": entry.read_at,
        }

    def list_history(self, user_id: int, limit: int = 50) -> list[dict[str, Any]]:
        results = (
            self.db_session.query(ReadingHistory, Chapter.chapter_number)
            .outerjoin(Chapter, ReadingHistory.chapter_id == Chapter.id)
            .filter(ReadingHistory.user_id == user_id)
            .order_by(ReadingHistory.read_at.desc())
            .limit(limit)
            .all()
        )
        return [
            {
                "id": entry.id,
                "slug": self._novel_slug(entry.novel_id),
                "chapter_id": str(entry.chapter_id) if entry.chapter_id is not None else None,
                "chapter_number": chapter_number,
                "read_at": entry.read_at,
            }
            for entry, chapter_number in results
        ]

    def _novel_slug(self, novel_id: int | None) -> str | None:
        if novel_id is None:
            return None
        novel = self.db_session.query(Novel).filter_by(id=novel_id).one_or_none()
        return novel.slug if novel else None
