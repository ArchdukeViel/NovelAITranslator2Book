from __future__ import annotations

import asyncio
import contextlib
import logging
import re
from collections.abc import Callable
from typing import Any

from novelai.core.errors import SourceError
from novelai.db.engine import session_scope
from novelai.db.models.novel import Novel
from novelai.glossary import extract_candidate_glossary_terms
from novelai.prompts import METADATA_TRANSLATION_PROMPT_VERSION
from novelai.services.catalog_service import safely_refresh_catalog_projection_after_storage_write
from novelai.services.glossary_repository import GlossaryRepository
from novelai.services.library_summary_service import best_effort_invalidate, invalidate_library_summary_cache
from novelai.sources.quality import (
    chapter_content_hash,
    evaluate_chapter_quality,
    evaluate_metadata_quality,
)

logger = logging.getLogger(__name__)

# In-process per-novel crawl lock registry.
# Keys are "source_key:novel_id", values are asyncio.Lock instances.
# This prevents concurrent scrapes of the same novel from corrupting storage.
_crawl_locks: dict[str, asyncio.Lock] = {}
_METADATA_TRANSLATION_UNAVAILABLE_MESSAGE = (
    "Metadata translation skipped because no active Gemini provider is configured."
)
_METADATA_TRANSLATION_ERROR_MAX_CHARS = 500


def _get_crawl_lock(source_key: str, novel_id: str) -> asyncio.Lock:
    """Get or create a per-novel crawl lock."""
    lock_key = f"{source_key}:{novel_id}"
    if lock_key not in _crawl_locks:
        _crawl_locks[lock_key] = asyncio.Lock()
    return _crawl_locks[lock_key]


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


def _metadata_translation_config(self: Any) -> dict[str, str]:
    try:
        provider_key, provider_model = self._resolve_provider_and_model(None, None)
    except Exception:
        return {}
    if provider_key == "dummy":
        return {}
    return {
        "metadata_translation_provider": str(provider_key),
        "metadata_translation_model": str(provider_model),
    }


def _bounded_metadata_translation_error(exc: Exception) -> str:
    message = str(exc).strip() or exc.__class__.__name__
    if len(message) <= _METADATA_TRANSLATION_ERROR_MAX_CHARS:
        return message
    return f"{message[:_METADATA_TRANSLATION_ERROR_MAX_CHARS - 3]}..."


def _mark_metadata_translation_failure(meta: dict[str, Any], exc: Exception, *, config: dict[str, str]) -> None:
    meta["metadata_translation_prompt_version"] = METADATA_TRANSLATION_PROMPT_VERSION
    if _METADATA_TRANSLATION_UNAVAILABLE_MESSAGE in str(exc):
        meta["metadata_translation_status"] = "unavailable"
        meta.pop("metadata_translation_error", None)
        return
    meta.update(config)
    meta["metadata_translation_status"] = "failed"
    meta["metadata_translation_error"] = _bounded_metadata_translation_error(exc)


