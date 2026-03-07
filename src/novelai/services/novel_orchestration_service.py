from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any, Callable, Optional

from novelai.config.settings import settings
from novelai.providers.base import TranslationProvider
from novelai.services.settings_service import SettingsService
from novelai.services.storage_service import StorageService
from novelai.services.translation_cache import TranslationCache
from novelai.services.translation_service import TranslationService
from novelai.services.usage_service import UsageService
from novelai.sources.base import SourceAdapter
from novelai.utils.chapter_selection import is_full_chapter_selection, parse_chapter_selection

logger = logging.getLogger(__name__)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


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
        provider_factory: Optional[Callable[[str], TranslationProvider]] = None,
        settings_service: Optional[SettingsService] = None,
        translation_cache: Optional[TranslationCache] = None,
        usage_service: Optional[UsageService] = None,
    ) -> None:
        if source_factory is None:
            # Default: import and use registry
            from novelai.sources.registry import get_source
            source_factory = get_source
        if provider_factory is None:
            from novelai.providers.registry import get_provider
            provider_factory = get_provider
        
        self.storage = storage
        self.translation = translation
        self._source_factory = source_factory
        self._provider_factory = provider_factory
        self._settings = settings_service or SettingsService()
        self._cache = translation_cache or TranslationCache()
        self._usage = usage_service or UsageService()
        self._missing_api_key_warning_emitted = False

    @staticmethod
    def _infer_source_language(source_key: str, metadata: dict[str, Any] | None = None) -> str | None:
        if isinstance(metadata, dict):
            for key in ("source_language", "language", "lang"):
                value = metadata.get(key)
                if isinstance(value, str) and value.strip():
                    return value.strip()

        language_map = {
            "syosetu_ncode": "Japanese",
            "novel18_syosetu": "Japanese",
            "kakuyomu": "Japanese",
            "narou": "Japanese",
        }
        return language_map.get(source_key)

    def _selected_chapter_numbers(self, metadata: dict[str, Any], selection: str) -> list[int]:
        chapter_map = {
            int(chapter["id"]): chapter
            for chapter in metadata.get("chapters", [])
            if isinstance(chapter, dict) and str(chapter.get("id", "")).isdigit()
        }
        if is_full_chapter_selection(selection):
            return sorted(chapter_map.keys())

        return [spec.chapter for spec in parse_chapter_selection(selection)]

    @staticmethod
    def _chapter_content_signature(text: str, images: list[dict[str, Any]] | None = None) -> str:
        image_items = []
        for image in images or []:
            if not isinstance(image, dict):
                continue
            image_items.append(
                {
                    "index": image.get("index"),
                    "placeholder": image.get("placeholder"),
                    "original_url": image.get("original_url"),
                    "alt": image.get("alt"),
                    "title": image.get("title"),
                }
            )
        payload = {
            "text": text,
            "images": image_items,
        }
        return json.dumps(payload, ensure_ascii=False, sort_keys=True)

    def _resolve_provider_and_model(
        self,
        provider_key: str | None = None,
        provider_model: str | None = None,
    ) -> tuple[str, str]:
        key = provider_key or self._settings.get_provider_key()
        model = provider_model or self._settings.get_provider_model()
        if key == "openai" and not self._settings.get_api_key():
            if not self._missing_api_key_warning_emitted:
                logger.warning("OpenAI API key missing; falling back to dummy provider for metadata translation.")
                self._missing_api_key_warning_emitted = True
            return "dummy", "dummy"
        self._missing_api_key_warning_emitted = False
        if key == "dummy":
            return "dummy", "dummy"
        return key, model

    def _record_usage(self, provider_key: str, model: str, metadata: Any) -> None:
        usage = metadata.get("usage") if isinstance(metadata, dict) else None
        self._usage.record(
            {
                "timestamp": _utc_now_iso(),
                "provider": provider_key,
                "model": model,
                "tokens": usage.get("total_tokens") if isinstance(usage, dict) else None,
                "metadata": metadata if isinstance(metadata, dict) else {},
            }
        )

    async def _translate_text(
        self,
        text: str,
        *,
        provider_key: str | None = None,
        provider_model: str | None = None,
    ) -> str:
        normalized = text.strip()
        if not normalized:
            return normalized

        provider_key, provider_model = self._resolve_provider_and_model(provider_key, provider_model)
        cached = self._cache.get(normalized, provider_key, provider_model)
        if cached is not None:
            return cached

        provider = self._provider_factory(provider_key)
        result = await provider.translate(prompt=normalized, model=provider_model)
        translated = str(result.get("text", "")).strip() or normalized
        self._record_usage(provider.key, provider_model, result.get("metadata"))
        self._cache.set(normalized, provider.key, provider_model, translated)
        return translated

    async def _translate_metadata_fields(
        self,
        metadata: dict[str, Any],
        existing_metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        translated_metadata = dict(metadata)
        previous = existing_metadata or {}

        title = translated_metadata.get("title")
        if isinstance(title, str) and title:
            if previous.get("title") == title and isinstance(previous.get("translated_title"), str):
                translated_metadata["translated_title"] = previous["translated_title"]
            else:
                translated_metadata["translated_title"] = await self._translate_text(title)

        author = translated_metadata.get("author")
        if isinstance(author, str) and author:
            if previous.get("author") == author and isinstance(previous.get("translated_author"), str):
                translated_metadata["translated_author"] = previous["translated_author"]
            else:
                translated_metadata["translated_author"] = await self._translate_text(author)

        previous_chapters = previous.get("chapters", [])
        previous_by_id = {
            str(chapter.get("id")): chapter
            for chapter in previous_chapters
            if isinstance(chapter, dict) and chapter.get("id") is not None
        }

        chapters = translated_metadata.get("chapters", [])
        if not isinstance(chapters, list):
            return translated_metadata

        translated_chapters: list[dict[str, Any]] = []
        for chapter in chapters:
            if not isinstance(chapter, dict):
                continue

            translated_chapter = dict(chapter)
            chapter_id = str(chapter.get("id"))
            previous_chapter = previous_by_id.get(chapter_id, {})
            chapter_title = translated_chapter.get("title")
            if isinstance(chapter_title, str) and chapter_title:
                if (
                    previous_chapter.get("title") == chapter_title
                    and isinstance(previous_chapter.get("translated_title"), str)
                ):
                    translated_chapter["translated_title"] = previous_chapter["translated_title"]
                else:
                    translated_chapter["translated_title"] = await self._translate_text(chapter_title)

            translated_chapters.append(translated_chapter)

        translated_metadata["chapters"] = translated_chapters
        return translated_metadata

    async def scrape_metadata(
        self,
        source_key: str,
        novel_id: str,
        mode: str = "update",
        max_chapter: int | None = None,
    ) -> dict[str, Any]:
        logger.info(f"Scraping metadata for {novel_id} from {source_key} (mode={mode})")
        existing_metadata = self.storage.load_metadata(novel_id) if mode != "full" else None
        if mode == "full":
            logger.debug(f"Full scrape mode - deleting existing data for {novel_id}")
            self.storage.delete_novel(novel_id)

        source = self._source_factory(source_key)
        meta = await source.fetch_metadata(novel_id, max_chapter=max_chapter)
        try:
            meta = await self._translate_metadata_fields(meta, existing_metadata)
        except Exception as exc:
            logger.warning("Failed to translate metadata for %s: %s", novel_id, exc)
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
            try:
                meta = await self._translate_metadata_fields(meta)
            except Exception as exc:
                logger.warning("Failed to translate metadata for %s: %s", novel_id, exc)
            self.storage.save_metadata(novel_id, meta)
        else:
            meta = self.storage.load_metadata(novel_id)
            if not meta:
                raise RuntimeError("Metadata not found; run scrape-metadata first.")

        chapter_map = {int(c["id"]): c for c in meta.get("chapters", [])}
        selected_numbers = self._selected_chapter_numbers(meta, chapters)

        for chapter_num in selected_numbers:
            chapter = chapter_map.get(chapter_num)
            if not chapter:
                continue

            chapter_id = str(chapter_num)
            payload = await source.fetch_chapter_payload(chapter["url"])
            text = payload.get("text")
            if not isinstance(text, str):
                raise RuntimeError(f"Source returned invalid chapter text for {chapter['url']}.")

            images = payload.get("images")
            image_manifest = [image for image in images if isinstance(image, dict)] if isinstance(images, list) else []

            existing = self.storage.load_chapter(novel_id, chapter_id) or {}
            existing_text = existing.get("text")
            existing_images = existing.get("images") if isinstance(existing.get("images"), list) else []
            existing_signature = self._chapter_content_signature(
                existing_text if isinstance(existing_text, str) else "",
                existing_images,
            )
            new_signature = self._chapter_content_signature(text, image_manifest)

            if mode == "update" and existing_signature == new_signature:
                continue

            downloaded_images: list[dict[str, Any]] = []
            self.storage.clear_chapter_image_assets(novel_id, chapter_id)
            for image in image_manifest:
                entry = dict(image)
                original_url = entry.get("original_url")
                if not isinstance(original_url, str) or not original_url.strip():
                    downloaded_images.append(entry)
                    continue
                try:
                    asset = await source.fetch_asset(original_url, referer=chapter.get("url"))
                    content = asset.get("content")
                    if not isinstance(content, (bytes, bytearray)):
                        raise RuntimeError("Source returned invalid asset bytes.")
                    if not content:
                        raise RuntimeError("Source returned empty asset bytes.")
                    content_type = asset.get("content_type") if isinstance(asset.get("content_type"), str) else None
                    if isinstance(content_type, str) and content_type.lower().startswith("text/html"):
                        raise RuntimeError("Asset response was HTML instead of image content.")
                    stored_asset = self.storage.save_chapter_image_asset(
                        novel_id,
                        chapter_id,
                        image_index=int(entry.get("index", len(downloaded_images))),
                        content=bytes(content),
                        source_url=str(asset.get("url") or original_url),
                        content_type=content_type,
                    )
                    entry.update(stored_asset)
                    entry["original_url"] = str(asset.get("url") or original_url)
                except Exception as exc:
                    logger.warning(
                        "Failed to download chapter image for %s/%s from %s: %s",
                        novel_id,
                        chapter_id,
                        original_url,
                        exc,
                    )
                    entry["download_error"] = str(exc)
                downloaded_images.append(entry)

            self.storage.save_chapter(
                novel_id,
                chapter_id,
                text,
                source_key=source_key,
                source_url=chapter.get("url"),
                images=downloaded_images,
            )

    async def translate_chapters(
        self,
        source_key: str,
        novel_id: str,
        chapters: str,
        provider_key: Optional[str] = None,
        provider_model: Optional[str] = None,
        force: bool = False,
        source_language: str | None = None,
        target_language: str | None = None,
        glossary: Any | None = None,
        style_preset: str | None = None,
        consistency_mode: bool = False,
        json_output: bool = False,
    ) -> None:
        source = self._source_factory(source_key)
        meta = self.storage.load_metadata(novel_id)
        if not meta:
            raise RuntimeError("Metadata not found; run scrape-metadata first.")

        effective_source_language = source_language or self._infer_source_language(source_key, meta)
        effective_target_language = target_language or settings.TRANSLATION_TARGET_LANGUAGE

        chapter_map = {int(c["id"]): c for c in meta.get("chapters", [])}
        selected_numbers = self._selected_chapter_numbers(meta, chapters)

        for chapter_num in selected_numbers:
            chapter = chapter_map.get(chapter_num)
            if not chapter:
                continue

            existing = self.storage.load_translated_chapter(novel_id, str(chapter_num))
            if existing and not force:
                continue

            result = await self.translation.translate_chapter(
                source_adapter=source,
                chapter_url=chapter["url"],
                provider_key=provider_key,
                provider_model=provider_model,
                source_language=effective_source_language,
                target_language=effective_target_language,
                glossary=glossary,
                style_preset=style_preset,
                consistency_mode=consistency_mode,
                json_output=json_output,
            )
            translated = result.final_text or ""
            self.storage.save_translated_chapter(
                novel_id,
                str(chapter_num),
                translated,
                provider=result.provider_key,
                model=result.provider_model,
            )
