"""Catalog service — storage-key bridge.

Writes chapter content to file/object storage and persists the storage key
and checksum in the database (architecture.md §21).

Storage-path knowledge stays inside the storage boundary (storage/*).
This service bridges the file-backed StorageService with the DB models so
the two can run in parallel during the file→DB transition.
"""

from __future__ import annotations

import hashlib

from sqlalchemy.orm import Session

from novelai.db.models.chapter import Chapter
from novelai.db.models.novel import Novel
from novelai.services.taxonomy_persistence import persist_taxonomy_assignments
from novelai.storage.service import StorageService


def _sha256(text: str) -> str:
    """Return a hex SHA-256 digest for a text string."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class CatalogService:
    """Bridge between file-backed StorageService and the DB catalog.

    Responsibilities:
    - Persist raw/translated chapter text via StorageService (file/object storage).
    - Write the resulting storage key + checksum into the Chapter DB row.
    - Keep all path/key construction inside StorageService; this layer only
      stores the returned key string and a content checksum.

    Args:
        storage: The file-backed StorageService instance.
        session: An active SQLAlchemy session (caller owns lifecycle).
    """

    def __init__(self, storage: StorageService, session: Session) -> None:
        self._storage = storage
        self._session = session

    # ------------------------------------------------------------------
    # Novel catalog helpers
    # ------------------------------------------------------------------

    def get_or_create_novel(self, novel_id: str, metadata: dict) -> Novel:
        """Return the DB Novel row, creating it if it does not exist.

        Args:
            novel_id: The canonical novel_id (used as slug).
            metadata: Novel metadata dict from StorageService/source adapter.

        Returns:
            The Novel ORM instance (added to session, not yet committed).
        """
        novel = self._session.query(Novel).filter_by(slug=novel_id).one_or_none()
        if novel is None:
            novel = Novel(
                slug=novel_id,
                title=metadata.get("title") or novel_id,
                original_title=metadata.get("original_title"),
                author=metadata.get("author"),
                source_site=metadata.get("source_key"),
                source_url=metadata.get("source_url"),
                language=metadata.get("language", "ja"),
                status=metadata.get("status", "unknown"),
                synopsis=metadata.get("description"),
            )
            self._session.add(novel)
            self._session.flush()  # Ensure novel.id is available

        # Persist taxonomy assignments from scraped metadata
        source_key = metadata.get("source_key") or metadata.get("source")
        persist_taxonomy_assignments(
            self._session,
            novel.id,
            metadata,
            source_key=str(source_key) if source_key else None,
        )
        return novel

    # ------------------------------------------------------------------
    # Chapter storage-key bridge
    # ------------------------------------------------------------------

    def save_raw_chapter(
        self,
        novel_id: str,
        chapter_id: str,
        content: str,
        *,
        title: str | None = None,
        source_key: str | None = None,
        chapter_number: int = 0,
    ) -> Chapter:
        """Save raw chapter text to file storage; persist key+checksum in DB.

        Args:
            novel_id: Parent novel identifier.
            chapter_id: Chapter identifier (used as storage key suffix).
            content: Raw chapter text.
            title: Optional chapter title.
            source_key: Optional source site key.
            chapter_number: Chapter number for ordering.

        Returns:
            The Chapter ORM instance (added to session, not yet committed).
        """
        self._storage.save_chapter(
            novel_id, chapter_id, content, title=title, source_key=source_key
        )
        storage_key = f"{novel_id}/{chapter_id}/raw"
        checksum = _sha256(content)

        novel = self._session.query(Novel).filter_by(slug=novel_id).one_or_none()
        novel_db_id = novel.id if novel else None

        chapter = self._get_or_create_chapter(
            novel_db_id=novel_db_id,
            chapter_id=chapter_id,
            chapter_number=chapter_number,
            title=title,
        )
        chapter.raw_storage_key = f"{storage_key}:{checksum[:8]}"
        chapter.raw_status = "fetched"
        self._session.add(chapter)
        return chapter

    def save_translated_chapter(
        self,
        novel_id: str,
        chapter_id: str,
        content: str,
        *,
        provider: str | None = None,
    ) -> Chapter:
        """Save translated chapter text to file storage; persist key+checksum in DB.

        Args:
            novel_id: Parent novel identifier.
            chapter_id: Chapter identifier.
            content: Translated chapter text.
            provider: Optional provider key for traceability.

        Returns:
            The Chapter ORM instance (updated in session, not yet committed).
        """
        self._storage.save_translated_chapter(novel_id, chapter_id, content, provider=provider)
        storage_key = f"{novel_id}/{chapter_id}/translated"
        checksum = _sha256(content)

        novel = self._session.query(Novel).filter_by(slug=novel_id).one_or_none()
        novel_db_id = novel.id if novel else None

        chapter = self._get_or_create_chapter(
            novel_db_id=novel_db_id,
            chapter_id=chapter_id,
            chapter_number=0,
        )
        chapter.translated_storage_key = f"{storage_key}:{checksum[:8]}"
        chapter.translation_status = "translated"
        self._session.add(chapter)
        return chapter

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_or_create_chapter(
        self,
        novel_db_id: int | None,
        chapter_id: str,
        chapter_number: int,
        title: str | None = None,
    ) -> Chapter:
        """Return existing Chapter DB row or create a new one."""
        chapter = None
        if novel_db_id is not None:
            chapter = (
                self._session.query(Chapter)
                .filter_by(novel_id=novel_db_id)
                .filter(Chapter.title == (title or chapter_id))
                .one_or_none()
            )
        if chapter is None:
            chapter = Chapter(
                novel_id=novel_db_id,
                chapter_number=chapter_number,
                title=title or chapter_id,
            )
        return chapter
