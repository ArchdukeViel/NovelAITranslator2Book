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
from novelai.utils.chapter_selection import (
    _chapter_logical_id,
    resolve_chapter_selection,
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


def _clear_stale_metadata_translations(
    meta: dict[str, Any],
    previous: dict[str, Any] | None,
) -> None:
    """Prevent an old synopsis translation from masking corrected source text."""
    if not previous:
        return
    current_source = meta.get("narrative_synopsis") or meta.get("synopsis") or meta.get("description")
    previous_source = (
        previous.get("narrative_synopsis")
        or previous.get("synopsis")
        or previous.get("description")
        or previous.get("summary")
    )
    if not isinstance(current_source, str) or not current_source.strip():
        return
    if not isinstance(previous_source, str) or current_source.strip() == previous_source.strip():
        return
    for key in ("translated_narrative_synopsis", "translated_synopsis", "translated_description"):
        meta[key] = None


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

    for key in (
        "title",
        "translated_title",
        "author",
        "narrative_synopsis",
        "synopsis",
        "description",
        "summary",
    ):
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

    _clear_stale_metadata_translations(meta, existing_metadata)
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
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Fetch chapter content from the source site and persist it.

    In ``full`` mode, a new generation is staged for the complete current
    index. If validation fails the stage is rolled back and the previous
    active generation remains in effect â€” no active
    data is deleted. In ``update`` mode (default), a generation is staged
    for the complete index but only selected chapters are fetched; unselected
    chapters are carried forward from the active generation. A scoped crawl
    (e.g. ``chapters="1"`` against a 100-chapter work) still activates a
    generation representing all 100 index entries.

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
            metadata=metadata,
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


async def _scrape_chapters_r2_impl(
    self: Any,
    source_key: str,
    novel_id: str,
    chapters: str,
    mode: str,
    progress_callback: Callable[[str], None] | None,
    cancellation_check: Callable[[], bool] | None = None,
    progress_events_callback: Callable[[CrawlProgressEvent], None] | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Fetch chapters into immutable R2 artifacts and activate DB references.

    R2 objects are written before the PostgreSQL transaction.  The transaction
    then records the chapter references and changes the active generation in a
    single commit; there is no filesystem stage or R2 pointer object.
    """

    from novelai.db.models.chapter import Chapter
    from novelai.services.catalog_service import CatalogService
    from novelai.services.r2_activation_service import R2GenerationActivationService

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
        if progress_events_callback is not None:
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

    if mode == "full" and metadata is None:
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
    else:
        load_metadata_for_crawl = getattr(self.storage, "load_metadata_for_crawl", self.storage.load_metadata)
        meta = dict(metadata) if isinstance(metadata, dict) else load_metadata_for_crawl(novel_id)
        if not isinstance(meta, dict) or not meta:
            raise RuntimeError("Metadata not found; run scrape-metadata first.")

    raw_index_entries = meta.get("chapters")
    if not isinstance(raw_index_entries, list) or not raw_index_entries:
        raise RuntimeError(f"Chapter index is empty for {source_key}/{novel_id}; cannot crawl chapters.")
    complete_index_entries: list[dict[str, Any]] = [entry for entry in raw_index_entries if isinstance(entry, dict)]
    try:
        storage_novel_id = self.storage.resolve_storage_novel_id(novel_id)
    except ValueError:
        # Full crawls may begin from a source URL without a prior metadata
        # request. Establish the PostgreSQL identity before writing R2 keys.
        self.storage.save_metadata(novel_id, meta)
        storage_novel_id = self.storage.resolve_storage_novel_id(novel_id)
    resolved = resolve_chapter_selection(meta, chapters)
    if not resolved:
        raise ValueError(
            f"No chapters matched selection {chapters!r} for {source_key}/{novel_id}; refusing to activate."
        )

    total = len(resolved)
    existing_source_state = self.storage.load_source_state(novel_id) or {}
    existing_by_id: dict[str, dict[str, Any]] = {}
    for record in resolved:
        existing = self.storage.load_chapter(novel_id, record.chapter_id)
        if isinstance(existing, dict):
            existing_by_id[record.chapter_id] = existing

    selected_index_entries: list[dict[str, Any]] = []
    for record in resolved:
        entry = dict(record.metadata)
        entry.setdefault("id", record.chapter_id)
        entry.setdefault("source_episode_id", record.source_episode_id)
        entry.setdefault("sequence_number", record.sequence_number)
        selected_index_entries.append(entry)
    crawl_plan = create_crawl_plan(
        novel_id,
        selected_index_entries,
        existing_source_state,
        existing_by_id,
        mode=mode,
        all_chapters=complete_index_entries,
    )
    chapters_to_fetch = crawl_plan.chapters_to_fetch_set

    if progress_callback:
        progress_callback(f"Preparing to scrape {len(complete_index_entries)} chapter(s)…")

    fetched: dict[str, dict[str, Any]] = {}
    scraped_for_state: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []
    succeeded = 0
    skipped = 0
    failed = 0
    image_download_failures = 0
    cached_hashes = _stored_chapter_hashes(self.storage, novel_id, exclude_chapter_id="")

    for _index, record in enumerate(resolved):
        if cancellation_check is not None and cancellation_check():
            raise asyncio.CancelledError(f"Scrape cancelled for {source_key}/{novel_id}")
        chapter = record.metadata if isinstance(record.metadata, dict) else {}
        chapter_id = record.chapter_id
        chapter_number = record.sequence_number
        episode_id = record.source_episode_id or chapter_id
        retry_attempts = 0

        if mode != "full" and episode_id not in chapters_to_fetch:
            existing = existing_by_id.get(chapter_id, {})
            existing_text = existing.get("text") if isinstance(existing.get("text"), str) else ""
            existing_images = existing.get("images") if isinstance(existing.get("images"), list) else []
            existing_signature = self._chapter_content_signature(existing_text, existing_images)
            skipped += 1
            scraped_for_state.append({**chapter, "id": chapter_id, "content_hash": existing_signature})
            if progress_callback:
                progress_callback(f"Chapter {chapter_id}: reused via planner")
            _emit(
                STAGE_BODY_CRAWL,
                "skipped",
                succeeded + skipped + failed,
                total,
                source_episode_id=episode_id,
                label=f"Chapter {chapter_id}: unchanged",
            )
            continue

        if progress_callback:
            progress_callback(f"Chapter {chapter_id}: fetching")

        def _on_retry(attempt: int, _error: Exception) -> None:
            nonlocal retry_attempts
            retry_attempts = max(retry_attempts, int(attempt))

        try:
            payload = await source.fetch_chapter_payload(chapter["url"], on_retry=_on_retry)
            text = payload.get("text")
            if not isinstance(text, str):
                raise RuntimeError("Source returned invalid chapter text.")
            raw_images = payload.get("images")
            image_manifest = (
                [item for item in raw_images if isinstance(item, dict)] if isinstance(raw_images, list) else []
            )
            quality = evaluate_chapter_quality(
                text,
                source_key=source_key,
                url=chapter.get("url") if isinstance(chapter.get("url"), str) else None,
                images=image_manifest,
                duplicate_hashes=cached_hashes,
            )
            if quality.errors:
                raise SourceError(
                    f"Chapter quality gate failed for {source_key}/{novel_id}/{chapter_id}: "
                    + ", ".join(quality.errors)
                )

            existing = existing_by_id.get(chapter_id, {})
            existing_signature = self._chapter_content_signature(
                existing.get("text") if isinstance(existing.get("text"), str) else "",
                existing.get("images") if isinstance(existing.get("images"), list) else [],
            )
            new_signature = self._chapter_content_signature(text, image_manifest)
            if mode != "full" and existing and existing_signature == new_signature:
                skipped += 1
                scraped_for_state.append({**chapter, "id": chapter_id, "content_hash": new_signature})
                _emit(
                    STAGE_BODY_CRAWL,
                    "skipped",
                    succeeded + skipped + failed,
                    total,
                    source_episode_id=episode_id,
                    label=f"Chapter {chapter_id}: unchanged",
                )
                continue

            stored_images: list[dict[str, Any]] = []
            chapter_image_failed = False
            for image_index, image in enumerate(image_manifest):
                entry = dict(image)
                original_url = entry.get("original_url")
                if isinstance(original_url, str) and original_url.strip() and hasattr(source, "fetch_asset"):
                    try:
                        asset = await source.fetch_asset(original_url, referer=chapter.get("url"))
                        content = asset.get("content")
                        if not isinstance(content, (bytes, bytearray)) or not content:
                            raise RuntimeError("Source returned invalid asset bytes.")
                        content_type = asset.get("content_type") if isinstance(asset.get("content_type"), str) else None
                        if content_type and content_type.lower().startswith("text/html"):
                            raise RuntimeError("Asset response was HTML instead of image content.")
                        entry.update(
                            self.storage.save_chapter_image_asset(
                                novel_id,
                                chapter_id,
                                storage_novel_id=storage_novel_id,
                                image_index=image_index,
                                content=bytes(content),
                                source_url=str(asset.get("url") or original_url),
                                content_type=content_type,
                            )
                        )
                    except Exception as exc:
                        chapter_image_failed = True
                        entry["download_error"] = str(exc)[:500]
                stored_images.append(entry)
            if chapter_image_failed:
                image_download_failures += 1

            chapter_payload = self.storage.build_chapter_payload(
                novel_id,
                chapter_id,
                text,
                title=chapter.get("title"),
                source_key=source_key,
                source_url=chapter.get("url"),
                images=stored_images,
                source_blocks=payload.get("source_blocks") if isinstance(payload.get("source_blocks"), list) else None,
                input_adapter_key="web",
                origin_type="url",
                origin_uri_or_path=str(chapter.get("url") or meta.get("source_url") or novel_id),
                document_type="web_novel",
                unit_type="chapter",
                import_order=chapter_number,
                context_group_id=novel_id,
            )
            raw_artifact = self.storage.save_raw_chapter_artifact(
                novel_id,
                chapter_id,
                text,
                title=chapter.get("title"),
                source_key=source_key,
                source_url=chapter.get("url"),
                artifact_payload=chapter_payload,
                storage_novel_id=storage_novel_id,
            )
            media_artifact = None
            if stored_images:
                media_artifact = self.storage._r2_artifacts().put_json(
                    storage_novel_id=storage_novel_id,
                    kind="media",
                    identity=chapter_id,
                    payload={"chapter_id": chapter_id, "images": stored_images},
                )
            fetched[chapter_id] = {
                "chapter": chapter,
                "text": text,
                "signature": new_signature,
                "payload": chapter_payload,
                "raw_artifact": raw_artifact,
                "media_artifact": media_artifact,
                "images": stored_images,
            }
            cached_hashes.add(new_signature)
            succeeded += 1
            scraped_for_state.append({**chapter, "id": chapter_id, "content_hash": new_signature})
            _emit(
                STAGE_BODY_CRAWL,
                "completed",
                succeeded + skipped + failed,
                total,
                source_episode_id=episode_id,
                label=f"Chapter {chapter_id}: saved",
            )
            if progress_callback:
                progress_callback(f"Chapter {chapter_id}: saved")
        except Exception as exc:
            failed += 1
            message = str(exc)[:500] or type(exc).__name__
            failure = {
                "chapter_id": chapter_id,
                "chapter_number": chapter_number,
                "title": chapter.get("title"),
                "source_url": chapter.get("url"),
                "error_type": type(exc).__name__,
                "error_message": message,
                "error_category": _classify_error(exc, message, _extract_http_status(exc)),
                "http_status_code": _extract_http_status(exc),
                "retry_attempts": retry_attempts,
            }
            failures.append(failure)
            if progress_callback:
                progress_callback(f"Chapter {chapter_id} failed ({type(exc).__name__}): {message}")
            _emit(
                STAGE_BODY_CRAWL,
                "failed",
                succeeded + skipped + failed,
                total,
                source_episode_id=episode_id,
                label=f"Chapter {chapter_id}: failed",
                details=failure,
            )

    terminal_status = crawl_terminal_status(
        succeeded=succeeded,
        skipped=skipped,
        failed=failed,
        image_download_failures=image_download_failures,
    )
    expected_generation_id = self.storage.resolve_active_generation_id(novel_id)
    if expected_generation_id and succeeded == 0 and failed == 0 and skipped == total:
        return {
            "succeeded": 0,
            "skipped": skipped,
            "failed": 0,
            "failures": [],
            "image_download_failures": 0,
            "terminal_status": terminal_status,
            "generation_id": expected_generation_id,
            "no_op": True,
        }

    if progress_callback:
        if failures:
            progress_callback(
                f"Scrape finished with partial success: {succeeded} saved, {skipped} skipped, {failed} failed."
            )
        else:
            progress_callback(f"Scrape finished: {succeeded} saved, {skipped} skipped.")

    generation_id = f"gen-{uuid.uuid4().hex[:12]}"
    new_source_state = update_source_state(
        novel_id=novel_id,
        existing_state=existing_source_state,
        metadata=meta,
        scraped_chapters=scraped_for_state,
    )
    meta = dict(meta)
    if terminal_status in (TERMINAL_STATUS_COMPLETED, TERMINAL_STATUS_COMPLETED_WITH_WARNINGS):
        meta["onboarding_status"] = "ready_for_translation"
        meta["body_scrape_required"] = False
    elif terminal_status == TERMINAL_STATUS_COMPLETED_WITH_ERRORS:
        meta["onboarding_status"] = "partially_scraped"
        meta["body_scrape_required"] = True

    with session_scope() as session:
        catalog = CatalogService(storage=self.storage, session=session)
        novel = catalog.get_or_create_novel(novel_id, meta)
        for chapter_id, item in fetched.items():
            chapter = item["chapter"]
            row = catalog.save_raw_chapter(
                novel_id,
                chapter_id,
                item["text"],
                title=chapter.get("title"),
                source_key=source_key,
                chapter_number=chapter.get("num") or chapter.get("chapter_number"),
                source_episode_id=chapter.get("source_episode_id"),
                sequence_number=chapter.get("sequence_number") or item["chapter"].get("num"),
                source_url=chapter.get("url"),
                artifact_payload=item["payload"],
            )
            media_artifact = item.get("media_artifact")
            if media_artifact is not None:
                row.media_storage_key = media_artifact.key
                row.media_content_hash = media_artifact.logical_sha256
                row.media_state_json = {"images": item["images"]}
                session.add(row)
        novel.source_state_json = dict(new_source_state)
        manifest_chapters: list[dict[str, Any]] = []
        rows = {
            row.logical_chapter_id: row for row in session.query(Chapter).filter(Chapter.novel_id == novel.id).all()
        }
        for entry in complete_index_entries:
            if not isinstance(entry, dict):
                continue
            chapter_id = _chapter_logical_id(entry)
            if not chapter_id:
                continue
            row = rows.get(chapter_id)
            manifest_entry: dict[str, Any] = {"chapter_id": chapter_id}
            if row is not None:
                for field in ("raw_storage_key", "translated_storage_key", "media_storage_key"):
                    value = getattr(row, field, None)
                    if value:
                        manifest_entry[field] = value
                for field in ("raw_content_hash", "translated_content_hash", "media_content_hash"):
                    value = getattr(row, field, None)
                    if value:
                        manifest_entry[field] = value
            images = fetched.get(chapter_id, {}).get("images")
            if not isinstance(images, list):
                existing = existing_by_id.get(chapter_id, {})
                existing_images = existing.get("images")
                images = existing_images if isinstance(existing_images, list) else []
            manifest_entry["assets"] = sorted(
                str(image["storage_key"])
                for image in images
                if isinstance(image, dict) and isinstance(image.get("storage_key"), str)
            )
            manifest_chapters.append(manifest_entry)
        manifest = {
            "schema_version": 1,
            "novel_id": str(novel.id),
            "public_slug": novel_id,
            "generation_id": generation_id,
            "mode": mode,
            "source": {"source_key": source_key},
            "chapters": manifest_chapters,
        }
        R2GenerationActivationService(storage=self.storage, db_session=session).activate(
            novel_id=novel_id,
            generation_id=generation_id,
            manifest=manifest,
            expected_generation_id=expected_generation_id,
        )

    safely_refresh_catalog_projection_after_storage_write(
        novel_id,
        self.storage,
        context="scrape_chapters_r2",
    )
    best_effort_invalidate(context="scrape_chapters_r2")
    _emit(
        STAGE_RECONCILIATION,
        terminal_status,
        succeeded + skipped + failed,
        total,
        label="Scrape finished",
        details={"succeeded": succeeded, "skipped": skipped, "failed": failed, "generation_id": generation_id},
    )
    return {
        "succeeded": succeeded,
        "skipped": skipped,
        "failed": failed,
        "failures": failures,
        "image_download_failures": image_download_failures,
        "terminal_status": terminal_status,
        "generation_id": generation_id,
        "no_op": False,
    }


async def _scrape_chapters_impl(
    self: Any,
    source_key: str,
    novel_id: str,
    chapters: str,
    mode: str,
    progress_callback: Callable[[str], None] | None,
    cancellation_check: Callable[[], bool] | None = None,
    progress_events_callback: Callable[[CrawlProgressEvent], None] | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Run chapter crawling through the R2 immutable-generation pipeline."""

    return await _scrape_chapters_r2_impl(
        self,
        source_key,
        novel_id,
        chapters,
        mode,
        progress_callback,
        cancellation_check,
        progress_events_callback,
        metadata=metadata,
    )
