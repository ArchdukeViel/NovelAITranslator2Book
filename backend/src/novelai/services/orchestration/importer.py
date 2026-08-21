from __future__ import annotations

import logging
from typing import Any
from uuid import uuid4

from novelai.services.catalog_service import safely_refresh_catalog_projection_after_storage_write
from novelai.services.library_summary_service import best_effort_invalidate

logger = logging.getLogger(__name__)


async def _import_document_r2(
    self: Any,
    adapter: Any,
    document: Any,
    novel_id: str,
) -> dict[str, Any]:
    """Import a source document into immutable R2 artifacts and activate it."""

    from novelai.db.engine import session_scope
    from novelai.db.models.chapter import Chapter
    from novelai.services.catalog_service import CatalogService
    from novelai.services.r2_activation_service import R2GenerationActivationService

    units = list(adapter.list_units(document))
    chapter_rows: list[dict[str, Any]] = [
        {
            "id": unit.unit_id,
            "num": unit.import_order,
            "title": unit.title or f"Unit {unit.import_order}",
            "url": unit.source_ref,
            "import_order": unit.import_order,
            "unit_type": unit.unit_type,
        }
        for unit in units
    ]
    metadata = {
        "title": document.title,
        "author": document.author,
        "source_language": document.source_language,
        "origin_type": document.origin_type,
        "origin_uri_or_path": document.origin_uri_or_path,
        "document_type": document.document_type,
        "input_adapter_key": document.adapter_key,
        "source_key": document.adapter_key,
        "context_group_id": document.metadata.get("context_group_id")
        if isinstance(document.metadata.get("context_group_id"), str)
        else novel_id,
        "onboarding_status": "ready_for_translation",
        "chapters": chapter_rows,
        **document.metadata,
    }

    prepared: list[dict[str, Any]] = []
    for unit in units:
        existing = self.storage.load_chapter(novel_id, unit.unit_id)
        image_entries: list[dict[str, Any]] = []
        for index, asset in enumerate(await adapter.load_assets(document, unit)):
            entry: dict[str, Any] = {
                "index": index,
                "placeholder": asset.placeholder,
                "original_url": asset.source_ref,
                "alt": asset.alt,
                "title": asset.title,
            }
            if asset.region_metadata:
                entry["region_metadata"] = dict(asset.region_metadata)
            if asset.ocr_text:
                entry["ocr_text"] = asset.ocr_text
            if asset.content is not None:
                entry.update(
                    self.storage.save_chapter_image_asset(
                        novel_id,
                        unit.unit_id,
                        image_index=index,
                        content=asset.content,
                        source_url=asset.source_ref,
                        content_type=asset.content_type,
                    )
                )
            image_entries.append(entry)

        joined_ocr_text = (
            "\n".join(
                text
                for text in (
                    asset.ocr_text
                    for asset in unit.images
                    if isinstance(asset.ocr_text, str) and asset.ocr_text.strip()
                )
                if text
            )
            or None
        )
        chapter_payload = self.storage.build_chapter_payload(
            novel_id,
            unit.unit_id,
            unit.text,
            title=unit.title,
            source_key=document.adapter_key,
            source_url=unit.source_ref,
            images=image_entries,
            input_adapter_key=document.adapter_key,
            origin_type=document.origin_type,
            origin_uri_or_path=document.origin_uri_or_path,
            document_type=document.document_type,
            unit_type=unit.unit_type,
            import_order=unit.import_order,
            context_group_id=unit.context_group_id or novel_id,
            region_metadata=[dict(item) for item in unit.region_metadata],
            ocr_artifacts=[dict(item) for item in unit.ocr_artifacts],
            existing=existing,
        )
        raw_artifact = self.storage.save_raw_chapter_artifact(
            novel_id,
            unit.unit_id,
            unit.text,
            title=unit.title,
            source_key=document.adapter_key,
            source_url=unit.source_ref,
            artifact_payload=chapter_payload,
        )
        media_state = {
            "ocr_required": unit.ocr_required,
            "ocr_text": joined_ocr_text,
            "ocr_status": "pending" if unit.ocr_required else "skipped",
            "reembed_status": "pending" if unit.ocr_required else "skipped",
        }
        media_artifact = self.storage._r2_artifacts().put_json(
            novel_id=novel_id,
            kind="media",
            identity=unit.unit_id,
            payload={"chapter_id": unit.unit_id, "state": media_state, "images": image_entries},
        )
        prepared.append(
            {
                "unit": unit,
                "chapter_payload": chapter_payload,
                "raw_artifact": raw_artifact,
                "media_artifact": media_artifact,
                "media_state": media_state,
                "assets": sorted(
                    {str(entry["storage_key"]) for entry in image_entries if isinstance(entry.get("storage_key"), str)}
                ),
            }
        )

    generation_id = f"import-{uuid4().hex}"
    expected_generation_id = self.storage.resolve_active_generation_id(novel_id)
    manifest_chapters = [
        {
            "chapter_id": item["unit"].unit_id,
            "raw_storage_key": item["raw_artifact"].key,
            "raw_content_hash": item["raw_artifact"].logical_sha256,
            "translated_storage_key": None,
            "translated_content_hash": None,
            "media_storage_key": item["media_artifact"].key,
            "media_content_hash": item["media_artifact"].logical_sha256,
            "assets": item["assets"],
        }
        for item in prepared
    ]
    manifest = {
        "schema_version": 1,
        "novel_id": novel_id,
        "generation_id": generation_id,
        "mode": "document_import",
        "source": {
            "adapter_key": document.adapter_key,
            "origin_type": document.origin_type,
            "origin_uri_or_path": document.origin_uri_or_path,
        },
        "chapters": manifest_chapters,
    }

    with session_scope() as session:
        catalog = CatalogService(storage=self.storage, session=session)
        novel = catalog.get_or_create_novel(novel_id, metadata)
        imported_ids = {str(unit.unit_id) for unit in units}
        for existing_chapter in session.query(Chapter).filter(Chapter.novel_id == novel.id).all():
            if existing_chapter.logical_chapter_id not in imported_ids:
                session.delete(existing_chapter)
        session.flush()

        for item in prepared:
            unit = item["unit"]
            chapter = catalog.save_raw_chapter(
                novel_id,
                unit.unit_id,
                unit.text,
                title=unit.title,
                source_key=document.adapter_key,
                chapter_number=unit.import_order,
                sequence_number=unit.import_order,
                source_url=unit.source_ref,
                artifact_payload=item["chapter_payload"],
            )
            chapter.media_storage_key = item["media_artifact"].key
            chapter.media_content_hash = item["media_artifact"].logical_sha256
            chapter.media_state_json = item["media_state"]
            session.add(chapter)

        R2GenerationActivationService(storage=self.storage, db_session=session).activate(
            novel_id=novel_id,
            generation_id=generation_id,
            manifest=manifest,
            expected_generation_id=expected_generation_id,
        )

    safely_refresh_catalog_projection_after_storage_write(
        novel_id,
        self.storage,
        context="import_document_r2",
    )
    best_effort_invalidate(context="import_document_r2")
    return self.storage.load_metadata(novel_id) or metadata


async def import_document(
    self: Any,
    adapter_key: str,
    novel_id: str,
    source: str,
    *,
    max_units: int | None = None,
) -> dict[str, Any]:
    adapter = self._input_adapter_factory(adapter_key)
    document = await adapter.import_document(source, max_units=max_units)
    return await _import_document_r2(self, adapter, document, novel_id)
