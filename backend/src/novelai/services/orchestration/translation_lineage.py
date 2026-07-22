"""Translation lineage + delta retranslation — extracted from translation.py.

Paragraph lineage tracking, lineage comparison (LCS-based), delta window
detection, delta retranslation execution, and glossary pending count.
Core orchestration and metadata translation are in other split files.
"""

from __future__ import annotations

import hashlib
import json
import logging
from itertools import pairwise
from typing import Any

from novelai.config.settings import settings
from novelai.db.engine import session_scope
from novelai.db.models.novel import Novel
from novelai.sources.base import SourceAdapter
from novelai.translation.pipeline.context import TranslationChunk
from novelai.translation.pipeline.stages.segment import SmartSegmentStage
from novelai.translation.qa import (
    evaluate_translation_quality,
    normalize_translation_output,
)

logger = logging.getLogger(__name__)


def _positive_padding(value: object) -> int:
    if isinstance(value, bool):
        return 1
    if isinstance(value, int) and value >= 0:
        return value
    return 1


def _lineage_key(item: dict[str, Any]) -> tuple[str, str]:
    return str(item.get("chapter_id") or ""), str(item.get("paragraph_id") or "")


def _normalize_lineage_item(
    item: dict[str, Any], *, fallback_index: int, text: str | None = None
) -> dict[str, Any] | None:
    source_hash = item.get("source_hash")
    if not isinstance(source_hash, str) or not source_hash.strip():
        source_hash = item.get("paragraph_hash")
    if not isinstance(source_hash, str) or not source_hash.strip():
        return None
    chapter_id = item.get("chapter_id")
    paragraph_id = item.get("paragraph_id")
    if not isinstance(chapter_id, str) or not chapter_id.strip():
        return None
    if not isinstance(paragraph_id, str) or not paragraph_id.strip():
        return None
    try:
        paragraph_index = int(item.get("paragraph_index") or fallback_index)
    except (TypeError, ValueError):
        paragraph_index = fallback_index
    normalized = {
        "chapter_id": chapter_id,
        "paragraph_id": paragraph_id,
        "paragraph_index": paragraph_index,
        "source_hash": source_hash,
        "char_count": int(item.get("char_count") or (len(text) if isinstance(text, str) else 0)),
    }
    if isinstance(text, str):
        normalized["text"] = text
    return normalized


def _lineage_from_paragraphs(paragraphs: list[Any]) -> list[dict[str, Any]]:
    lineage: list[dict[str, Any]] = []
    for index, paragraph in enumerate(paragraphs, start=1):
        item = _normalize_lineage_item(
            {
                "chapter_id": paragraph.chapter_id,
                "paragraph_id": paragraph.paragraph_id,
                "paragraph_index": paragraph.paragraph_index,
                "source_hash": paragraph.source_hash,
                "char_count": paragraph.char_count,
            },
            fallback_index=index,
            text=paragraph.text,
        )
        if item is not None:
            lineage.append(item)
    return lineage


def _old_lineage_by_chapter(storage: Any, novel_id: str) -> tuple[dict[str, list[dict[str, Any]]], list[str]]:
    notes: list[str] = []
    records = storage.read_translation_chunks(novel_id)
    if not isinstance(records, list) or not records:
        return {}, ["no previous paragraph hash lineage found"]

    by_key: dict[tuple[str, str], dict[str, Any]] = {}
    saw_record_without_hashes = False
    for record in records:
        if not isinstance(record, dict):
            continue
        raw_lineage = record.get("paragraph_lineage")
        if isinstance(raw_lineage, list) and raw_lineage:
            for fallback_index, item in enumerate(raw_lineage, start=1):
                if not isinstance(item, dict):
                    continue
                normalized = _normalize_lineage_item(item, fallback_index=fallback_index)
                if normalized is not None:
                    by_key.setdefault(_lineage_key(normalized), normalized)
            continue

        raw_hashes = record.get("paragraph_hashes")
        raw_ids = record.get("paragraph_ids")
        raw_chapters = record.get("chapter_ids")
        if not isinstance(raw_hashes, list) or not raw_hashes:
            saw_record_without_hashes = True
            continue
        if not isinstance(raw_ids, list) or not raw_ids:
            saw_record_without_hashes = True
            continue
        chapter_id = str(raw_chapters[0]) if isinstance(raw_chapters, list) and len(raw_chapters) == 1 else None
        if chapter_id is None:
            saw_record_without_hashes = True
            continue
        for fallback_index, (paragraph_id, source_hash) in enumerate(zip(raw_ids, raw_hashes, strict=False), start=1):
            normalized = _normalize_lineage_item(
                {
                    "chapter_id": chapter_id,
                    "paragraph_id": str(paragraph_id),
                    "paragraph_index": fallback_index,
                    "source_hash": str(source_hash),
                },
                fallback_index=fallback_index,
            )
            if normalized is not None:
                by_key.setdefault(_lineage_key(normalized), normalized)

    if saw_record_without_hashes:
        notes.append("some previous chunk records lacked paragraph hash lineage")
    by_chapter: dict[str, list[dict[str, Any]]] = {}
    for item in by_key.values():
        by_chapter.setdefault(str(item["chapter_id"]), []).append(item)
    for items in by_chapter.values():
        items.sort(key=lambda item: int(item.get("paragraph_index") or 0))
    return by_chapter, notes