async def _translate_and_mark_metadata(
    self: Any,
    meta: dict[str, Any],
    existing_metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    config = _metadata_translation_config(self)
    try:
        translated = await self._translate_metadata_fields(meta, existing_metadata)
    except Exception as exc:
        logger.warning("Failed to translate metadata for %s: %s", meta.get("context_group_id") or meta.get("novel_id"), exc)
        _mark_metadata_translation_failure(meta, exc, config=config)
        return meta

    translated.update(config)
    translated["metadata_translation_status"] = "completed"
    translated.pop("metadata_translation_error", None)
    return translated


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


def _bootstrap_source_texts(storage: Any, novel_id: str, meta: dict[str, Any]) -> list[str]:
    texts: list[str] = []
    list_chapters = getattr(storage, "list_stored_chapters", None)
    load_chapter = getattr(storage, "load_chapter", None)
    if callable(list_chapters) and callable(load_chapter):
        with contextlib.suppress(Exception):
            chapter_ids = list_chapters(novel_id)
            if isinstance(chapter_ids, list):
                for chapter_id in chapter_ids:
                    chapter = load_chapter(novel_id, str(chapter_id))
                    text = chapter.get("text") if isinstance(chapter, dict) else None
                    if isinstance(text, str) and text.strip():
                        texts.append(text)
    if texts:
        return texts

    for key in ("title", "translated_title", "author", "synopsis", "description", "summary"):
        value = meta.get(key)
        if isinstance(value, str) and value.strip():
            texts.append(value)
    for chapter in meta.get("chapters") or []:
        if not isinstance(chapter, dict):
            continue
        title = chapter.get("title") or chapter.get("translated_title")
        if isinstance(title, str) and title.strip():
            texts.append(title)
    return texts


async def bootstrap_glossary_if_needed(self: Any, novel_id: str, meta: dict[str, Any]) -> int:
    """Seed DB glossary candidates during onboarding without making it fatal."""
    try:
        texts = _bootstrap_source_texts(self.storage, novel_id, meta)
        candidates = extract_candidate_glossary_terms(texts, max_terms=50) if texts else []
        added = 0
        with session_scope() as session:
            novel = session.query(Novel).filter_by(slug=novel_id).one_or_none()
            if novel is None:
                return 0
            if novel.glossary_status == "glossary_ready":
                return 0
            novel.glossary_status = "glossary_pending"
            repository = GlossaryRepository(session)
            existing = {
                entry.canonical_term.casefold()
                for entry in repository.list_glossary_entries_for_novel(novel.id)
            }
            for candidate in candidates:
                canonical = candidate.source.strip()
                if not canonical or canonical.casefold() in existing:
                    continue
                repository.create_glossary_entry(
                    novel_id=novel.id,
                    canonical_term=canonical,
                    term_type="other",
                    approved_translation=None,
                    status="candidate",
                    confidence=None,
                    admin_notes=candidate.context_summary or candidate.notes,
                    actor_user_id=None,
                    decision_source="glossary_bootstrap",
                    rationale="Automatic glossary bootstrap during novel onboarding.",
                )
                existing.add(canonical.casefold())
                added += 1
            if added == 0:
                logger.warning("Glossary bootstrap found no candidates for %s.", novel_id)
        return added
    except Exception as exc:
        logger.warning("Glossary bootstrap failed for %s: %s", novel_id, exc.__class__.__name__)
        return 0


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
        # Destructive deletion: invalidate cache immediately so the Admin
        # Library does not continue reporting the deleted inventory.
        best_effort_invalidate()

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

    meta = await _translate_and_mark_metadata(self, meta, existing_metadata)
    self.storage.save_metadata(novel_id, meta)
    safely_refresh_catalog_projection_after_storage_write(
        novel_id,
        self.storage,
        context="scrape_metadata",
    )
    # Replacement metadata can change the discovered chapter total; invalidate.
    try:
        invalidate_library_summary_cache()
    except Exception:
        logger.debug("Library summary cache invalidation failed (non-fatal)", exc_info=True)
    meta["bootstrap_candidate_count"] = await bootstrap_glossary_if_needed(self, novel_id, meta)
    if meta.get("chapters"):
        self.storage.update_onboarding_status(novel_id, "chapters_pending")
        meta["onboarding_status"] = "chapters_pending"
        meta["body_scrape_required"] = True
    else:
        self.storage.update_onboarding_status(novel_id, "metadata_discovered")
        meta["onboarding_status"] = "metadata_discovered"
        meta["body_scrape_required"] = False
    logger.info(f"Metadata scraped: {len(meta)} fields saved")
    if progress_callback:
        progress_callback(f"Metadata saved ({len(meta)} fields).")
    return meta


def _extract_http_status(exc: Exception) -> int | None:
    if hasattr(exc, "response"):
        try:
            response = exc.response  # type: ignore[attr-defined]
        except AttributeError:
            response = None
        status_code = getattr(response, "status_code", None) if response is not None else None
        if isinstance(status_code, int):
            return status_code
    status_code = getattr(exc, "status_code", None)
    if isinstance(status_code, int):
        return status_code
    message = str(exc)
    for pattern in (r"\bstatus=(\d{3})\b", r"\bstatus_code=(\d{3})\b", r"\bHTTP\s+(\d{3})\b", r"\b(429|404|5\d\d)\b"):
        match = re.search(pattern, message, re.IGNORECASE)
        if match:
            return int(match.group(1))
    return None


def _is_quality_gate_error(exc: Exception, msg: str) -> bool:
    return isinstance(exc, SourceError) and msg.startswith("Chapter quality gate failed")


def _classify_error(exc: Exception, error_message: str, http_status_code: int | None = None) -> str:
    msg = error_message.lower()
    if _is_quality_gate_error(exc, error_message):
        return "quality_gate"
    if http_status_code == 429 or "rate limit" in msg or "rate_limited" in msg:
        return "rate_limited"
    if http_status_code == 404 or "not found" in msg:
        return "not_found"
    if "timeout" in msg:
        return "timeout"
    if http_status_code is not None and 500 <= http_status_code <= 599:
        return "server_error"
    if isinstance(exc, SourceError):
        return "fetch_error"
    return "unknown"


async def scrape_chapters(
    self: Any,
    source_key: str,
    novel_id: str,
    chapters: str,
    mode: str = "update",
    progress_callback: Callable[[str], None] | None = None,
    cancellation_check: Callable[[], bool] | None = None,
) -> dict[str, Any]:
    """Fetch chapter content from the source site and persist it.

    In ``full`` mode, existing data is deleted before re-scraping.
    In ``update`` mode (default), only new or changed chapters are fetched.
    Chapters are identified by the *chapters* selection string (e.g.
    ``"all"`` or ``"1-5"``).

    Returns a summary dict with ``succeeded``, ``skipped``, ``failed`` counts
    and a ``failures`` list describing each failed chapter. Per-chapter
    failures are non-fatal; metadata/list-level failures still raise.

    Raises ``RuntimeError`` if another scrape is already in progress for the
    same source_key + novel_id combination.
    Raises ``asyncio.CancelledError`` if *cancellation_check* returns True.
    """
    lock = _get_crawl_lock(source_key, novel_id)
    if lock.locked():
        raise RuntimeError(
            f"A scrape is already in progress for {source_key}/{novel_id}. "
            "Wait for it to finish before starting another."
        )

    async with lock:
        result = await _scrape_chapters_impl(
            self, source_key, novel_id, chapters, mode, progress_callback, cancellation_check
        )

    if result["succeeded"] > 0:
        self.storage.update_onboarding_status(novel_id, "ready_for_translation")
    elif result["failed"] > 0 and result["succeeded"] == 0:
        self.storage.update_onboarding_status(
            novel_id,
            "failed",
            error_code="scrape_completed_without_chapters",
            error_message="Chapter scrape finished without saving any usable raw chapters.",
        )

    return result


async def _scrape_chapters_impl(
    self: Any,
    source_key: str,
    novel_id: str,
    chapters: str,
    mode: str,
    progress_callback: Callable[[str], None] | None,
    cancellation_check: Callable[[], bool] | None = None,
) -> dict[str, Any]:
    """Internal implementation of scrape_chapters (called under lock)."""
    source = self._source_factory(source_key)

    self.storage.update_onboarding_status(novel_id, "scraping_chapters", clear_error=True)

    if mode == "full":
        self.storage.delete_novel(novel_id)
        # Destructive deletion: invalidate immediately. If later work
        # fails, the cache still reflects the absent storage.
        best_effort_invalidate()
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
        meta = await _translate_and_mark_metadata(self, meta)
        self.storage.save_metadata(novel_id, meta)
        safely_refresh_catalog_projection_after_storage_write(
            novel_id,
            self.storage,
            context="scrape_chapters_metadata",
        )
        # Replacement metadata may have changed discovered total.
        best_effort_invalidate()
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
    retry_attempts = [0]
    image_download_failures = 0

    for _chapter_index, chapter_num in enumerate(selected_numbers):
        if cancellation_check is not None and cancellation_check():
            raise asyncio.CancelledError(f"Scrape cancelled for {source_key}/{novel_id}")
        chapter = chapter_map.get(chapter_num)
        if not chapter:
            continue

        chapter_id = str(chapter_num)
        if progress_callback:
            _ch_title = str(chapter.get("title") or f"Chapter {chapter_id}")
            progress_callback(f"[{_chapter_index + 1}/{_total_chapters}] {_ch_title}")

        def _on_retry(retry_number: int, exc: Exception) -> None:
            retry_attempts[0] = retry_number

        try:
            payload = await source.fetch_chapter_payload(chapter["url"], on_retry=_on_retry)
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
                source_blocks=payload.get("source_blocks") if isinstance(payload.get("source_blocks"), list) else None,
                input_adapter_key="web",
                origin_type="url",
                origin_uri_or_path=str(chapter.get("url") or meta.get("source_url") or novel_id),
                document_type="web_novel",
                unit_type="chapter",
                import_order=chapter_num,
                context_group_id=novel_id,
            )
            safely_refresh_catalog_projection_after_storage_write(
                novel_id,
                self.storage,
                context="scrape_chapter",
            )
            # Invalidate library summary cache after successful storage write
            best_effort_invalidate()
            if progress_callback:
                progress_callback(f"  Saved chapter {chapter_id}.")
            if any(img.get("download_error") for img in downloaded_images):
                image_download_failures += 1
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

            http_status_code = _extract_http_status(exc)
            failures.append({
                "chapter_id": chapter_id,
                "chapter_number": chapter_num,
                "title": chapter.get("title"),
                "source_url": chapter.get("url"),
                "error_type": error_type,
                "error_message": error_message,
                "error_category": _classify_error(exc, error_message, http_status_code),
                "http_status_code": http_status_code,
                "retry_attempts": retry_attempts[0],
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
        "image_download_failures": image_download_failures,
    }
