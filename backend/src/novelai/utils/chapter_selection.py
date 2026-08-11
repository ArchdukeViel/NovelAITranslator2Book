from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ChapterRange:
    chapter: int
    subchapter: int | None = None


def is_full_chapter_selection(selection: str) -> bool:
    normalized = selection.strip().lower()
    return normalized in {"*", "all", "full"}


def parse_range_segment(segment: str) -> Iterable[int]:
    """Parse a numeric range segment like '1', '3-5' into a list of ints."""
    if "-" in segment:
        start, end = segment.split("-", 1)
        return list(range(int(start), int(end) + 1))
    return [int(segment)]


def parse_chapter_selection(selection: str) -> list[ChapterRange]:
    """Parse a selection string like '1-3;5:1-2,4' into explicit ranges."""
    selection = selection.strip()
    if not selection:
        return []

    out: list[ChapterRange] = []
    for part in selection.split(";"):
        part = part.strip()
        if not part:
            continue

        if ":" in part:
            chapter_part, sub_part = part.split(":", 1)
            chapters = parse_range_segment(chapter_part)
            sub_items = [s.strip() for s in sub_part.split(",") if s.strip()]
            for chap in chapters:
                for subseg in sub_items:
                    for sub in parse_range_segment(subseg):
                        out.append(ChapterRange(chapter=chap, subchapter=sub))
        else:
            for chap in parse_range_segment(part):
                out.append(ChapterRange(chapter=chap))

    return out


# ---------------------------------------------------------------------------
# Resolved chapter selection (Section 2 contract)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ResolvedChapterSelection:
    """A single resolved chapter from a section string.

    ``chapter_id`` is the stable logical chapter identifier used by every
    downstream storage and translation call. ``source_episode_id`` is the
    source-native identifier (Syosetu ``num``, Kakuyomu ``episode_id``).
    ``sequence_number`` is the mutable reading position. ``metadata`` carries
    the source-supplied chapter dict (title, url, source_update_date, …).
    """

    chapter_id: str
    source_episode_id: str
    sequence_number: int
    metadata: dict[str, Any] = field(default_factory=dict)


def _chapter_logical_id(chapter: dict[str, Any]) -> str:
    """Return the logical chapter_id for a chapter index entry.

    Adapters may emit ``"id"`` for non-numeric ids (Kakuyomu) or only
    ``"num"`` (legacy Syosetu). Stable ids win; sequence-only entries fall
    back to the stringified ``num``.
    """
    for key in ("id", "chapter_id"):
        raw = chapter.get(key)
        if isinstance(raw, str) and raw.strip():
            return raw.strip()
        if isinstance(raw, int):
            return str(raw)
    return ""


def _chapter_source_episode_id(chapter: dict[str, Any], fallback: str) -> str:
    raw = chapter.get("source_episode_id")
    if isinstance(raw, str) and raw.strip():
        return raw.strip()
    if isinstance(raw, int):
        return str(raw)
    num = chapter.get("num")
    if isinstance(num, int):
        return str(num)
    return fallback


def _chapter_sequence_number(chapter: dict[str, Any], fallback: int) -> int:
    for key in ("sequence_number", "num"):
        raw = chapter.get(key)
        if isinstance(raw, int) and raw > 0:
            return raw
    return fallback


def _split_explicit_tokens(selection: str) -> Iterable[str]:
    """Yield explicit non-numeric selection tokens (``kakuyomu:123``)."""
    for raw in (selection or "").replace(",", ";").split(";"):
        token = raw.strip()
        if not token:
            continue
        if token.isdigit():
            continue
        if "-" in token and all(part.strip().isdigit() for part in token.split("-", 1)):
            continue
        if ":" in token and all(part.strip().isdigit() for part in token.split(":", 1)):
            continue
        yield token


def resolve_chapter_selection(
    metadata: dict[str, Any],
    selection: str,
) -> list[ResolvedChapterSelection]:
    """Resolve a selection string to stable :class:`ResolvedChapterSelection` items.

    Inputs:

    - ``metadata`` — the current novel metadata whose ``chapters`` list is the
      complete current source index.
    - ``selection`` — the DSL string (``"all"``, ``"1-3;8"``, ``"2"``,
      ``"kakuyomu:16818093075570329555"``).

    Returns one ``ResolvedChapterSelection`` per matching chapter, in source
    order, deduplicated by chapter_id. Numeric range tokens resolve to the
    chapters at that sequence position so a re-read of the index never maps
    a stable id onto the wrong chapter.
    """
    if not isinstance(metadata, dict):
        return []
    chapters = metadata.get("chapters")
    if not isinstance(chapters, list) or not chapters:
        return []

    by_id: dict[str, dict[str, Any]] = {}
    ordered_ids: list[str] = []
    for chapter in chapters:
        if not isinstance(chapter, dict):
            continue
        chapter_id = _chapter_logical_id(chapter)
        if not chapter_id or chapter_id in by_id:
            continue
        by_id[chapter_id] = chapter
        ordered_ids.append(chapter_id)
    if not ordered_ids:
        return []

    by_position: dict[int, str] = {position: chapter_id for position, chapter_id in enumerate(ordered_ids, start=1)}

    chosen_ids: list[str] = []
    seen: set[str] = set()
    if is_full_chapter_selection(selection):
        chosen_ids = list(ordered_ids)
    else:
        try:
            ranges = parse_chapter_selection(selection)
        except ValueError:
            ranges = []
        for spec in ranges:
            chapter_id = by_position.get(int(spec.chapter))
            if not chapter_id or chapter_id in seen:
                continue
            chosen_ids.append(chapter_id)
            seen.add(chapter_id)
        for token in _split_explicit_tokens(selection):
            if token in by_id and token not in seen:
                chosen_ids.append(token)
                seen.add(token)

    resolved: list[ResolvedChapterSelection] = []
    for chapter_id in chosen_ids:
        chapter = by_id.get(chapter_id)
        if not isinstance(chapter, dict):
            continue
        position = ordered_ids.index(chapter_id) + 1
        resolved.append(
            ResolvedChapterSelection(
                chapter_id=chapter_id,
                source_episode_id=_chapter_source_episode_id(chapter, chapter_id),
                sequence_number=_chapter_sequence_number(chapter, position),
                metadata=dict(chapter),
            )
        )
    return resolved


def resolve_chapter_ids(metadata: dict[str, Any], selection: str) -> list[str]:
    """Return the resolved stable chapter_ids for a selection.

    Convenience wrapper used by orchestrator call sites that previously
    consumed a numeric ``selected_numbers`` list. Pure-numeric selections
    still resolve to the chapter_id sitting at that sequence position so
    the legacy contract is preserved end-to-end.
    """
    return [record.chapter_id for record in resolve_chapter_selection(metadata, selection)]


def select_sequence_numbers(metadata: dict[str, Any], selection: str) -> list[int]:
    """Return the resolved sequence numbers (1-based) for a selection.

    Numeric selections return the exact positions the orchestrator
    requested; non-numeric explicit ids resolve to the current position of
    the matching chapter. Used by legacy orchestrator paths that still
    compare against ``chapter["num"]``/``chapter["sequence_number"]``.
    """
    return [record.sequence_number for record in resolve_chapter_selection(metadata, selection)]
