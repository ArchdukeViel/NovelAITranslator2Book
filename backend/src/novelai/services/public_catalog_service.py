"""PublicCatalogService — business logic for the public reader surface."""

from __future__ import annotations

import logging
import re
from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from novelai.db.models.novel import Novel
from novelai.services.glossary_repository import GlossaryRepository
from novelai.services.public_glossary_annotations import find_annotations, select_public_terms
from novelai.sources.status import normalize_publication_status
from novelai.storage.service import StorageService

logger = logging.getLogger(__name__)

VALID_SORT_FIELDS = {"added_at", "title", "chapter_count"}
PUBLIC_SLUG_MAX_LENGTH = 160
PUBLIC_PROTOCOL_MARKER_RE = re.compile(
    r"^\s*(?:\[CHAPTER[^\]]*\]|\[P\s+p\d{4}\])\s*",
    re.IGNORECASE,
)
PUBLIC_PARAGRAPH_MARKER_RE = re.compile(
    r"^\s*\[P\s+p\d{4}\]\s*",
    re.IGNORECASE,
)


def _optional_str(value: Any) -> str | None:
    return value.strip() if isinstance(value, str) and value.strip() else None


def _datetime_to_public_string(value: datetime | None) -> str | None:
    return value.isoformat() if isinstance(value, datetime) else None


def _metadata_chapters(meta: dict[str, Any]) -> list[dict[str, Any]]:
    chapters = meta.get("chapters")
    return chapters if isinstance(chapters, list) else []