def _hash_counts(items: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in items:
        source_hash = str(item.get("source_hash") or "")
        counts[source_hash] = counts.get(source_hash, 0) + 1
    return counts


def _lcs_pairs(old_hashes: list[str], new_hashes: list[str]) -> list[tuple[int, int]]:
    rows = len(old_hashes) + 1
    cols = len(new_hashes) + 1
    table = [[0 for _ in range(cols)] for _ in range(rows)]
    for old_index, old_hash in enumerate(old_hashes, start=1):
        for new_index, new_hash in enumerate(new_hashes, start=1):
            if old_hash == new_hash:
                table[old_index][new_index] = table[old_index - 1][new_index - 1] + 1
            else:
                table[old_index][new_index] = max(table[old_index - 1][new_index], table[old_index][new_index - 1])
    pairs: list[tuple[int, int]] = []
    old_index = len(old_hashes)
    new_index = len(new_hashes)
    while old_index > 0 and new_index > 0:
        if old_hashes[old_index - 1] == new_hashes[new_index - 1]:
            pairs.append((old_index - 1, new_index - 1))
            old_index -= 1
            new_index -= 1
        elif table[old_index - 1][new_index] >= table[old_index][new_index - 1]:
            old_index -= 1
        else:
            new_index -= 1
    pairs.reverse()
    return pairs


def _stable_anchor_pairs(old_items: list[dict[str, Any]], new_items: list[dict[str, Any]]) -> list[tuple[int, int]]:
    old_counts = _hash_counts(old_items)
    new_counts = _hash_counts(new_items)
    old_unique = [
        str(item.get("source_hash") or "")
        for item in old_items
        if old_counts.get(str(item.get("source_hash") or ""), 0) == 1
        and new_counts.get(str(item.get("source_hash") or ""), 0) == 1
    ]
    new_unique = [
        str(item.get("source_hash") or "")
        for item in new_items
        if old_counts.get(str(item.get("source_hash") or ""), 0) == 1
        and new_counts.get(str(item.get("source_hash") or ""), 0) == 1
    ]
    old_index_by_hash = {str(item.get("source_hash") or ""): index for index, item in enumerate(old_items)}
    new_index_by_hash = {str(item.get("source_hash") or ""): index for index, item in enumerate(new_items)}
    return [
        (old_index_by_hash[old_unique[old_pos]], new_index_by_hash[new_unique[new_pos]])
        for old_pos, new_pos in _lcs_pairs(old_unique, new_unique)
    ]


def _compare_lineage(old_items: list[dict[str, Any]], new_items: list[dict[str, Any]]) -> dict[str, Any]:
    old_counts = _hash_counts(old_items)
    new_counts = _hash_counts(new_items)
    anchors = _stable_anchor_pairs(old_items, new_items)
    unchanged_new_indexes = {new_index for _, new_index in anchors}
    moved_hashes = {
        source_hash for source_hash, count in old_counts.items() if count == 1 and new_counts.get(source_hash) == 1
    } - {str(new_items[new_index].get("source_hash") or "") for _, new_index in anchors}

    inserted: set[int] = set()
    changed: set[int] = set()
    ambiguous: set[int] = set()
    deleted_old: set[int] = set()
    boundaries = [(-1, -1), *anchors, (len(old_items), len(new_items))]
    for (old_start, new_start), (old_end, new_end) in pairwise(boundaries):
        old_gap = list(range(old_start + 1, old_end))
        new_gap = list(range(new_start + 1, new_end))
        if not old_gap and not new_gap:
            continue
        if not old_gap:
            for new_index in new_gap:
                new_hash = str(new_items[new_index].get("source_hash") or "")
                if new_hash in old_counts:
                    ambiguous.add(new_index)
                else:
                    inserted.add(new_index)
            continue
        if not new_gap:
            deleted_old.update(old_gap)
            continue
        if len(old_gap) == len(new_gap):
            for old_index, new_index in zip(old_gap, new_gap, strict=True):
                old_hash = str(old_items[old_index].get("source_hash") or "")
                new_hash = str(new_items[new_index].get("source_hash") or "")
                if old_hash == new_hash:
                    ambiguous.add(new_index)
                elif new_hash in moved_hashes or old_counts.get(new_hash, 0) > 1 or new_counts.get(new_hash, 0) > 1:
                    ambiguous.add(new_index)
                    deleted_old.add(old_index)
                else:
                    changed.add(new_index)
            continue
        for old_index in old_gap:
            deleted_old.add(old_index)
        for new_index in new_gap:
            new_hash = str(new_items[new_index].get("source_hash") or "")
            if new_hash in old_counts:
                ambiguous.add(new_index)
            else:
                inserted.add(new_index)

    return {
        "unchanged_new_indexes": unchanged_new_indexes,
        "changed_new_indexes": changed,
        "inserted_new_indexes": inserted,
        "deleted_old_indexes": deleted_old,
        "ambiguous_new_indexes": ambiguous,
    }


def _merge_windows(windows: list[dict[str, int]]) -> list[dict[str, int]]:
    ordered = sorted(windows, key=lambda item: (item["start"], item["end"]))
    merged: list[dict[str, int]] = []
    for window in ordered:
        if not merged or window["start"] > merged[-1]["end"] + 1:
            merged.append(dict(window))
            continue
        merged[-1]["end"] = max(merged[-1]["end"], window["end"])
    return merged


def _changed_windows_for_chapter(
    *,
    new_items: list[dict[str, Any]],
    comparison: dict[str, Any],
    padding: int,
) -> list[dict[str, int]]:
    paragraph_count = len(new_items)
    raw_indexes = (
        set(comparison["changed_new_indexes"])
        | set(comparison["inserted_new_indexes"])
        | set(comparison["ambiguous_new_indexes"])
    )
    windows = [
        {"start": max(0, index - padding), "end": min(paragraph_count - 1, index + padding)}
        for index in raw_indexes
        if paragraph_count > 0
    ]
    if comparison["deleted_old_indexes"] and paragraph_count > 0:
        if raw_indexes:
            for index in raw_indexes:
                windows.append({"start": max(0, index - padding), "end": min(paragraph_count - 1, index + padding)})
        else:
            windows.append({"start": 0, "end": min(paragraph_count - 1, padding)})
    return _merge_windows(windows)


def _estimate_delta_requests(
    self: Any,
    *,
    novel_id: str,
    new_lineage_by_chapter: dict[str, list[dict[str, Any]]],
    full_body_requests: int,
    segment: SmartSegmentStage,
) -> dict[str, Any]:
    padding = _positive_padding(settings.TRANSLATION_DELTA_WINDOW_PADDING_PARAGRAPHS)
    old_lineage_by_chapter, notes = _old_lineage_by_chapter(self.storage, novel_id)
    base = {
        "available": False,
        "safe_for_reuse": False,
        "mode": "estimate_only",
        "padding_paragraphs": padding,
        "full_body_requests": full_body_requests,
        "delta_body_requests": full_body_requests,
        "unchanged_paragraphs": 0,
        "changed_paragraphs": 0,
        "inserted_paragraphs": 0,
        "deleted_paragraphs": 0,
        "ambiguous_paragraphs": 0,
        "changed_windows": [],
        "notes": ["estimate only; actual delta retranslation not enabled"],
    }
    if notes:
        base["notes"].extend(notes)
    if not old_lineage_by_chapter:
        base["notes"].append("delta unavailable; falling back to full body estimate")
        return base

    missing = sorted(chapter_id for chapter_id in new_lineage_by_chapter if chapter_id not in old_lineage_by_chapter)
    if missing:
        base["notes"].append(f"partial previous lineage missing chapters: {', '.join(missing)}")
        base["notes"].append("delta unavailable; falling back to full body estimate")
        return base

    delta_chunks = 0
    changed_windows: list[dict[str, Any]] = []
    for chapter_id, new_items in new_lineage_by_chapter.items():
        old_items = old_lineage_by_chapter.get(chapter_id, [])
        comparison = _compare_lineage(old_items, new_items)
        base["unchanged_paragraphs"] += len(comparison["unchanged_new_indexes"])
        base["changed_paragraphs"] += len(comparison["changed_new_indexes"])
        base["inserted_paragraphs"] += len(comparison["inserted_new_indexes"])
        base["deleted_paragraphs"] += len(comparison["deleted_old_indexes"])
        base["ambiguous_paragraphs"] += len(comparison["ambiguous_new_indexes"])
        for window in _changed_windows_for_chapter(new_items=new_items, comparison=comparison, padding=padding):
            window_items = new_items[window["start"] : window["end"] + 1]
            window_text = "\n\n".join(str(item.get("text") or "") for item in window_items)
            _, window_chunks, _ = segment.estimate_chapter_chunks(
                novel_id=novel_id,
                chapter_id=chapter_id,
                text=window_text,
            )
            estimated_chunks = len(window_chunks)
            delta_chunks += estimated_chunks
            changed_windows.append(
                {
                    "chapter_id": chapter_id,
                    "start_paragraph_index": int(window_items[0].get("paragraph_index") or 0),
                    "end_paragraph_index": int(window_items[-1].get("paragraph_index") or 0),
                    "paragraph_hashes": [str(item.get("source_hash") or "") for item in window_items],
                    "estimated_chunks": estimated_chunks,
                }
            )

    base["available"] = True
    base["delta_body_requests"] = delta_chunks
    base["changed_windows"] = changed_windows
    base["notes"].append("chunk-boundary reuse remains unsafe until delta execution is implemented")
    return base


def _lineage_signature(lineage: list[dict[str, Any]]) -> str:
    payload = [
        {
            "chapter_id": item.get("chapter_id"),
            "paragraph_id": item.get("paragraph_id"),
            "paragraph_index": item.get("paragraph_index"),
            "source_hash": item.get("source_hash"),
        }
        for item in lineage
    ]
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _structured_paragraphs_from_outputs(
    storage: Any, novel_id: str, chapter_id: str
) -> dict[tuple[str, str], dict[str, str]]:
    outputs = storage.read_translation_output(novel_id)
    if not isinstance(outputs, list):
        return {}
    translated_by_ref: dict[tuple[str, str], dict[str, str]] = {}
    for output in outputs:
        if not isinstance(output, dict):
            continue
        lineage = output.get("paragraph_lineage")
        paragraph_hash_by_ref: dict[tuple[str, str], str] = {}
        if isinstance(lineage, list):
            for item in lineage:
                if not isinstance(item, dict):
                    continue
                normalized = _normalize_lineage_item(item, fallback_index=0)
                if normalized is not None and normalized["chapter_id"] == chapter_id:
                    paragraph_hash_by_ref[(normalized["chapter_id"], normalized["paragraph_id"])] = normalized[
                        "source_hash"
                    ]
        paragraph_map = output.get("structured_paragraph_map")
        if not isinstance(paragraph_map, list):
            continue
        for item in paragraph_map:
            if not isinstance(item, dict):
                continue
            paragraph_id = item.get("paragraph_id")
            translated = item.get("translated_text")
            if paragraph_id is None or not isinstance(translated, str):
                continue
            mapped_chapter_id = str(item.get("chapter_id") or chapter_id)
            if mapped_chapter_id != chapter_id:
                continue
            key = (mapped_chapter_id, str(paragraph_id))
            source_hash = paragraph_hash_by_ref.get(key)
            if source_hash is None:
                continue
            translated_by_ref[key] = {"translated_text": translated, "source_hash": source_hash}
    return translated_by_ref


def _structured_map_from_result(result: Any, window_items: list[dict[str, Any]]) -> list[str] | None:
    raw_outputs: list[str] = []
    metadata = getattr(result, "metadata", None)
    if isinstance(metadata, dict):
        raw_values = metadata.get("raw_provider_translations")
        if isinstance(raw_values, list):
            raw_outputs.extend(str(value) for value in raw_values if isinstance(value, str))
        raw_value = metadata.get("raw_provider_translation")
        if isinstance(raw_value, str):
            raw_outputs.append(raw_value)
    raw_translations = getattr(result, "translations", None)
    if isinstance(raw_translations, list):
        raw_outputs.extend(str(value) for value in raw_translations if isinstance(value, str))
    final_text = getattr(result, "final_text", None)
    if isinstance(final_text, str):
        raw_outputs.append(final_text)

    mapped: list[str] = []
    for raw in raw_outputs:
        parsed = normalize_translation_output(raw)
        if not parsed.paragraph_map:
            continue
        for item in parsed.paragraph_map:
            translated = item.get("translated_text")
            if isinstance(translated, str):
                mapped.append(translated)
    if len(mapped) < len(window_items):
        return None
    return mapped[: len(window_items)]


def _qa_reassembled_chapter(
    *, source_text: str, translated_text: str, chapter_id: str, lineage: list[dict[str, Any]]
) -> dict[str, Any]:
    chunk = TranslationChunk(
        chunk_id="delta_final",
        novel_id="delta",
        chapter_ids=[chapter_id],
        paragraph_ids=[str(item["paragraph_id"]) for item in lineage],
        source_text=source_text,
        char_count=len(source_text),
        paragraph_refs=[(chapter_id, str(item["paragraph_id"])) for item in lineage],
        paragraph_hashes=[str(item["source_hash"]) for item in lineage],
        paragraph_lineage=[dict(item) for item in lineage],
    )
    result = evaluate_translation_quality(source_text=source_text, translated_text=translated_text, chunk=chunk)
    return result.to_dict()


async def _try_delta_translate_chapter(
    self: Any,
    *,
    source: SourceAdapter | None,
    source_key: str,
    novel_id: str,
    chapter_id: str,
    chapter_url: str,
    raw_text: str,
    provider_key: str,
    provider_model: str,
    platform_novel_id: int | None,
    source_language: str | None,
    target_language: str | None,
    glossary: Any | None,
    style_preset: str | None,
    consistency_mode: bool,
    job_id: str | None,
    activity_id: str | None,
    allow_cross_provider_fallback: bool,
) -> dict[str, Any]:
    if not settings.TRANSLATION_DELTA_RETRANSLATION_ENABLED:
        return {"applied": False, "fallback_reason": "delta_disabled"}

    segment = SmartSegmentStage()
    paragraphs, _, _ = segment.estimate_chapter_chunks(novel_id=novel_id, chapter_id=chapter_id, text=raw_text)
    new_lineage = _lineage_from_paragraphs(paragraphs)
    old_by_chapter, notes = _old_lineage_by_chapter(self.storage, novel_id)
    old_lineage = old_by_chapter.get(chapter_id)
    if not old_lineage:
        return {"applied": False, "fallback_reason": "missing_lineage", "notes": notes}

    comparison = _compare_lineage(old_lineage, new_lineage)
    if comparison["ambiguous_new_indexes"]:
        return {"applied": False, "fallback_reason": "ambiguous_or_moved_region"}

    windows = _changed_windows_for_chapter(
        new_items=new_lineage,
        comparison=comparison,
        padding=_positive_padding(settings.TRANSLATION_DELTA_WINDOW_PADDING_PARAGRAPHS),
    )
    existing_translation = self.storage.load_translated_chapter(novel_id, chapter_id)
    if not windows:
        if existing_translation and isinstance(existing_translation.get("text"), str):
            return {
                "applied": True,
                "mode": "whole_chapter_unchanged",
                "text": existing_translation["text"],
                "provider": existing_translation.get("provider"),
                "model": existing_translation.get("model"),
                "provenance": {
                    "delta_retranslation": True,
                    "mode": "whole_chapter_unchanged",
                    "old_lineage_signature": _lineage_signature(old_lineage),
                    "new_lineage_signature": _lineage_signature(new_lineage),
                    "reused_paragraph_ids": [str(item["paragraph_id"]) for item in new_lineage],
                    "newly_translated_paragraph_ids": [],
                    "changed_windows": [],
                    "qa_result": {"passed": True, "warnings": [], "errors": []},
                },
            }
        return {"applied": False, "fallback_reason": "missing_previous_translation"}

    old_translations = _structured_paragraphs_from_outputs(self.storage, novel_id, chapter_id)
    if settings.TRANSLATION_DELTA_REQUIRE_STRUCTURED_PARAGRAPH_MAP and not old_translations:
        return {"applied": False, "fallback_reason": "missing_structured_paragraph_map"}

    changed_indexes: set[int] = set()
    for window in windows:
        changed_indexes.update(range(window["start"], window["end"] + 1))
    reused: dict[int, str] = {}
    for index, item in enumerate(new_lineage):
        if index in changed_indexes:
            continue
        key = (chapter_id, str(item["paragraph_id"]))
        old = old_translations.get(key)
        if old is None or old.get("source_hash") != item.get("source_hash"):
            return {"applied": False, "fallback_reason": "missing_structured_paragraph_map"}
        reused[index] = old["translated_text"]

    newly_translated: dict[int, str] = {}
    changed_windows_payload: list[dict[str, Any]] = []
    for window_number, window in enumerate(windows, start=1):
        window_items = new_lineage[window["start"] : window["end"] + 1]
        window_text = "\n\n".join(str(item.get("text") or "") for item in window_items)
        try:
            result = await self.translation.translate_chapter(
                source_adapter=source,
                chapter_url=f"{chapter_url}#delta-window-{window_number}",
                job_id=job_id,
                activity_id=activity_id,
                novel_id=novel_id,
                chapter_id=chapter_id,
                source_key=source_key,
                provider_key=provider_key,
                provider_model=provider_model,
                platform_novel_id=platform_novel_id,
                source_language=source_language,
                target_language=target_language,
                glossary=glossary,
                style_preset=style_preset,
                consistency_mode=consistency_mode,
                json_output=True,
                allow_cross_provider_fallback=allow_cross_provider_fallback,
                force_retranslate=True,
                raw_text=window_text,
            )
        except Exception:
            if settings.TRANSLATION_DELTA_FORCE_FULL_ON_UNSAFE:
                return {"applied": False, "fallback_reason": "changed_window_qa_failed"}
            raise
        mapped = _structured_map_from_result(result, window_items)
        if mapped is None:
            return {"applied": False, "fallback_reason": "changed_window_qa_failed"}
        for offset, translated in enumerate(mapped):
            newly_translated[window["start"] + offset] = translated
        changed_windows_payload.append(
            {
                "chapter_id": chapter_id,
                "start_paragraph_index": int(window_items[0]["paragraph_index"]),
                "end_paragraph_index": int(window_items[-1]["paragraph_index"]),
                "paragraph_hashes": [str(item["source_hash"]) for item in window_items],
            }
        )

    final_parts: list[str] = []
    reused_ids: list[str] = []
    translated_ids: list[str] = []
    for index, item in enumerate(new_lineage):
        if index in newly_translated:
            final_parts.append(newly_translated[index])
            translated_ids.append(str(item["paragraph_id"]))
        elif index in reused:
            final_parts.append(reused[index])
            reused_ids.append(str(item["paragraph_id"]))
        else:
            return {"applied": False, "fallback_reason": "incomplete_reassembly"}
    if len(final_parts) != len(new_lineage):
        return {"applied": False, "fallback_reason": "incomplete_reassembly"}

    final_text = "\n\n".join(final_parts)
    qa_result = _qa_reassembled_chapter(
        source_text=raw_text, translated_text=final_text, chapter_id=chapter_id, lineage=new_lineage
    )
    if not qa_result.get("passed"):
        return {"applied": False, "fallback_reason": "final_qa_failed", "qa_result": qa_result}

    return {
        "applied": True,
        "mode": "delta",
        "text": final_text,
        "provider_key": provider_key,
        "provider_model": provider_model,
        "provenance": {
            "delta_retranslation": True,
            "mode": "delta",
            "old_lineage_signature": _lineage_signature(old_lineage),
            "new_lineage_signature": _lineage_signature(new_lineage),
            "reused_paragraph_ids": reused_ids,
            "newly_translated_paragraph_ids": translated_ids,
            "changed_windows": changed_windows_payload,
            "qa_result": qa_result,
        },
    }


def _count_pending_glossary_entries(novel_id: str) -> int:
    """Return the count of glossary entries awaiting review for *novel_id*."""
    from sqlalchemy import func, select

    from novelai.db.models.glossary import NovelGlossaryEntry

    with session_scope() as session:
        novel = session.query(Novel).filter_by(slug=novel_id).one_or_none()
        if novel is None:
            return 0
        stmt = (
            select(func.count())
            .select_from(NovelGlossaryEntry)
            .where(
                NovelGlossaryEntry.novel_id == novel.id,
                NovelGlossaryEntry.status.in_(("candidate", "recommended")),
            )
        )
        return session.scalar(stmt) or 0
