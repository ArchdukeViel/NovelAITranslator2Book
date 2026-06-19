from __future__ import annotations

from typing import Any

from novelai.services.catalog_service import safely_refresh_catalog_projection_after_storage_write


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

    chapter_rows: list[dict[str, Any]] = []
    for unit in adapter.list_units(document):
        chapter_rows.append(
            {
                "id": unit.unit_id,
                "num": unit.import_order,
                "title": unit.title or f"Unit {unit.import_order}",
                "url": unit.source_ref,
                "import_order": unit.import_order,
                "unit_type": unit.unit_type,
            }
        )

    metadata = {
        "title": document.title,
        "author": document.author,
        "source_language": document.source_language,
        "origin_type": document.origin_type,
        "origin_uri_or_path": document.origin_uri_or_path,
        "document_type": document.document_type,
        "input_adapter_key": document.adapter_key,
        "context_group_id": document.metadata.get("context_group_id") if isinstance(document.metadata.get("context_group_id"), str) else novel_id,
        "chapters": chapter_rows,
        **document.metadata,
    }
    self.storage.save_metadata(novel_id, metadata)
    safely_refresh_catalog_projection_after_storage_write(
        novel_id,
        self.storage,
        context="import_metadata",
    )

    for unit in adapter.list_units(document):
        self.storage.clear_chapter_image_assets(novel_id, unit.unit_id)
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
                stored_asset = self.storage.save_chapter_image_asset(
                    novel_id,
                    unit.unit_id,
                    image_index=index,
                    content=asset.content,
                    source_url=asset.source_ref,
                    content_type=asset.content_type,
                )
                entry.update(stored_asset)
            image_entries.append(entry)

        joined_ocr_text = "\n".join(
            text for text in [asset.ocr_text for asset in unit.images if isinstance(asset.ocr_text, str) and asset.ocr_text.strip()] if text
        ) or None
        self.storage.save_chapter(
            novel_id,
            unit.unit_id,
            unit.text,
            title=unit.title,
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
        )
        safely_refresh_catalog_projection_after_storage_write(
            novel_id,
            self.storage,
            context="import_chapter",
        )
        self.storage.save_chapter_media_state(
            novel_id,
            unit.unit_id,
            ocr_required=unit.ocr_required,
            ocr_text=joined_ocr_text,
            ocr_status="pending" if unit.ocr_required else "skipped",
            reembed_status="pending" if unit.ocr_required else "skipped",
        )

    return self.storage.load_metadata(novel_id) or metadata
