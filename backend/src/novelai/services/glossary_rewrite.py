"""Safe text replacement engine for glossary apply.

Replaces old-text spans with new-text spans right-to-left, protecting
structural markers and preventing double-replacement.
"""

from __future__ import annotations

import re
from typing import Any

MARKER_PATTERN = re.compile(r"\[(?:CHAPTER\s[^\]]+|P\s+p?\d+)\]")


def _marker_spans(text: str) -> set[tuple[int, int]]:
    """Return sorted set of (start, end) spans for protected markers."""
    return {(m.start(), m.end()) for m in MARKER_PATTERN.finditer(text)}


def _overlaps(span: tuple[int, int], committed: set[tuple[int, int]]) -> bool:
    s_start, s_end = span
    return any(not (s_end <= c_start or s_start >= c_end) for c_start, c_end in committed)


def apply_glossary_replacements(
    text: str,
    replacements: list[Any],
    *,
    protect_markers: bool = True,
) -> tuple[str, int]:
    """Return (rewritten_text, replacement_count).

    Parameters
    ----------
    text : str
        Source text to apply replacements to.
    replacements : list[ReplacementCandidate-like]
        Each must have ``start_offset``, ``end_offset``, ``old_text``,
        ``new_text`` attributes.
    protect_markers : bool
        When True, skip replacements overlapping ``[CHAPTER ...]`` or
        ``[P pNNNN]`` markers.

    Rules
    -----
    - Sort replacements by span length descending (longest match wins ties),
      then by ``start_offset`` descending (right-to-left to preserve offsets).
    - Skip any replacement whose span overlaps a committed span (marker or
      earlier replacement).
    """
    if not text or not replacements:
        return text, 0

    committed: set[tuple[int, int]] = set()
    if protect_markers:
        committed.update(_marker_spans(text))

    # Sort: longest span first, then rightmost first (descending start_offset)
    sorted_repls = sorted(
        replacements,
        key=lambda r: (r.start_offset, r.end_offset - r.start_offset),
        reverse=True,
    )

    applied = 0
    for r in sorted_repls:
        span = (r.start_offset, r.end_offset)
        if _overlaps(span, committed):
            continue
        # Verify the text still matches at this position
        if text[r.start_offset : r.end_offset] != r.old_text:
            continue
        text = text[: r.start_offset] + r.new_text + text[r.end_offset :]
        committed.add(span)
        applied += 1
        # Adjust subsequent committed spans for length change
        delta = len(r.new_text) - len(r.old_text)
        if delta != 0:
            adjusted: set[tuple[int, int]] = set()
            for c_start, c_end in committed:
                if c_start > r.start_offset:
                    adjusted.add((c_start + delta, c_end + delta))
                else:
                    adjusted.add((c_start, c_end))
            committed = adjusted

    return text, applied
