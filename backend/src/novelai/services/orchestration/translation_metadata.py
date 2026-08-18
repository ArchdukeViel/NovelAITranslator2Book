"""Translation metadata helpers — extracted from translation.py.

Metadata translation, batch translation, cache/estimate, text translation,
metadata fields translation, and request estimation.
Core orchestration and lineage/delta are in other split files.
"""

from __future__ import annotations

import hashlib
import json
import logging
import math
import re
from typing import Any

from novelai.config.settings import GEMINI_DEFAULT_MODEL, settings
from novelai.core.errors import ProviderError, ProviderErrorCode
from novelai.glossary import canonical_glossary_hash
from novelai.prompts import (
    METADATA_TRANSLATION_PROMPT_VERSION,
    build_metadata_batch_translation_prompt,
    build_metadata_translation_prompt,
)
from novelai.prompts.templates import PROMPT_TEMPLATE_VERSION
from novelai.providers.model_fallbacks import model_candidates
from novelai.services.orchestration.glossary import INCREMENTAL_GLOSSARY_DISCOVERY_PROMPT_VERSION
from novelai.services.translation_cache import TranslationCacheService, make_cache_key
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
    if normalized_field in {"title", "chapter_title", "section_title", "glossary_term"}:
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
    if normalized_field in {"title", "author", "chapter_title", "section_title", "glossary_term"}:
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

    if normalized_field in {"title", "chapter_title", "section_title", "glossary_term"}:
        source_core = _source_title_core(source)
        candidate_core = _source_title_core(candidate)
        source_has_meaning_after_marker = bool(source_core) and source_core != source
        if source_has_meaning_after_marker and _GENERIC_TITLE_RE.fullmatch(candidate):
            return False
        if source_has_meaning_after_marker and not candidate_core:
            return False

    if normalized_field in {"title", "chapter_title", "section_title", "synopsis", "glossary_term"}:
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
    candidates = model_candidates(provider_key, provider_model, supported_models)
    if not candidates:
        raise RuntimeError(f"No translation model configured for provider {provider_key}.")
    candidate_model = candidates[0]
    purpose = (
        "chapter_title_translation"
        if all(item.get("field") == "chapter_title" for item in items)
        else "metadata_translation"
    )
    max_attempts = max(1, int(settings.TRANSLATION_MAX_ATTEMPTS_PER_CHUNK or 1))
    for attempt in range(max_attempts):
        try:
            result = await provider.translate(
                prompt=prompt,
                model=candidate_model,
                max_tokens=_metadata_batch_max_tokens(items),
                request_purpose=purpose,
                retry_attempt=attempt,
                chapter_id=items[0].get("id") if len(items) == 1 else None,
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
                self._cache.set(
                    _metadata_cache_text(item["source_text"], item["field"]),
                    provider.key,
                    candidate_model,
                    translations[item["id"]],
                )
            return translations
        except ProviderError as exc:
            retryable = exc.provider_error_code in {
                ProviderErrorCode.RATE_LIMITED,
                ProviderErrorCode.QUOTA_EXHAUSTED,
                ProviderErrorCode.TEMPORARY,
                ProviderErrorCode.TIMEOUT,
            }
            # A provider Retry-After is a defer signal; do not immediately
            # spend another request while the provider's window is closed.
            if not retryable or exc.retry_after_seconds is not None or attempt + 1 >= max_attempts:
                logger.warning(
                    "Metadata batch translation failed with the configured %s/%s; no fallback model will be attempted: %s",
                    provider_key,
                    candidate_model,
                    exc.provider_error_code.value,
                )
                raise
            continue
        except (ValueError, RuntimeError) as exc:
            # Structural batch failures retry the same bounded batch/model.
            # They never fall back to N individual term/title requests.
            if attempt + 1 >= max_attempts:
                logger.warning(
                    "Metadata batch translation failed with the configured %s/%s; no fallback model will be attempted: %s",
                    provider_key,
                    candidate_model,
                    exc.__class__.__name__,
                )
                raise
            continue
    raise RuntimeError("Metadata batch translation exhausted its same-model retry budget.")


async def _translate_metadata_items(
    self: Any,
    items: list[dict[str, str]],
) -> dict[str, str]:
    if not items:
        return {}
    return await _translate_metadata_batch(self, items)


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


def _can_reuse_metadata_translation(
    source_text: str, previous_source: Any, previous_translation: Any, field: str
) -> bool:
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
    if metadata.get(
        "metadata_translation_prompt_version"
    ) == METADATA_TRANSLATION_PROMPT_VERSION and _can_reuse_metadata_translation(
        source_text,
        source_text,
        metadata.get(translated_key),
        field,
    ):
        return False, "reused"
    if _cached_metadata_translation(self, source_text, field) is not None:
        return False, "cached"
    return True, None


def _chapter_title_estimate(
    self: Any, chapter: dict[str, Any], *, can_reuse: bool
) -> tuple[bool, str | None, str | None]:
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


def _section_title_estimate(
    self: Any, chapter: dict[str, Any], *, can_reuse: bool
) -> tuple[bool, str | None, str | None]:
    section_title = chapter.get("section_title")
    if not isinstance(section_title, str) or not section_title.strip():
        return False, None, None
    if can_reuse and _can_reuse_metadata_translation(
        section_title,
        chapter.get("section_title"),
        chapter.get("translated_section_title"),
        "section_title",
    ):
        return False, "reused", section_title.strip()
    if _cached_metadata_translation(self, section_title, "section_title") is not None:
        return False, "cached", section_title.strip()
    return True, None, section_title.strip()


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
            for key in ("narrative_synopsis", "synopsis", "description", "summary")
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
    unique_section_titles: set[str] = set()
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
            section_needed, section_skip, section_source = _section_title_estimate(
                self,
                chapter,
                can_reuse=can_reuse_previous,
            )
            if section_skip == "reused":
                reusable_fields += 1
            elif section_skip == "cached":
                cached_fields += 1
            if section_needed and section_source is not None:
                unique_section_titles.add(section_source)

    batch_size = _metadata_batch_size(settings.TRANSLATION_METADATA_CHAPTER_TITLE_BATCH_SIZE)
    chapter_titles = math.ceil(len(unique_chapter_titles) / batch_size) if unique_chapter_titles else 0
    section_titles = math.ceil(len(unique_section_titles) / batch_size) if unique_section_titles else 0
    total = novel_fields + chapter_titles + section_titles
    return {
        "title": int(title_needed),
        "author": int(author_needed),
        "synopsis": int(synopsis_needed),
        "novel_fields": novel_fields,
        "chapter_titles": chapter_titles,
        "chapter_title_batch_size": batch_size,
        "unique_chapter_titles": len(unique_chapter_titles),
        "section_titles": section_titles,
        "section_title_batch_size": batch_size,
        "unique_section_titles": len(unique_section_titles),
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

    cache_text = (
        normalized if field_key is None else f"metadata:{field_key}:{settings.TRANSLATION_TARGET_LANGUAGE}:{normalized}"
    )
    candidates = model_candidates(provider_key, provider_model, supported_models)
    if not candidates:
        raise RuntimeError(f"No translation model configured for provider {provider_key}.")
    candidate_model = candidates[0]
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

    result = await provider.translate(
        prompt=prompt,
        model=candidate_model,
        max_tokens=max_tokens,
        request_purpose=(
            "chapter_title_translation"
            if field_key == "chapter_title"
            else "glossary_translation"
            if field_key == "glossary_term"
            else "metadata_translation"
        ),
        **provider_kwargs,
    )
    translated = str(result.get("text", "")).strip() or normalized
    if field_key:
        translated = _clean_metadata_translation(translated, normalized, field_key)
        if not _metadata_translation_is_usable(normalized, translated, field_key):
            raise RuntimeError(
                f"Incomplete metadata translation for {field_key} with {provider_key}/{candidate_model}."
            )
    self._record_usage(provider.key, candidate_model, result.get("metadata"))
    self._cache.set(cache_text, provider.key, candidate_model, translated)
    return translated


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

    synopsis_source_key = next(
        (
            key
            for key in ("narrative_synopsis", "synopsis", "description", "summary")
            if isinstance(translated_metadata.get(key), str) and str(translated_metadata.get(key)).strip()
        ),
        None,
    )
    synopsis = translated_metadata.get(synopsis_source_key) if synopsis_source_key is not None else None
    if isinstance(synopsis, str) and synopsis:
        previous_synopsis = previous.get("narrative_synopsis")
        if not isinstance(previous_synopsis, str) or not previous_synopsis.strip():
            previous_synopsis = previous.get("synopsis") or previous.get("description") or previous.get("summary")
        previous_translation = previous.get("translated_narrative_synopsis") or previous.get("translated_synopsis")
        if can_reuse_previous and _can_reuse_metadata_translation(
            synopsis,
            previous_synopsis,
            previous_translation,
            "synopsis",
        ):
            translated_metadata["translated_narrative_synopsis"] = previous_translation
            translated_metadata["translated_synopsis"] = previous_translation
        elif cached := _cached_metadata_translation(self, synopsis, "synopsis"):
            translated_metadata["translated_narrative_synopsis"] = cached
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
            translated_metadata["translated_narrative_synopsis"] = novel_translations["synopsis"]
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
    section_title_to_item_id: dict[str, str] = {}
    section_item_sources: dict[str, str] = {}
    section_item_refs: dict[str, list[dict[str, Any]]] = {}
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

        section_title = translated_chapter.get("section_title")
        if isinstance(section_title, str) and section_title.strip():
            if can_reuse_previous and _can_reuse_metadata_translation(
                section_title,
                previous_chapter.get("section_title"),
                previous_chapter.get("translated_section_title"),
                "section_title",
            ):
                translated_chapter["translated_section_title"] = previous_chapter["translated_section_title"]
            elif cached := _cached_metadata_translation(self, section_title, "section_title"):
                translated_chapter["translated_section_title"] = cached
            else:
                normalized_section_title = section_title.strip()
                item_id = section_title_to_item_id.get(normalized_section_title)
                if item_id is None:
                    item_id = f"section:{len(section_title_to_item_id) + 1}"
                    section_title_to_item_id[normalized_section_title] = item_id
                    section_item_sources[item_id] = normalized_section_title
                section_item_refs.setdefault(item_id, []).append(translated_chapter)

        translated_chapters.append(translated_chapter)

    batch_size = _metadata_batch_size(settings.TRANSLATION_METADATA_CHAPTER_TITLE_BATCH_SIZE)
    chapter_items = [
        {"id": item_id, "field": "chapter_title", "source_text": source_text}
        for item_id, source_text in title_item_sources.items()
    ]
    section_items = [
        {"id": item_id, "field": "section_title", "source_text": source_text}
        for item_id, source_text in section_item_sources.items()
    ]
    metadata_items = chapter_items + section_items
    for start in range(0, len(metadata_items), batch_size):
        batch = metadata_items[start : start + batch_size]
        translations = await _translate_metadata_items(self, batch)
        for item in batch:
            translated_value = translations.get(item["id"])
            if translated_value is None:
                translated_value = await self._translate_text(item["source_text"], field=item["field"])
            for translated_chapter in chapter_item_refs.get(item["id"], []):
                translated_chapter["translated_title"] = translated_value
            for translated_chapter in section_item_refs.get(item["id"], []):
                translated_chapter["translated_section_title"] = translated_value

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
    chunk_texts: list[str] = []
    source_text_by_chapter: dict[str, str] = {}
    new_lineage_by_chapter: dict[str, list[dict[str, Any]]] = {}
    for number in included_numbers:
        chapter_id = str(number)
        raw_chapter = self.storage.load_chapter(novel_id, chapter_id)
        raw_text = raw_chapter.get("text") if isinstance(raw_chapter, dict) else None
        if not isinstance(raw_text, str):
            missing_text.append(chapter_id)
            continue
        source_text_by_chapter[chapter_id] = raw_text

        paragraphs, chunks_for_chapter, warnings = segment.estimate_chapter_chunks(
            novel_id=novel_id,
            chapter_id=chapter_id,
            text=raw_text,
        )
        from novelai.services.orchestration.translation_lineage import _lineage_from_paragraphs

        new_lineage_by_chapter[chapter_id] = _lineage_from_paragraphs(paragraphs)
        chunk_texts.extend(chunk.source_text for chunk in chunks_for_chapter)
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

    # Zero-provider-call request plan. Token estimates are deliberately local
    # and conservative; actual Gemini usage is reconciled by the provider.
    source_chars = sum(int(item.get("source_chars") or 0) for item in per_chapter)
    body_input_tokens = max(0, math.ceil(source_chars / 3))
    body_output_tokens = estimated_chunks * settings.GEMINI_ESTIMATED_OUTPUT_TOKENS
    metadata_synopsis_key = next(
        (
            key
            for key in ("narrative_synopsis", "synopsis", "description", "summary")
            if isinstance(metadata.get(key), str) and str(metadata.get(key)).strip()
        ),
        None,
    )
    metadata_source_chars = sum(
        len(str(metadata.get(key) or "")) for key in ("title", "author", metadata_synopsis_key) if key is not None
    )
    metadata_input_tokens = max(0, math.ceil(metadata_source_chars / 3))
    metadata_output_tokens = metadata_requests["total"] * 256
    discovery_state_raw = metadata.get("incremental_glossary_discovery")
    discovery_state = discovery_state_raw if isinstance(discovery_state_raw, dict) else {}
    discovery_model = GEMINI_DEFAULT_MODEL
    changed_discovery_chapters: list[str] = []
    unchanged_discovery_chapters: list[str] = []
    for chapter_id, text in source_text_by_chapter.items():
        state = discovery_state.get(chapter_id)
        source_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()
        if (
            isinstance(state, dict)
            and state.get("source_hash") == source_hash
            and state.get("prompt_version") == INCREMENTAL_GLOSSARY_DISCOVERY_PROMPT_VERSION
            and state.get("provider_model") == discovery_model
        ):
            unchanged_discovery_chapters.append(chapter_id)
        else:
            changed_discovery_chapters.append(chapter_id)

    glossary_discovery_batch_size = 3
    glossary_discovery_calls = (
        math.ceil(len(changed_discovery_chapters) / glossary_discovery_batch_size) if changed_discovery_chapters else 0
    )
    discovery_source_chars = sum(
        min(len(source_text_by_chapter[chapter_id]), 4000) for chapter_id in changed_discovery_chapters
    )
    glossary_input_tokens = math.ceil(discovery_source_chars / 3) if discovery_source_chars else 0
    glossary_output_tokens = glossary_discovery_calls * 2048

    try:
        glossary_entries = [dict(entry) for entry in self.storage.load_glossary(novel_id) if isinstance(entry, dict)]
    except Exception:
        glossary_entries = []
    pending_glossary_entries = [
        entry
        for entry in glossary_entries
        if str(entry.get("status") or "pending").strip().lower() == "pending" and str(entry.get("source") or "").strip()
    ]
    glossary_translation_batch_size = max(1, int(settings.TRANSLATION_GLOSSARY_BATCH_SIZE or 1))
    glossary_cached_terms = 0
    glossary_uncached_terms = 0
    if settings.TRANSLATION_CACHE_ENABLED:
        for entry in pending_glossary_entries:
            source = str(entry.get("source") or "").strip()
            cache_text = f"metadata:glossary_term:{settings.TRANSLATION_TARGET_LANGUAGE}:{source}"
            if self._cache.get(cache_text, "gemini", GEMINI_DEFAULT_MODEL) is not None:
                glossary_cached_terms += 1
            else:
                glossary_uncached_terms += 1
    else:
        glossary_uncached_terms = len(pending_glossary_entries)
    known_glossary_translation_batches = (
        math.ceil(glossary_uncached_terms / glossary_translation_batch_size) if glossary_uncached_terms else 0
    )
    # Discovery output is not known until Gemini returns it. Keep a bounded
    # upper estimate for quota planning without presenting it as an exact term
    # count. The discovery prompt caps each batch at ``max_terms=50``.
    unknown_discovered_terms_upper_bound = glossary_discovery_calls * 50
    estimated_glossary_translation_terms = glossary_uncached_terms + unknown_discovered_terms_upper_bound
    estimated_glossary_translation_batches = (
        math.ceil(estimated_glossary_translation_terms / glossary_translation_batch_size)
        if estimated_glossary_translation_terms
        else 0
    )
    glossary_translation_source_chars = sum(
        len(str(entry.get("source") or "")) + len(str(entry.get("context_summary") or entry.get("notes") or ""))
        for entry in pending_glossary_entries
    )
    glossary_translation_input_tokens = (
        math.ceil(glossary_translation_source_chars / 3) if glossary_translation_source_chars else 0
    )
    glossary_translation_output_tokens = estimated_glossary_translation_batches * glossary_translation_batch_size * 96

    # Accepted body-cache entries are looked up using the same key dimensions
    # as the runtime cache. If discovery has changed, the glossary hash may
    # change before body translation, so do not count those hits optimistically.
    body_cache_hits = 0
    body_cache_hit_chars = 0
    body_cache_lookup_possible = bool(settings.TRANSLATION_CACHE_ENABLED and not changed_discovery_chapters)
    if body_cache_lookup_possible and chunk_texts:
        source_language = str(metadata.get("source_language") or "").strip()
        if not source_language:
            source_language = (
                "Japanese" if source_key in {"syosetu_ncode", "novel18_syosetu", "kakuyomu", "narou"} else "auto"
            )
        prompt_version = str(
            metadata.get("prompt_version") or metadata.get("prompt_template_version") or PROMPT_TEMPLATE_VERSION
        )
        glossary_hash = canonical_glossary_hash(glossary_entries)
        cache_service = TranslationCacheService()
        for chunk_text in chunk_texts:
            cache_key = make_cache_key(
                chunk_text,
                source_language,
                settings.TRANSLATION_TARGET_LANGUAGE,
                glossary_hash,
                provider_key="gemini",
                provider_model=GEMINI_DEFAULT_MODEL,
                prompt_version=prompt_version,
            )
            if cache_service.get(cache_key) is not None:
                body_cache_hits += 1
                body_cache_hit_chars += len(chunk_text)
    body_provider_requests = max(0, estimated_chunks - body_cache_hits)
    body_input_tokens = max(0, math.ceil(max(0, source_chars - body_cache_hit_chars) / 3))
    body_output_tokens = body_provider_requests * settings.GEMINI_ESTIMATED_OUTPUT_TOKENS
    body_requests.update(
        {
            "cache_hits": body_cache_hits,
            "cache_hit_chars": body_cache_hit_chars,
            "provider_requests": body_provider_requests,
            "cache_lookup_possible": body_cache_lookup_possible,
        }
    )

    llm_qa_calls = 0
    if body_provider_requests and settings.LLM_QA_ENABLED and settings.LLM_QA_SAMPLE_RATE > 0:
        llm_qa_calls = max(1, math.ceil(body_provider_requests * settings.LLM_QA_SAMPLE_RATE))
    llm_qa_input_tokens = llm_qa_calls * math.ceil(settings.LLM_QA_MAX_CONTEXT_CHARS / 3)
    llm_qa_output_tokens = llm_qa_calls * 128
    base_request_breakdown = {
        "metadata": int(metadata_requests["novel_fields"]),
        "chapter_title": int(metadata_requests["chapter_titles"]),
        "body": int(body_provider_requests),
        "glossary_discovery": glossary_discovery_calls,
        "glossary_translation": known_glossary_translation_batches,
        "llm_qa": llm_qa_calls,
        "validation": 0,
    }
    base_requests = sum(base_request_breakdown.values())
    estimated_unknown_requests = max(0, estimated_glossary_translation_batches - known_glossary_translation_batches)
    estimated_provider_requests = base_requests + estimated_unknown_requests
    configured_max_attempts = max(1, int(settings.TRANSLATION_MAX_ATTEMPTS_PER_CHUNK or 1))
    retryable_requests = estimated_provider_requests
    retry_ceiling = max(0, configured_max_attempts - 1) * retryable_requests
    estimated_total_tokens = (
        body_input_tokens
        + metadata_input_tokens
        + glossary_input_tokens
        + glossary_translation_input_tokens
        + llm_qa_input_tokens
        + body_output_tokens
        + metadata_output_tokens
        + glossary_output_tokens
        + glossary_translation_output_tokens
        + llm_qa_output_tokens
    )
    estimated_max_request_tokens = max(
        [
            math.ceil(max((len(chunk) for chunk in chunk_texts), default=0) / 3)
            + settings.GEMINI_ESTIMATED_OUTPUT_TOKENS,
            4096 if metadata_requests["total"] else 0,
            math.ceil(max((min(len(text), 4000) for text in source_text_by_chapter.values()), default=0) / 3) + 2048,
            min(4096, max(256, glossary_translation_batch_size * 96)) if estimated_glossary_translation_batches else 0,
            math.ceil(settings.LLM_QA_MAX_CONTEXT_CHARS / 3) + 128 if llm_qa_calls else 0,
        ]
    )
    minimum_wall_clock_seconds_from_rpm = (
        max(0, base_requests - 1) * 60 / settings.GEMINI_RPM_LIMIT if base_requests else 0.0
    )
    estimated_wall_clock_seconds_from_rpm = (
        max(0, estimated_provider_requests - 1) * 60 / settings.GEMINI_RPM_LIMIT if estimated_provider_requests else 0.0
    )
    one_day_completion_theoretically_possible = (
        estimated_provider_requests <= settings.GEMINI_RPD_LIMIT
        and estimated_max_request_tokens <= settings.GEMINI_TPM_LIMIT
    )
    one_day_completion_with_retry_reserve = (
        base_requests + retry_ceiling <= settings.GEMINI_RPD_LIMIT
        and estimated_max_request_tokens <= settings.GEMINI_TPM_LIMIT
    )
    quota_projection = {
        "request_breakdown": base_request_breakdown,
        "base_requests": base_requests,
        "minimum_provider_requests": base_requests,
        "estimated_provider_requests": estimated_provider_requests,
        "estimated_unknown_requests": estimated_unknown_requests,
        "configured_max_attempts": configured_max_attempts,
        "retryable_requests": retryable_requests,
        "retry_ceiling": retry_ceiling,
        "worst_case_requests": estimated_provider_requests + retry_ceiling,
        "estimated_input_tokens": body_input_tokens
        + metadata_input_tokens
        + glossary_input_tokens
        + glossary_translation_input_tokens
        + llm_qa_input_tokens,
        "estimated_output_tokens": body_output_tokens
        + metadata_output_tokens
        + glossary_output_tokens
        + glossary_translation_output_tokens
        + llm_qa_output_tokens,
        "estimated_total_tokens": estimated_total_tokens,
        "estimated_max_request_tokens": estimated_max_request_tokens,
        "estimated_minimum_rpd_usage": base_requests,
        "estimated_provider_rpd_usage": estimated_provider_requests,
        "one_day_completion_theoretically_possible": one_day_completion_theoretically_possible,
        "one_day_completion_with_retry_reserve": one_day_completion_with_retry_reserve,
        "minimum_wall_clock_seconds_from_rpm": minimum_wall_clock_seconds_from_rpm,
        "estimated_wall_clock_seconds_from_rpm": estimated_wall_clock_seconds_from_rpm,
        "limits": {
            "requests_per_minute": settings.GEMINI_RPM_LIMIT,
            "tokens_per_minute": settings.GEMINI_TPM_LIMIT,
            "requests_per_day": settings.GEMINI_RPD_LIMIT,
        },
        "delta_alternative_body_requests": int(delta.get("delta_body_requests", estimated_chunks)),
        "provider_calls": False,
    }

    return {
        "novel_id": novel_id,
        "source_key": source_key,
        "chapters_selected": len(selected_numbers),
        "chapters_included": len(included_numbers),
        "include_already_translated": bool(include_already_translated),
        "metadata_requests": metadata_requests,
        "body_requests": body_requests,
        "delta": delta,
        "total_estimated_requests": metadata_requests["total"] + body_provider_requests,
        "total_estimated_provider_requests": base_requests,
        "quota_projection": quota_projection,
        "request_estimate_quality": {
            "known": {
                "chapters": len(included_numbers),
                "characters": source_chars,
                "body_chunks": estimated_chunks,
                "body_cache_hits": body_cache_hits,
                "metadata_batches": int(metadata_requests["total"]),
                "chapter_title_batches": int(metadata_requests["chapter_titles"]),
                "glossary_discovery_batches": glossary_discovery_calls,
                "glossary_translation_batches": known_glossary_translation_batches,
                "minimum_provider_requests": base_requests,
            },
            "estimated": {
                "glossary_terms_from_undiscovered_output_upper_bound": unknown_discovered_terms_upper_bound,
                "glossary_translation_batches": estimated_glossary_translation_batches,
                "provider_requests": estimated_provider_requests,
                "input_tokens": quota_projection["estimated_input_tokens"],
                "output_tokens": quota_projection["estimated_output_tokens"],
            },
            "unknown": [
                "new glossary terms returned by incremental discovery",
                "actual provider token usage",
                "runtime retry and defer timing",
            ],
        },
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
            "glossary_discovery_batch_size": glossary_discovery_batch_size,
            "glossary_translation_batch_size": glossary_translation_batch_size,
            "glossary_discovery_prompt_version": INCREMENTAL_GLOSSARY_DISCOVERY_PROMPT_VERSION,
            "glossary_discovery_changed_chapters": sorted(changed_discovery_chapters),
            "glossary_discovery_unchanged_chapters": sorted(unchanged_discovery_chapters),
            "glossary_discovery_requests_are_known": True,
            "glossary_translation_requests_include_unknown_discovery_upper_bound": True,
            "body_cache_identity_checked": body_cache_lookup_possible,
            "body_cache_hits_are_excluded_from_provider_requests": True,
            "paragraph_hash_lineage": True,
            "delta_window_padding_paragraphs": settings.TRANSLATION_DELTA_WINDOW_PADDING_PARAGRAPHS,
            "delta_retranslation_enabled": settings.TRANSLATION_DELTA_RETRANSLATION_ENABLED,
            "delta_require_structured_paragraph_map": settings.TRANSLATION_DELTA_REQUIRE_STRUCTURED_PARAGRAPH_MAP,
            "delta_force_full_on_unsafe": settings.TRANSLATION_DELTA_FORCE_FULL_ON_UNSAFE,
            "provider_calls": False,
            "already_translated_chapters": "included" if include_already_translated else "excluded",
        },
    }
