"""Glossary diagnostics — compact admin-only glossary observability for translations.

Normalizes raw translation context metadata into a safe bounded shape.
No full prompts, no source/chapter text, no provider payloads.
"""

from __future__ import annotations

from typing import Any

# ---------------------------------------------------------------------------
# Bounds
# ---------------------------------------------------------------------------

MAX_DIAGNOSTIC_ITEMS = 20
MAX_TERM_LENGTH = 40

# ---------------------------------------------------------------------------
# Normalizer
# ---------------------------------------------------------------------------


def normalize_glossary_diagnostics(metadata: dict[str, Any] | None) -> dict[str, Any]:
    """Normalize raw translation context metadata into compact diagnostics.

    Returns a dict with the following optional keys:
    - diagnostics_available (bool)
    - glossary_revision (int | None)
    - glossary_hash (str | None)
    - term_count_available (int)
    - term_count_injected (int)
    - prompt_block_truncated (bool)
    - conflict_count (int)
    - warning_count (int)
    - warnings (list[str], bounded)
    - conflicts (list[str], bounded)
    """
    if not metadata:
        return {"diagnostics_available": False}

    raw = _extract_glossary_metadata(metadata)
    if not _has_diagnostics(raw):
        return {"diagnostics_available": False}

    warnings = _bound_list(raw.get("warnings", []), MAX_DIAGNOSTIC_ITEMS)
    conflicts = _bound_list(raw.get("conflicts", []), MAX_DIAGNOSTIC_ITEMS)

    return {
        "diagnostics_available": True,
        "glossary_revision": raw.get("glossary_revision"),
        "glossary_hash": raw.get("glossary_hash"),
        "term_count_available": raw.get("term_count_available", 0),
        "term_count_injected": raw.get("term_count_injected", 0),
        "prompt_block_truncated": _safe_bool(raw.get("prompt_block_truncated")),
        "conflict_count": len(conflicts),
        "warning_count": len(warnings),
        "warnings": [_safe_term(w, MAX_TERM_LENGTH) for w in warnings],
        "conflicts": [_safe_term(c, MAX_TERM_LENGTH) for c in conflicts],
    }


def _extract_glossary_metadata(metadata: dict[str, Any]) -> dict[str, Any]:
    """Extract glossary-related fields from various possible locations."""
    # Direct path
    if "glossary_term_count" in metadata or "glossary_hash" in metadata:
        return {
            "glossary_revision": metadata.get("glossary_revision"),
            "glossary_hash": metadata.get("glossary_hash"),
            "term_count_available": metadata.get("glossary_term_count_available") or metadata.get("glossary_term_count", 0),
            "term_count_injected": metadata.get("glossary_term_count_injected", 0),
            "prompt_block_truncated": metadata.get("glossary_prompt_truncated") or metadata.get("prompt_block_truncated"),
            "warnings": metadata.get("glossary_warnings") or metadata.get("warnings", []),
            "conflicts": metadata.get("glossary_conflicts") or metadata.get("conflicts", []),
        }

    # Prompt-injection service metadata path
    injection = metadata.get("glossary_injection", {}) or metadata.get("glossary_prompt_injection", {})
    if isinstance(injection, dict):
        return {
            "glossary_revision": injection.get("glossary_revision") or metadata.get("glossary_revision"),
            "glossary_hash": injection.get("glossary_hash") or metadata.get("glossary_hash"),
            "term_count_available": injection.get("terms_available", 0),
            "term_count_injected": injection.get("terms_injected", 0),
            "prompt_block_truncated": injection.get("truncated", False),
            "warnings": injection.get("warnings", []),
            "conflicts": injection.get("conflicts", []),
        }

    return {}


def _has_diagnostics(raw: dict[str, Any]) -> bool:
    """Check if raw extracted data contains any diagnostics."""
    return bool(raw.get("glossary_revision") or raw.get("glossary_hash") or raw.get("term_count_available"))


def _safe_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.lower() in ("true", "1", "yes")
    return bool(value)


def _safe_term(value: Any, max_length: int) -> str:
    s = str(value) if value is not None else ""
    if len(s) > max_length:
        s = s[: max_length - 3] + "..."
    return s


def _bound_list(items: list[Any], limit: int) -> list[str]:
    return [str(i) for i in (items or [])][:limit]


def aggregate_glossary_diagnostics(
    chapter_diagnostics: list[dict[str, Any]],
) -> dict[str, Any]:
    """Aggregate per-chapter diagnostics into a compact activity summary.

    Returns a dict with:
    - chapters_with_diagnostics (int)
    - chapters_missing_diagnostics (int)
    - chapters_with_conflicts (int)
    - chapters_with_warnings (int)
    - chapters_with_truncated_blocks (int)
    - chapters_with_zero_injected_terms (int)
    - total_terms_available (int)
    - total_terms_injected (int)
    - total_warnings (int)
    - total_conflicts (int)
    """
    result = {
        "chapters_with_diagnostics": 0,
        "chapters_missing_diagnostics": 0,
        "chapters_with_conflicts": 0,
        "chapters_with_warnings": 0,
        "chapters_with_truncated_blocks": 0,
        "chapters_with_zero_injected_terms": 0,
        "total_terms_available": 0,
        "total_terms_injected": 0,
        "total_warnings": 0,
        "total_conflicts": 0,
    }

    for d in chapter_diagnostics:
        if not d.get("diagnostics_available"):
            result["chapters_missing_diagnostics"] += 1
            continue

        result["chapters_with_diagnostics"] += 1
        if d.get("conflict_count", 0) > 0:
            result["chapters_with_conflicts"] += 1
        if d.get("warning_count", 0) > 0:
            result["chapters_with_warnings"] += 1
        if d.get("prompt_block_truncated"):
            result["chapters_with_truncated_blocks"] += 1
        if d.get("term_count_injected", 0) == 0:
            result["chapters_with_zero_injected_terms"] += 1

        result["total_terms_available"] += d.get("term_count_available", 0)
        result["total_terms_injected"] += d.get("term_count_injected", 0)
        result["total_warnings"] += d.get("warning_count", 0)
        result["total_conflicts"] += d.get("conflict_count", 0)

    return result