class PublicCatalogService:
    def __init__(self, *, storage: StorageService, db_session: Session | None = None) -> None:
        self.storage = storage
        self.db_session = db_session

    def public_glossary_annotations(
        self,
        *,
        novel_id: str,
        metadata: dict[str, Any],
        translated_text: str,
        reader_blocks: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Return bounded public-safe glossary annotations for one chapter."""
        if self.db_session is None:
            return []

        platform_novel_id: int | None = None
        for key in ("platform_novel_id", "db_novel_id", "glossary_novel_id"):
            value = metadata.get(key)
            if isinstance(value, int) and value > 0:
                platform_novel_id = value
                break
        if platform_novel_id is None:
            novel_row = self.db_session.query(Novel).filter_by(slug=novel_id).one_or_none()
            if novel_row is not None:
                platform_novel_id = novel_row.id
        if platform_novel_id is None:
            return []

        repository = GlossaryRepository(self.db_session)
        entries = repository.list_glossary_entries_for_novel(
            platform_novel_id,
            public_visible=True,
        )
        entry_dicts = [
            {
                "id": entry.id,
                "canonical_term": entry.canonical_term,
                "approved_translation": entry.approved_translation,
                "term_type": entry.term_type,
                "status": entry.status,
                "public_visible": entry.public_visible,
                "short_definition": entry.public_description,
                "aliases": [
                    {"alias_text": alias.alias_text, "alias_type": alias.alias_type}
                    for alias in entry.aliases
                    if alias.alias_type in {"allowed", "approved", "preferred"}
                ],
            }
            for entry in entries
        ]
        return find_annotations(
            select_public_terms(entry_dicts),
            translated_text,
            reader_blocks,
        )

    # -- read helpers (static) --------------------------------------------------

    @staticmethod
    def novel_matches_search(meta: dict[str, Any], query: str) -> bool:
        q = query.lower()
        title = (_optional_str(meta.get("translated_title")) or _optional_str(meta.get("title")) or "").lower()
        author = (_optional_str(meta.get("translated_author")) or _optional_str(meta.get("author")) or "").lower()
        return q in title or q in author

    @staticmethod
    def novel_added_at(meta: dict[str, Any]) -> str | None:
        for key in ("scraped_at", "updated_at"):
            value = meta.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        return None

    @staticmethod
    def publication_status_from_metadata(meta: dict[str, Any]) -> str:
        return normalize_publication_status(meta.get("publication_status"))

    @staticmethod
    def slugify_public_title(value: str) -> str:
        slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
        return slug[:PUBLIC_SLUG_MAX_LENGTH].strip("-") or "novel"

    @staticmethod
    def public_slug_from_metadata(novel_id: str, meta: dict[str, Any]) -> str:
        storage_slug = _optional_str(meta.get("storage_slug"))
        if storage_slug:
            return storage_slug
        translated_title = _optional_str(meta.get("translated_title"))
        if translated_title:
            return PublicCatalogService.slugify_public_title(translated_title)
        return novel_id

    @staticmethod
    def public_synopsis_from_metadata(meta: dict[str, Any]) -> str | None:
        for key in ("translated_synopsis", "translated_description", "synopsis", "description"):
            value = _optional_str(meta.get(key))
            if value:
                return value
        return None

    @staticmethod
    def taxonomy_from_db_novel(
        novel: Novel,
        *,
        include_adult: bool = True,
    ) -> tuple[list[str], list[str]]:
        genre_slugs = [
            genre.slug
            for genre in sorted(novel.genres, key=lambda item: (item.display_order, item.slug))
            if genre.is_active and (include_adult or not genre.is_adult)
        ]
        tag_names = sorted({tag.name for tag in novel.tags if include_adult or not tag.is_adult})
        return genre_slugs, tag_names

    @staticmethod
    def db_summary_needs_storage_hydration(
        novel: Novel,
        storage_summary: dict[str, Any],
    ) -> bool:
        title_is_placeholder = PublicCatalogService.db_title_is_placeholder(novel)
        count_is_underfed = (
            title_is_placeholder and (novel.chapter_count or 0) <= 0 and storage_summary.get("chapter_count", 0) > 0
        )
        translated_is_underfed = (novel.translated_count or 0) <= 0 and storage_summary.get("translated_count", 0) > 0
        latest_is_underfed = not novel.latest_chapter_id and storage_summary.get("latest_chapter_id") is not None
        return title_is_placeholder or count_is_underfed or translated_is_underfed or latest_is_underfed

    @staticmethod
    def db_title_is_placeholder(novel: Novel) -> bool:
        title = (novel.title or "").strip()
        return not title or title == novel.slug

    @staticmethod
    def is_db_catalog_base_request(**kwargs) -> bool:
        sort_by = kwargs.get("sort_by")
        return sort_by is None or sort_by in VALID_SORT_FIELDS

    # -- instance helpers (need storage / db) ----------------------------------

    def _novel_summary(
        self,
        novel_id: str,
        meta: dict[str, Any],
        *,
        genres: list[str] | None = None,
        tags: list[str] | None = None,
    ) -> dict[str, Any]:
        translated_count = self.storage.count_translated_chapters(novel_id)
        chapter_count = len(meta.get("chapters", [])) or max(
            self.storage.count_stored_chapters(novel_id),
            translated_count,
        )
        translated_title = _optional_str(meta.get("translated_title"))
        original_title = _optional_str(meta.get("title"))
        display_title = translated_title or original_title or novel_id
        source_title = (
            original_title if (translated_title and original_title and translated_title != original_title) else None
        )
        latest_chapter = self._latest_translated_chapter(novel_id, meta)
        pub_status = self.publication_status_from_metadata(meta)
        return {
            "novel_id": novel_id,
            "slug": self.public_slug_from_metadata(novel_id, meta),
            "title": display_title,
            "source_title": source_title,
            "author": _optional_str(meta.get("translated_author")) or _optional_str(meta.get("author")),
            "language": _optional_str(meta.get("language")),
            "synopsis": self.public_synopsis_from_metadata(meta),
            "publication_status": pub_status,
            "chapter_count": chapter_count,
            "translated_count": translated_count,
            "added_at": self.novel_added_at(meta),
            "latest_chapter_id": latest_chapter.get("id") if latest_chapter else None,
            "latest_chapter_number": latest_chapter.get("number") if latest_chapter else None,
            "latest_chapter_title": latest_chapter.get("title") if latest_chapter else None,
            "latest_chapter_updated_at": latest_chapter.get("updated_at") if latest_chapter else None,
            "genres": genres or [],
            "tags": tags or [],
        }

    def _db_novel_summary(
        self,
        novel: Novel,
        *,
        include_adult: bool,
    ) -> dict[str, Any]:
        genres, tags = self.taxonomy_from_db_novel(novel, include_adult=include_adult)
        source_title = novel.original_title if (novel.original_title and novel.original_title != novel.title) else None
        pub_status = normalize_publication_status(novel.publication_status)
        storage_summary: dict[str, Any] | None = None
        resolved = self._resolve_storage_metadata_for_db_novel(
            novel.slug,
            allow_title_slug_scan=self.db_title_is_placeholder(novel),
        )
        if resolved is not None:
            storage_novel_id, metadata, _ = resolved
            storage_summary = self._novel_summary(
                storage_novel_id,
                metadata,
                genres=genres,
                tags=tags,
            )
        if storage_summary is not None and self.db_summary_needs_storage_hydration(novel, storage_summary):
            storage_summary["added_at"] = _datetime_to_public_string(novel.created_at)
            return storage_summary
        public_slug = storage_summary.get("slug") if storage_summary is not None else novel.slug
        return {
            "novel_id": novel.slug,
            "slug": public_slug,
            "title": novel.title,
            "source_title": source_title,
            "author": novel.author,
            "language": novel.language,
            "synopsis": novel.synopsis,
            "publication_status": pub_status,
            "chapter_count": novel.chapter_count,
            "translated_count": novel.translated_count,
            "added_at": _datetime_to_public_string(novel.created_at),
            "latest_chapter_id": novel.latest_chapter_id,
            "latest_chapter_number": novel.latest_chapter_number,
            "latest_chapter_title": novel.latest_chapter_title,
            "latest_chapter_updated_at": _datetime_to_public_string(novel.latest_chapter_updated_at),
            "genres": genres,
            "tags": tags,
        }

    def _resolve_storage_metadata_for_db_novel(
        self,
        novel_slug: str,
        *,
        allow_title_slug_scan: bool = False,
    ) -> tuple[str, dict[str, Any], str] | None:
        meta = self.storage.load_metadata(novel_slug)
        if meta is not None:
            source_id = _optional_str(meta.get("novel_id")) or novel_slug
            return source_id, meta, self.public_slug_from_metadata(source_id, meta)
        if not allow_title_slug_scan:
            return None
        title_slug_root = getattr(self.storage, "base_dir", None)
        if title_slug_root is not None:
            title_slug_root = title_slug_root / "novel"
        if title_slug_root is not None and title_slug_root.exists():
            return self._resolve_public_novel(novel_slug)
        return None

    def _db_row_allows_storage_catalog_entry(self, novel_id: str) -> bool:
        if self.db_session is None:
            return True
        novel = self.db_session.query(Novel).filter_by(slug=novel_id).one_or_none()
        return novel is None or novel.is_published is True

    def _load_taxonomy_for_novel(
        self,
        slug: str,
        *,
        include_adult: bool = True,
    ) -> tuple[list[str], list[str], bool]:
        if self.db_session is None:
            return [], [], False
        novel = self.db_session.query(Novel).filter_by(slug=slug).one_or_none()
        if novel is None:
            return [], [], False
        genre_slugs = []
        has_adult_genre = False
        for g in novel.genres:
            if not g.is_active:
                continue
            if not include_adult and g.is_adult:
                has_adult_genre = True
                continue
            genre_slugs.append(g.slug)
        genre_slugs.sort(
            key=lambda s: next(
                (g.display_order for g in novel.genres if g.slug == s),
                999,
            )
        )
        tag_names = sorted({t.name for t in novel.tags if include_adult or not t.is_adult})
        return genre_slugs, tag_names, has_adult_genre

    def _latest_translated_chapter(
        self,
        novel_id: str,
        meta: dict[str, Any],
    ) -> dict[str, Any] | None:
        translated_ids = set(self.storage.list_translated_chapters(novel_id))
        if not translated_ids:
            return None
        latest: dict[str, Any] | None = None
        for index, chapter in enumerate(_metadata_chapters(meta)):
            chapter_id = str(chapter.get("id", "")).strip()
            if not chapter_id or chapter_id not in translated_ids:
                continue
            latest = {
                "id": chapter_id,
                "number": chapter.get("num") or (index + 1),
                "title": _optional_str(chapter.get("translated_title")) or _optional_str(chapter.get("title")),
                "updated_at": (
                    _optional_str(chapter.get("translated_at"))
                    or _optional_str(chapter.get("updated_at"))
                    or _optional_str(chapter.get("scraped_at"))
                ),
            }
        return latest

    def _resolve_public_novel(
        self,
        slug: str,
    ) -> tuple[str, dict[str, Any], str] | None:
        meta = self.storage.load_metadata(slug)
        if meta is not None:
            source_id = _optional_str(meta.get("novel_id")) or slug
            if not self._db_row_allows_storage_catalog_entry(source_id):
                return None
            return source_id, meta, self.public_slug_from_metadata(source_id, meta)
        if self.db_session is not None:
            novel = self.db_session.query(Novel).filter_by(slug=slug).one_or_none()
            if novel is not None:
                if novel.is_published is not True:
                    return None
                meta = self.storage.load_metadata(novel.slug) or {}
                source_id = _optional_str(meta.get("novel_id")) or novel.slug
                return source_id, meta, self.public_slug_from_metadata(source_id, meta)
        for novel_id in self.storage.list_novels():
            candidate_meta = self.storage.load_metadata(novel_id) or {}
            public_slug = self.public_slug_from_metadata(novel_id, candidate_meta)
            source_id = _optional_str(candidate_meta.get("novel_id")) or novel_id
            aliases = {
                novel_id,
                source_id,
                public_slug,
                _optional_str(candidate_meta.get("source_novel_id")) or "",
            }
            if slug in aliases:
                if not self._db_row_allows_storage_catalog_entry(novel_id):
                    return None
                return source_id, candidate_meta, public_slug
        return None


# Module-level functions for backward compatibility with tests that import these
# as module-level functions. These delegate to the instance methods.
def _latest_translated_chapter(novel_id: str, meta: dict[str, Any], storage: Any) -> dict[str, Any] | None:
    """Module-level wrapper for PublicCatalogService._latest_translated_chapter."""
    service = PublicCatalogService(storage=storage)
    return service._latest_translated_chapter(novel_id, meta)


def _resolve_public_novel(slug: str, storage: Any) -> tuple[str, dict[str, Any], str] | None:
    """Module-level wrapper for PublicCatalogService._resolve_public_novel."""
    service = PublicCatalogService(storage=storage)
    return service._resolve_public_novel(slug)
