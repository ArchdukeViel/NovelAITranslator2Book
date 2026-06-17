from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

from novelai.core.errors import SourceError
from novelai.sources.quality import (
    chapter_content_hash,
    evaluate_chapter_quality,
    evaluate_metadata_quality,
)

logger = logging.getLogger(__name__)


def _apply_metadata_quality_gate(meta: dict[str, Any], *, source_key: str, novel_id: str) -> dict[str, Any]:
    meta.setdefault("source_key", source_key)
    meta.setdefault("source", source_key)
    quality = evaluate_metadata_quality(meta, source_key=source_key, novel_id=novel_id)
    meta["source_quality"] = quality.to_dict()
    if quality.warnings:
        logger.warning("Metadata quality warnings for %s/%s: %s", source_key, novel_id, quality.warnings)
    if quality.errors:
        raise SourceError(f"Metadata quality gate failed for {source_key}/{novel_id}: {', '.join(quality.errors)}")
    return meta


def _stored_chapter_hashes(storage: Any, novel_id: str, *, exclude_chapter_id: str) -> set[str]:
    hashes: set[str] = set()
    list_chapters = getattr(storage, "list_stored_chapters", None)
    if not callable(list_chapters):
        return hashes
    load_chapter = getattr(storage, "load_chapter", None)
    if not callable(load_chapter):
        return hashes
    stored_chapter_ids = list_chapters(novel_id)
    if not isinstance(stored_chapter_ids, list):
        return hashes
    for chapter_id in stored_chapter_ids:
        if str(chapter_id) == exclude_chapter_id:
            continue
        chapter = load_chapter(novel_id, str(chapter_id))
        text = chapter.get("text") if isinstance(chapter, dict) else None
        if isinstance(text, str) and text.strip():
            hashes.add(chapter_content_hash(text))
    return hashes

async def scrape_metadata(
    self: Any,
    source_key: str,
    novel_id: str,
    mode: str = "update",
    max_chapter: int | None = None,
    source_identifier: str | None = None,
    progress_callback: Callable[[str], None] | None = None,
) -> dict[str, Any]:
    logger.info(f"Scraping metadata for {novel_id} from {source_key} (mode={mode})")
    existing_metadata = self.storage.load_metadata(novel_id) if mode != "full" else None
    if mode == "full":
        logger.debug(f"Full scrape mode - deleting existing data for {novel_id}")
        self.storage.delete_novel(novel_id)

    if progress_callback:
        progress_callback(f"Connecting to {source_key}\u2026")
    source = self._source_factory(source_key)
    fetch_target = source_identifier.strip() if isinstance(source_identifier, str) and source_identifier.strip() else novel_id
    meta = await source.fetch_metadata(fetch_target, max_chapter=max_chapter)
    meta = _apply_metadata_quality_gate(meta, source_key=source_key, novel_id=novel_id)
    if progress_callback:
        chapter_count = len(meta.get("chapters") or [])
        progress_callback(f"Fetched: {str(meta.get('title') or novel_id)!r}  ({chapter_count} chapters listed)")

    # Persist detected source language so prompts and exports can use it.
    if not meta.get("source_language"):
        detected = self._infer_source_language(source_key, meta)
        if detected:
            meta["source_language"] = detected
    meta.setdefault("origin_type", "url")
    meta.setdefault("origin_uri_or_path", str(meta.get("source_url") or fetch_target))
    meta.setdefault("document_type", "web_novel")
    meta.setdefault("input_adapter_key", "web")
    meta.setdefault("context_group_id", novel_id)

    try:
        meta = await self._translate_metadata_fields(meta, existing_metadata)
        meta["metadata_translation_status"] = "completed"
    except Exception as exc:
        logger.warning("Failed to translate metadata for %s: %s", novel_id, exc)
        meta["metadata_translation_status"] = "failed"
        meta["metadata_translation_error"] = str(exc)
    self.storage.save_metadata(novel_id, meta)
    logger.info(f"Metadata scraped: {len(meta)} fields saved")
    if progress_callback:
        progress_callback(f"Metadata saved ({len(meta)} fields).")
    return meta


