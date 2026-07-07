"""Standalone helpers for preliminary novel crawl orchestration.

Extracted from ``operations.py`` to thin the module.  All functions
are stateless — no service references.
"""

from __future__ import annotations

import re
from typing import Any

from novelai.sources.registry import detect_source

NCODE_ID_PATTERN = r"^n\d{4}[a-z]{2}$"
SYOSETU_SOURCE_PAIR = ("novel18_syosetu", "syosetu_ncode")


def looks_like_ncode_id(identifier: str) -> bool:
    return re.fullmatch(NCODE_ID_PATTERN, identifier.strip(), flags=re.IGNORECASE) is not None


def resolved_preliminary_source(identifier: str, requested_source_key: str | None) -> str:
    detected_source = detect_source(identifier)
    if detected_source:
        return detected_source
    if requested_source_key:
        return requested_source_key
    if looks_like_ncode_id(identifier):
        return "syosetu_ncode"
    if identifier.strip().isdigit() and len(identifier.strip()) >= 12:
        return "kakuyomu"
    return "generic"


def preliminary_source_attempts(identifier: str, requested_source_key: str | None) -> list[str]:
    detected_source = detect_source(identifier)
    requested = requested_source_key.strip() if isinstance(requested_source_key, str) else None
    if requested == "":
        requested = None

    if detected_source in SYOSETU_SOURCE_PAIR:
        fallback = "syosetu_ncode" if detected_source == "novel18_syosetu" else "novel18_syosetu"
        return [detected_source, fallback]

    if looks_like_ncode_id(identifier) and requested in {None, "syosetu_ncode", "novel18_syosetu"}:
        return list(SYOSETU_SOURCE_PAIR)

    if requested in SYOSETU_SOURCE_PAIR:
        fallback = "syosetu_ncode" if requested == "novel18_syosetu" else "novel18_syosetu"
        return [requested, fallback]

    if detected_source:
        return [detected_source]

    if looks_like_ncode_id(identifier):
        if requested is None:
            return list(SYOSETU_SOURCE_PAIR)
        return [requested]

    return [resolved_preliminary_source(identifier, requested_source_key)]


def preliminary_failure_code(errors: list[str]) -> str:
    if not errors:
        return "PRELIMINARY_CRAWL_FAILED"
    normalized = [error.lower() for error in errors]
    timeout_count = sum("timed out" in error for error in normalized)
    no_metadata_count = sum("no metadata or chapters detected" in error for error in normalized)
    if timeout_count == len(normalized):
        return "PRELIMINARY_CRAWL_TIMEOUT"
    if timeout_count > 0:
        return "PRELIMINARY_CRAWL_PARTIAL_TIMEOUT"
    if no_metadata_count == len(normalized):
        return "PRELIMINARY_CRAWL_NO_METADATA"
    return "PRELIMINARY_CRAWL_FAILED"


def preliminary_failure_explanation(code: str) -> str:
    explanations = {
        "PRELIMINARY_CRAWL_TIMEOUT": (
            "Every attempted source timed out before metadata could be detected. Try again later, "
            "check the source website, or increase the backend request timeout."
        ),
        "PRELIMINARY_CRAWL_PARTIAL_TIMEOUT": (
            "At least one source timed out, and the fallback source did not return usable metadata. "
            "Open Activity Log details to see which source timed out and which fallback returned nothing."
        ),
        "PRELIMINARY_CRAWL_NO_METADATA": (
            "The crawler reached the attempted source pages, but none returned usable metadata or chapters. "
            "Check whether the ID belongs to a different source or requires an exact URL."
        ),
    }
    return explanations.get(
        code,
        "The crawler tried every configured source fallback for this input, but none returned usable novel metadata or chapters.",
    )


def chapter_count(metadata: dict[str, Any]) -> int:
    chapters = metadata.get("chapters")
    return len(chapters) if isinstance(chapters, list) else 0


def preliminary_metadata_is_usable(metadata: dict[str, Any]) -> bool:
    if chapter_count(metadata) > 0:
        return True
    for key in ("title", "author", "synopsis", "description", "summary"):
        value = metadata.get(key)
        if isinstance(value, str) and value.strip():
            return True
    return False


def chapter_rows(metadata: dict[str, Any]) -> list[dict[str, Any]]:
    chapters = metadata.get("chapters")
    if not isinstance(chapters, list):
        return []
    rows: list[dict[str, Any]] = []
    fallback_date = metadata.get("updated_at") or metadata.get("published_at")
    for chapter in chapters:
        if not isinstance(chapter, dict):
            continue
        row = dict(chapter)
        date_added = chapter.get("date_added") or chapter.get("updated_at") or chapter.get("published_at") or fallback_date
        if date_added:
            row.setdefault("date_added", date_added)
        rows.append(row)
    return rows
