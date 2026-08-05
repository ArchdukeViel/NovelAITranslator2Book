from __future__ import annotations

import asyncio
import contextlib
import hashlib
import json
import logging
import re
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from novelai.core.errors import ProviderConfigError, SourceError
from novelai.db.engine import session_scope
from novelai.db.models.novel import Novel
from novelai.glossary import extract_candidate_glossary_terms
from novelai.prompts import METADATA_TRANSLATION_PROMPT_VERSION
from novelai.services.catalog_service import safely_refresh_catalog_projection_after_storage_write
from novelai.services.glossary_repository import GlossaryRepository
from novelai.services.library_summary_service import best_effort_invalidate
from novelai.services.orchestration.planner import create_crawl_plan, update_source_state
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

# Terminal statuses for crawl results. A crawl that saved some chapters but
# failed others is *not* a plain success or a total failure: it is reported
# as ``completed_with_errors`` so callers and source health reflect the
# partial outcome.
TERMINAL_STATUS_COMPLETED = "completed"
TERMINAL_STATUS_COMPLETED_WITH_WARNINGS = "completed_with_warnings"
TERMINAL_STATUS_COMPLETED_WITH_ERRORS = "completed_with_errors"
TERMINAL_STATUS_FAILED = "failed"
CRAWL_TERMINAL_STATUSES = frozenset(
    {
        TERMINAL_STATUS_COMPLETED,
        TERMINAL_STATUS_COMPLETED_WITH_WARNINGS,
        TERMINAL_STATUS_COMPLETED_WITH_ERRORS,
        TERMINAL_STATUS_FAILED,
    }
)

# Progress-reporting stages of a crawl run.
STAGE_METADATA_CRAWL = "metadata_crawl"
STAGE_INDEX_CRAWL = "index_crawl"
STAGE_BODY_CRAWL = "body_crawl"
STAGE_ASSETS = "assets"
STAGE_STORAGE_COMMIT = "storage_commit"
STAGE_RECONCILIATION = "reconciliation"


@dataclass(frozen=True)
class CrawlProgressEvent:
    """Structured crawl progress event.

    ``completed`` is monotonic and only increments when a real unit (chapter,
    index page, or stage) reaches a terminal outcome. Labels and arbitrary
    log messages never change the numeric progress.
    """

    stage: str
    status: str
    completed: int
    total: int | None = None
    source_episode_id: str | None = None
    label: str | None = None
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "stage": self.stage,
            "status": self.status,
            "completed": self.completed,
        }
        if self.total is not None:
            payload["total"] = self.total
        if self.source_episode_id is not None:
            payload["source_episode_id"] = self.source_episode_id
        if self.label is not None:
            payload["label"] = self.label
        if self.details:
            payload["details"] = self.details
        return payload


def crawl_terminal_status(*, succeeded: int, skipped: int, failed: int, image_download_failures: int) -> str:
    """Derive the terminal status of a chapter crawl from its counts."""
    if failed > 0:
        return TERMINAL_STATUS_COMPLETED_WITH_ERRORS
    if image_download_failures > 0 or (succeeded == 0 and skipped > 0):
        return TERMINAL_STATUS_COMPLETED_WITH_WARNINGS
    return TERMINAL_STATUS_COMPLETED