async def scrape_chapters(
    self: Any,
    source_key: str,
    novel_id: str,
    chapters: str,
    mode: str = "update",
    progress_callback: Callable[[str], None] | None = None,
) -> dict[str, Any]:
    """Fetch chapter content from the source site and persist it.

    In ``full`` mode, existing data is deleted before re-scraping.
    In ``update`` mode (default), only new or changed chapters are fetched.
    Chapters are identified by the *chapters* selection string (e.g.
    ``"all"`` or ``"1-5"``).

    Returns a summary dict with ``succeeded``, ``skipped``, ``failed`` counts
    and a ``failures`` list describing each failed chapter. Per-chapter
    failures are non-fatal; metadata/list-level failures still raise.
    """
    source = self._source_factory(source_key)

    if mode == "full":
        self.storage.delete_novel(novel_id)
        meta = await source.fetch_metadata(novel_id)
        meta = _apply_metadata_quality_gate(meta, source_key=source_key, novel_id=novel_id)
        if not meta.get("source_language"):
            detected = self._infer_source_language(source_key, meta)
            if detected:
                meta["source_language"] = detected
        meta.setdefault("origin_type", "url")
        meta.setdefault("origin_uri_or_path", str(meta.get("source_url") or novel_id))
        meta.setdefault("document_type", "web_novel")
        meta.setdefault("input_adapter_key", "web")
        meta.setdefault("context_group_id", novel_id)
        try:
            meta = await self._translate_metadata_fields(meta)
            meta["metadata_translation_status"] = "completed"
        except Exception as exc:
            logger.warning("Failed to translate metadata for %s: %s", novel_id, exc)
            meta["metadata_translation_status"] = "failed"
            meta["metadata_translation_error"] = str(exc)
        self.storage.save_metadata(novel_id, meta)
    else:
        meta = self.storage.load_metadata(novel_id)
        if not meta:
            raise RuntimeError("Metadata not found; run scrape-metadata first.")

    chapter_map = {int(c["id"]): c for c in meta.get("chapters", [])}
    selected_numbers = self._selected_chapter_numbers(meta, chapters)
    _total_chapters = len(selected_numbers)
    if progress_callback:
        progress_callback(f"Preparing to scrape {_total_chapters} chapter(s)…")

    succeeded = 0
    skipped = 0
    failed = 0
    failures: list[dict[str, Any]] = []

    for _chapter_index, chapter_num in enumerate(selected_numbers):
        chapter = chapter_map.get(chapter_num)
        if not chapter:
            continue

        chapter_id = str(chapter_num)
        if progress_callback:
            _ch_title = str(chapter.get("title") or f"Chapter {chapter_id}")
            progress_callback(f"[{_chapter_index + 1}/{_total_chapters}] {_ch_title}")

        try:
            payload = await source.fetch_chapter_payload(chapter["url"])
            text = payload.get("text")
            if not isinstance(text, str):
                raise RuntimeError(f"Source returned invalid chapter text for {chapter['url']}.")

            images = payload.get("images")
            image_manifest = [image for image in images if isinstance(image, dict)] if isinstance(images, list) else []
            quality = evaluate_chapter_quality(
                text,
                source_key=source_key,
                url=chapter.get("url") if isinstance(chapter.get("url"), str) else None,
                images=image_manifest,
                duplicate_hashes=_stored_chapter_hashes(self.storage, novel_id, exclude_chapter_id=chapter_id),
            )
            if quality.warnings:
                logger.warning(
                    "Chapter quality warnings for %s/%s/%s: %s",
                    source_key,
                    novel_id,
                    chapter_id,
                    quality.warnings,
                )
                if progress_callback:
                    progress_callback(f"  Quality warnings: {', '.join(quality.warnings)}")
            if quality.errors:
                raise SourceError(
                    f"Chapter quality gate failed for {source_key}/{novel_id}/{chapter_id}: "
                    + ", ".join(quality.errors)
                )

            existing = self.storage.load_chapter(novel_id, chapter_id) or {}
            existing_text = existing.get("text")
            existing_images = existing.get("images") if isinstance(existing.get("images"), list) else []
            existing_signature = self._chapter_content_signature(
                existing_text if isinstance(existing_text, str) else "",
                existing_images,
            )
            new_signature = self._chapter_content_signature(text, image_manifest)

            if mode == "update" and existing_signature == new_signature:
                if progress_callback:
                    progress_callback(f"  Chapter {chapter_id}: unchanged, skipping.")
                skipped += 1
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
                input_adapter_key="web",
                origin_type="url",
                origin_uri_or_path=str(chapter.get("url") or meta.get("source_url") or novel_id),
                document_type="web_novel",
                unit_type="chapter",
                import_order=chapter_num,
                context_group_id=novel_id,
            )
            if progress_callback:
                progress_callback(f"  Saved chapter {chapter_id}.")
            succeeded += 1

        except (SourceError, RuntimeError, Exception) as exc:
            error_type = type(exc).__name__
            error_message = str(exc) if str(exc) else error_type
            # Sanitize: remove stack traces, limit length
            if "\nTraceback" in error_message:
                error_message = error_message.split("\nTraceback")[0]
            error_message = error_message[:500]

            logger.warning(
                "Chapter %s/%s/%s failed (%s): %s",
                source_key, novel_id, chapter_id, error_type, error_message,
            )
            if progress_callback:
                progress_callback(
                    f"  Chapter {chapter_id} failed ({error_type}): {error_message}"
                )

            failures.append({
                "chapter_id": chapter_id,
                "chapter_number": chapter_num,
                "title": chapter.get("title"),
                "source_url": chapter.get("url"),
                "error_type": error_type,
                "error_message": error_message,
            })
            failed += 1

    if progress_callback:
        if failures:
            progress_callback(
                f"Scrape finished with partial success: {succeeded} saved, "
                f"{skipped} skipped, {failed} failed."
            )
        else:
            progress_callback(
                f"Scrape finished: {succeeded} saved, {skipped} skipped."
            )

    return {
        "succeeded": succeeded,
        "skipped": skipped,
        "failed": failed,
        "failures": failures,
    }
