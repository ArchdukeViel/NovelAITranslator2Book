from __future__ import annotations

import contextlib
import json
import logging
import math
import re
from typing import Any

from novelai.config.settings import settings
from novelai.core.chapter_state import ChapterState
from novelai.glossary import glossary_status_counts, normalize_glossary_entries
from novelai.prompts import (
    METADATA_TRANSLATION_PROMPT_VERSION,
    build_metadata_batch_translation_prompt,
    build_metadata_translation_prompt,
)
from novelai.providers.model_fallbacks import model_candidates
from novelai.services.orchestration.common import PreflightIssue, _make_state_data
from novelai.sources.base import SourceAdapter
from novelai.translation.pipeline.stages.segment import SmartSegmentStage

logger = logging.getLogger(__name__)

_METADATA_TRANSLATION_PROMPT_SOURCES = {"gemini", "openai"}
_CJK_RE = re.compile(r"[\u3040-\u30ff\u3400-\u9fff]")
_GENERIC_TITLE_RE = re.compile(
    r"^\s*(?:episode|chapter|part|volume|section|arc)(?:\s+[\w.-]+)?\s*$",
    flags=re.IGNORECASE,
)


def _pipeline_context_from_exception(exc: BaseException) -> Any | None:
    context = getattr(exc, "pipeline_context", None)
    return context if context is not None else None


def _pipeline_events_from_exception(exc: BaseException) -> list[dict[str, Any]]:
    events = getattr(exc, "pipeline_events", None)
    if not isinstance(events, list):
        context = _pipeline_context_from_exception(exc)
        events = getattr(context, "pipeline_events", None)
    if not isinstance(events, list):
        return []
    return [dict(event) for event in events if isinstance(event, dict)]


def _failed_stage_name_from_exception(exc: BaseException) -> str:
    failed_stage = getattr(exc, "failed_stage_name", None)
    if isinstance(failed_stage, str) and failed_stage.strip():
        return failed_stage.strip()
    for event in reversed(_pipeline_events_from_exception(exc)):
        if event.get("status_after") == "failed" and isinstance(event.get("stage_name"), str):
            return str(event["stage_name"])
    context = _pipeline_context_from_exception(exc)
    current_stage = getattr(context, "current_stage", None)
    if isinstance(current_stage, str) and current_stage.strip():
        return current_stage.strip()
    return "Pipeline"


def _persist_chunk_qa_results_to_outputs(storage: Any, novel_id: str, chunk_states: dict[str, Any]) -> None:
    if not isinstance(novel_id, str) or not novel_id.strip():
        return
    for chunk_id, state in chunk_states.items():
        if not isinstance(chunk_id, str) or not chunk_id.strip() or not isinstance(state, dict):
            continue
        outputs = storage.read_translation_output(novel_id, chunk_id=chunk_id)
        if not isinstance(outputs, list) or not outputs:
            continue
        latest = outputs[-1]
        if not isinstance(latest, dict):
            continue
        qa_status = state.get("status")
        storage.save_translation_output(
            {
                **latest,
                "output_id": latest.get("output_id"),
                "qa_score": state.get("qa_score"),
                "qa_warnings": state.get("qa_warnings") or [],
                "qa_errors": state.get("qa_errors") or [],
                "qa_status": qa_status,
            }
        )


