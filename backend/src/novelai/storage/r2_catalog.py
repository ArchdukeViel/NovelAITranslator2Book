"""PostgreSQL-backed domain operations for the canonical R2 content store.

Metadata, crawl state, OCR state, glossary state, activation state, and exact
artifact references are kept in PostgreSQL. R2 is reserved for immutable
chapter, translation, media, asset, and generation artifacts.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from novelai.config.workflow_profiles import normalize_workflow_defaults, normalize_workflow_profiles
from novelai.core.security import safe_child_path, validate_storage_identifier
from novelai.db.engine import session_scope
from novelai.sources.status import normalize_publication_status

VALID_ONBOARDING_STATUSES = frozenset(
    {
        "not_started",
        "metadata_discovered",
        "glossary_pending",
        "chapters_pending",
        "scraping_chapters",
        "ready_for_translation",
        "partially_scraped",
        "failed",
        "cancelled",
    }
)


@contextmanager
def _storage_session(storage: Any) -> Iterator[Any]:
    """Use an explicitly bound test session, otherwise the app session factory.

    CatalogService tests often provide an isolated SQLite session while the
    production storage facade intentionally does not own a database session.
    The binding is test-only and lets R2 reads observe the same transaction as
    the service under test without adding a production global-session cache.
    """

    bound_session = getattr(storage, "_test_db_session", None)
    if bound_session is not None:
        yield bound_session
        return
    with session_scope() as session:
        try:
            yield session
        finally:
            # CatalogService may bind this session temporarily so nested R2
            # projections observe the caller's transaction. Never let that
            # application-owned session leak into the next storage call.
            if getattr(storage, "_test_db_session", None) is session:
                delattr(storage, "_test_db_session")


def _marker(kind: str, novel_id: str, chapter_id: str | None = None) -> Path:
    suffix = f"/{chapter_id}" if chapter_id is not None else ""
    return Path(f"r2:{kind}/{novel_id}{suffix}")


def _chapter_metadata(row: Any, stored: dict[str, Any] | None = None) -> dict[str, Any]:
    item = dict(stored) if isinstance(stored, dict) else {}
    item.update(
        {
            "id": row.logical_chapter_id,
            "title": row.title,
            "num": row.chapter_number,
            "chapter_number": row.chapter_number,
            "sequence_number": row.sequence_number,
            "source_episode_id": row.source_episode_id,
            "source_url": row.source_url,
            "translated": bool(row.translated_storage_key),
        }
    )
    return item


def _metadata_from_row(novel: Any, chapters: list[Any]) -> dict[str, Any]:
    metadata = dict(novel.metadata_json) if isinstance(novel.metadata_json, dict) else {}
    metadata.setdefault("novel_id", novel.slug)
    metadata.setdefault("title", novel.original_title or novel.title)
    if novel.title and novel.title != metadata.get("title"):
        metadata.setdefault("translated_title", novel.title)
    if novel.author:
        metadata.setdefault("author", novel.author)
    if novel.language:
        metadata.setdefault("language", novel.language)
    if novel.publication_status:
        metadata.setdefault("publication_status", novel.publication_status)
    if novel.public_reader_unavailable_policy is not None:
        metadata["public_reader_unavailable_policy"] = novel.public_reader_unavailable_policy

    stored_chapters = {
        str(item.get("id")): item
        for item in metadata.get("chapters", [])
        if isinstance(item, dict) and item.get("id") is not None
    }
    rows_by_id = {str(row.logical_chapter_id): row for row in chapters}
    if isinstance(metadata.get("chapters"), list):
        # PostgreSQL keeps historical Chapter rows so their immutable R2
        # artifacts remain addressable.  The metadata index is the active
        # source index, so reads must not resurrect an episode removed from
        # that current index.
        metadata["chapters"] = [
            _chapter_metadata(rows_by_id[chapter_id], item) if chapter_id in rows_by_id else dict(item)
            for chapter_id, item in (
                (str(item.get("id") or item.get("chapter_id") or ""), item)
                for item in metadata["chapters"]
                if isinstance(item, dict)
            )
            if chapter_id
        ]
    else:
        metadata["chapters"] = [_chapter_metadata(row, stored_chapters.get(row.logical_chapter_id)) for row in chapters]
    metadata.setdefault(
        "onboarding_status",
        "ready_for_translation"
        if any(row.raw_storage_key for row in chapters)
        else "chapters_pending"
        if metadata.get("chapters")
        else "metadata_discovered",
    )
    return metadata


def load_metadata(storage: Any, novel_id: str) -> dict[str, Any] | None:
    from novelai.db.models.chapter import Chapter
    from novelai.db.models.novel import Novel

    with _storage_session(storage) as session:
        novel = session.query(Novel).filter_by(slug=novel_id).one_or_none()
        if novel is None:
            return None
        chapters = (
            session.query(Chapter)
            .filter_by(novel_id=novel.id)
            .order_by(Chapter.sequence_number.asc().nulls_last(), Chapter.chapter_number.asc(), Chapter.id.asc())
            .all()
        )
        return _metadata_from_row(novel, chapters)


def save_metadata(storage: Any, novel_id: str, data: dict[str, Any]) -> Path:
    from novelai.db.models.novel import Novel
    from novelai.services.catalog_service import CatalogService

    validate_storage_identifier(str(novel_id), "novel_id")
    with _storage_session(storage) as session:
        payload = dict(data)
        for legacy_field, canonical_field in {"source": "source_key", "status": "publication_status"}.items():
            if legacy_field in payload:
                raise ValueError(f"Legacy metadata field '{legacy_field}' is not supported; use '{canonical_field}'.")

        existing = session.query(Novel).filter_by(slug=novel_id).one_or_none()
        previous = existing.metadata_json if existing is not None and isinstance(existing.metadata_json, dict) else {}
        if "translation_profiles" in payload:
            payload["translation_profiles"] = normalize_workflow_profiles(payload["translation_profiles"])["steps"]
        elif "translation_profiles" not in previous:
            payload["translation_profiles"] = normalize_workflow_profiles(None)["steps"]
        if "translation_defaults" in payload:
            payload["translation_defaults"] = normalize_workflow_defaults(payload["translation_defaults"])
        elif "translation_defaults" not in previous:
            payload["translation_defaults"] = normalize_workflow_defaults(None)

        CatalogService(storage=storage, session=session).get_or_create_novel(novel_id, payload)
    return _marker("metadata", novel_id)


def list_metadata_history(storage: Any, novel_id: str, *, limit: int = 10) -> list[dict[str, Any]]:
    """Return the current PostgreSQL projection and retained prior snapshots."""

    from novelai.db.models.novel import Novel

    bounded_limit = max(1, min(int(limit), 25))
    with _storage_session(storage) as session:
        novel = session.query(Novel).filter_by(slug=novel_id).one_or_none()
        if novel is None:
            return []
        current = dict(novel.metadata_json) if isinstance(novel.metadata_json, dict) else {}
        entries = [
            {
                "snapshot_id": "current",
                "created_at": novel.updated_at.isoformat() if novel.updated_at else None,
                "size_bytes": len(json.dumps(current, ensure_ascii=False).encode("utf-8")),
                "metadata": current,
                "publication_status": normalize_publication_status(current.get("publication_status")),
                "title": current.get("translated_title") or current.get("title"),
                "source_title": current.get("title"),
                "author": current.get("translated_author") or current.get("author"),
                "is_current": True,
            }
        ]
        history = novel.metadata_history_json if isinstance(novel.metadata_history_json, list) else []
        for item in reversed(history):
            if not isinstance(item, dict):
                continue
            entry = dict(item)
            raw_snapshot = entry.get("metadata")
            snapshot: dict[str, Any] = raw_snapshot if isinstance(raw_snapshot, dict) else {}
            entry.setdefault("publication_status", normalize_publication_status(snapshot.get("publication_status")))
            entry.setdefault("title", snapshot.get("translated_title") or snapshot.get("title"))
            entry.setdefault("source_title", snapshot.get("title"))
            entry.setdefault("author", snapshot.get("translated_author") or snapshot.get("author"))
            entries.append(entry)
        return entries[:bounded_limit]


def load_metadata_snapshot(storage: Any, novel_id: str, snapshot_id: str) -> dict[str, Any] | None:
    """Load one current or retained PostgreSQL metadata snapshot."""

    if not isinstance(snapshot_id, str) or not snapshot_id or snapshot_id in {".", ".."}:
        raise ValueError("Invalid snapshot id")
    if any(part in snapshot_id for part in ("/", "\\")):
        raise ValueError("Invalid snapshot id")
    for entry in list_metadata_history(storage, novel_id, limit=25):
        if entry.get("snapshot_id") == snapshot_id:
            return entry
    return None


def delete_novel(storage: Any, novel_id: str) -> None:
    """Mark a novel unavailable without deleting its immutable R2 artifacts."""

    from novelai.db.models.novel import Novel

    with _storage_session(storage) as session:
        novel = session.query(Novel).filter_by(slug=novel_id).one_or_none()
        if novel is None:
            raise KeyError(f"Novel {novel_id} not found")
        novel.is_published = False
        novel.publication_status = "deleted"
        novel.public_reader_unavailable_policy = "deleted"
        state = dict(novel.source_state_json) if isinstance(novel.source_state_json, dict) else {}
        state["deletion_state"] = "requested"
        state["deletion_requested_at"] = datetime.now(UTC).isoformat().replace("+00:00", "Z")
        novel.source_state_json = state
        session.add(novel)


def load_source_state(storage: Any, novel_id: str) -> dict[str, Any] | None:
    from novelai.db.models.novel import Novel

    with _storage_session(storage) as session:
        novel = session.query(Novel).filter_by(slug=novel_id).one_or_none()
        if novel is None or not isinstance(novel.source_state_json, dict):
            return None
        return dict(novel.source_state_json)


def save_source_state(storage: Any, novel_id: str, data: dict[str, Any]) -> Path:
    from novelai.db.models.novel import Novel

    with _storage_session(storage) as session:
        novel = session.query(Novel).filter_by(slug=novel_id).one_or_none()
        if novel is None:
            raise ValueError(f"No metadata found for novel {novel_id!r}")
        novel.source_state_json = dict(data)
        session.add(novel)
    return _marker("source-state", novel_id)


def load_glossary(storage: Any, novel_id: str) -> list[dict[str, Any]]:
    """Load the mutable glossary projection from PostgreSQL, never from R2."""

    from novelai.db.models.novel import Novel
    from novelai.services.glossary_repository import GlossaryRepository

    with _storage_session(storage) as session:
        novel = session.query(Novel).filter_by(slug=novel_id).one_or_none()
        if novel is None:
            return []
        entries = GlossaryRepository(session).list_glossary_entries_for_novel(novel.id)
        runtime_statuses = {
            "approved": "approved",
            "translated": "translated",
            "candidate": "pending",
            "recommended": "pending",
            "rejected": "ignored",
            "deprecated": "ignored",
        }
        return [
            {
                "source": entry.canonical_term,
                "target": entry.approved_translation or "",
                "status": runtime_statuses.get(str(entry.status).strip().lower(), "ignored"),
                "_db_status": str(entry.status).strip().lower(),
                "confidence": entry.confidence,
                "notes": entry.admin_notes,
                "context_summary": entry.admin_notes,
                "locked": entry.owner_locked,
            }
            for entry in entries
        ]


def save_glossary(storage: Any, novel_id: str, entries: list[dict[str, Any]]) -> Path:
    """Upsert the legacy-shaped glossary API into PostgreSQL glossary rows."""

    from novelai.db.models.novel import Novel
    from novelai.services.glossary_repository import GlossaryRepository

    status_map = {
        "approved": "approved",
        "recommended": "recommended",
        "rejected": "rejected",
        "deprecated": "deprecated",
        "ignored": "rejected",
        "pending": "candidate",
        "needs_manual_review": "candidate",
    }
    with _storage_session(storage) as session:
        novel = session.query(Novel).filter_by(slug=novel_id).one_or_none()
        if novel is None:
            from novelai.services.catalog_service import CatalogService

            novel = CatalogService(storage=storage, session=session).get_or_create_novel(
                novel_id,
                {"title": novel_id},
            )
        repository = GlossaryRepository(session)
        existing = {entry.canonical_term: entry for entry in repository.list_glossary_entries_for_novel(novel.id)}
        for raw in entries:
            if not isinstance(raw, dict):
                continue
            source = str(raw.get("source") or raw.get("canonical_term") or "").strip()
            if not source:
                continue
            target_raw = raw.get("target") or raw.get("approved_translation")
            target = str(target_raw).strip() if target_raw is not None else ""
            requested_status = str(raw.get("status") or "candidate").strip().lower()
            status = status_map.get(requested_status, "candidate")
            notes_raw = raw.get("notes") or raw.get("context_summary") or raw.get("admin_notes")
            notes = str(notes_raw).strip() if notes_raw is not None else None
            confidence = raw.get("confidence")
            confidence_value = float(confidence) if isinstance(confidence, (int, float)) else None
            entry = existing.get(source)
            if entry is None:
                entry = repository.create_glossary_entry(
                    novel_id=novel.id,
                    canonical_term=source,
                    term_type="extracted",
                    approved_translation=target or None,
                    status=status,
                    admin_notes=notes,
                    confidence=confidence_value,
                    decision_source="storage_api",
                )
                existing[source] = entry
                continue
            fields: dict[str, Any] = {}
            if target != (entry.approved_translation or ""):
                fields["approved_translation"] = target or None
            if notes != entry.admin_notes:
                fields["admin_notes"] = notes
            if confidence_value != entry.confidence:
                fields["confidence"] = confidence_value
            if fields:
                repository.update_glossary_entry(entry.id, novel_id=novel.id, **fields)
            if status != entry.status and not (entry.status == "approved" and status == "candidate"):
                repository.change_glossary_entry_status(
                    entry.id,
                    novel_id=novel.id,
                    status=status,
                    decision_source="storage_api",
                )
    return _marker("glossary", novel_id)


def update_onboarding_status(
    storage: Any,
    novel_id: str,
    status: str,
    *,
    error_code: str | None = None,
    error_message: str | None = None,
    clear_error: bool = False,
) -> dict[str, Any]:
    if status not in VALID_ONBOARDING_STATUSES:
        raise ValueError(f"Invalid onboarding status: {status}")
    metadata = load_metadata(storage, novel_id)
    if metadata is None:
        raise ValueError(f"No metadata found for novel {novel_id!r}")
    metadata["onboarding_status"] = status
    metadata["onboarding_updated_at"] = datetime.now(UTC).isoformat().replace("+00:00", "Z")
    if clear_error:
        metadata.pop("onboarding_error_code", None)
        metadata.pop("onboarding_error_message", None)
    elif error_code is not None or error_message is not None:
        if error_code is not None:
            metadata["onboarding_error_code"] = error_code
        if error_message is not None:
            metadata["onboarding_error_message"] = error_message
    save_metadata(storage, novel_id, metadata)
    return metadata


def resolve_onboarding_status(storage: Any, novel_id: str) -> str:
    metadata = load_metadata(storage, novel_id)
    if metadata is None:
        return "not_started"
    status = metadata.get("onboarding_status")
    if status in VALID_ONBOARDING_STATUSES:
        return str(status)
    chapters = metadata.get("chapters") or []
    if not chapters:
        return "metadata_discovered"
    stored = list_stored_chapters(storage, novel_id)
    return "ready_for_translation" if stored else "chapters_pending"


def list_novels(storage: Any) -> list[str]:
    from novelai.db.models.novel import Novel

    with _storage_session(storage) as session:
        return [str(slug) for (slug,) in session.query(Novel.slug).order_by(Novel.slug.asc()).all()]


def get_novel_chapter_summary(storage: Any, novel_id: str) -> dict[str, Any] | None:
    """Return chapter counts and exact catalog identities for one novel.

    Administrative summaries use this PostgreSQL projection instead of
    listing the R2 bucket. R2 remains the byte store; the catalog is the
    source of truth for which immutable references are active.
    """

    from novelai.db.models.chapter import Chapter
    from novelai.db.models.novel import Novel

    with _storage_session(storage) as session:
        novel = session.query(Novel).filter_by(slug=novel_id).one_or_none()
        if novel is None:
            return None
        rows = session.query(Chapter).filter_by(novel_id=novel.id).all()
        metadata_chapters = novel.metadata_json.get("chapters") if isinstance(novel.metadata_json, dict) else []
        metadata_count = len(metadata_chapters) if isinstance(metadata_chapters, list) else 0
        raw_ids = {row.logical_chapter_id for row in rows if row.raw_storage_key}
        translated_ids = {row.logical_chapter_id for row in rows if row.translated_storage_key}
        total = max(metadata_count, len(rows), len(raw_ids), len(translated_ids))
        return {
            "total": total,
            "raw_ids": raw_ids,
            "translated_ids": translated_ids,
        }


def resolve_active_generation_id(storage: Any, novel_id: str) -> str | None:
    from novelai.db.models.novel import Novel

    with _storage_session(storage) as session:
        novel = session.query(Novel).filter_by(slug=novel_id).one_or_none()
        return str(novel.active_generation_id) if novel and novel.active_generation_id else None


def load_chapter(storage: Any, novel_id: str, chapter_id: str) -> dict[str, Any] | None:
    from novelai.db.models.chapter import Chapter
    from novelai.db.models.novel import Novel

    with _storage_session(storage) as session:
        novel = session.query(Novel).filter_by(slug=novel_id).one_or_none()
        if novel is None:
            return None
        row = session.query(Chapter).filter_by(novel_id=novel.id, logical_chapter_id=str(chapter_id)).one_or_none()
        if row is None or not row.raw_storage_key:
            return None
        payload = storage.load_r2_json_artifact(row.raw_storage_key)
        raw = payload.get("raw") if isinstance(payload.get("raw"), dict) else {}
        result: dict[str, Any] = {
            "id": row.logical_chapter_id,
            "title": payload.get("title") or row.title,
            "source_key": payload.get("source_key") or novel.source_site,
            "source_url": payload.get("source_url") or row.source_url,
            "text": raw.get("text"),
            "paragraphs": raw.get("paragraphs"),
            "source_blocks": raw.get("source_blocks"),
            "images": raw.get("images") if isinstance(raw.get("images"), list) else [],
            "raw": raw,
            "media_storage_key": row.media_storage_key,
        }
        for key in (
            "input_adapter_key",
            "origin_type",
            "origin_uri_or_path",
            "document_type",
            "unit_type",
            "import_order",
            "context_group_id",
            "region_metadata",
            "ocr_artifacts",
        ):
            if key in payload:
                result[key] = payload[key]
        state = row.media_state_json if isinstance(row.media_state_json, dict) else {}
        result.update(state)
        return result


def save_chapter(storage: Any, novel_id: str, chapter_id: str, text: str, **kwargs: Any) -> Path:
    from novelai.db.models.novel import Novel
    from novelai.services.catalog_service import CatalogService

    images = kwargs.get("images") if isinstance(kwargs.get("images"), list) else None
    existing = load_chapter(storage, novel_id, chapter_id)
    artifact_payload = storage.build_chapter_payload(
        novel_id,
        chapter_id,
        text,
        title=kwargs.get("title"),
        source_key=kwargs.get("source_key"),
        source_url=kwargs.get("source_url"),
        images=images,
        source_blocks=kwargs.get("source_blocks"),
        input_adapter_key=kwargs.get("input_adapter_key"),
        origin_type=kwargs.get("origin_type"),
        origin_uri_or_path=kwargs.get("origin_uri_or_path"),
        document_type=kwargs.get("document_type"),
        unit_type=kwargs.get("unit_type"),
        import_order=kwargs.get("import_order"),
        context_group_id=kwargs.get("context_group_id"),
        region_metadata=kwargs.get("region_metadata"),
        ocr_artifacts=kwargs.get("ocr_artifacts"),
        existing=existing,
    )
    with _storage_session(storage) as session:
        catalog = CatalogService(storage=storage, session=session)
        if session.query(Novel).filter_by(slug=novel_id).one_or_none() is None:
            catalog.get_or_create_novel(novel_id, {"title": novel_id})
        catalog.save_raw_chapter(
            novel_id,
            chapter_id,
            text,
            title=kwargs.get("title"),
            source_key=kwargs.get("source_key"),
            chapter_number=kwargs.get("chapter_number"),
            source_episode_id=kwargs.get("source_episode_id"),
            sequence_number=kwargs.get("sequence_number"),
            source_url=kwargs.get("source_url"),
            artifact_payload=artifact_payload,
        )
    return _marker("chapter", novel_id, chapter_id)


def list_stored_chapters(storage: Any, novel_id: str) -> list[str]:
    from novelai.db.models.chapter import Chapter
    from novelai.db.models.novel import Novel

    with _storage_session(storage) as session:
        novel = session.query(Novel).filter_by(slug=novel_id).one_or_none()
        if novel is None:
            return []
        rows = (
            session.query(Chapter.logical_chapter_id)
            .filter(
                Chapter.novel_id == novel.id,
                (Chapter.raw_storage_key.is_not(None) | Chapter.translated_storage_key.is_not(None)),
            )
            .order_by(Chapter.sequence_number.asc().nulls_last(), Chapter.chapter_number.asc())
            .all()
        )
        return [str(chapter_id) for (chapter_id,) in rows]


def count_stored_chapters(storage: Any, novel_id: str) -> int:
    return len(list_stored_chapters(storage, novel_id))


def _translation_payload(chapter_id: str, text: str, kwargs: dict[str, Any]) -> dict[str, Any]:
    version_id = kwargs.get("version_id")
    if not isinstance(version_id, str) or not version_id.strip():
        version_id = f"r2-{hashlib.sha256(text.encode('utf-8')).hexdigest()[:16]}"
    version_kind = kwargs.get("version_kind")
    version_kind = getattr(version_kind, "value", version_kind)
    payload: dict[str, Any] = {
        "schema_version": 2,
        "chapter_id": chapter_id,
        "version_id": version_id,
        "version_kind": version_kind or "machine_translation",
        "text": text,
        "paragraphs": [part for part in text.replace("\r\n", "\n").split("\n\n") if part],
    }
    allowed = (
        "provider_key",
        "provider_model",
        "confidence_score",
        "polish_needed",
        "confidence_details",
        "glossary_revision",
        "glossary_injected_term_count",
        "prompt_template_version",
        "glossary_hash",
        "batch_id",
        "base_version_id",
        "translation_run_id",
        "raw_generation_id",
        "source_episode_id",
        "source_structure_hash",
        "source_image_manifest_hash",
        "qa_policy_fingerprint",
        "source_language",
        "target_language",
        "style_preset",
        "consistency_mode",
        "json_output",
        "output_hash",
        "activation_disposition",
        "honorific_policy",
    )
    for key in allowed:
        value = kwargs.get(key)
        if value is not None:
            payload[key] = value
    source_hash = kwargs.get("source_hash")
    if isinstance(source_hash, str) and source_hash:
        payload["source_hash"] = source_hash
        payload["source_content_hash"] = source_hash
    return payload


def _translation_version_rows(row: Any) -> list[dict[str, Any]]:
    value = getattr(row, "translation_versions_json", None)
    if not isinstance(value, list):
        return []
    return [dict(item) for item in value if isinstance(item, dict)]


def _translation_version_record(payload: dict[str, Any], stored: Any) -> dict[str, Any]:
    record = {key: value for key, value in payload.items() if key not in {"text", "paragraphs", "active"}}
    record["storage_key"] = stored.key
    record["content_hash"] = stored.logical_sha256
    record.setdefault("created_at", datetime.now(UTC).isoformat().replace("+00:00", "Z"))
    record.setdefault("translated_at", record["created_at"])
    return record


def _append_translation_version(row: Any, record: dict[str, Any]) -> None:
    version_id = record.get("version_id")
    versions = [item for item in _translation_version_rows(row) if item.get("version_id") != version_id]
    versions.append(dict(record))
    row.translation_versions_json = versions


def _append_translation_history(row: Any, entry: dict[str, Any]) -> None:
    history = getattr(row, "translation_edit_history_json", None)
    items = [dict(item) for item in history if isinstance(item, dict)] if isinstance(history, list) else []
    items.append(dict(entry))
    row.translation_edit_history_json = items


def save_translated_chapter(storage: Any, novel_id: str, chapter_id: str, text: str, **kwargs: Any) -> Path:
    from novelai.db.models.chapter import Chapter
    from novelai.db.models.novel import Novel

    payload = _translation_payload(str(chapter_id), text, kwargs)
    stored = storage._r2_artifacts().put_json(
        novel_id=novel_id,
        kind="translations",
        identity=str(chapter_id),
        payload=payload,
    )
    with _storage_session(storage) as session:
        novel = session.query(Novel).filter_by(slug=novel_id).one_or_none()
        if novel is None:
            from novelai.services.catalog_service import CatalogService

            novel = CatalogService(storage=storage, session=session).get_or_create_novel(
                novel_id,
                {"title": novel_id},
            )
        row = session.query(Chapter).filter_by(novel_id=novel.id, logical_chapter_id=str(chapter_id)).one_or_none()
        if row is None:
            row = Chapter(
                novel_id=novel.id,
                logical_chapter_id=str(chapter_id),
                chapter_number=0,
                title=str(chapter_id),
            )
        _append_translation_version(row, _translation_version_record(payload, stored))
        if kwargs.get("auto_activate", True) is not False:
            row.translated_storage_key = stored.key
            row.translated_content_hash = stored.logical_sha256
            row.translation_status = "translated"
        session.add(row)
        if kwargs.get("auto_activate", True) is not False:
            from novelai.services.catalog_service import CatalogService

            CatalogService(storage=storage, session=session).recompute_catalog_projection(
                novel_id,
                novel=novel,
            )
    marker_kind = "translation" if kwargs.get("auto_activate", True) is not False else "translation-pending"
    return _marker(marker_kind, novel_id, chapter_id)


def load_translated_chapter(storage: Any, novel_id: str, chapter_id: str) -> dict[str, Any] | None:
    from novelai.db.models.chapter import Chapter
    from novelai.db.models.novel import Novel

    with _storage_session(storage) as session:
        novel = session.query(Novel).filter_by(slug=novel_id).one_or_none()
        if novel is None:
            return None
        row = session.query(Chapter).filter_by(novel_id=novel.id, logical_chapter_id=str(chapter_id)).one_or_none()
        if row is None or not row.translated_storage_key:
            return None
        payload = storage.load_r2_json_artifact(row.translated_storage_key)
        payload.setdefault("chapter_id", row.logical_chapter_id)
        payload.setdefault("source_hash", payload.get("source_content_hash"))
        active_version = next(
            (item for item in _translation_version_rows(row) if item.get("version_id") == payload.get("version_id")),
            None,
        )
        if isinstance(active_version, dict):
            if active_version.get("created_at") is not None:
                payload.setdefault("created_at", active_version["created_at"])
            if active_version.get("translated_at") is not None:
                payload.setdefault("translated_at", active_version["translated_at"])
        return payload


def load_translated_chapter_by_version_id(
    storage: Any, novel_id: str, chapter_id: str, version_id: str
) -> dict[str, Any] | None:
    from novelai.db.models.chapter import Chapter
    from novelai.db.models.novel import Novel

    with _storage_session(storage) as session:
        novel = session.query(Novel).filter_by(slug=novel_id).one_or_none()
        if novel is None:
            return None
        row = session.query(Chapter).filter_by(novel_id=novel.id, logical_chapter_id=str(chapter_id)).one_or_none()
        if row is None:
            return None
        record = next((item for item in _translation_version_rows(row) if item.get("version_id") == version_id), None)
        if record is None or not isinstance(record.get("storage_key"), str):
            return None
        payload = storage.load_r2_json_artifact(record["storage_key"])
        payload.setdefault("chapter_id", row.logical_chapter_id)
        payload.setdefault("source_hash", payload.get("source_content_hash"))
        if record.get("created_at") is not None:
            payload.setdefault("created_at", record["created_at"])
        if record.get("translated_at") is not None:
            payload.setdefault("translated_at", record["translated_at"])
        return payload


def list_translated_chapter_versions(storage: Any, novel_id: str, chapter_id: str) -> list[dict[str, Any]]:
    from novelai.db.models.chapter import Chapter
    from novelai.db.models.novel import Novel

    with _storage_session(storage) as session:
        novel = session.query(Novel).filter_by(slug=novel_id).one_or_none()
        if novel is None:
            return []
        row = session.query(Chapter).filter_by(novel_id=novel.id, logical_chapter_id=str(chapter_id)).one_or_none()
        if row is None:
            return []
        versions: list[dict[str, Any]] = []
        for record in _translation_version_rows(row):
            key = record.get("storage_key")
            if not isinstance(key, str):
                continue
            try:
                payload = storage.load_r2_json_artifact(key)
            except FileNotFoundError, RuntimeError:
                continue
            item = {**record, **payload}
            item["active"] = key == row.translated_storage_key
            versions.append(item)
        return versions


def list_translated_chapters(storage: Any, novel_id: str) -> list[str]:
    from novelai.db.models.chapter import Chapter
    from novelai.db.models.novel import Novel

    with _storage_session(storage) as session:
        novel = session.query(Novel).filter_by(slug=novel_id).one_or_none()
        if novel is None:
            return []
        rows = (
            session.query(Chapter.logical_chapter_id)
            .filter(Chapter.novel_id == novel.id, Chapter.translated_storage_key.is_not(None))
            .order_by(Chapter.sequence_number.asc().nulls_last(), Chapter.chapter_number.asc())
            .all()
        )
        return [str(chapter_id) for (chapter_id,) in rows]


def count_translated_chapters(storage: Any, novel_id: str) -> int:
    return len(list_translated_chapters(storage, novel_id))


def save_edited_translation(
    storage: Any,
    novel_id: str,
    chapter_id: str,
    text: str,
    *,
    editor: str | None = None,
    note: str | None = None,
    glossary_qa: dict[str, Any] | None = None,
    glossary_revision: int,
) -> Path:
    if type(glossary_revision) is not int or glossary_revision < 0:
        raise ValueError("glossary_revision must be a non-negative integer")

    from novelai.db.models.chapter import Chapter
    from novelai.db.models.novel import Novel

    with _storage_session(storage) as session:
        novel = session.query(Novel).filter_by(slug=novel_id).one_or_none()
        if novel is None:
            raise ValueError(f"No metadata found for novel {novel_id!r}")
        row = session.query(Chapter).filter_by(novel_id=novel.id, logical_chapter_id=str(chapter_id)).one_or_none()
        if row is None:
            raise ValueError(f"No chapter found for {novel_id!r}/{chapter_id!r}")
        versions = _translation_version_rows(row)
        used_ids = {str(item.get("version_id")) for item in versions}
        index = len(used_ids) + 1
        while f"v{index}" in used_ids:
            index += 1
        version_id = f"v{index}"
        previous_id = next(
            (str(item.get("version_id")) for item in versions if item.get("storage_key") == row.translated_storage_key),
            None,
        )
        previous = next((item for item in versions if item.get("version_id") == previous_id), {})

    created_at = datetime.now(UTC).isoformat().replace("+00:00", "Z")
    payload: dict[str, Any] = {
        "schema_version": 2,
        "chapter_id": str(chapter_id),
        "version_id": version_id,
        "version_kind": "manual_edit",
        "provider_key": previous.get("provider_key"),
        "provider_model": previous.get("provider_model"),
        "created_at": created_at,
        "translated_at": created_at,
        "text": text,
        "paragraphs": [part for part in text.replace("\r\n", "\n").split("\n\n") if part],
        "base_version_id": previous_id,
        "glossary_revision": glossary_revision,
    }
    if isinstance(editor, str) and editor.strip():
        payload["editor"] = editor.strip()
    if isinstance(note, str) and note.strip():
        payload["note"] = note.strip()
    if isinstance(glossary_qa, dict) and glossary_qa:
        payload["glossary_qa"] = dict(glossary_qa)
    stored = storage._r2_artifacts().put_json(
        novel_id=novel_id,
        kind="translations",
        identity=str(chapter_id),
        payload=payload,
    )

    with _storage_session(storage) as session:
        novel = session.query(Novel).filter_by(slug=novel_id).one_or_none()
        if novel is None:
            raise ValueError(f"No metadata found for novel {novel_id!r}")
        row = session.query(Chapter).filter_by(novel_id=novel.id, logical_chapter_id=str(chapter_id)).one_or_none()
        if row is None:
            raise ValueError(f"No chapter found for {novel_id!r}/{chapter_id!r}")
        _append_translation_version(row, _translation_version_record(payload, stored))
        _append_translation_history(
            row,
            {
                "id": f"e{len(getattr(row, 'translation_edit_history_json', None) or []) + 1}",
                "action": "manual_edit",
                "version_id": version_id,
                "previous_version_id": previous_id,
                "created_at": created_at,
                "editor": payload.get("editor"),
                "note": payload.get("note"),
            },
        )
        row.translated_storage_key = stored.key
        row.translated_content_hash = stored.logical_sha256
        row.translation_status = "translated"
        session.add(row)
    return _marker("translation", novel_id, chapter_id)


def load_translation_edit_history(storage: Any, novel_id: str, chapter_id: str) -> list[dict[str, Any]]:
    from novelai.db.models.chapter import Chapter
    from novelai.db.models.novel import Novel

    with _storage_session(storage) as session:
        novel = session.query(Novel).filter_by(slug=novel_id).one_or_none()
        if novel is None:
            return []
        row = session.query(Chapter).filter_by(novel_id=novel.id, logical_chapter_id=str(chapter_id)).one_or_none()
        history = getattr(row, "translation_edit_history_json", None) if row is not None else None
        return [dict(item) for item in history if isinstance(item, dict)] if isinstance(history, list) else []


def activate_translated_chapter_version(
    storage: Any,
    novel_id: str,
    chapter_id: str,
    version_id: str,
    *,
    editor: str | None = None,
    note: str | None = None,
) -> bool:
    from novelai.db.models.chapter import Chapter
    from novelai.db.models.novel import Novel

    with _storage_session(storage) as session:
        novel = session.query(Novel).filter_by(slug=novel_id).one_or_none()
        if novel is None:
            return False
        row = session.query(Chapter).filter_by(novel_id=novel.id, logical_chapter_id=str(chapter_id)).one_or_none()
        if row is None:
            return False
        records = _translation_version_rows(row)
        target = next((item for item in records if item.get("version_id") == version_id), None)
        if target is None or not isinstance(target.get("storage_key"), str):
            return False
        previous_id = next(
            (str(item.get("version_id")) for item in records if item.get("storage_key") == row.translated_storage_key),
            None,
        )
        created_at = datetime.now(UTC).isoformat().replace("+00:00", "Z")
        _append_translation_history(
            row,
            {
                "id": f"e{len(getattr(row, 'translation_edit_history_json', None) or []) + 1}",
                "action": "rollback",
                "version_id": version_id,
                "previous_version_id": previous_id,
                "created_at": created_at,
                "editor": editor.strip() if isinstance(editor, str) and editor.strip() else None,
                "note": note.strip() if isinstance(note, str) and note.strip() else None,
            },
        )
        row.translated_storage_key = target["storage_key"]
        row.translated_content_hash = target.get("content_hash")
        row.translation_status = "translated"
        session.add(row)
    return True


def load_chapter_media_state(storage: Any, novel_id: str, chapter_id: str) -> dict[str, Any] | None:
    from novelai.db.models.chapter import Chapter
    from novelai.db.models.novel import Novel

    with _storage_session(storage) as session:
        novel = session.query(Novel).filter_by(slug=novel_id).one_or_none()
        if novel is None:
            return None
        row = session.query(Chapter).filter_by(novel_id=novel.id, logical_chapter_id=str(chapter_id)).one_or_none()
        if row is None or not isinstance(row.media_state_json, dict):
            return None
        return dict(row.media_state_json)


def save_chapter_media_state(storage: Any, novel_id: str, chapter_id: str, **kwargs: Any) -> Path:
    from novelai.db.models.chapter import Chapter
    from novelai.db.models.novel import Novel

    fields = {key: value for key, value in kwargs.items() if value is not None}
    with _storage_session(storage) as session:
        novel = session.query(Novel).filter_by(slug=novel_id).one_or_none()
        if novel is None:
            raise ValueError(f"No metadata found for novel {novel_id!r}")
        row = session.query(Chapter).filter_by(novel_id=novel.id, logical_chapter_id=str(chapter_id)).one_or_none()
        if row is None:
            row = Chapter(
                novel_id=novel.id,
                logical_chapter_id=str(chapter_id),
                chapter_number=0,
                title=str(chapter_id),
            )
        current = dict(row.media_state_json) if isinstance(row.media_state_json, dict) else {}
        current.update(fields)
        media_artifact = storage._r2_artifacts().put_json(
            novel_id=novel_id,
            kind="media",
            identity=str(chapter_id),
            payload={"chapter_id": str(chapter_id), "state": current},
        )
        row.media_storage_key = media_artifact.key
        row.media_content_hash = media_artifact.logical_sha256
        row.media_state_json = current
        session.add(row)
    return _marker("media-state", novel_id, chapter_id)


def save_chapter_image_asset(
    storage: Any,
    novel_id: str,
    chapter_id: str,
    *,
    image_index: int,
    content: bytes,
    source_url: str | None = None,
    content_type: str | None = None,
) -> dict[str, Any]:
    extension = "bin"
    if isinstance(content_type, str) and "/" in content_type:
        extension = content_type.rsplit("/", 1)[-1].split("+", 1)[0].lower() or extension
    stored = storage._r2_artifacts().put_asset(novel_id=novel_id, content=content, extension=extension)
    return {
        "index": image_index,
        "storage_key": stored.key,
        "source_url": source_url,
        "content_type": content_type,
        "size_bytes": len(content),
        "sha256": stored.logical_sha256,
    }


def clear_chapter_image_assets(storage: Any, novel_id: str, chapter_id: str) -> None:
    # Immutable assets are intentionally retained for GC.  Clearing the
    # database reference is safe; deleting the object here could race a
    # published generation or another chapter that reuses the same digest.
    from novelai.db.models.chapter import Chapter
    from novelai.db.models.novel import Novel

    with _storage_session(storage) as session:
        novel = session.query(Novel).filter_by(slug=novel_id).one_or_none()
        if novel is None:
            return
        row = session.query(Chapter).filter_by(novel_id=novel.id, logical_chapter_id=str(chapter_id)).one_or_none()
        if row is not None:
            row.media_storage_key = None
            row.media_content_hash = None
            session.add(row)


def resolve_asset_path(storage: Any, novel_id: str, local_path: str | None) -> None:
    # R2 callers must use an exact storage_key and stream through the object
    # backend; a local Path would falsely imply canonical disk content.
    validate_storage_identifier(str(novel_id), "novel_id")
    if local_path is not None:
        safe_child_path(Path("."), local_path)
    return None
