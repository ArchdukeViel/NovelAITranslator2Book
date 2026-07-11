"""Translation metadata helpers — extracted from translation.py.

Metadata translation, batch translation, cache/estimate, text translation,
metadata fields translation, and request estimation.
Core orchestration and lineage/delta are in other split files.
"""

from __future__ import annotations

import json
import logging
import math
import re
from typing import Any

from novelai.config.settings import settings
from novelai.prompts import (
    METADATA_TRANSLATION_PROMPT_VERSION,
    build_metadata_batch_translation_prompt,
    build_metadata_translation_prompt,
)
from novelai.providers.model_fallbacks import model_candidates
from novelai.translation.pipeline.stages.segment import SmartSegmentStage
from novelai.translation.qa import extract_unambiguous_json_object

logger = logging.getLogger(__name__)

_METADATA_TRANSLATION_PROMPT_SOURCES = {"gemini"}
_CJK_RE = re.compile(r"[\u3040-\u30ff\u3400-\u9fff]")
_GENERIC_TITLE_RE = re.compile(
    r"^\s*(?:episode|chapter|part|volume|section|arc)(?:\s+[\w.-]+)?\s*$",
    flags=re.IGNORECASE,
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


def _metadata_cache_text(source_text: str, field: str) -> str:
    return f"metadata:{field}:{settings.TRANSLATION_TARGET_LANGUAGE}:{source_text.strip()}"


def _parse_metadata_batch_response(raw_text: str) -> dict[str, str]:
    payload = json.loads(extract_unambiguous_json_object(raw_text))
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
        normalized_id = str(item_id)
        if normalized_id in translations:
            raise ValueError(f"Metadata batch response duplicated item id {normalized_id!r}.")
        translations[normalized_id] = str(translation)
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
            "Metadata translation skipped because no active Gemini provider is configured. "
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
                "Metadata translation skipped because no active Gemini provider is configured. "
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
        raise last_error
    raise RuntimeError(f"No translation models available for provider {provider_key}.")


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
    new_lineage_by_chapter: dict[str, list[dict[str, Any]]] = {}
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
        from novelai.services.orchestration.translation_lineage import _lineage_from_paragraphs

        new_lineage_by_chapter[chapter_id] = _lineage_from_paragraphs(paragraphs)
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
    from novelai.services.orchestration.translation_lineage import _estimate_delta_requests

    delta = _estimate_delta_requests(
        self,
        novel_id=novel_id,
        new_lineage_by_chapter=new_lineage_by_chapter,
        full_body_requests=estimated_chunks,
        segment=segment,
    )

    return {
        "novel_id": novel_id,
        "source_key": source_key,
        "chapters_selected": len(selected_numbers),
        "chapters_included": len(included_numbers),
        "include_already_translated": bool(include_already_translated),
        "metadata_requests": metadata_requests,
        "body_requests": body_requests,
        "delta": delta,
        "total_estimated_requests": metadata_requests["total"] + estimated_chunks,
        "assumptions": {
            "chunk_target_chars": segment.target_chars,
            "chunk_hard_max_chars": segment.hard_max_chars,
            "adaptive_chunking": segment.adaptive_chunking_enabled,
            "adaptive_soft_target_chars": segment.adaptive_soft_target_chars,
            "adaptive_hard_max_chars": segment.adaptive_hard_max_chars,
            "chunk_overlap_paragraphs": segment.overlap_paragraphs,
            "conditional_overlap": segment.conditional_overlap_enabled,
            "default_overlap_paragraphs": segment.default_overlap_paragraphs,
            "unsafe_boundary_overlap_paragraphs": segment.unsafe_boundary_overlap_paragraphs,
            "boundary_context_chars": segment.boundary_context_chars,
            "allow_multi_chapter_bundles": segment.allow_multi_chapter_bundles,
            "max_chapters_per_bundle": segment.max_chapters_per_bundle,
            "metadata_batching": True,
            "metadata_chapter_title_batch_size": settings.TRANSLATION_METADATA_CHAPTER_TITLE_BATCH_SIZE,
            "paragraph_hash_lineage": True,
            "delta_window_padding_paragraphs": settings.TRANSLATION_DELTA_WINDOW_PADDING_PARAGRAPHS,
            "delta_retranslation_enabled": settings.TRANSLATION_DELTA_RETRANSLATION_ENABLED,
            "delta_require_structured_paragraph_map": settings.TRANSLATION_DELTA_REQUIRE_STRUCTURED_PARAGRAPH_MAP,
            "delta_force_full_on_unsafe": settings.TRANSLATION_DELTA_FORCE_FULL_ON_UNSAFE,
            "provider_calls": False,
            "already_translated_chapters": "included" if include_already_translated else "excluded",
        },
    }
