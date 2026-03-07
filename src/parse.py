from __future__ import annotations

from typing import Any

from src.models import ChapterDocument, ChapterMetadata
from src.segment import segment_fragment, segments_to_plain_text

PARSER_VERSION = "1.0.0"


def build_chapter_document(
    *,
    site: str,
    adapter_name: str,
    novel_id: str,
    chapter_id: str,
    url: str,
    fetched_at: str,
    title: str,
    metadata: dict[str, Any] | None,
    source_html: str,
) -> ChapterDocument:
    """Build the canonical chapter document plus derived artifacts."""
    normalized_metadata = _normalize_metadata(metadata)
    segments = segment_fragment(source_html, chapter_id=chapter_id)
    plain_text = segments_to_plain_text(segments)
    return ChapterDocument(
        site=site,
        novel_id=novel_id,
        chapter_id=chapter_id,
        url=url,
        fetched_at=fetched_at,
        title=title.strip() or chapter_id,
        parser_version=PARSER_VERSION,
        adapter=adapter_name,
        metadata=normalized_metadata,
        source_html=source_html,
        plain_text=plain_text,
        segments=segments,
    )


def _normalize_metadata(metadata: dict[str, Any] | None) -> ChapterMetadata:
    payload = metadata or {}
    return ChapterMetadata(
        author=_string_or_none(payload.get("author")),
        chapter_number=_string_or_none(payload.get("chapter_number")),
        published_at=_string_or_none(payload.get("published_at")),
        updated_at=_string_or_none(payload.get("updated_at")),
    )


def _string_or_none(value: Any) -> str | None:
    if isinstance(value, str):
        text = value.strip()
        return text or None
    return None

