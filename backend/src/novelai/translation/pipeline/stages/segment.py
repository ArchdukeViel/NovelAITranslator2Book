from __future__ import annotations

import logging
import re
from collections.abc import Iterable
from dataclasses import dataclass
from urllib.parse import urlparse

from novelai.config.settings import settings
from novelai.translation.pipeline.context import Paragraph, PipelineContext, TranslationChunk
from novelai.translation.pipeline.stages.base import PipelineStage

logger = logging.getLogger(__name__)

_PARAGRAPH_SPLIT_RE = re.compile(r"\n\s*\n+")


@dataclass(frozen=True)
class _ChapterParagraphs:
    novel_id: str
    chapter_id: str
    paragraphs: list[Paragraph]

    @property
    def char_count(self) -> int:
        return sum(paragraph.char_count for paragraph in self.paragraphs)


class SmartSegmentStage(PipelineStage):
    """Create deterministic paragraph IDs and budget-aware translation chunks."""

    def __init__(
        self,
        *,
        target_chars: int | None = None,
        hard_max_chars: int | None = None,
        overlap_paragraphs: int | None = None,
        allow_multi_chapter_bundles: bool | None = None,
        max_chapters_per_bundle: int | None = None,
    ) -> None:
        self.target_chars = self._positive_int(
            target_chars if target_chars is not None else settings.TRANSLATION_TARGET_CHARS_PER_CHUNK,
            default=4500,
        )
        self.hard_max_chars = self._positive_int(
            hard_max_chars if hard_max_chars is not None else settings.TRANSLATION_HARD_MAX_CHARS_PER_CHUNK,
            default=7000,
        )
        if self.hard_max_chars < self.target_chars:
            self.hard_max_chars = self.target_chars

        self.overlap_paragraphs = max(
            0,
            self._positive_int(
                overlap_paragraphs
                if overlap_paragraphs is not None
                else settings.TRANSLATION_CHUNK_OVERLAP_PARAGRAPHS,
                default=1,
                allow_zero=True,
            ),
        )
        self.allow_multi_chapter_bundles = (
            settings.TRANSLATION_ALLOW_MULTI_CHAPTER_BUNDLES
            if allow_multi_chapter_bundles is None
            else bool(allow_multi_chapter_bundles)
        )
        self.max_chapters_per_bundle = self._positive_int(
            max_chapters_per_bundle
            if max_chapters_per_bundle is not None
            else settings.TRANSLATION_MAX_CHAPTERS_PER_BUNDLE,
            default=3,
        )

    @staticmethod
    def _positive_int(value: object, *, default: int, allow_zero: bool = False) -> int:
        if isinstance(value, bool):
            return default
        if isinstance(value, int):
            if value > 0 or (allow_zero and value == 0):
                return value
        return default

    @staticmethod
    def _clean_id(value: object) -> str | None:
        if not isinstance(value, str):
            return None
        cleaned = value.strip()
        return cleaned or None

    @classmethod
    def _infer_chapter_id(cls, context: PipelineContext) -> str:
        explicit = cls._clean_id(context.chapter_id) or cls._clean_id(context.metadata.get("chapter_id"))
        if explicit:
            return explicit

        parsed = urlparse(context.chapter_url)
        path_parts = [part for part in parsed.path.split("/") if part]
        if path_parts:
            return path_parts[-1]
        return "chapter"

    @classmethod
    def _infer_novel_id(cls, context: PipelineContext) -> str:
        explicit = cls._clean_id(context.novel_id) or cls._clean_id(context.metadata.get("novel_id"))
        if explicit:
            return explicit

        parsed = urlparse(context.chapter_url)
        path_parts = [part for part in parsed.path.split("/") if part]
        if len(path_parts) >= 2:
            return path_parts[-2]
        if parsed.netloc:
            return parsed.netloc
        return "unknown_novel"

    @staticmethod
    def split_paragraphs(text: str, *, chapter_id: str) -> list[Paragraph]:
        """Split normalized chapter text using the current blank-line behavior."""
        parts = [part.strip() for part in _PARAGRAPH_SPLIT_RE.split(text or "") if part.strip()]
        return [
            Paragraph(
                paragraph_id=f"p{index:04d}",
                chapter_id=chapter_id,
                text=part,
                char_count=len(part),
            )
            for index, part in enumerate(parts, start=1)
        ]

    def _chapter_inputs(self, context: PipelineContext) -> list[_ChapterParagraphs]:
        raw_chapters = context.metadata.get("_normalized_chapters")
        if isinstance(raw_chapters, list):
            chapters: list[_ChapterParagraphs] = []
            fallback_novel_id = self._infer_novel_id(context)
            for index, raw_chapter in enumerate(raw_chapters, start=1):
                if not isinstance(raw_chapter, dict):
                    continue
                text = raw_chapter.get("normalized_text", raw_chapter.get("text"))
                if not isinstance(text, str):
                    continue
                chapter_id = (
                    self._clean_id(raw_chapter.get("chapter_id"))
                    or self._clean_id(raw_chapter.get("id"))
                    or f"chapter_{index:04d}"
                )
                novel_id = self._clean_id(raw_chapter.get("novel_id")) or fallback_novel_id
                paragraphs = self.split_paragraphs(text, chapter_id=chapter_id)
                chapters.append(_ChapterParagraphs(novel_id=novel_id, chapter_id=chapter_id, paragraphs=paragraphs))
            return chapters

        chapter_id = self._infer_chapter_id(context)
        novel_id = self._infer_novel_id(context)
        paragraphs = self.split_paragraphs(context.normalized_text or "", chapter_id=chapter_id)
        return [_ChapterParagraphs(novel_id=novel_id, chapter_id=chapter_id, paragraphs=paragraphs)]

    @staticmethod
    def _ordered_unique(values: Iterable[str]) -> list[str]:
        seen: set[str] = set()
        ordered: list[str] = []
        for value in values:
            if value in seen:
                continue
            seen.add(value)
            ordered.append(value)
        return ordered

    @staticmethod
    def _format_chunk_source(paragraphs: list[Paragraph]) -> str:
        lines: list[str] = []
        current_chapter_id: str | None = None
        for paragraph in paragraphs:
            if paragraph.chapter_id != current_chapter_id:
                if lines:
                    lines.append("")
                lines.append(f"[CHAPTER {paragraph.chapter_id}]")
                current_chapter_id = paragraph.chapter_id
            lines.append(f"[P {paragraph.paragraph_id}]")
            lines.append(paragraph.text)
            lines.append("")
        return "\n".join(lines).strip()

    def _previous_context(self, previous_paragraphs: list[Paragraph]) -> str | None:
        if self.overlap_paragraphs <= 0 or not previous_paragraphs:
            return None
        selected = previous_paragraphs[-self.overlap_paragraphs :]
        return "\n\n".join(paragraph.text for paragraph in selected) or None

    def _make_chunk(
        self,
        *,
        index: int,
        novel_id: str,
        paragraphs: list[Paragraph],
        previous_paragraphs: list[Paragraph],
    ) -> TranslationChunk:
        return TranslationChunk(
            chunk_id=f"c{index:04d}",
            novel_id=novel_id,
            chapter_ids=self._ordered_unique(paragraph.chapter_id for paragraph in paragraphs),
            paragraph_ids=[paragraph.paragraph_id for paragraph in paragraphs],
            source_text=self._format_chunk_source(paragraphs),
            char_count=sum(paragraph.char_count for paragraph in paragraphs),
            previous_context=self._previous_context(previous_paragraphs),
            paragraph_refs=[(paragraph.chapter_id, paragraph.paragraph_id) for paragraph in paragraphs],
        )

    def _flush_chunk(
        self,
        *,
        chunks: list[TranslationChunk],
        pending: list[Paragraph],
        novel_id: str,
        previous_paragraphs: list[Paragraph],
    ) -> tuple[list[Paragraph], str]:
        if not pending:
            return previous_paragraphs, novel_id
        chunk = self._make_chunk(
            index=len(chunks) + 1,
            novel_id=novel_id,
            paragraphs=list(pending),
            previous_paragraphs=previous_paragraphs,
        )
        chunks.append(chunk)
        return list(pending), novel_id

    def _append_paragraphs_as_chunks(
        self,
        *,
        chapter: _ChapterParagraphs,
        chunks: list[TranslationChunk],
        warnings: list[str],
        previous_paragraphs: list[Paragraph],
    ) -> list[Paragraph]:
        pending: list[Paragraph] = []
        pending_chars = 0
        for paragraph in chapter.paragraphs:
            if paragraph.char_count > self.hard_max_chars:
                previous_paragraphs, _ = self._flush_chunk(
                    chunks=chunks,
                    pending=pending,
                    novel_id=chapter.novel_id,
                    previous_paragraphs=previous_paragraphs,
                )
                pending = []
                pending_chars = 0
                warnings.append(
                    f"Oversized paragraph {chapter.chapter_id}/{paragraph.paragraph_id} has "
                    f"{paragraph.char_count} chars; isolated in its own chunk."
                )
                previous_paragraphs, _ = self._flush_chunk(
                    chunks=chunks,
                    pending=[paragraph],
                    novel_id=chapter.novel_id,
                    previous_paragraphs=previous_paragraphs,
                )
                continue

            projected = pending_chars + paragraph.char_count
            if pending and (projected > self.hard_max_chars or projected > self.target_chars):
                previous_paragraphs, _ = self._flush_chunk(
                    chunks=chunks,
                    pending=pending,
                    novel_id=chapter.novel_id,
                    previous_paragraphs=previous_paragraphs,
                )
                pending = []
                pending_chars = 0

            pending.append(paragraph)
            pending_chars += paragraph.char_count

        previous_paragraphs, _ = self._flush_chunk(
            chunks=chunks,
            pending=pending,
            novel_id=chapter.novel_id,
            previous_paragraphs=previous_paragraphs,
        )
        return previous_paragraphs

    def _pack_chunks(self, chapters: list[_ChapterParagraphs]) -> tuple[list[TranslationChunk], list[str]]:
        chunks: list[TranslationChunk] = []
        warnings: list[str] = []
        pending: list[Paragraph] = []
        pending_novel_id = chapters[0].novel_id if chapters else "unknown_novel"
        pending_chars = 0
        previous_paragraphs: list[Paragraph] = []

        for chapter in chapters:
            if not chapter.paragraphs:
                continue

            long_chapter = chapter.char_count > self.target_chars
            can_bundle = self.allow_multi_chapter_bundles and not long_chapter

            if not can_bundle:
                previous_paragraphs, pending_novel_id = self._flush_chunk(
                    chunks=chunks,
                    pending=pending,
                    novel_id=pending_novel_id,
                    previous_paragraphs=previous_paragraphs,
                )
                pending = []
                pending_chars = 0
                previous_paragraphs = self._append_paragraphs_as_chunks(
                    chapter=chapter,
                    chunks=chunks,
                    warnings=warnings,
                    previous_paragraphs=previous_paragraphs,
                )
                continue

            pending_chapter_ids = self._ordered_unique(paragraph.chapter_id for paragraph in pending)
            would_add_chapter = chapter.chapter_id not in pending_chapter_ids
            too_many_chapters = (
                bool(pending)
                and would_add_chapter
                and len(pending_chapter_ids) >= self.max_chapters_per_bundle
            )
            would_exceed_target = bool(pending) and pending_chars + chapter.char_count > self.target_chars
            would_exceed_hard_max = bool(pending) and pending_chars + chapter.char_count > self.hard_max_chars
            if too_many_chapters or would_exceed_target or would_exceed_hard_max:
                previous_paragraphs, pending_novel_id = self._flush_chunk(
                    chunks=chunks,
                    pending=pending,
                    novel_id=pending_novel_id,
                    previous_paragraphs=previous_paragraphs,
                )
                pending = []
                pending_chars = 0

            for paragraph in chapter.paragraphs:
                if paragraph.char_count > self.hard_max_chars:
                    previous_paragraphs, pending_novel_id = self._flush_chunk(
                        chunks=chunks,
                        pending=pending,
                        novel_id=pending_novel_id,
                        previous_paragraphs=previous_paragraphs,
                    )
                    pending = []
                    pending_chars = 0
                    warnings.append(
                        f"Oversized paragraph {chapter.chapter_id}/{paragraph.paragraph_id} has "
                        f"{paragraph.char_count} chars; isolated in its own chunk."
                    )
                    previous_paragraphs, pending_novel_id = self._flush_chunk(
                        chunks=chunks,
                        pending=[paragraph],
                        novel_id=chapter.novel_id,
                        previous_paragraphs=previous_paragraphs,
                    )
                    continue

                projected_chars = pending_chars + paragraph.char_count
                if pending and (projected_chars > self.hard_max_chars or projected_chars > self.target_chars):
                    previous_paragraphs, pending_novel_id = self._flush_chunk(
                        chunks=chunks,
                        pending=pending,
                        novel_id=pending_novel_id,
                        previous_paragraphs=previous_paragraphs,
                    )
                    pending = []
                    pending_chars = 0

                pending.append(paragraph)
                pending_chars += paragraph.char_count
                pending_novel_id = chapter.novel_id

        self._flush_chunk(
            chunks=chunks,
            pending=pending,
            novel_id=pending_novel_id,
            previous_paragraphs=previous_paragraphs,
        )
        return chunks, warnings

    async def run(self, context: PipelineContext) -> PipelineContext:
        chapters = self._chapter_inputs(context)
        paragraphs = [paragraph for chapter in chapters for paragraph in chapter.paragraphs]
        chunks, warnings = self._pack_chunks(chapters)

        context.paragraphs = paragraphs
        context.translation_chunks = chunks
        context.chunks = [chunk.source_text for chunk in chunks]
        context.metadata["segmentation"] = {
            "stage": "SmartSegmentStage",
            "target_chars_per_chunk": self.target_chars,
            "hard_max_chars_per_chunk": self.hard_max_chars,
            "paragraph_count": len(paragraphs),
            "chunk_count": len(chunks),
            "warnings": warnings,
        }

        logger.info("Segmented %s paragraphs into %s chunks", len(paragraphs), len(chunks))
        if warnings:
            logger.warning("Segmentation warnings: %s", warnings)
        logger.debug("Chunk sizes: %s", [chunk.char_count for chunk in chunks])
        return context


class SegmentStage(SmartSegmentStage):
    """Backward-compatible name for the smart segmenter."""
