"""Deterministic synopsis extraction and classification helpers.

Source adapters provide the strongest structural hints available to them.  This
module only handles the shared representation and conservative boundary
classification; it never rewrites narrative prose.
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Mapping, Sequence
from typing import Any

from novelai.utils.text_normalization import normalize_text

_URL_ONLY_RE = re.compile(r"^(?:https?://|www\.)\S+$", re.IGNORECASE)
_URL_RE = re.compile(r"(?:https?://|www\.)\S+", re.IGNORECASE)
_NOTICE_PREFIX_RE = re.compile(
    r"^(?:※|注(?:意)?[：:]?|お知らせ|告知|更新(?:のお知らせ)?|作者(?:より|から)|"
    r"読んでくださっている皆様|いつも応援ありがとうございます|ありがとうございます|"
    r"ネタバレ防止|別で掲載|誤字脱字|修正は中断)",
)
_NOTICE_CONTENT_RE = re.compile(r"(?:ネタバレ防止|別で掲載|誤字脱字|修正は中断|お陰です)")
_PROMOTION_RE = re.compile(
    r"(?:書籍化|出版|コミカライズ|漫画化|アニメ化|電子書籍|単行本|発売中|"
    r"連載開始|掲載開始|マンガ|コミック|pixiv|マンガUP|KADOKAWA|スクウェア・エニックス)",
    re.IGNORECASE,
)
_PROMOTION_PREFIX_RE = re.compile(
    r"^(?:書籍化|出版|コミカライズ|漫画化|アニメ化|電子書籍|単行本|発売中|"
    r"連載開始|掲載開始|コミック|マンガ)",
    re.IGNORECASE,
)
_DATE_RE = re.compile(r"(?:19|20)\d{2}(?:[年/.-]\d{1,2}[月/.-]\d{1,2}|年)")
_STRUCTURAL_HINTS = {
    "narrative",
    "promotion",
    "notice",
    "author_notice",
    "publication_notice",
    "update_notice",
    "external_link",
    "link",
}


def _split_text_blocks(text: str, *, separator: str) -> list[str]:
    normalized = normalize_text(text)
    if not normalized:
        return []
    if separator == "\n":
        candidates = normalized.splitlines()
    else:
        candidates = re.split(r"\n\s*\n+", normalized)
    return [block for block in (normalize_text(candidate) for candidate in candidates) if block]


def _is_story_like(text: str) -> bool:
    """Return true when a short promo-looking block still reads like prose."""
    if len(text) > 120:
        return True
    return bool(
        re.search(
            r"(?:主人公|物語|ある日|彼女|彼|彼ら|女性|男性|少女|少年|\b(?:was|is|are|the)\b)",
            text,
            re.IGNORECASE,
        )
    )


def _heuristic_classification(text: str) -> str:
    if _URL_ONLY_RE.fullmatch(text.strip()):
        return "external_link"
    if _NOTICE_PREFIX_RE.search(text):
        return "notice"
    if _NOTICE_CONTENT_RE.search(text) and len(text) <= 240:
        return "notice"

    promotion = _PROMOTION_RE.search(text)
    if promotion and not _is_story_like(text):
        if (
            _PROMOTION_PREFIX_RE.search(text)
            or "様より" in text
            or _DATE_RE.search(text)
            or "発売中" in text
            or "電子書籍" in text
            or "pixiv" in text.lower()
            or "！！！！" in text
            or "!!!!" in text
        ):
            return "promotion"
    if _URL_RE.search(text) and len(_URL_RE.findall(text)) >= 1 and len(text) <= 240:
        return "external_link"
    return "narrative"


def _normalize_input_blocks(
    raw_text: str,
    *,
    blocks: Sequence[Mapping[str, Any]] | None,
    separator: str,
) -> list[dict[str, Any]]:
    if blocks is None:
        texts = _split_text_blocks(raw_text, separator=separator)
        return [
            {
                "id": f"b{index:04d}",
                "text": text,
                "hint": None,
            }
            for index, text in enumerate(texts, start=1)
        ]

    normalized: list[dict[str, Any]] = []
    for index, item in enumerate(blocks, start=1):
        text = item.get("text")
        if not isinstance(text, str) or not text.strip():
            continue
        hint_value = item.get("classification") or item.get("kind") or item.get("type")
        hint = hint_value.strip().lower() if isinstance(hint_value, str) and hint_value.strip() else None
        normalized.append(
            {
                "id": str(item.get("id") or item.get("source_block_id") or f"b{index:04d}"),
                "text": normalize_text(text),
                "hint": hint if hint in _STRUCTURAL_HINTS else None,
            }
        )
    return [item for item in normalized if item["text"]]


def normalize_synopsis_metadata(
    raw_text: object,
    *,
    source_key: str,
    blocks: Sequence[Mapping[str, Any]] | None = None,
    separator: str = "\n\n",
) -> dict[str, Any]:
    """Return raw and narrative synopsis metadata.

    The legacy ``synopsis`` field is retained as a compatibility alias for the
    narrative result.  ``source_synopsis`` and ``source_synopsis_blocks`` keep
    the faithful source overview and its classification provenance.
    """
    raw = normalize_text(raw_text) if isinstance(raw_text, str) else ""
    input_blocks = _normalize_input_blocks(raw, blocks=blocks, separator=separator)
    if not input_blocks:
        return {}

    if not raw:
        raw = separator.join(str(item["text"]) for item in input_blocks)

    classified: list[dict[str, Any]] = []
    for item in input_blocks:
        hint = item.get("hint")
        classification = hint or _heuristic_classification(str(item["text"]))
        classified.append(
            {
                "id": str(item["id"]),
                "text": str(item["text"]),
                "classification": classification,
            }
        )

    narrative_indices = [index for index, item in enumerate(classified) if item["classification"] == "narrative"]
    if narrative_indices:
        first_narrative = min(narrative_indices)
        last_narrative = max(narrative_indices)
        selected_indices = set(range(first_narrative, last_narrative + 1))
        # Explicit source structure is authoritative even when a source marks a
        # non-narrative block inside the selected range.
        selected_indices.update(index for index, item in enumerate(classified) if item["classification"] == "narrative")
    else:
        # If there is no unambiguous narrative span, preserve the source rather
        # than risk deleting a real story paragraph.
        selected_indices = set(range(len(classified)))

    records: list[dict[str, Any]] = []
    narrative_blocks: list[str] = []
    narrative_ids: list[str] = []
    for index, item in enumerate(classified):
        included = index in selected_indices
        record = {
            "id": item["id"],
            "text": item["text"],
            "classification": item["classification"],
            "included_in_narrative": included,
        }
        records.append(record)
        if included:
            narrative_blocks.append(item["text"])
            narrative_ids.append(item["id"])

    narrative = separator.join(narrative_blocks).strip() or raw
    return {
        "source_synopsis": raw,
        "raw_synopsis": raw,
        "source_synopsis_blocks": records,
        "narrative_synopsis": narrative,
        "narrative_synopsis_block_ids": narrative_ids,
        "narrative_synopsis_hash": hashlib.sha256(narrative.encode("utf-8")).hexdigest(),
        "synopsis": narrative,
        "synopsis_source_key": source_key,
    }
