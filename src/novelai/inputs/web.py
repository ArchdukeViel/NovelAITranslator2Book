from __future__ import annotations

from pathlib import Path

from novelai.inputs.base import DocumentAdapter
from novelai.inputs.models import ImportedAsset, ImportedDocument, ImportedUnit
from novelai.sources.registry import detect_source, get_source


class WebDocumentAdapter(DocumentAdapter):
    @property
    def key(self) -> str:
        return "web"

    def probe(self, source: str | Path) -> bool:
        value = str(source).strip().lower()
        return value.startswith("http://") or value.startswith("https://")

    async def import_document(
        self,
        source: str | Path,
        *,
        max_units: int | None = None,
    ) -> ImportedDocument:
        url = str(source).strip()
        source_key = detect_source(url) or "generic"
        adapter = get_source(source_key)
        metadata = await adapter.fetch_metadata(url, max_chapter=max_units)
        chapter_items = metadata.get("chapters", [])
        if not isinstance(chapter_items, list):
            raise RuntimeError("Web source returned invalid chapter metadata.")

        units: list[ImportedUnit] = []
        for index, item in enumerate(chapter_items, start=1):
            if not isinstance(item, dict):
                continue
            chapter_url = item.get("url")
            if not isinstance(chapter_url, str) or not chapter_url.strip():
                continue
            payload = await adapter.fetch_chapter_payload(chapter_url)
            images: list[ImportedAsset] = []
            for image in payload.get("images", []) if isinstance(payload.get("images"), list) else []:
                if not isinstance(image, dict):
                    continue
                images.append(
                    ImportedAsset(
                        source_ref=image.get("original_url") if isinstance(image.get("original_url"), str) else None,
                        content_type=image.get("content_type") if isinstance(image.get("content_type"), str) else None,
                        placeholder=image.get("placeholder") if isinstance(image.get("placeholder"), str) else None,
                        alt=image.get("alt") if isinstance(image.get("alt"), str) else None,
                        title=image.get("title") if isinstance(image.get("title"), str) else None,
                        ocr_text=image.get("ocr_text") if isinstance(image.get("ocr_text"), str) else None,
                        region_metadata=image if isinstance(image, dict) else None,
                    )
                )
            units.append(
                ImportedUnit(
                    unit_id=str(item.get("id") or index),
                    import_order=index,
                    title=item.get("title") if isinstance(item.get("title"), str) else f"Chapter {index}",
                    text=str(payload.get("text") or ""),
                    source_ref=chapter_url,
                    unit_type="chapter",
                    images=tuple(images),
                    context_group_id=str(metadata.get("title") or Path(url).stem or "web"),
                )
            )

        if not units:
            raise RuntimeError(f"No chapters imported from {url}")

        return ImportedDocument(
            adapter_key=self.key,
            origin_type="url",
            origin_uri_or_path=url,
            document_type="web_novel",
            title=str(metadata.get("title") or url),
            author=metadata.get("author") if isinstance(metadata.get("author"), str) else None,
            source_language=metadata.get("source_language") if isinstance(metadata.get("source_language"), str) else None,
            metadata={
                "source": metadata.get("source") or source_key,
                "source_url": metadata.get("source_url") or url,
            },
            units=tuple(units),
        )
