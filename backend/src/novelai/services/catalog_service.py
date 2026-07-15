"""Catalog service — storage-key bridge.

Writes chapter content to file/object storage and persists the storage key
and checksum in the database (architecture.md §21).

Storage-path knowledge stays inside the storage boundary (storage/*).
This service bridges the file-backed StorageService with the DB models so
the two can run in parallel during the file→DB transition.
"""

from __future__ import annotations

import hashlib
import logging
from collections import deque
from collections.abc import Callable
from contextlib import AbstractContextManager, suppress
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy.orm import Session

from novelai.db.engine import session_scope
from novelai.db.models.chapter import Chapter
from novelai.db.models.novel import Novel
from novelai.services.library_summary_service import invalidate_library_summary_cache
from novelai.services.taxonomy_persistence import persist_taxonomy_assignments
from novelai.sources.status import normalize_publication_status
from novelai.storage.service import StorageService

logger = logging.getLogger(__name__)


CATALOG_PROJECTION_FIELDS = (
    "title",
    "original_title",
    "synopsis",
    "publication_status",
    "source_updated_at",
    "chapter_count",
    "translated_count",
    "latest_chapter_id",
    "latest_chapter_number",
    "latest_chapter_title",
    "latest_chapter_updated_at",
    "glossary_status",
    "glossary_revision",
)


@dataclass(frozen=True)
class CatalogProjectionReconciliation:
    novel_id: str
    created: bool
    before: dict[str, object] | None
    after: dict[str, object]
    changed_fields: list[str]


@dataclass(frozen=True)
class CatalogProjectionFailure:
    novel_id: str
    error: str


@dataclass(frozen=True)
class CatalogProjectionBulkReconciliation:
    dry_run: bool
    scanned: int
    created: int
    updated: int
    unchanged: int
    failed: int
    changed: list[CatalogProjectionReconciliation]
    failures: list[CatalogProjectionFailure]
    details_truncated: bool = False


@dataclass(frozen=True)
class CatalogPublicationResult:
    novel: Novel
    visibility_warnings: list[str]


