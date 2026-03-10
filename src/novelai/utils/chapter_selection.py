from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass


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
