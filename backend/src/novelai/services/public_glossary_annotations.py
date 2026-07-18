"""Public reader glossary annotations — optional public-safe term annotations.

Selects approved glossary entries safe for public display, matches their
translated forms against public chapter text, and returns compact annotation
metadata. No admin diagnostics, no pending/rejected terms, no prompts.
"""

from __future__ import annotations

import re
from typing import Any

# ---------------------------------------------------------------------------
# Bounds
# ---------------------------------------------------------------------------

MAX_ANNOTATIONS = 50
MAX_ALIASES = 5
MAX_MATCHES = 20

# ---------------------------------------------------------------------------
# Public-safe term selection
# ---------------------------------------------------------------------------

# Term types considered safe for public display
_PUBLIC_SAFE_TYPES = {"character", "location", "skill", "title", "item", "concept", "term"}

# Statuses that are allowed for public display
_PUBLIC_SAFE_STATUSES = {"approved", "published"}

# Fields that must never be exposed in public annotations
_ADMIN_ONLY_FIELDS = {
    "status", "review_state", "internal_notes", "confidence_score",
    "editor_notes", "locked_by", "owner_locked", "created_by",
    "updated_by", "revision", "enforcement_level",
}


def select_public_terms(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Filter glossary entries to those safe for public display.

    Each entry dict should have at minimum: id, canonical_term,
    approved_translation, term_type, status.
    """
    results: list[dict[str, Any]] = []
    for entry in entries:
        term_type = str(entry.get("term_type", "term")).lower()
        status = str(entry.get("status", "")).lower()
        if entry.get("public_visible") is not True:
            continue
        if term_type not in _PUBLIC_SAFE_TYPES:
            continue
        if status not in _PUBLIC_SAFE_STATUSES:
            continue
        canonical = str(entry.get("canonical_term", "") or "")
        translation = str(entry.get("approved_translation", "") or "")
        if not canonical and not translation:
            continue
        safe = {
            "term_id": entry.get("id"),
            "canonical_term": canonical,
            "display_term": translation or canonical,
        }
        # Optional public-safe fields
        if entry.get("reading"):
            safe["reading"] = str(entry["reading"])
        if term_type != "term":
            safe["term_type"] = term_type
        # Optional public-safe aliases (bounded)
        aliases = _safe_aliases(entry.get("aliases", []))
        if aliases:
            safe["aliases"] = aliases
        # Optional short definition
        if entry.get("short_definition"):
            safe["short_definition"] = str(entry["short_definition"])[:200]
        results.append(safe)
    return results


def _safe_aliases(aliases: list[Any]) -> list[str]:
    """Extract safe alias texts, bounded."""
    result: list[str] = []
    for alias in (aliases or [])[:MAX_ALIASES]:
        if isinstance(alias, str):
            text = alias
        elif isinstance(alias, dict):
            text = str(alias.get("alias_text") or alias.get("text", ""))
        elif hasattr(alias, "alias_text"):
            text = str(alias.alias_text)
        elif hasattr(alias, "text"):
            text = str(alias.text)
        else:
            text = str(alias)
        if text.strip():
            result.append(text.strip())
    return result


# ---------------------------------------------------------------------------
# Deterministic matching against translated text
# ---------------------------------------------------------------------------


def find_annotations(
    terms: list[dict[str, Any]],
    translated_text: str,
    blocks: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """Match public-safe terms against translated text.

    Returns annotation objects with match positions.
    Bounded to MAX_ANNOTATIONS.
    """
    annotations: list[dict[str, Any]] = []
    matched_texts: set[str] = set()

    for term in terms:
        if len(annotations) >= MAX_ANNOTATIONS:
            break
        display = term.get("display_term", "")
        if not display or display in matched_texts:
            continue
        matches = _find_matches(display, translated_text, blocks)
        if not matches:
            continue
        annotation = {
            "term_id": term["term_id"],
            "canonical_term": str(term.get("canonical_term") or display),
            "display_term": display,
        }
        if term.get("reading"):
            annotation["reading"] = term["reading"]
        if term.get("term_type"):
            annotation["term_type"] = term["term_type"]
        if term.get("short_definition"):
            annotation["short_definition"] = term["short_definition"]
        if term.get("aliases"):
            annotation["aliases"] = term["aliases"]
        annotation["matches"] = matches[:MAX_MATCHES]
        annotations.append(annotation)
        matched_texts.add(display)

    return annotations


def _find_matches(
    display_term: str,
    text: str,
    blocks: list[dict[str, Any]] | None,
) -> list[dict[str, Any]]:
    """Find all occurrences of display_term in text or blocks."""
    pattern = re.compile(re.escape(display_term), re.IGNORECASE)
    matches: list[dict[str, Any]] = []

    if blocks:
        for block_idx, block in enumerate(blocks):
            block_text = str(block.get("text", ""))
            for m in pattern.finditer(block_text):
                matches.append({
                    "surface": m.group(),
                    "block_index": block_idx,
                    "start": m.start(),
                    "end": m.end(),
                })
                if len(matches) >= MAX_MATCHES:
                    return matches
    else:
        for m in pattern.finditer(text):
            matches.append({
                "surface": m.group(),
                "start": m.start(),
                "end": m.end(),
            })
            if len(matches) >= MAX_MATCHES:
                return matches

    return matches