def _sha256(text: str) -> str:
    """Return a hex SHA-256 digest for a text string."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _metadata_datetime(value: object) -> datetime | None:
    """Return a datetime from safe metadata timestamp shapes."""
    if isinstance(value, datetime):
        return value
    if isinstance(value, str) and value.strip():
        text = value.strip()
        if text.endswith("Z"):
            text = f"{text[:-1]}+00:00"
        try:
            return datetime.fromisoformat(text)
        except ValueError:
            return None
    return None


def _metadata_chapters(metadata: dict) -> list[dict]:
    chapters = metadata.get("chapters")
    return [chapter for chapter in chapters if isinstance(chapter, dict)] if isinstance(chapters, list) else []


def _optional_string(value: object) -> str | None:
    return value.strip() if isinstance(value, str) and value.strip() else None


def _metadata_public_title(novel_id: str, metadata: dict) -> str:
    return (
        _optional_string(metadata.get("translated_title"))
        or _optional_string(metadata.get("title"))
        or novel_id
    )


def _metadata_original_title(metadata: dict) -> str | None:
    translated_title = _optional_string(metadata.get("translated_title"))
    source_title = (
        _optional_string(metadata.get("title"))
        or _optional_string(metadata.get("original_title"))
        or _optional_string(metadata.get("source_title"))
    )
    if translated_title and source_title and translated_title == source_title:
        return None
    return source_title


def _metadata_public_synopsis(metadata: dict) -> str | None:
    for key in ("translated_synopsis", "translated_description", "synopsis", "description"):
        value = _optional_string(metadata.get(key))
        if value:
            return value
    return None


def _projection_snapshot(novel: Novel) -> dict[str, object]:
    return {field: getattr(novel, field) for field in CATALOG_PROJECTION_FIELDS}


def refresh_catalog_projection_for_storage_novel(
    novel_id: str,
    storage: StorageService,
    session: Session,
) -> Novel | None:
    """Refresh one DB catalog projection from canonical storage state."""
    service = CatalogService(storage=storage, session=session)
    metadata = storage.load_metadata(novel_id)
    if metadata is not None:
        return service.get_or_create_novel(novel_id, metadata)
    return service.recompute_catalog_projection(novel_id)


def safely_refresh_catalog_projection_after_storage_write(
    novel_id: str,
    storage: StorageService,
    *,
    context: str,
    session: Session | None = None,
    session_scope_factory: Callable[[], AbstractContextManager[Session]] = session_scope,
) -> bool:
    """Best-effort DB catalog projection refresh after a storage write."""
    try:
        if session is not None:
            refresh_catalog_projection_for_storage_novel(novel_id, storage, session)
        else:
            with session_scope_factory() as scoped_session:
                refresh_catalog_projection_for_storage_novel(novel_id, storage, scoped_session)
        _clear_projection_refresh_failure(novel_id)
        return True
    except Exception as exc:
        logger.warning(
            "Catalog projection refresh failed after %s for novel_id=%s: %s",
            context,
            novel_id,
            exc,
            exc_info=True,
        )
        _record_projection_refresh_failure(novel_id, str(exc), context=context)
        return False


# ---------------------------------------------------------------------------
# Projection refresh failure tracker (module-level, maxlen=50)
# ---------------------------------------------------------------------------

_PROJECTION_REFRESH_FAILURES: deque[dict] = deque(maxlen=50)


def _record_projection_refresh_failure(
    novel_id: str,
    error: str,
    context: str = "",
) -> None:
    """Record a projection refresh failure (non-raising)."""
    with suppress(Exception):
        _PROJECTION_REFRESH_FAILURES.append({
            "novel_id": novel_id,
            "error": str(error),
            "context": context,
            "recorded_at": datetime.utcnow().isoformat(),
        })


def _clear_projection_refresh_failure(novel_id: str) -> None:
    """Remove all failure records for a given novel_id."""
    try:
        to_keep: deque[dict] = deque(maxlen=50)
        for record in _PROJECTION_REFRESH_FAILURES:
            if record.get("novel_id") != novel_id:
                to_keep.append(record)
        _PROJECTION_REFRESH_FAILURES.clear()
        _PROJECTION_REFRESH_FAILURES.extend(to_keep)
    except Exception:
        pass  # Must not raise.


def get_projection_refresh_failures() -> list[dict]:
    """Return a snapshot of recent projection refresh failures."""
    return list(_PROJECTION_REFRESH_FAILURES)


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
        has_publication_status = "publication_status" in metadata or "status" in metadata
        publication_status = normalize_publication_status(
            metadata.get("publication_status") or metadata.get("status")
        )
        source_updated_at = _metadata_datetime(
            metadata.get("source_updated_at")
            or metadata.get("scraped_at")
            or metadata.get("updated_at")
        )
        if novel is None:
            novel = Novel(
                slug=novel_id,
                title=_metadata_public_title(novel_id, metadata),
                original_title=_metadata_original_title(metadata),
                author=_optional_string(metadata.get("translated_author")) or metadata.get("author"),
                source_site=metadata.get("source_key"),
                source_url=metadata.get("source_url"),
                language=metadata.get("language", "ja"),
                status=publication_status,
                publication_status=publication_status,
                source_updated_at=source_updated_at,
                synopsis=_metadata_public_synopsis(metadata),
            )
            self._session.add(novel)
            self._session.flush()  # Ensure novel.id is available
        else:
            if has_publication_status:
                novel.status = publication_status
                novel.publication_status = publication_status
            if source_updated_at is not None:
                novel.source_updated_at = source_updated_at

        self.recompute_catalog_projection(novel.slug, novel=novel, metadata=metadata)

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
        self.recompute_catalog_projection(novel_id, novel=novel)
        invalidate_library_summary_cache()
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
        self.recompute_catalog_projection(novel_id, novel=novel)
        invalidate_library_summary_cache()
        return chapter

    def recompute_catalog_projection(
        self,
        novel_id: str,
        *,
        novel: Novel | None = None,
        metadata: dict | None = None,
    ) -> Novel | None:
        """Refresh denormalized catalog summary fields for one novel.

        Mirrors the current public catalog's file-backed semantics so later
        DB-backed listing phases can switch storage without changing values.
        """
        novel = novel or self._session.query(Novel).filter_by(slug=novel_id).one_or_none()
        if novel is None:
            return None

        metadata = metadata if metadata is not None else (self._storage.load_metadata(novel_id) or {})
        translated_count = self._storage.count_translated_chapters(novel_id)
        metadata_chapters = _metadata_chapters(metadata)
        chapter_count = len(metadata_chapters) or max(
            self._storage.count_stored_chapters(novel_id),
            translated_count,
        )
        latest_chapter = self._latest_translated_chapter(novel_id, metadata_chapters)

        if metadata:
            novel.title = _metadata_public_title(novel_id, metadata)
            novel.original_title = _metadata_original_title(metadata)
            novel.author = _optional_string(metadata.get("translated_author")) or _optional_string(metadata.get("author"))
            novel.synopsis = _metadata_public_synopsis(metadata)
        novel.chapter_count = chapter_count
        novel.translated_count = translated_count
        novel.latest_chapter_id = latest_chapter["id"] if latest_chapter else None  # type: ignore[reportAttributeAccessIssue]
        novel.latest_chapter_number = latest_chapter["number"] if latest_chapter else None  # type: ignore[reportAttributeAccessIssue]
        novel.latest_chapter_title = latest_chapter["title"] if latest_chapter else None  # type: ignore[reportAttributeAccessIssue]
        novel.latest_chapter_updated_at = latest_chapter["updated_at"] if latest_chapter else None  # type: ignore[reportAttributeAccessIssue]
        return novel

    def reconcile_catalog_projection(
        self,
        novel_id: str,
    ) -> CatalogProjectionReconciliation | None:
        """Repair one DB catalog projection from canonical storage state.

        Returns None only when neither a DB row nor storage metadata exists.
        Storage-backed novels with metadata may create the missing DB row via
        the same CatalogService ownership path used by write refreshes.
        """
        metadata = self._storage.load_metadata(novel_id)
        novel = self._session.query(Novel).filter_by(slug=novel_id).one_or_none()
        if novel is None and metadata is None:
            return None

        before = _projection_snapshot(novel) if novel is not None else None
        created = novel is None
        if metadata is not None and novel is None:
            novel = self.get_or_create_novel(novel_id, metadata)
        elif metadata is not None and novel is not None:
            publication_status = normalize_publication_status(
                metadata.get("publication_status") or metadata.get("status")
            )
            novel.status = publication_status
            novel.publication_status = publication_status
            novel.source_updated_at = _metadata_datetime(
                metadata.get("source_updated_at")
                or metadata.get("scraped_at")
                or metadata.get("updated_at")
            )
            self.recompute_catalog_projection(novel_id, novel=novel, metadata=metadata)
        elif novel is not None:
            publication_status = normalize_publication_status(
                novel.publication_status or novel.status
            )
            novel.status = publication_status
            novel.publication_status = publication_status
            self.recompute_catalog_projection(novel_id, novel=novel, metadata={})

        if novel is None:
            return None

        self._session.add(novel)
        self._session.flush()
        after = _projection_snapshot(novel)
        changed_fields = [
            field
            for field in CATALOG_PROJECTION_FIELDS
            if before is None or before.get(field) != after.get(field)
        ]
        return CatalogProjectionReconciliation(
            novel_id=novel_id,
            created=created,
            before=before,
            after=after,
            changed_fields=changed_fields,
        )

    def reconcile_all_catalog_projections(
        self,
        *,
        dry_run: bool = True,
        limit: int | None = None,
        offset: int = 0,
        detail_limit: int = 100,
    ) -> CatalogProjectionBulkReconciliation:
        """Audit or repair catalog projections for DB and storage-backed novels.

        Candidate order is deterministic: DB slugs first, then storage slugs
        not already present in DB. Storage folders without metadata are
        harmless unchanged candidates because the single-novel creator requires
        canonical metadata to create a DB row.
        """
        candidates = self._catalog_projection_candidates()
        selected = candidates[offset:]
        if limit is not None:
            selected = selected[:limit]

        created = 0
        updated = 0
        unchanged = 0
        failed = 0
        failures: list[CatalogProjectionFailure] = []
        changed: list[CatalogProjectionReconciliation] = []
        details_truncated = False

        for novel_id in selected:
            try:
                if dry_run:
                    transaction = self._session.begin_nested()
                    try:
                        result = self.reconcile_catalog_projection(novel_id)
                    finally:
                        transaction.rollback()
                        self._session.expire_all()
                else:
                    result = self.reconcile_catalog_projection(novel_id)
                    self._session.flush()
            except Exception as exc:
                failed += 1
                logger.warning(
                    "Catalog projection bulk reconciliation failed for novel_id=%s: %s",
                    novel_id,
                    exc,
                    exc_info=True,
                )
                if len(failures) < detail_limit:
                    failures.append(CatalogProjectionFailure(novel_id=novel_id, error=str(exc)))
                else:
                    details_truncated = True
                continue

            if result is None:
                unchanged += 1
                continue
            if result.created:
                created += 1
            elif result.changed_fields:
                updated += 1
            else:
                unchanged += 1

            if result.created or result.changed_fields:
                if len(changed) < detail_limit:
                    changed.append(result)
                else:
                    details_truncated = True

        return CatalogProjectionBulkReconciliation(
            dry_run=dry_run,
            scanned=len(selected),
            created=created,
            updated=updated,
            unchanged=unchanged,
            failed=failed,
            changed=changed,
            failures=failures,
            details_truncated=details_truncated,
        )

    def _catalog_projection_candidates(self) -> list[str]:
        seen: set[str] = set()
        candidates: list[str] = []

        for (slug,) in self._session.query(Novel.slug).order_by(Novel.slug.asc()).all():
            if slug not in seen:
                seen.add(slug)
                candidates.append(slug)

        for novel_id in self._storage.list_novels():
            if novel_id in seen:
                continue
            seen.add(novel_id)
            candidates.append(novel_id)

        return candidates

    def set_publication_state(
        self,
        novel_id: str,
        *,
        is_published: bool,
    ) -> CatalogPublicationResult | None:
        """Refresh projection and publish/unpublish a translated catalog novel."""
        reconciliation = self.reconcile_catalog_projection(novel_id)
        if reconciliation is None:
            return None

        novel = self._session.query(Novel).filter_by(slug=novel_id).one_or_none()
        if novel is None:
            return None

        if is_published and novel.translated_count <= 0:
            raise ValueError("Cannot publish a novel without translated chapters.")

        novel.is_published = is_published
        self._session.add(novel)
        self._session.flush()

        visibility_warnings: list[str] = []
        if is_published and any(genre.is_adult for genre in novel.genres if genre.is_active):
            visibility_warnings.append("adult_hidden_by_default")
        return CatalogPublicationResult(novel=novel, visibility_warnings=visibility_warnings)

    def _latest_translated_chapter(
        self,
        novel_id: str,
        metadata_chapters: list[dict],
    ) -> dict[str, object] | None:
        """Return latest public-readable chapter metadata using public semantics."""
        translated_ids = set(self._storage.list_translated_chapters(novel_id))
        if not translated_ids:
            return None

        latest: dict[str, object] | None = None
        for index, chapter in enumerate(metadata_chapters):
            chapter_id = str(chapter.get("id", "")).strip()
            if not chapter_id or chapter_id not in translated_ids:
                continue
            # Pull timestamp from metadata first, then fall back to the
            # chapter translation bundle (source of truth).  save_translated_chapter
            # writes translated_at to the bundle but not to metadata.
            chapter_updated_at = _metadata_datetime(
                _optional_string(chapter.get("translated_at"))
                or _optional_string(chapter.get("updated_at"))
                or _optional_string(chapter.get("scraped_at"))
            )
            if chapter_updated_at is None:
                translated = self._storage.load_translated_chapter(novel_id, chapter_id)
                if isinstance(translated, dict):
                    chapter_updated_at = _metadata_datetime(translated.get("translated_at"))
            latest = {
                "id": chapter_id,
                "number": chapter.get("num") or (index + 1),
                "title": _optional_string(chapter.get("translated_title"))
                or _optional_string(chapter.get("title")),
                "updated_at": chapter_updated_at,
            }

        return latest

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
