from __future__ import annotations

import logging
from typing import Any, Callable, Optional

from novelai.services.storage_service import StorageService
from novelai.services.translation_service import TranslationService
from novelai.sources.base import SourceAdapter
from novelai.utils.chapter_selection import parse_chapter_selection

logger = logging.getLogger(__name__)


class NovelOrchestrationService:
    """Shared orchestration logic used by CLI, TUI, and potentially web UI.
    
    Requires injection of:
    - storage: StorageService
    - translation: TranslationService
    - source_factory: Callable that returns SourceAdapter for a given key
    """

    def __init__(
        self,
        storage: StorageService,
        translation: TranslationService,
        source_factory: Optional[Callable[[str], SourceAdapter]] = None,
    ) -> None:
        if source_factory is None:
            # Default: import and use registry
            from novelai.sources.registry import get_source
            source_factory = get_source
        
        self.storage = storage
        self.translation = translation
        self._source_factory = source_factory

    async def scrape_metadata(self, source_key: str, novel_id: str, mode: str = "update") -> dict[str, Any]:
        logger.info(f"Scraping metadata for {novel_id} from {source_key} (mode={mode})")
        if mode == "full":
            logger.debug(f"Full scrape mode - deleting existing data for {novel_id}")
            self.storage.delete_novel(novel_id)

        source = self._source_factory(source_key)
        meta = await source.fetch_metadata(novel_id)
        self.storage.save_metadata(novel_id, meta)
        logger.info(f"Metadata scraped: {len(meta)} fields saved")
        return meta

    async def scrape_chapters(
        self,
        source_key: str,
        novel_id: str,
        chapters: str,
        mode: str = "update",
    ) -> None:
        source = self._source_factory(source_key)

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
        source = self._source_factory(source_key)
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
