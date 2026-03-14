from __future__ import annotations

import contextlib
import json
import logging
import re
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from novelai.config.workflow_profiles import normalize_workflow_profiles
from novelai.config.settings import settings
from novelai.core.chapter_state import ChapterState, ChapterStateTransition
from novelai.glossary import extract_candidate_glossary_terms, normalize_glossary_entries
from novelai.inputs.base import DocumentAdapter
from novelai.providers.base import TranslationProvider
from novelai.services.preferences_service import PreferencesService
from novelai.services.storage_service import StorageService
from novelai.services.translation_cache import TranslationCache
from novelai.services.translation_service import TranslationService
from novelai.services.usage_service import UsageService
from novelai.sources.base import SourceAdapter
from novelai.utils.chapter_selection import is_full_chapter_selection, parse_chapter_selection

logger = logging.getLogger(__name__)


def _utc_now_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _make_state_data(
    state: ChapterState,
    *,
    error: str | None = None,
    previous: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a state_data dict suitable for StorageService.save_chapter_state."""
    now = datetime.now(UTC)
    prev_state = None
    transitions: list[ChapterStateTransition] = []
    error_count = 0

    if previous:
        prev_state_raw = previous.get("current_state")
        if isinstance(prev_state_raw, ChapterState):
            prev_state = prev_state_raw
        elif isinstance(prev_state_raw, str):
            with contextlib.suppress(ValueError):
                prev_state = ChapterState(prev_state_raw)
        transitions = previous.get("transitions", [])
        error_count = previous.get("error_count", 0)

    transitions.append(ChapterStateTransition(
        from_state=prev_state,
        to_state=state,
        timestamp=now,
        error=error,
    ))

    if error:
        error_count += 1

    return {
        "current_state": state,
        "transitions": transitions,
        "last_updated": now,
        "error_count": error_count,
        "retry_count": previous.get("retry_count", 0) if previous else 0,
    }


@dataclass(frozen=True)
class PreflightIssue:
    code: str
    reason: str


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
        source_factory: Callable[[str], SourceAdapter] | None = None,
        input_adapter_factory: Callable[[str], DocumentAdapter] | None = None,
        provider_factory: Callable[[str], TranslationProvider] | None = None,
        settings_service: PreferencesService | None = None,
        translation_cache: TranslationCache | None = None,
        usage_service: UsageService | None = None,
    ) -> None:
        if source_factory is None:
            # Default: import and use registry
            from novelai.sources.registry import get_source
            source_factory = get_source
        if input_adapter_factory is None:
            from novelai.inputs.registry import get_input_adapter
            input_adapter_factory = get_input_adapter
        if provider_factory is None:
            from novelai.providers.registry import get_provider
            provider_factory = get_provider

        self.storage = storage
        self.translation = translation
        self._source_factory = source_factory
        self._input_adapter_factory = input_adapter_factory
        self._provider_factory = provider_factory
        self._settings = settings_service or PreferencesService()
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

    @staticmethod
    def _infer_source_language_from_text(text: str) -> str | None:
        if any("\u3040" <= char <= "\u30ff" for char in text):
            return "Japanese"
        if any("\u4e00" <= char <= "\u9fff" for char in text):
            return "Chinese"
        if re.search(r"[A-Za-z]", text):
            return "English"
        return None

    def _resolve_workflow_profile(
        self,
        step: str,
        metadata: dict[str, Any] | None = None,
    ) -> tuple[str | None, str | None]:
        novel_profiles = normalize_workflow_profiles(metadata.get("translation_profiles")) if isinstance(metadata, dict) else normalize_workflow_profiles(None)
        global_profile = self._settings.get_workflow_profile(step)
        provider = novel_profiles[step]["provider"] or global_profile["provider"]
        model = novel_profiles[step]["model"] or global_profile["model"]
        return provider, model

    def _selected_chapter_numbers(self, metadata: dict[str, Any], selection: str) -> list[int]:
        """Resolve a chapter selection string into concrete chapter numbers.

        Returns all chapter IDs when *selection* is ``"all"``; otherwise
        parses the DSL (e.g. ``"1-3;5"``) via :func:`parse_chapter_selection`.
        """
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

    @staticmethod
    def _latest_checkpoint_name(storage: StorageService, novel_id: str, chapter_id: str) -> str | None:
        checkpoints = storage.list_checkpoints(novel_id, chapter_id)
        if not checkpoints:
            return None
        return checkpoints[-1].get("checkpoint_name")

    def _restore_latest_checkpoint_for_resume(self, novel_id: str, chapter_id: str) -> bool:
        checkpoint_name = self._latest_checkpoint_name(self.storage, novel_id, chapter_id)
        if not checkpoint_name:
            return False
        restored = self.storage.restore_from_checkpoint(novel_id, chapter_id, checkpoint_name)
        if restored:
            logger.info(
                "Restored latest checkpoint '%s' before resuming chapter %s/%s.",
                checkpoint_name,
                novel_id,
                chapter_id,
            )
        return restored

    def _preflight_translation(
        self,
        *,
        novel_id: str,
        source_key: str,
        meta: dict[str, Any],
        selected_numbers: list[int],
        force: bool,
        source_language: str | None,
        target_language: str | None,
        glossary: Any | None,
    ) -> list[PreflightIssue]:
        issues: list[PreflightIssue] = []

        if not selected_numbers:
            issues.append(
                PreflightIssue(
                    code="empty_selection",
                    reason="No chapters match the requested selection.",
                )
            )
            return issues

        chapter_map = {
            int(chapter["id"]): chapter
            for chapter in meta.get("chapters", [])
            if isinstance(chapter, dict) and str(chapter.get("id", "")).isdigit()
        }

        missing_chapters = [number for number in selected_numbers if number not in chapter_map]
        if missing_chapters:
            issues.append(
                PreflightIssue(
                    code="metadata_mismatch",
                    reason=(
                        "Selected chapters are missing from metadata: "
                        + ", ".join(str(number) for number in missing_chapters)
                    ),
                )
            )

        unresolved_urls: list[int] = []
        for number in selected_numbers:
            chapter = chapter_map.get(number)
            if chapter is None:
                continue
            chapter_id = str(number)
            raw_chapter = self.storage.load_chapter(novel_id, chapter_id)
            if chapter.get("url") or (raw_chapter and isinstance(raw_chapter.get("text"), str)):
                continue
            unresolved_urls.append(number)
        if unresolved_urls:
            issues.append(
                PreflightIssue(
                    code="missing_chapter_url",
                    reason=(
                        "Some selected chapters have no source URL: "
                        + ", ".join(str(number) for number in unresolved_urls)
                    ),
                )
            )

        effective_source_language = source_language or self._infer_source_language(source_key, meta)
        if not effective_source_language:
            for number in selected_numbers:
                raw_chapter = self.storage.load_chapter(novel_id, str(number))
                if raw_chapter is None:
                    continue
                raw_text = raw_chapter.get("text")
                if isinstance(raw_text, str) and raw_text.strip():
                    effective_source_language = self._infer_source_language_from_text(raw_text)
                    if effective_source_language:
                        break
        if not isinstance(effective_source_language, str) or not effective_source_language.strip():
            issues.append(
                PreflightIssue(
                    code="missing_source_language",
                    reason=(
                        "Source language is unknown. Provide source_language explicitly or include it in metadata."
                    ),
                )
            )

        if not isinstance(target_language, str) or not target_language.strip():
            issues.append(
                PreflightIssue(
                    code="missing_target_language",
                    reason="Target language is empty. Configure translation target language before running.",
                )
            )

        try:
            normalized_glossary = normalize_glossary_entries(glossary)
        except Exception as exc:
            issues.append(
                PreflightIssue(
                    code="invalid_glossary",
                    reason=f"Glossary entries are invalid: {exc}",
                )
            )
            normalized_glossary = []

        pending_terms = [entry.source for entry in normalized_glossary if entry.status == "pending"]
        if pending_terms:
            preview = ", ".join(pending_terms[:5])
            if len(pending_terms) > 5:
                preview += f", +{len(pending_terms) - 5} more"
            issues.append(
                PreflightIssue(
                    code="pending_glossary_terms",
                    reason=(
                        "Review glossary terms before translation. "
                        f"Pending terms: {preview}."
                    ),
                )
            )

        chapters_missing_ocr_review: list[str] = []
        for number in selected_numbers:
            chapter_id = str(number)
            media_state = self.storage.load_chapter_media_state(novel_id, chapter_id)
            if media_state is None:
                continue

            if not bool(media_state.get("ocr_required", False)):
                continue

            ocr_status = str(media_state.get("ocr_status") or "pending").strip().lower()
            if ocr_status != "reviewed":
                chapters_missing_ocr_review.append(chapter_id)

        if chapters_missing_ocr_review:
            issues.append(
                PreflightIssue(
                    code="missing_ocr_review",
                    reason=(
                        "OCR review is required before translation for chapter(s): "
                        + ", ".join(chapters_missing_ocr_review)
                    ),
                )
            )

        if not force:
            translatable = 0
            for number in selected_numbers:
                if number not in chapter_map:
                    continue
                chapter_id = str(number)
                if self.storage.load_translated_chapter(novel_id, chapter_id) is None:
                    translatable += 1
            if translatable == 0:
                issues.append(
                    PreflightIssue(
                        code="nothing_to_translate",
                        reason="All selected chapters are already translated. Use force=True to retranslate.",
                    )
                )

        return issues

    @staticmethod
    def _extract_ocr_candidate_text(images: list[dict[str, Any]]) -> str | None:
        snippets: list[str] = []
        seen: set[str] = set()
        ordered = sorted(
            [item for item in images if isinstance(item, dict)],
            key=lambda item: int(item.get("index", 0)),
        )

        for image in ordered:
            for field in ("ocr_text", "alt", "title", "caption", "placeholder", "text"):
                value = image.get(field)
                if not isinstance(value, str):
                    continue
                cleaned = re.sub(r"\s+", " ", value).strip()
                if not cleaned:
                    continue
                key = cleaned.casefold()
                if key in seen:
                    continue
                seen.add(key)
                snippets.append(cleaned)

        if not snippets:
            return None

        candidate = "\n".join(f"- {snippet}" for snippet in snippets)
        if len(candidate) > 4000:
            return candidate[:3997] + "..."
        return candidate

    async def ingest_ocr_candidates(
        self,
        novel_id: str,
        chapters: str = "all",
        *,
        mark_required: bool = True,
        overwrite: bool = False,
    ) -> dict[str, Any]:
        """Build OCR candidate text from stored image manifests and persist chapter media state."""
        meta = self.storage.load_metadata(novel_id)
        if not meta:
            raise RuntimeError("Metadata not found; run scrape-metadata first.")

        selected_numbers = self._selected_chapter_numbers(meta, chapters)
        summary: dict[str, Any] = {
            "novel_id": novel_id,
            "selected": len(selected_numbers),
            "updated": 0,
            "skipped_no_images": 0,
            "skipped_reviewed": 0,
            "failed": [],
        }

        for chapter_num in selected_numbers:
            chapter_id = str(chapter_num)
            chapter = self.storage.load_chapter(novel_id, chapter_id)
            if chapter is None:
                summary["failed"].append(
                    {
                        "chapter_id": chapter_id,
                        "code": "missing_chapter",
                        "reason": "Raw chapter is missing; scrape chapters first.",
                    }
                )
                continue

            media_state = self.storage.load_chapter_media_state(novel_id, chapter_id) or {}
            existing_status = str(media_state.get("ocr_status") or "pending").strip().lower()
            if existing_status == "reviewed" and not overwrite:
                summary["skipped_reviewed"] += 1
                continue

            images = chapter.get("images") if isinstance(chapter.get("images"), list) else []
            if not images:
                summary["skipped_no_images"] += 1
                self.storage.save_chapter_media_state(
                    novel_id,
                    chapter_id,
                    ocr_required=False,
                    ocr_status="skipped",
                )
                continue

            candidate = self._extract_ocr_candidate_text(images)
            if not candidate:
                summary["failed"].append(
                    {
                        "chapter_id": chapter_id,
                        "code": "missing_candidate",
                        "reason": "No OCR candidate text could be extracted from image metadata.",
                    }
                )
                self.storage.save_chapter_media_state(
                    novel_id,
                    chapter_id,
                    ocr_required=mark_required,
                    ocr_status="failed",
                )
                continue

            existing_text = media_state.get("ocr_text") if isinstance(media_state.get("ocr_text"), str) else None
            self.storage.save_chapter_media_state(
                novel_id,
                chapter_id,
                ocr_required=mark_required,
                ocr_text=candidate if (overwrite or not existing_text) else existing_text,
                ocr_status="pending" if mark_required else "skipped",
            )
            summary["updated"] += 1

        return summary

    async def import_document(
        self,
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
            self.storage.save_chapter_media_state(
                novel_id,
                unit.unit_id,
                ocr_required=unit.ocr_required,
                ocr_text=joined_ocr_text,
                ocr_status="pending" if unit.ocr_required else "skipped",
                reembed_status="pending" if unit.ocr_required else "skipped",
            )

        return self.storage.load_metadata(novel_id) or metadata

    async def extract_glossary_terms(
        self,
        novel_id: str,
        chapters: str = "all",
        *,
        max_terms: int = 50,
    ) -> dict[str, Any]:
        meta = self.storage.load_metadata(novel_id)
        if not meta:
            raise RuntimeError("Metadata not found; import or scrape a novel first.")

        selected_numbers = self._selected_chapter_numbers(meta, chapters)
        texts: list[str] = []
        for number in selected_numbers:
            chapter_id = str(number)
            media_state = self.storage.load_chapter_media_state(novel_id, chapter_id) or {}
            if bool(media_state.get("ocr_required")) and str(media_state.get("ocr_status") or "").lower() == "reviewed":
                ocr_text = media_state.get("ocr_text")
                if isinstance(ocr_text, str) and ocr_text.strip():
                    texts.append(ocr_text)
                    continue
            chapter = self.storage.load_chapter(novel_id, chapter_id)
            if chapter and isinstance(chapter.get("text"), str) and chapter["text"].strip():
                texts.append(chapter["text"])

        candidates = extract_candidate_glossary_terms(texts, max_terms=max_terms)
        existing = {
            entry["source"]: dict(entry)
            for entry in self.storage.load_glossary(novel_id)
            if isinstance(entry, dict) and isinstance(entry.get("source"), str)
        }
        added = 0
        for candidate in candidates:
            if candidate.source in existing:
                continue
            existing[candidate.source] = {
                "source": candidate.source,
                "target": candidate.target,
                "locked": candidate.locked,
                "notes": candidate.notes,
                "status": candidate.status,
                "context_history": list(candidate.context_history),
                "context_summary": candidate.context_summary,
                "occurrence_count": candidate.occurrence_count,
                "last_seen_index": candidate.last_seen_index,
            }
            added += 1

        ordered_entries = sorted(existing.values(), key=lambda item: (str(item.get("source")).casefold(), str(item.get("source"))))
        self.storage.save_glossary(novel_id, ordered_entries)
        return {
            "novel_id": novel_id,
            "selected_chapters": len(selected_numbers),
            "candidates_found": len(candidates),
            "added": added,
            "total_terms": len(ordered_entries),
        }

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
        """Translate title, author, and per-chapter titles in *metadata*.

        Reuses previously translated values from *existing_metadata* when the
        source text has not changed, avoiding redundant API calls.
        """
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

        # Persist detected source language so prompts and exports can use it.
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
        """Fetch chapter content from the source site and persist it.

        In ``full`` mode, existing data is deleted before re-scraping.
        In ``update`` mode (default), only new or changed chapters are fetched.
        Chapters are identified by the *chapters* selection string (e.g.
        ``"all"`` or ``"1-5"``).
        """
        source = self._source_factory(source_key)

        if mode == "full":
            self.storage.delete_novel(novel_id)
            meta = await source.fetch_metadata(novel_id)
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
                input_adapter_key="web",
                origin_type="url",
                origin_uri_or_path=str(chapter.get("url") or meta.get("source_url") or novel_id),
                document_type="web_novel",
                unit_type="chapter",
                import_order=chapter_num,
                context_group_id=novel_id,
            )

    async def translate_chapters(
        self,
        source_key: str,
        novel_id: str,
        chapters: str,
        provider_key: str | None = None,
        provider_model: str | None = None,
        force: bool = False,
        source_language: str | None = None,
        target_language: str | None = None,
        glossary: Any | None = None,
        style_preset: str | None = None,
        consistency_mode: bool = False,
        json_output: bool = False,
    ) -> None:
        """Translate selected chapters through the pipeline.

        Loads metadata and glossary, then iterates over the requested
        chapters.  Each chapter's state is tracked via checkpoints
        (SEGMENTED → TRANSLATED) for crash recovery.  Already-translated
        chapters are skipped unless *force* is ``True``.
        """
        source: SourceAdapter | None = None
        with contextlib.suppress(Exception):
            source = self._source_factory(source_key)
        meta = self.storage.load_metadata(novel_id)
        if not meta:
            raise RuntimeError("Metadata not found; run scrape-metadata first.")

        effective_source_language = source_language or self._infer_source_language(source_key, meta)
        effective_target_language = target_language or settings.TRANSLATION_TARGET_LANGUAGE
        profile_provider, profile_model = self._resolve_workflow_profile("body_translation", meta)
        effective_provider_key = provider_key or profile_provider
        effective_provider_model = provider_model or profile_model

        # Auto-load stored glossary when none was explicitly provided.
        if glossary is None:
            stored_entries = self.storage.load_glossary(novel_id)
            if stored_entries:
                glossary = stored_entries

        chapter_map = {int(c["id"]): c for c in meta.get("chapters", [])}
        selected_numbers = self._selected_chapter_numbers(meta, chapters)

        preflight_issues = self._preflight_translation(
            novel_id=novel_id,
            source_key=source_key,
            meta=meta,
            selected_numbers=selected_numbers,
            force=force,
            source_language=effective_source_language,
            target_language=effective_target_language,
            glossary=glossary,
        )
        if preflight_issues:
            details = "; ".join(f"{issue.code}: {issue.reason}" for issue in preflight_issues)
            raise RuntimeError(f"Translation preflight failed: {details}")

        for chapter_num in selected_numbers:
            chapter = chapter_map.get(chapter_num)
            if not chapter:
                continue

            chapter_id = str(chapter_num)

            existing = self.storage.load_translated_chapter(novel_id, chapter_id)
            if existing and not force:
                continue

            state_before = self.storage.load_chapter_state(novel_id, chapter_id)
            if state_before and state_before.get("error_count", 0) > 0:
                self._restore_latest_checkpoint_for_resume(novel_id, chapter_id)

            # Persist an explicit resume point before making changes.
            self.storage.create_checkpoint(novel_id, chapter_id, "before_translate")

            # Checkpoint: mark chapter as in-progress
            prev_state = self.storage.load_chapter_state(novel_id, chapter_id)
            self.storage.save_chapter_state(
                novel_id, chapter_id,
                _make_state_data(ChapterState.SEGMENTED, previous=prev_state),
            )

            try:
                raw_chapter = self.storage.load_chapter(novel_id, chapter_id)
                media_state = self.storage.load_chapter_media_state(novel_id, chapter_id) or {}
                raw_text = None
                raw_images: list[dict[str, Any]] | None = None
                if raw_chapter is not None:
                    reviewed_ocr_text = media_state.get("ocr_text")
                    if (
                        bool(media_state.get("ocr_required", False))
                        and str(media_state.get("ocr_status") or "").strip().lower() == "reviewed"
                        and isinstance(reviewed_ocr_text, str)
                        and reviewed_ocr_text.strip()
                    ):
                        raw_text = reviewed_ocr_text
                    else:
                        raw_text = raw_chapter.get("text") if isinstance(raw_chapter.get("text"), str) else None
                    raw_images = raw_chapter.get("images") if isinstance(raw_chapter.get("images"), list) else None
                chapter_url = str(chapter.get("url") or (raw_chapter or {}).get("source_url") or f"import://{novel_id}/{chapter_id}")
                result = await self.translation.translate_chapter(
                    source_adapter=source,
                    chapter_url=chapter_url,
                    provider_key=effective_provider_key,
                    provider_model=effective_provider_model,
                    source_language=effective_source_language,
                    target_language=effective_target_language,
                    glossary=glossary,
                    style_preset=style_preset,
                    consistency_mode=consistency_mode,
                    json_output=json_output,
                    raw_text=raw_text,
                    raw_images=raw_images,
                )
                translated = result.final_text or ""
                self.storage.save_translated_chapter(
                    novel_id,
                    chapter_id,
                    translated,
                    provider=result.provider_key,
                    model=result.provider_model,
                )
                self.storage.save_chapter_state(
                    novel_id, chapter_id,
                    _make_state_data(ChapterState.TRANSLATED, previous=prev_state),
                )
                self.storage.create_checkpoint(novel_id, chapter_id, "translated")
            except Exception as exc:
                logger.error("Failed to translate chapter %s/%s: %s", novel_id, chapter_id, exc)
                self.storage.save_chapter_state(
                    novel_id, chapter_id,
                    _make_state_data(ChapterState.SEGMENTED, error=str(exc), previous=prev_state),
                )
                self.storage.create_checkpoint(novel_id, chapter_id, "failed")
                raise

    async def retranslate_chapter(
        self,
        source_key: str,
        novel_id: str,
        chapter_id: str,
        provider_key: str | None = None,
        provider_model: str | None = None,
        source_language: str | None = None,
        target_language: str | None = None,
        glossary: Any | None = None,
        style_preset: str | None = None,
        consistency_mode: bool = False,
        json_output: bool = False,
    ) -> None:
        """Force retranslation for a single chapter using chapter-scoped selection."""
        normalized_chapter_id = str(chapter_id).strip()
        if not normalized_chapter_id.isdigit():
            raise ValueError("chapter_id must be a numeric chapter identifier.")

        await self.translate_chapters(
            source_key=source_key,
            novel_id=novel_id,
            chapters=normalized_chapter_id,
            provider_key=provider_key,
            provider_model=provider_model,
            force=True,
            source_language=source_language,
            target_language=target_language,
            glossary=glossary,
            style_preset=style_preset,
            consistency_mode=consistency_mode,
            json_output=json_output,
        )
