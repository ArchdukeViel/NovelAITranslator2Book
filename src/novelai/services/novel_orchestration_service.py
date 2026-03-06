from __future__ import annotations

from typing import Any, Optional

from novelai.services.storage_service import StorageService
from novelai.services.translation_service import TranslationService
from novelai.sources.registry import get_source
from novelai.utils.chapter_selection import parse_chapter_selection


class NovelOrchestrationService:
    """Shared orchestration logic used by CLI, TUI, and potentially web UI."""

    def __init__(
        self,
        storage: StorageService,
        translation: TranslationService,
    ) -> None:
        self.storage = storage
        self.translation = translation

    async def scrape_metadata(self, source_key: str, novel_id: str, mode: str = "update") -> dict[str, Any]:
        if mode == "full":
            self.storage.delete_novel(novel_id)

        source = get_source(source_key)
        meta = await source.fetch_metadata(novel_id)
        self.storage.save_metadata(novel_id, meta)
        return meta

    async def scrape_chapters(
        self,
        source_key: str,
        novel_id: str,
        chapters: str,
        mode: str = "update",
    ) -> None:
        source = get_source(source_key)

        if mode == "full":
            self.storage.delete_novel(novel_id)
            meta = await source.fetch_metadata(novel_id)
            self.storage.save_metadata(novel_id, meta)
        else:
            meta = self.storage.load_metadata(novel_id)
            if not meta:
                raise RuntimeError("Metadata not found; run scrape-metadata first.")

        selection = parse_chapter_selection(chapters)
        chapter_map = {int(c["id"]): c for c in meta.get("chapters", [])}

        for spec in selection:
            chapter_num = spec.chapter
            chapter = chapter_map.get(chapter_num)
            if not chapter:
                continue

            chapter_id = str(chapter_num)
            existing_hash = self.storage.existing_chapter_hash(novel_id, chapter_id)
            text = await source.fetch_chapter(chapter["url"])
            new_hash = self.storage._hash_text(text)

            if mode == "update" and existing_hash == new_hash:
                continue

            self.storage.save_chapter(
                novel_id,
                chapter_id,
                text,
                source_key=source_key,
                source_url=chapter.get("url"),
            )

    async def translate_chapters(
        self,
        source_key: str,
        novel_id: str,
        chapters: str,
        provider_key: Optional[str] = None,
        provider_model: Optional[str] = None,
    ) -> None:
        source = get_source(source_key)
        meta = self.storage.load_metadata(novel_id)
        if not meta:
            raise RuntimeError("Metadata not found; run scrape-metadata first.")

        selection = parse_chapter_selection(chapters)
        chapter_map = {int(c["id"]): c for c in meta.get("chapters", [])}

        for spec in selection:
            chapter_num = spec.chapter
            chapter = chapter_map.get(chapter_num)
            if not chapter:
                continue

            existing = self.storage.load_translated_chapter(novel_id, str(chapter_num))
            if existing:
                continue

            result = await self.translation.translate_chapter(
                source_adapter=source,
                chapter_url=chapter["url"],
                provider_key=provider_key,
                provider_model=provider_model,
            )
            translated = result.final_text or ""
            self.storage.save_translated_chapter(
                novel_id,
                str(chapter_num),
                translated,
                provider=result.provider_key,
                model=result.provider_model,
            )
