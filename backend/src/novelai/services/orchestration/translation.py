from __future__ import annotations

import contextlib
import logging
from typing import Any

from novelai.config.settings import settings
from novelai.core.chapter_state import ChapterState
from novelai.glossary import glossary_status_counts, normalize_glossary_entries
from novelai.services.orchestration.common import PreflightIssue, _make_state_data
from novelai.sources.base import SourceAdapter

logger = logging.getLogger(__name__)

def _preflight_translation(
    self: Any,
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


async def polish_low_confidence_chapters(
    self: Any,
    *,
    source_key: str,
    novel_id: str,
    chapters: str = "all",
    provider_key: str | None = None,
    provider_model: str | None = None,
    source_language: str | None = None,
    target_language: str | None = None,
    confidence_threshold: float = 0.55,
    low_confidence_only: bool = True,
    consistency_mode: bool = True,
    json_output: bool = False,
) -> dict[str, Any]:
    """Retranslate only chapters that look low-confidence via heuristics."""
    meta = self.storage.load_metadata(novel_id)
    if not meta:
        raise RuntimeError("Metadata not found; import or scrape a novel first.")
    profile_provider, profile_model = self._resolve_workflow_profile("polish", meta)
    effective_provider = provider_key or profile_provider
    effective_model = provider_model or profile_model

    chapter_map = {
        int(chapter["id"]): chapter
        for chapter in meta.get("chapters", [])
        if isinstance(chapter, dict) and str(chapter.get("id", "")).isdigit()
    }
    selected_numbers = self._selected_chapter_numbers(meta, chapters)
    low_confidence_ids: list[str] = []
    normalized_threshold = max(0.0, min(1.0, confidence_threshold))

    for number in selected_numbers:
        chapter_id = str(number)
        if number not in chapter_map:
            continue
        raw = self.storage.load_chapter(novel_id, chapter_id) or {}
        translated = self.storage.load_translated_chapter(novel_id, chapter_id) or {}

        raw_text = raw.get("text")
        translated_raw_text = translated.get("text")
        source_text = raw_text if isinstance(raw_text, str) else ""
        translated_text = translated_raw_text if isinstance(translated_raw_text, str) else ""
        stored_score = translated.get("confidence_score") if isinstance(translated.get("confidence_score"), float) else None
        polish_needed_flag = translated.get("polish_needed") if isinstance(translated.get("polish_needed"), bool) else None

        if low_confidence_only and isinstance(polish_needed_flag, bool):
            if polish_needed_flag:
                low_confidence_ids.append(chapter_id)
            continue

        confidence_score = stored_score if isinstance(stored_score, float) else self._score_translation_confidence(source_text, translated_text)

        if confidence_score < normalized_threshold:
            low_confidence_ids.append(chapter_id)

    if not low_confidence_ids:
        return self._phase_payload(
            phase="phase3_polish",
            status="completed",
            message="No low-confidence chapters required polishing.",
            novel_id=novel_id,
            selected_chapters=len(selected_numbers),
            polished=0,
            candidates=0,
            threshold=normalized_threshold,
        )

    approved_glossary = [
        dict(entry)
        for entry in self.storage.load_glossary(novel_id)
        if isinstance(entry, dict) and str(entry.get("status") or "pending").strip().lower() in {"approved", "translated"}
    ]
    retranslate_selection = ",".join(low_confidence_ids)
    await self.translate_chapters(
        source_key=source_key,
        novel_id=novel_id,
        chapters=retranslate_selection,
        provider_key=effective_provider,
        provider_model=effective_model,
        force=True,
        source_language=source_language,
        target_language=target_language,
        glossary=approved_glossary,
        style_preset="polish",
        confidence_threshold=normalized_threshold,
        mark_polish_needed=True,
        consistency_mode=consistency_mode,
        json_output=json_output,
    )
    return self._phase_payload(
        phase="phase3_polish",
        status="completed",
        message="Low-confidence chapters polished.",
        novel_id=novel_id,
        selected_chapters=len(selected_numbers),
        polished=len(low_confidence_ids),
        candidates=len(low_confidence_ids),
        chapter_ids=low_confidence_ids,
        threshold=normalized_threshold,
    )


async def run_phased_translation_pipeline(
    self: Any,
    *,
    source_key: str,
    novel_id: str,
    chapters: str = "all",
    phase: str = "full",
    glossary_provider_key: str | None = None,
    glossary_provider_model: str | None = None,
    review_auto_approve: bool = True,
    review_min_target_length: int = 2,
    body_provider_key: str | None = None,
    body_provider_model: str | None = None,
    source_language: str | None = None,
    target_language: str | None = None,
    confidence_threshold: float = 0.55,
    polish_low_confidence_only: bool = True,
    consistency_mode: bool = False,
    json_output: bool = False,
    run_polish_phase: bool = False,
) -> dict[str, Any]:
    """Run one phase or the full phase chain with a shared payload schema."""
    normalized_phase = phase.strip().lower()
    if normalized_phase not in {"1", "1b", "2", "3", "full"}:
        raise ValueError("phase must be one of: 1, 1b, 2, 3, full")

    results: dict[str, Any] = {}

    if normalized_phase in {"1", "full"}:
        results["phase1"] = await self.extract_glossary_terms(
            novel_id=novel_id,
            chapters=chapters,
            max_terms=50,
        )
        if normalized_phase == "1":
            return self._phase_payload(
                phase="phase1_glossary_extraction",
                status="completed",
                message="Phase 1 completed.",
                novel_id=novel_id,
                blocked=False,
                results=results,
            )

    if normalized_phase in {"1b", "full"}:
        results["phase1b"] = await self.translate_glossary_terms(
            novel_id=novel_id,
            provider_key=glossary_provider_key,
            provider_model=glossary_provider_model,
            only_pending=True,
        )
        if normalized_phase == "1b":
            return self._phase_payload(
                phase="phase1b_glossary_translation",
                status="completed",
                message="Phase 1b completed.",
                novel_id=novel_id,
                blocked=False,
                results=results,
            )

    if normalized_phase == "full":
        results["phase1c"] = await self.review_glossary_terms(
            novel_id=novel_id,
            auto_approve_translated=review_auto_approve,
            min_target_length=review_min_target_length,
        )

    if normalized_phase in {"2", "full"}:
        counts = glossary_status_counts(self.storage.load_glossary(novel_id))
        pending = int(counts.get("pending", 0))
        if pending > 0:
            return self._phase_payload(
                phase="phase2_body_translation",
                status="blocked",
                message="Glossary review required before phase 2.",
                novel_id=novel_id,
                blocked=True,
                blocked_reason=f"Pending glossary terms: {pending}.",
                results=results,
            )

        await self.translate_chapters(
            source_key=source_key,
            novel_id=novel_id,
            chapters=chapters,
            provider_key=body_provider_key,
            provider_model=body_provider_model,
            force=False,
            source_language=source_language,
            target_language=target_language,
            confidence_threshold=confidence_threshold,
            mark_polish_needed=True,
            consistency_mode=consistency_mode,
            json_output=json_output,
        )
        results["phase2"] = self._phase_payload(
            phase="phase2_body_translation",
            status="completed",
            message="Phase 2 completed.",
            novel_id=novel_id,
            chapters=chapters,
            threshold=max(0.0, min(1.0, confidence_threshold)),
        )

        if normalized_phase == "2":
            return self._phase_payload(
                phase="phase2_body_translation",
                status="completed",
                message="Phase 2 completed.",
                novel_id=novel_id,
                blocked=False,
                results=results,
            )

    if normalized_phase in {"3", "full"} and (normalized_phase == "3" or run_polish_phase):
        results["phase3"] = await self.polish_low_confidence_chapters(
            source_key=source_key,
            novel_id=novel_id,
            chapters=chapters,
            provider_key=body_provider_key,
            provider_model=body_provider_model,
            source_language=source_language,
            target_language=target_language,
            confidence_threshold=confidence_threshold,
            low_confidence_only=polish_low_confidence_only,
            consistency_mode=True,
            json_output=json_output,
        )

        if normalized_phase == "3":
            return self._phase_payload(
                phase="phase3_polish",
                status="completed",
                message="Phase 3 completed.",
                novel_id=novel_id,
                blocked=False,
                results=results,
            )

    return self._phase_payload(
        phase="pipeline_full",
        status="completed",
        message="Phased pipeline completed.",
        novel_id=novel_id,
        blocked=False,
        results=results,
    )


async def _translate_text(
    self: Any,
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
    self: Any,
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

    synopsis = translated_metadata.get("synopsis") or translated_metadata.get("description") or translated_metadata.get("summary")
    if isinstance(synopsis, str) and synopsis:
        if previous.get("synopsis") == synopsis and isinstance(previous.get("translated_synopsis"), str):
            translated_metadata["translated_synopsis"] = previous["translated_synopsis"]
        else:
            translated_metadata["translated_synopsis"] = await self._translate_text(synopsis)

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


async def translate_chapters(
    self: Any,
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
    confidence_threshold: float = 0.55,
    mark_polish_needed: bool = True,
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
    normalized_threshold = max(0.0, min(1.0, confidence_threshold))

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
            confidence_score = self._score_translation_confidence(raw_text or "", translated)
            polish_needed = mark_polish_needed and confidence_score < normalized_threshold
            self.storage.save_translated_chapter(
                novel_id,
                chapter_id,
                translated,
                provider=result.provider_key,
                model=result.provider_model,
                confidence_score=confidence_score,
                polish_needed=polish_needed,
                confidence_details={
                    "threshold": normalized_threshold,
                    "source_length": len((raw_text or "").strip()),
                    "translated_length": len(translated.strip()),
                    "style_preset": style_preset,
                },
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
    self: Any,
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