def _metadata_translation_max_tokens(source_text: str, field: str) -> int:
    normalized_field = field.strip().lower()
    if normalized_field == "author":
        return 48
    if normalized_field in {"title", "chapter_title", "glossary_term"}:
        return 96
    if normalized_field == "synopsis":
        return min(2048, max(384, len(source_text) // 2 + 192))
    return 256


def _clean_metadata_translation(translated: str, source_text: str, field: str) -> str:
    cleaned = translated.strip()
    if not cleaned:
        return source_text

    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```[a-zA-Z0-9_-]*\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned).strip()

    cleaned = re.sub(
        r"^(translation|translated text|english|title|author|chapter title)\s*:\s*",
        "",
        cleaned,
        flags=re.IGNORECASE,
    ).strip()

    normalized_field = field.strip().lower()
    if normalized_field in {"title", "author", "chapter_title", "glossary_term"}:
        lines = [line.strip().strip("\"'") for line in cleaned.splitlines() if line.strip()]
        if lines:
            cleaned = lines[0]
        cleaned = re.sub(r"^[-*]\s+", "", cleaned).strip()

    return cleaned or source_text


def _source_title_core(source_text: str) -> str:
    text = source_text.strip()
    text = re.sub(
        r"^\s*(?:第\s*[0-9０-９一二三四五六七八九十百千万]+\s*[話章部幕節]|[0-9０-９]+\s*[話章部幕節])\s*",
        "",
        text,
    )
    text = re.sub(r"^\s*(?:episode|chapter|part|volume|section|arc)\s*[\w.-]*\s*", "", text, flags=re.IGNORECASE)
    return text.strip(" \t\r\n:：-–—_、。.,")


def _metadata_translation_is_usable(source_text: str, translated: str, field: str) -> bool:
    normalized_field = field.strip().lower()
    candidate = translated.strip()
    if not candidate:
        return False

    source = source_text.strip()
    if candidate == source:
        return not _CJK_RE.search(source)

    if normalized_field in {"title", "chapter_title", "glossary_term"}:
        source_core = _source_title_core(source)
        candidate_core = _source_title_core(candidate)
        source_has_meaning_after_marker = bool(source_core) and source_core != source
        if source_has_meaning_after_marker and _GENERIC_TITLE_RE.fullmatch(candidate):
            return False
        if source_has_meaning_after_marker and not candidate_core:
            return False

    if normalized_field in {"title", "chapter_title", "synopsis", "glossary_term"}:
        source_has_cjk = bool(_CJK_RE.search(source))
        candidate_has_cjk = bool(_CJK_RE.search(candidate))
        candidate_has_latin = bool(re.search(r"[A-Za-z]", candidate))
        if source_has_cjk and candidate_has_cjk and not candidate_has_latin:
            return False

    return True


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
    field: str | None = None,
) -> str:
    normalized = text.strip()
    if not normalized:
        return normalized

    resolved_provider_key, resolved_provider_model = self._resolve_provider_and_model(provider_key, provider_model)
    provider_key = str(resolved_provider_key)
    provider_model = str(resolved_provider_model)
    if provider_key == "dummy":
        if field is not None:
            raise RuntimeError(
                "Metadata translation skipped because no active Gemini/OpenAI provider is configured. "
                "Add and use a provider API token in Settings."
            )
        return normalized

    provider = self._provider_factory(provider_key)
    try:
        supported_models = provider.available_models() or []
    except Exception:
        supported_models = []

    field_key = field.strip().lower() if isinstance(field, str) and field.strip() else None
    prompt = normalized
    max_tokens: int | None = None
    provider_kwargs: dict[str, Any] = {}
    if field_key and provider_key in _METADATA_TRANSLATION_PROMPT_SOURCES:
        prompt = build_metadata_translation_prompt(normalized, field_key)
        max_tokens = _metadata_translation_max_tokens(normalized, field_key)
        if provider_key == "gemini":
            provider_kwargs["temperature"] = 0.0

    cache_text = normalized if field_key is None else f"metadata:{field_key}:{settings.TRANSLATION_TARGET_LANGUAGE}:{normalized}"
    candidates = model_candidates(provider_key, provider_model, supported_models)
    last_error: Exception | None = None
    for candidate_model in candidates:
        cached = self._cache.get(cache_text, provider.key, candidate_model)
        if cached is not None:
            if field_key and not _metadata_translation_is_usable(normalized, cached, field_key):
                logger.warning(
                    "Ignoring cached incomplete metadata translation for %s with %s/%s.",
                    field_key,
                    provider_key,
                    candidate_model,
                )
            else:
                return cached

        try:
            result = await provider.translate(
                prompt=prompt,
                model=candidate_model,
                max_tokens=max_tokens,
                **provider_kwargs,
            )
        except Exception as exc:
            last_error = exc
            logger.warning(
                "Metadata translation failed with %s/%s; trying fallback model if available: %s",
                provider_key,
                candidate_model,
                exc,
            )
            continue

        translated = str(result.get("text", "")).strip() or normalized
        if field_key:
            translated = _clean_metadata_translation(translated, normalized, field_key)
            if not _metadata_translation_is_usable(normalized, translated, field_key):
                last_error = RuntimeError(
                    f"Incomplete metadata translation for {field_key} with {provider_key}/{candidate_model}: {translated!r}"
                )
                logger.warning(
                    "Metadata translation from %s/%s looked incomplete for %s; trying fallback model if available.",
                    provider_key,
                    candidate_model,
                    field_key,
                )
                continue
        self._record_usage(provider.key, candidate_model, result.get("metadata"))
        self._cache.set(cache_text, provider.key, candidate_model, translated)
        return translated

    if last_error is not None:
        if field_key:
            logger.warning(
                "Metadata translation fell back to original text for %s after all models failed quality checks: %s",
                field_key,
                last_error,
            )
            return normalized
        raise last_error
    raise RuntimeError(f"No translation models available for provider {provider_key}.")


def _metadata_cache_text(source_text: str, field: str) -> str:
    return f"metadata:{field}:{settings.TRANSLATION_TARGET_LANGUAGE}:{source_text.strip()}"


def _parse_metadata_batch_response(raw_text: str) -> dict[str, str]:
    text = raw_text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z0-9_-]*\s*", "", text)
        text = re.sub(r"\s*```$", "", text).strip()
    payload = json.loads(text)
    if not isinstance(payload, dict) or not isinstance(payload.get("items"), list):
        raise ValueError("Metadata batch response must be a JSON object with an items array.")
    translations: dict[str, str] = {}
    for item in payload["items"]:
        if not isinstance(item, dict):
            continue
        item_id = item.get("id")
        translation = item.get("translation", item.get("translated_text"))
        if item_id is None or translation is None:
            continue
        translations[str(item_id)] = str(translation)
    return translations


def _metadata_batch_size(value: object) -> int:
    if isinstance(value, bool):
        return 25
    if isinstance(value, int) and value > 0:
        return value
    return 25


def _metadata_batch_max_tokens(items: list[dict[str, str]]) -> int:
    total_source_chars = sum(len(item["source_text"]) for item in items)
    return min(4096, max(256, total_source_chars // 2 + 128 * len(items)))


async def _translate_metadata_batch(
    self: Any,
    items: list[dict[str, str]],
    *,
    provider_key: str | None = None,
    provider_model: str | None = None,
) -> dict[str, str]:
    if not items:
        return {}

    resolved_provider_key, resolved_provider_model = self._resolve_provider_and_model(provider_key, provider_model)
    provider_key = str(resolved_provider_key)
    provider_model = str(resolved_provider_model)
    if provider_key == "dummy":
        raise RuntimeError(
            "Metadata translation skipped because no active Gemini/OpenAI provider is configured. "
            "Add and use a provider API token in Settings."
        )

    provider = self._provider_factory(provider_key)
    try:
        supported_models = provider.available_models() or []
    except Exception:
        supported_models = []

    prompt = build_metadata_batch_translation_prompt(items)
    provider_kwargs: dict[str, Any] = {}
    if provider_key == "gemini":
        provider_kwargs["temperature"] = 0.0

    expected_by_id = {item["id"]: item for item in items}
    last_error: Exception | None = None
    for candidate_model in model_candidates(provider_key, provider_model, supported_models):
        try:
            result = await provider.translate(
                prompt=prompt,
                model=candidate_model,
                max_tokens=_metadata_batch_max_tokens(items),
                **provider_kwargs,
            )
            raw_translations = _parse_metadata_batch_response(str(result.get("text", "")))
            translations: dict[str, str] = {}
            for item_id, item in expected_by_id.items():
                raw_translation = raw_translations.get(item_id)
                if raw_translation is None:
                    raise RuntimeError(f"Metadata batch response missing item id {item_id!r}.")
                translated = _clean_metadata_translation(raw_translation, item["source_text"], item["field"])
                if not _metadata_translation_is_usable(item["source_text"], translated, item["field"]):
                    raise RuntimeError(f"Metadata batch translation for {item_id!r} looked incomplete.")
                translations[item_id] = translated
            self._record_usage(provider.key, candidate_model, result.get("metadata"))
            for item in items:
                self._cache.set(_metadata_cache_text(item["source_text"], item["field"]), provider.key, candidate_model, translations[item["id"]])
            return translations
        except Exception as exc:
            last_error = exc
            logger.warning(
                "Metadata batch translation failed with %s/%s; trying fallback model if available: %s",
                provider_key,
                candidate_model,
                exc,
            )
            continue

    if last_error is not None:
        raise last_error
    raise RuntimeError(f"No translation models available for provider {provider_key}.")


async def _translate_metadata_items(
    self: Any,
    items: list[dict[str, str]],
) -> dict[str, str]:
    if not items:
        return {}
    try:
        return await _translate_metadata_batch(self, items)
    except Exception as exc:
        logger.warning("Metadata batch fell back to individual translation: %s", exc)

    translations: dict[str, str] = {}
    for item in items:
        translations[item["id"]] = await self._translate_text(item["source_text"], field=item["field"])
    return translations


def _cached_metadata_translation(self: Any, source_text: str, field: str) -> str | None:
    provider_key, provider_model = self._resolve_provider_and_model(None, None)
    if provider_key == "dummy":
        return None
    try:
        provider = self._provider_factory(provider_key)
    except Exception:
        return None
    try:
        supported_models = provider.available_models() or []
    except Exception:
        supported_models = []
    cache_text = _metadata_cache_text(source_text, field)
    for candidate_model in model_candidates(provider_key, provider_model, supported_models):
        cached = self._cache.get(cache_text, provider.key, candidate_model)
        if cached is not None and _metadata_translation_is_usable(source_text, cached, field):
            return cached
    return None


def _can_reuse_metadata_translation(source_text: str, previous_source: Any, previous_translation: Any, field: str) -> bool:
    if previous_source != source_text:
        return False
    if not isinstance(previous_translation, str) or not previous_translation.strip():
        return False
    return _metadata_translation_is_usable(source_text, previous_translation, field)


def _metadata_field_estimate(
    self: Any,
    metadata: dict[str, Any],
    source_key: str,
    translated_key: str,
    field: str,
) -> tuple[bool, str | None]:
    source_text = metadata.get(source_key)
    if not isinstance(source_text, str) or not source_text.strip():
        return False, None
    if metadata.get("metadata_translation_prompt_version") == METADATA_TRANSLATION_PROMPT_VERSION and _can_reuse_metadata_translation(
        source_text,
        source_text,
        metadata.get(translated_key),
        field,
    ):
        return False, "reused"
    if _cached_metadata_translation(self, source_text, field) is not None:
        return False, "cached"
    return True, None


def _chapter_title_estimate(self: Any, chapter: dict[str, Any], *, can_reuse: bool) -> tuple[bool, str | None, str | None]:
    chapter_title = chapter.get("title")
    if not isinstance(chapter_title, str) or not chapter_title.strip():
        return False, None, None
    if can_reuse and _can_reuse_metadata_translation(
        chapter_title,
        chapter.get("title"),
        chapter.get("translated_title"),
        "chapter_title",
    ):
        return False, "reused", chapter_title.strip()
    if _cached_metadata_translation(self, chapter_title, "chapter_title") is not None:
        return False, "cached", chapter_title.strip()
    return True, None, chapter_title.strip()


def _metadata_request_estimate(
    self: Any,
    metadata: dict[str, Any],
    *,
    included_chapter_ids: set[str],
) -> dict[str, int | bool]:
    reusable_fields = 0
    cached_fields = 0

    title_needed, title_skip = _metadata_field_estimate(self, metadata, "title", "translated_title", "title")
    author_needed, author_skip = _metadata_field_estimate(self, metadata, "author", "translated_author", "author")
    synopsis_source_key = next(
        (
            key
            for key in ("synopsis", "description", "summary")
            if isinstance(metadata.get(key), str) and str(metadata.get(key)).strip()
        ),
        None,
    )
    synopsis_needed, synopsis_skip = (
        _metadata_field_estimate(self, metadata, synopsis_source_key, "translated_synopsis", "synopsis")
        if synopsis_source_key is not None
        else (False, None)
    )
    for skip_reason in (title_skip, author_skip, synopsis_skip):
        if skip_reason == "reused":
            reusable_fields += 1
        elif skip_reason == "cached":
            cached_fields += 1
    novel_fields = int(title_needed or author_needed or synopsis_needed)

    can_reuse_previous = metadata.get("metadata_translation_prompt_version") == METADATA_TRANSLATION_PROMPT_VERSION
    chapters = metadata.get("chapters", [])
    unique_chapter_titles: set[str] = set()
    if isinstance(chapters, list):
        for chapter in chapters:
            if not isinstance(chapter, dict):
                continue
            chapter_id = str(chapter.get("id"))
            if chapter_id not in included_chapter_ids:
                continue
            needed, skip_reason, title_source = _chapter_title_estimate(self, chapter, can_reuse=can_reuse_previous)
            if skip_reason == "reused":
                reusable_fields += 1
            elif skip_reason == "cached":
                cached_fields += 1
            if needed and title_source is not None:
                unique_chapter_titles.add(title_source)

    batch_size = _metadata_batch_size(settings.TRANSLATION_METADATA_CHAPTER_TITLE_BATCH_SIZE)
    chapter_titles = math.ceil(len(unique_chapter_titles) / batch_size) if unique_chapter_titles else 0
    total = novel_fields + chapter_titles
    return {
        "title": int(title_needed),
        "author": int(author_needed),
        "synopsis": int(synopsis_needed),
        "novel_fields": novel_fields,
        "chapter_titles": chapter_titles,
        "chapter_title_batch_size": batch_size,
        "unique_chapter_titles": len(unique_chapter_titles),
        "reusable_fields": reusable_fields,
        "cached_fields": cached_fields,
        "metadata_batching": True,
        "total": total,
    }


def estimate_translation_requests(
    self: Any,
    *,
    source_key: str,
    novel_id: str,
    chapters: str = "all",
    include_already_translated: bool = False,
) -> dict[str, Any]:
    """Estimate current-baseline translation requests without provider calls or writes."""
    metadata = self.storage.load_metadata(novel_id)
    if not metadata:
        raise RuntimeError("Metadata not found; import or scrape a novel first.")

    chapter_map = {
        int(chapter["id"]): chapter
        for chapter in metadata.get("chapters", [])
        if isinstance(chapter, dict) and str(chapter.get("id", "")).isdigit()
    }
    selected_numbers = self._selected_chapter_numbers(metadata, chapters)
    included_numbers: list[int] = []
    skipped_translated: list[str] = []
    for number in selected_numbers:
        if number not in chapter_map:
            continue
        chapter_id = str(number)
        if not include_already_translated and self.storage.load_translated_chapter(novel_id, chapter_id) is not None:
            skipped_translated.append(chapter_id)
            continue
        included_numbers.append(number)

    included_chapter_ids = {str(number) for number in included_numbers}
    metadata_requests = _metadata_request_estimate(self, metadata, included_chapter_ids=included_chapter_ids)

    segment = SmartSegmentStage()
    per_chapter: list[dict[str, Any]] = []
    missing_text: list[str] = []
    estimated_chunks = 0
    for number in included_numbers:
        chapter_id = str(number)
        raw_chapter = self.storage.load_chapter(novel_id, chapter_id)
        raw_text = raw_chapter.get("text") if isinstance(raw_chapter, dict) else None
        if not isinstance(raw_text, str):
            missing_text.append(chapter_id)
            continue

        paragraphs, chunks_for_chapter, warnings = segment.estimate_chapter_chunks(
            novel_id=novel_id,
            chapter_id=chapter_id,
            text=raw_text,
        )
        chapter_estimate: dict[str, Any] = {
            "chapter_id": chapter_id,
            "source_chars": len(raw_text),
            "paragraphs": len(paragraphs),
            "chunks": len(chunks_for_chapter),
        }
        if warnings:
            chapter_estimate["warnings"] = warnings
        per_chapter.append(chapter_estimate)
        estimated_chunks += len(chunks_for_chapter)

    body_requests = {
        "estimated_chunks": estimated_chunks,
        "chapters_with_text": len(per_chapter),
        "chapters_missing_text": missing_text,
        "chapters_skipped_translated": skipped_translated,
        "per_chapter": per_chapter,
    }

    return {
        "novel_id": novel_id,
        "source_key": source_key,
        "chapters_selected": len(selected_numbers),
        "chapters_included": len(included_numbers),
        "include_already_translated": bool(include_already_translated),
        "metadata_requests": metadata_requests,
        "body_requests": body_requests,
        "total_estimated_requests": metadata_requests["total"] + estimated_chunks,
        "assumptions": {
            "chunk_target_chars": segment.target_chars,
            "chunk_hard_max_chars": segment.hard_max_chars,
            "chunk_overlap_paragraphs": segment.overlap_paragraphs,
            "allow_multi_chapter_bundles": segment.allow_multi_chapter_bundles,
            "max_chapters_per_bundle": segment.max_chapters_per_bundle,
            "metadata_batching": True,
            "metadata_chapter_title_batch_size": settings.TRANSLATION_METADATA_CHAPTER_TITLE_BATCH_SIZE,
            "adaptive_chunking": False,
            "provider_calls": False,
            "already_translated_chapters": "included" if include_already_translated else "excluded",
        },
    }


async def _translate_metadata_fields(
    self: Any,
    metadata: dict[str, Any],
    existing_metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Translate metadata fields in provider-agnostic batches.

    Reuses previously translated values from *existing_metadata* when the
    source text has not changed, avoiding redundant API calls.
    """
    translated_metadata = dict(metadata)
    previous = existing_metadata or {}
    can_reuse_previous = previous.get("metadata_translation_prompt_version") == METADATA_TRANSLATION_PROMPT_VERSION

    novel_items: list[dict[str, str]] = []
    title = translated_metadata.get("title")
    if isinstance(title, str) and title:
        if can_reuse_previous and _can_reuse_metadata_translation(
            title,
            previous.get("title"),
            previous.get("translated_title"),
            "title",
        ):
            translated_metadata["translated_title"] = previous["translated_title"]
        elif cached := _cached_metadata_translation(self, title, "title"):
            translated_metadata["translated_title"] = cached
        else:
            novel_items.append({"id": "novel_title", "field": "title", "source_text": title.strip()})

    author = translated_metadata.get("author")
    if isinstance(author, str) and author:
        if can_reuse_previous and _can_reuse_metadata_translation(
            author,
            previous.get("author"),
            previous.get("translated_author"),
            "author",
        ):
            translated_metadata["translated_author"] = previous["translated_author"]
        elif cached := _cached_metadata_translation(self, author, "author"):
            translated_metadata["translated_author"] = cached
        else:
            novel_items.append({"id": "author", "field": "author", "source_text": author.strip()})

    synopsis = translated_metadata.get("synopsis") or translated_metadata.get("description") or translated_metadata.get("summary")
    if isinstance(synopsis, str) and synopsis:
        if can_reuse_previous and _can_reuse_metadata_translation(
            synopsis,
            previous.get("synopsis"),
            previous.get("translated_synopsis"),
            "synopsis",
        ):
            translated_metadata["translated_synopsis"] = previous["translated_synopsis"]
        elif cached := _cached_metadata_translation(self, synopsis, "synopsis"):
            translated_metadata["translated_synopsis"] = cached
        else:
            novel_items.append({"id": "synopsis", "field": "synopsis", "source_text": synopsis.strip()})

    if novel_items:
        novel_translations = await _translate_metadata_items(self, novel_items)
        if "novel_title" in novel_translations:
            translated_metadata["translated_title"] = novel_translations["novel_title"]
        if "author" in novel_translations:
            translated_metadata["translated_author"] = novel_translations["author"]
        if "synopsis" in novel_translations:
            translated_metadata["translated_synopsis"] = novel_translations["synopsis"]

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
    title_to_item_id: dict[str, str] = {}
    title_item_sources: dict[str, str] = {}
    chapter_item_refs: dict[str, list[dict[str, Any]]] = {}
    for chapter in chapters:
        if not isinstance(chapter, dict):
            continue

        translated_chapter = dict(chapter)
        chapter_id = str(chapter.get("id"))
        previous_chapter = previous_by_id.get(chapter_id, {})
        chapter_title = translated_chapter.get("title")
        if isinstance(chapter_title, str) and chapter_title:
            if can_reuse_previous and _can_reuse_metadata_translation(
                chapter_title,
                previous_chapter.get("title"),
                previous_chapter.get("translated_title"),
                "chapter_title",
            ):
                translated_chapter["translated_title"] = previous_chapter["translated_title"]
            elif cached := _cached_metadata_translation(self, chapter_title, "chapter_title"):
                translated_chapter["translated_title"] = cached
            else:
                normalized_title = chapter_title.strip()
                item_id = title_to_item_id.get(normalized_title)
                if item_id is None:
                    item_id = f"chapter:{chapter_id}"
                    title_to_item_id[normalized_title] = item_id
                    title_item_sources[item_id] = normalized_title
                chapter_item_refs.setdefault(item_id, []).append(translated_chapter)

        translated_chapters.append(translated_chapter)

    batch_size = _metadata_batch_size(settings.TRANSLATION_METADATA_CHAPTER_TITLE_BATCH_SIZE)
    chapter_items = [
        {"id": item_id, "field": "chapter_title", "source_text": source_text}
        for item_id, source_text in title_item_sources.items()
    ]
    for start in range(0, len(chapter_items), batch_size):
        batch = chapter_items[start : start + batch_size]
        translations = await _translate_metadata_items(self, batch)
        for item in batch:
            translated_title = translations.get(item["id"])
            if translated_title is None:
                translated_title = await self._translate_text(item["source_text"], field="chapter_title")
            for translated_chapter in chapter_item_refs.get(item["id"], []):
                translated_chapter["translated_title"] = translated_title

    translated_metadata["chapters"] = translated_chapters
    translated_metadata["metadata_translation_prompt_version"] = METADATA_TRANSLATION_PROMPT_VERSION
    return translated_metadata


async def translate_chapters(
    self: Any,
    source_key: str,
    novel_id: str,
    chapters: str,
    provider_key: str | None = None,
    provider_model: str | None = None,
    job_id: str | None = None,
    activity_id: str | None = None,
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
            _make_state_data(ChapterState.TRANSLATING, previous=prev_state),
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
                job_id=job_id,
                activity_id=activity_id,
                novel_id=novel_id,
                chapter_id=chapter_id,
                source_key=source_key,
                provider_key=effective_provider_key,
                provider_model=effective_provider_model,
                source_language=effective_source_language,
                target_language=effective_target_language,
                glossary=glossary,
                style_preset=style_preset,
                consistency_mode=consistency_mode,
                json_output=json_output,
                force_retranslate=force,
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
            self.storage.append_pipeline_events(result.pipeline_events)
            for chunk_state in result.chunk_states.values():
                self.storage.upsert_chunk_state(chunk_state)
            _persist_chunk_qa_results_to_outputs(self.storage, novel_id, result.chunk_states)
            self.storage.create_checkpoint(novel_id, chapter_id, "translated")
        except Exception as exc:
            logger.error("Failed to translate chapter %s/%s: %s", novel_id, chapter_id, exc)
            provider_code = getattr(getattr(exc, "provider_error_code", None), "value", None)
            qa_status = getattr(exc, "qa_status", None)
            paused_reason = getattr(exc, "paused_reason", None)
            if isinstance(paused_reason, str) and paused_reason.strip():
                failed_state = ChapterState.TRANSLATED_PARTIAL
            elif qa_status == ChapterState.QA_FAILED.value:
                failed_state = ChapterState.QA_FAILED
            elif qa_status == ChapterState.NEEDS_REVIEW.value:
                failed_state = ChapterState.NEEDS_REVIEW
            else:
                failed_state = ChapterState.NEEDS_RETRY if isinstance(provider_code, str) else ChapterState.FAILED
            self.storage.save_chapter_state(
                novel_id, chapter_id,
                _make_state_data(failed_state, error=str(exc), previous=prev_state),
            )
            details = getattr(exc, "details", None)
            failed_chunk_id = details.get("chunk_id") if isinstance(details, dict) else None
            error_code = provider_code or getattr(exc, "error_code", None) or exc.__class__.__name__
            failed_context = _pipeline_context_from_exception(exc)
            failed_events = _pipeline_events_from_exception(exc)
            if failed_events:
                self.storage.append_pipeline_events(failed_events)
            failed_event_recorded = any(event.get("status_after") == "failed" for event in failed_events)
            chunk_states = getattr(failed_context, "chunk_states", None)
            if isinstance(chunk_states, dict):
                for chunk_state in chunk_states.values():
                    if isinstance(chunk_state, dict):
                        self.storage.upsert_chunk_state(chunk_state)
                _persist_chunk_qa_results_to_outputs(self.storage, novel_id, chunk_states)
            if isinstance(failed_chunk_id, str) and failed_chunk_id.strip():
                self.storage.upsert_chunk_state(
                    {
                        "chunk_id": failed_chunk_id,
                        "novel_id": novel_id,
                        "chapter_ids": [chapter_id],
                        "provider_key": getattr(exc, "provider_key", effective_provider_key),
                        "provider_model": getattr(exc, "provider_model", effective_provider_model),
                        "attempt_number": details.get("attempt_number", 1) if isinstance(details, dict) else 1,
                        "status": failed_state.value,
                        "error_code": str(error_code),
                    }
                )
            if not failed_event_recorded:
                self.storage.append_pipeline_event(
                    {
                        "job_id": job_id,
                        "activity_id": activity_id,
                        "novel_id": novel_id,
                        "chapter_id": chapter_id,
                        "source_key": source_key,
                        "provider_key": getattr(exc, "provider_key", effective_provider_key),
                        "provider_model": getattr(exc, "provider_model", effective_provider_model),
                        "chunk_id": failed_chunk_id,
                        "stage_name": _failed_stage_name_from_exception(exc),
                        "status_before": "running",
                        "status_after": failed_state.value,
                        "error_code": str(error_code),
                        "message": str(exc),
                    }
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