def _json_hash(value: Any) -> str:
    """SHA256 of a JSON-stable serialization (used for manifest hashes)."""
    return hashlib.sha256(
        json.dumps(value, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")
    ).hexdigest()


def _get_crawl_lock(source_key: str, novel_id: str) -> asyncio.Lock:
    """Get or create a per-novel crawl lock."""
    lock_key = f"{source_key}:{novel_id}"
    if lock_key not in _crawl_locks:
        _crawl_locks[lock_key] = asyncio.Lock()
    return _crawl_locks[lock_key]


def _apply_metadata_quality_gate(meta: dict[str, Any], *, source_key: str, novel_id: str) -> dict[str, Any]:
    meta.setdefault("source_key", source_key)
    meta.setdefault("source_novel_id", novel_id)
    quality = evaluate_metadata_quality(meta, source_key=source_key)
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
    return f"{message[: _METADATA_TRANSLATION_ERROR_MAX_CHARS - 3]}..."


def _mark_metadata_translation_failure(meta: dict[str, Any], exc: Exception, *, config: dict[str, str]) -> None:
    meta["metadata_translation_prompt_version"] = METADATA_TRANSLATION_PROMPT_VERSION
    if isinstance(exc, ProviderConfigError) or _METADATA_TRANSLATION_UNAVAILABLE_MESSAGE in str(exc):
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
        logger.warning(
            "Failed to translate metadata for %s: %s", meta.get("context_group_id") or meta.get("novel_id"), exc
        )
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
                entry.canonical_term.casefold() for entry in repository.list_glossary_entries_for_novel(novel.id)
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
    progress_events_callback: Callable[[CrawlProgressEvent], None] | None = None,
) -> dict[str, Any]:
    """Scrape novel metadata from the source and persist it.

    ``progress_callback`` receives human-readable labels only and never
    drives numeric progress. ``progress_events_callback`` receives structured
    :class:`CrawlProgressEvent` records whose ``completed`` counter increments
    only on real unit completion.
    """
    logger.info(f"Scraping metadata for {novel_id} from {source_key} (mode={mode})")

    def _emit(stage: str, status: str, completed: int, total: int | None, label: str | None = None) -> None:
        if progress_events_callback is not None:
            progress_events_callback(
                CrawlProgressEvent(
                    stage=stage,
                    status=status,
                    completed=completed,
                    total=total,
                    label=label,
                )
            )

    existing_metadata = self.storage.load_metadata(novel_id) if mode != "full" else None

    if progress_callback:
        progress_callback(f"Connecting to {source_key}\u2026")
    _emit(STAGE_METADATA_CRAWL, "started", 0, None, f"Connecting to {source_key}")
    source = self._source_factory(source_key)
    fetch_target = (
        source_identifier.strip() if isinstance(source_identifier, str) and source_identifier.strip() else novel_id
    )
    meta = await source.fetch_metadata(fetch_target, max_chapter=max_chapter)
    meta = _apply_metadata_quality_gate(meta, source_key=source_key, novel_id=novel_id)
    _emit(STAGE_METADATA_CRAWL, "completed", 1, 1, "Metadata fetched")
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
    best_effort_invalidate(context="scrape_metadata")
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
    _emit(STAGE_STORAGE_COMMIT, "completed", 1, 1, "Metadata saved")
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
    progress_events_callback: Callable[[CrawlProgressEvent], None] | None = None,
) -> dict[str, Any]:
    """Fetch chapter content from the source site and persist it.

    In ``full`` mode, existing data is deleted before re-scraping.
    In ``update`` mode (default), only new or changed chapters are fetched.
    Chapters are identified by the *chapters* selection string (e.g.
    ``"all"`` or ``"1-5"``).

    Returns a summary dict with ``succeeded``, ``skipped``, ``failed`` counts,
    a ``failures`` list describing each failed chapter, and a
    ``terminal_status`` (``completed``, ``completed_with_warnings``,
    ``completed_with_errors``, or ``failed``). Per-chapter failures are
    non-fatal; metadata/list-level failures still raise.

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
            self,
            source_key,
            novel_id,
            chapters,
            mode,
            progress_callback,
            cancellation_check,
            progress_events_callback,
        )

    terminal_status = result.get("terminal_status", TERMINAL_STATUS_FAILED)
    if terminal_status in (TERMINAL_STATUS_COMPLETED, TERMINAL_STATUS_COMPLETED_WITH_WARNINGS):
        self.storage.update_onboarding_status(novel_id, "ready_for_translation")
    elif terminal_status == TERMINAL_STATUS_COMPLETED_WITH_ERRORS or (result["failed"] > 0 and result["succeeded"] > 0):
        self.storage.update_onboarding_status(
            novel_id,
            "partially_scraped",
            error_code="scrape_completed_with_errors",
            error_message=f"Chapter scrape completed with errors: {result['succeeded']} succeeded, {result['failed']} failed.",
        )
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
    progress_events_callback: Callable[[CrawlProgressEvent], None] | None = None,
) -> dict[str, Any]:
    """Internal implementation of scrape_chapters (called under lock).

    ``progress_callback`` is a label-only channel; numeric progress is
    reported through ``progress_events_callback`` via
    :class:`CrawlProgressEvent` records. Only the terminal processing of a
    chapter increments ``completed``, and the value never exceeds ``total``.
    """
    source = self._source_factory(source_key)

    def _emit(
        stage: str,
        status: str,
        completed: int,
        total: int | None,
        source_episode_id: str | None = None,
        label: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        if progress_events_callback is None:
            return
        progress_events_callback(
            CrawlProgressEvent(
                stage=stage,
                status=status,
                completed=completed,
                total=total,
                source_episode_id=source_episode_id,
                label=label,
                details=details or {},
            )
        )

    self.storage.update_onboarding_status(novel_id, "scraping_chapters", clear_error=True)

    if mode == "full":
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

    chapter_map = {int(c.get("num") or idx + 1): c for idx, c in enumerate(meta.get("chapters", []))}
    selected_numbers = self._selected_chapter_numbers(meta, chapters)
    selected_chapters_list = [chapter_map[num] for num in selected_numbers if num in chapter_map]
    _total_chapters = len(selected_chapters_list)
    if progress_callback:
        progress_callback(f"Preparing to scrape {_total_chapters} chapter(s)…")

    succeeded = 0
    skipped = 0
    failed = 0
    failures: list[dict[str, Any]] = []
    image_download_failures = 0
    scraped_chapters_for_state: list[dict[str, Any]] = []
    existing_source_state = self.storage.load_source_state(novel_id)

    existing_chapters_map = {
        ch_id: (self.storage.load_chapter(novel_id, ch_id) or {})
        for ch_id in [str(c.get("id") or c.get("num")) for c in selected_chapters_list]
    }
    crawl_plan = create_crawl_plan(
        novel_id,
        selected_chapters_list,
        existing_source_state,
        existing_chapters_map,
        mode=mode,
        all_chapters=meta.get("chapters", []),
    )

    # Staged generation (DEBT-GEN-01): all crawl writes go into a generation
    # snapshot and become visible only after commit_generation swaps the
    # active_generation.json pointer (manifest written last). On any hard
    # failure the stage is rolled back and the previous active state stays.
    generation_id = f"gen-{uuid.uuid4().hex[:12]}"
    self.storage.create_generation_stage(
        novel_id,
        generation_id,
        source_key=source_key,
        source_work_id=str(meta.get("source_novel_id") or novel_id),
        mode=mode,
        expected_chapters=_total_chapters,
        metadata_fingerprint=str(meta.get("metadata_fingerprint") or ""),
        index_fingerprint=str(meta.get("index_fingerprint") or ""),
    )

    # Build stored chapter hash cache once before chapter loop to avoid O(n^2) disk re-scans
    cached_stored_hashes = _stored_chapter_hashes(self.storage, novel_id, exclude_chapter_id="")

    # Seed the stage with bundles the planner marks reusable (not refetched),
    # so the activated snapshot is complete (raw + translations + images).
    seed_targets = [
        str(ch.get("id") or ch.get("num"))
        for ch in selected_chapters_list
        if str(ch.get("source_episode_id") or ch.get("id") or ch.get("num")) in crawl_plan.reusable_episode_ids
    ]
    if seed_targets:
        self.storage.seed_generation_from_active(novel_id, generation_id, seed_targets)

    _emit(
        STAGE_INDEX_CRAWL,
        "started",
        0,
        _total_chapters,
        label="Preparing chapter crawl",
        details=crawl_plan.plan_reason,
    )

    try:
        for _chapter_index, chapter_num in enumerate(selected_numbers):
            if cancellation_check is not None and cancellation_check():
                raise asyncio.CancelledError(f"Scrape cancelled for {source_key}/{novel_id}")
            chapter = chapter_map.get(chapter_num)
            if not chapter:
                continue

            chapter_id = str(chapter.get("id") or chapter_num)
            ep_id = str(chapter.get("source_episode_id") or chapter_id)

            # Operationalized Crawl Plan Check: skip HTTP fetch when planner marked chapter reusable!
            if (
                mode != "full"
                and ep_id in crawl_plan.reusable_episode_ids
                and ep_id not in crawl_plan.chapters_to_fetch_set
            ):
                skipped += 1
                existing = existing_chapters_map.get(chapter_id) or {}
                scraped_chapters_for_state.append(
                    {
                        **chapter,
                        "id": chapter_id,
                        "source_episode_id": ep_id,
                        "content_hash": existing.get("content_hash"),
                    }
                )
                if progress_callback:
                    progress_callback(
                        f"[{_chapter_index + 1}/{_total_chapters}] Chapter {chapter_id}: reused via planner"
                    )
                _emit(
                    STAGE_BODY_CRAWL,
                    "reused",
                    succeeded + skipped + failed,
                    _total_chapters,
                    source_episode_id=ep_id,
                    label=f"Chapter {chapter_id}: reused",
                )
                continue
            # Retry telemetry is per-chapter: a retry performed for an earlier
            # chapter must never leak into the attempt count of a later chapter.
            retry_attempts = [0]
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
                image_manifest = (
                    [image for image in images if isinstance(image, dict)] if isinstance(images, list) else []
                )
                quality = evaluate_chapter_quality(
                    text,
                    source_key=source_key,
                    url=chapter.get("url") if isinstance(chapter.get("url"), str) else None,
                    images=image_manifest,
                    duplicate_hashes=cached_stored_hashes,
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
                    # Carry the existing bundle (raw + translations + images)
                    # forward into the staged snapshot.
                    self.storage.seed_generation_from_active(novel_id, generation_id, [chapter_id])
                    skipped += 1
                    _emit(
                        STAGE_BODY_CRAWL,
                        "skipped",
                        succeeded + skipped + failed,
                        _total_chapters,
                        source_episode_id=chapter_id,
                        label=f"Chapter {chapter_id}: unchanged",
                    )
                    continue

                downloaded_images: list[dict[str, Any]] = []
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
                        stored_asset = self.storage.stage_generation_image(
                            novel_id,
                            generation_id,
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

                chapter_payload = self.storage.build_chapter_payload(
                    novel_id,
                    chapter_id,
                    text,
                    source_key=source_key,
                    source_url=chapter.get("url"),
                    images=downloaded_images,
                    source_blocks=payload.get("source_blocks")
                    if isinstance(payload.get("source_blocks"), list)
                    else None,
                    input_adapter_key="web",
                    origin_type="url",
                    origin_uri_or_path=str(chapter.get("url") or meta.get("source_url") or novel_id),
                    document_type="web_novel",
                    unit_type="chapter",
                    import_order=chapter_num,
                    context_group_id=novel_id,
                )
                raw_block = chapter_payload.get("raw") if isinstance(chapter_payload.get("raw"), dict) else {}
                self.storage.stage_generation_chapter(
                    novel_id,
                    generation_id,
                    chapter_id,
                    chapter_payload,
                    source_hash=new_signature,
                    structure_hash=_json_hash(raw_block.get("source_blocks") or []),
                    image_manifest_hash=_json_hash(downloaded_images),
                    parser_version=str(meta.get("chapter_index_extraction_mode") or ""),
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
                cached_stored_hashes.add(new_signature)
                scraped_chapters_for_state.append(
                    {
                        "id": chapter_id,
                        "chapter_id": chapter_id,
                        "source_episode_id": str(chapter.get("source_episode_id") or chapter_id),
                        "source_update_date": chapter.get("source_update_date") or chapter.get("date_added"),
                        "content_hash": new_signature,
                    }
                )
                _emit(
                    STAGE_BODY_CRAWL,
                    "completed",
                    succeeded + skipped + failed,
                    _total_chapters,
                    source_episode_id=chapter_id,
                    label=f"Chapter {chapter_id}: saved",
                )

            except (SourceError, RuntimeError, Exception) as exc:
                error_type = type(exc).__name__
                error_message = str(exc) if str(exc) else error_type
                # Sanitize: remove stack traces, limit length
                if "\nTraceback" in error_message:
                    error_message = error_message.split("\nTraceback")[0]
                error_message = error_message[:500]

                logger.warning(
                    "Chapter %s/%s/%s failed (%s): %s",
                    source_key,
                    novel_id,
                    chapter_id,
                    error_type,
                    error_message,
                )
                if progress_callback:
                    progress_callback(f"  Chapter {chapter_id} failed ({error_type}): {error_message}")

                http_status_code = _extract_http_status(exc)
                failure = {
                    "chapter_id": chapter_id,
                    "chapter_number": chapter_num,
                    "title": chapter.get("title"),
                    "source_url": chapter.get("url"),
                    "error_type": error_type,
                    "error_message": error_message,
                    "error_category": _classify_error(exc, error_message, http_status_code),
                    "http_status_code": http_status_code,
                    "retry_attempts": retry_attempts[0],
                }
                failures.append(failure)
                failed += 1
                _emit(
                    STAGE_BODY_CRAWL,
                    "failed",
                    succeeded + skipped + failed,
                    _total_chapters,
                    source_episode_id=chapter_id,
                    label=f"Chapter {chapter_id}: failed ({error_type})",
                    details={
                        "error_type": error_type,
                        "error_category": failure["error_category"],
                        "http_status_code": http_status_code,
                        "retry_attempts": failure["retry_attempts"],
                    },
                )

        terminal_status = crawl_terminal_status(
            succeeded=succeeded,
            skipped=skipped,
            failed=failed,
            image_download_failures=image_download_failures,
        )

        if progress_callback:
            if failures:
                progress_callback(
                    f"Scrape finished with partial success: {succeeded} saved, {skipped} skipped, {failed} failed."
                )
            else:
                progress_callback(f"Scrape finished: {succeeded} saved, {skipped} skipped.")

        new_source_state = update_source_state(
            novel_id=novel_id,
            existing_state=existing_source_state,
            metadata=meta,
            scraped_chapters=scraped_chapters_for_state,
        )
        self.storage.save_source_state(novel_id, new_source_state)
        # Stage the source-state / chapter-index / metadata snapshots so the
        # committed generation is a complete, reproducible record of the run.
        self.storage.stage_generation_source_state(novel_id, generation_id, new_source_state)
        self.storage.stage_generation_chapter_index(novel_id, generation_id, meta.get("chapters", []))
        if mode == "full":
            self.storage.stage_generation_metadata(novel_id, generation_id, meta)

        # Manifest is written with final counts before the active pointer swaps,
        # so readers never observe a partially recorded snapshot as active.
        self.storage.commit_generation(
            novel_id,
            generation_id,
            removed_episode_ids=list(crawl_plan.removed_episode_ids),
            reused_chapters=skipped,
            failed_chapters=failed,
        )

        _emit(
            STAGE_RECONCILIATION,
            terminal_status,
            succeeded + skipped + failed,
            _total_chapters,
            label="Scrape finished",
            details={
                "succeeded": succeeded,
                "skipped": skipped,
                "failed": failed,
                "image_download_failures": image_download_failures,
                "generation_id": generation_id,
            },
        )

        return {
            "succeeded": succeeded,
            "skipped": skipped,
            "failed": failed,
            "failures": failures,
            "image_download_failures": image_download_failures,
            "terminal_status": terminal_status,
            "generation_id": generation_id,
        }
    except BaseException as exc:
        # A hard failure (including cancellation) must not leave a partially
        # recorded snapshot: roll the stage back and keep the previously
        # active generation (or legacy layout) in effect.
        self.storage.rollback_generation(novel_id, generation_id, reason=str(exc.__class__.__name__))
        raise
