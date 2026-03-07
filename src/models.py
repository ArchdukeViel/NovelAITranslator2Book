from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(slots=True)
class FetchResult:
    """Result of fetching a single chapter page."""

    url: str
    html: str
    fetched_at: str
    status_code: int


@dataclass(slots=True)
class ChapterMetadata:
    """Machine-friendly metadata derived from a chapter page."""

    author: str | None = None
    chapter_number: str | None = None
    published_at: str | None = None
    updated_at: str | None = None

    def to_dict(self) -> dict[str, str | None]:
        return {
            "author": self.author,
            "chapter_number": self.chapter_number,
            "published_at": self.published_at,
            "updated_at": self.updated_at,
        }


@dataclass(slots=True)
class Segment:
    """Stable segment produced from canonical cleaned HTML."""

    segment_id: str
    index: int
    kind: str
    html: str
    text: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "segment_id": self.segment_id,
            "index": self.index,
            "kind": self.kind,
            "html": self.html,
            "text": self.text,
        }


@dataclass(slots=True)
class ChapterDocument:
    """Canonical parsed chapter plus derived artifacts."""

    site: str
    novel_id: str
    chapter_id: str
    url: str
    fetched_at: str
    title: str
    parser_version: str
    adapter: str
    metadata: ChapterMetadata
    source_html: str
    plain_text: str
    segments: list[Segment] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "site": self.site,
            "novel_id": self.novel_id,
            "chapter_id": self.chapter_id,
            "url": self.url,
            "fetched_at": self.fetched_at,
            "title": self.title,
            "parser_version": self.parser_version,
            "adapter": self.adapter,
            "metadata": self.metadata.to_dict(),
            "source_html": self.source_html,
            "plain_text": self.plain_text,
            "segments": [segment.to_dict() for segment in self.segments],
        }


@dataclass(slots=True)
class StoredChapter:
    """Chapter document plus the file artifacts produced by the pipeline."""

    document: ChapterDocument
    raw_html_path: Path
    cleaned_html_path: Path
    json_path: Path

