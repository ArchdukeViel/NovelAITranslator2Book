from __future__ import annotations

import logging
import re
from collections.abc import Iterable
from dataclasses import dataclass
from urllib.parse import urlparse

from novelai.config.settings import settings
from novelai.shared.pipeline import ChunkTranslationStatus
from novelai.translation.pipeline.context import Paragraph, PipelineState, TranslationChunk, paragraph_source_hash
from novelai.translation.pipeline.stages.base import PipelineStage

logger = logging.getLogger(__name__)

_PARAGRAPH_SPLIT_RE = re.compile(r"\n\s*\n+")
# Sentence boundary candidates used to split oversized paragraphs safely.
# Picked to keep CJK dialogue/quote-pairs intact: prefer splitting AFTER
# closing quotes/parentheses if the closer ends a sentence.
_SENTENCE_SPLIT_RE = re.compile(
    r"(?<=[。！？!?])|(?<=[」』）)])\s+|(?<=\.)\s+"
)


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
        adaptive_chunking_enabled: bool | None = None,
        adaptive_soft_target_chars: int | None = None,
        adaptive_hard_max_chars: int | None = None,
        conditional_overlap_enabled: bool | None = None,
        default_overlap_paragraphs: int | None = None,
        unsafe_boundary_overlap_paragraphs: int | None = None,
        boundary_context_chars: int | None = None,
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
        explicit_baseline_budget = target_chars is not None or hard_max_chars is not None
        self.adaptive_chunking_enabled = (
            bool(settings.TRANSLATION_ADAPTIVE_CHUNKING_ENABLED) and not explicit_baseline_budget
            if adaptive_chunking_enabled is None
            else bool(adaptive_chunking_enabled)
        )
        self.adaptive_soft_target_chars = self._positive_int(
            adaptive_soft_target_chars
            if adaptive_soft_target_chars is not None
            else settings.TRANSLATION_ADAPTIVE_SOFT_TARGET_CHARS,
            default=5800,
        )
        self.adaptive_hard_max_chars = self._positive_int(
            adaptive_hard_max_chars
            if adaptive_hard_max_chars is not None
            else settings.TRANSLATION_ADAPTIVE_HARD_MAX_CHARS,
            default=7000,
        )
        if self.adaptive_hard_max_chars < self.adaptive_soft_target_chars:
            self.adaptive_soft_target_chars = self.adaptive_hard_max_chars

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
        self.conditional_overlap_enabled = (
            bool(settings.TRANSLATION_CONDITIONAL_OVERLAP_ENABLED)
            if conditional_overlap_enabled is None
            else bool(conditional_overlap_enabled)
        )
        self.default_overlap_paragraphs = max(
            0,
            self._positive_int(
                default_overlap_paragraphs
                if default_overlap_paragraphs is not None
                else settings.TRANSLATION_DEFAULT_OVERLAP_PARAGRAPHS,
                default=0,
                allow_zero=True,
            ),
        )
        self.unsafe_boundary_overlap_paragraphs = max(
            0,
            self._positive_int(
                unsafe_boundary_overlap_paragraphs
                if unsafe_boundary_overlap_paragraphs is not None
                else settings.TRANSLATION_UNSAFE_BOUNDARY_OVERLAP_PARAGRAPHS,
                default=1,
                allow_zero=True,
            ),
        )
        self.boundary_context_chars = self._positive_int(
            boundary_context_chars
            if boundary_context_chars is not None
            else settings.TRANSLATION_BOUNDARY_CONTEXT_CHARS,
            default=160,
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
    def _infer_chapter_id(cls, context: PipelineState) -> str:
        explicit = cls._clean_id(context.chapter_id) or cls._clean_id(context.metadata.get("chapter_id"))
        if explicit:
            return explicit

        parsed = urlparse(context.chapter_url)
        path_parts = [part for part in parsed.path.split("/") if part]
        if path_parts:
            return path_parts[-1]
        return "chapter"

    @classmethod
    def _infer_novel_id(cls, context: PipelineState) -> str:
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
                paragraph_index=index,
                source_hash=paragraph_source_hash(part),
            )
            for index, part in enumerate(parts, start=1)
        ]

    @classmethod
    def split_oversized_paragraph(
        cls,
        paragraph: Paragraph,
        *,
        budget_chars: int,
    ) -> list[Paragraph]:
        """Split an oversized paragraph into sub-paragraphs under ``budget_chars``.

        Strategy:
        1. Prefer sentence/dialogue-safe boundaries from ``_SENTENCE_SPLIT_RE``.
        2. If a single sentence still exceeds budget, fall back to a hard
           character-window split with continuation markers so providers still
           receive bounded text.
        3. Preserve the original ``paragraph_id`` on every split so downstream
           mapping (paragraph_refs, paragraph_hashes) still traces back.

        Each emitted sub-paragraph carries the source paragraph's hash so
        persisted hashes remain stable for QA. ``paragraph_split_index`` and
        ``paragraph_split_count`` record the split position; the base dataclass
        does not need a new field because we reuse the existing ``text`` and
        ``source_hash`` fields and attach split metadata when building the
        chunk lineage.
        """
        text = paragraph.text
        if len(text) <= budget_chars:
            return [paragraph]

        # 1) Sentence-boundary split. Greedy pack: accumulate sentences until
        # adding the next one would exceed budget, then flush.
        pieces: list[str] = []
        cursor = 0
        for match in _SENTENCE_SPLIT_RE.finditer(text):
            end = match.end()
            # Skip zero-length matches (e.g. when regex is anchored at index 0)
            if end <= cursor:
                continue
            pieces.append(text[cursor:end])
            cursor = end
        if cursor < len(text):
            pieces.append(text[cursor:])

        # If everything fit into a single piece (no safe boundary), fall back
        # to a hard character-window split.
        if len(pieces) <= 1 or any(len(piece) > budget_chars for piece in pieces):
            pieces = cls._hard_window_split(text, budget_chars)

        pieces = [piece for piece in pieces if piece]
        if not pieces:
            return [paragraph]

        return cls._build_split_paragraphs(paragraph, pieces)

    @staticmethod
    def _hard_window_split(text: str, budget_chars: int) -> list[str]:
        window = max(1, budget_chars)
        return [text[index : index + window] for index in range(0, len(text), window)]

    @staticmethod
    def _build_split_paragraphs(source: Paragraph, pieces: list[str]) -> list[Paragraph]:
        return [
            Paragraph(
                paragraph_id=source.paragraph_id,
                chapter_id=source.chapter_id,
                text=piece,
                char_count=len(piece),
                paragraph_index=source.paragraph_index,
                source_hash=source.source_hash,
            )
            for piece in pieces
        ]

    def _chapter_inputs(self, context: PipelineState) -> list[_ChapterParagraphs]:
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
    def _format_chunk_source(paragraphs: list[Paragraph], *, overlap_paragraphs: list[Paragraph] | None = None) -> str:
        lines: list[str] = []
        if overlap_paragraphs:
            lines.append("[CONTEXT OVERLAP]")
            lines.extend(paragraph.text for paragraph in overlap_paragraphs)
            lines.append("[END CONTEXT OVERLAP]")
            lines.append("")

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

    @staticmethod
    def _is_scene_separator(paragraph: Paragraph) -> bool:
        text = paragraph.text.strip()
        return text in {"***", "* * *", "---", "- - -", "◇◇◇", "◆◆◆"}

    @staticmethod
    def _has_protected_marker(paragraph: Paragraph) -> bool:
        text = paragraph.text
        return any(marker in text for marker in ("[Image:", "<ruby", "</ruby>", "{{", "}}"))

    @staticmethod
    def _quote_balance(text: str) -> int:
        pairs = {"「": "」", "『": "』", "（": "）", "(": ")", "[": "]", "【": "】", "《": "》"}
        closers = set(pairs.values())
        balance = 0
        for char in text:
            if char in pairs:
                balance += 1
            elif char in closers:
                balance -= 1
        return balance

    @staticmethod
    def _ends_with_sentence_punctuation(paragraph: Paragraph) -> bool:
        return paragraph.text.rstrip().endswith(("。", "！", "？", ".", "!", "?", "」", "』", "）", ")"))

    @staticmethod
    def _is_short_dialogue(paragraph: Paragraph) -> bool:
        text = paragraph.text.strip()
        return len(text) <= 80 and (text.startswith(("「", "『", '"')) or text.endswith(("」", "』", '"')))

    def _boundary_is_unsafe(self, previous_paragraph: Paragraph, next_paragraph: Paragraph) -> bool:
        if self._is_scene_separator(previous_paragraph):
            return False
        previous_balance = self._quote_balance(previous_paragraph.text)
        next_balance = self._quote_balance(next_paragraph.text)
        if previous_balance > 0 or next_balance < 0:
            return True
        if self._is_short_dialogue(previous_paragraph) and self._is_short_dialogue(next_paragraph):
            return True
        if self._has_protected_marker(previous_paragraph) or self._has_protected_marker(next_paragraph):
            return True
        return (
            not self._ends_with_sentence_punctuation(previous_paragraph)
            and (previous_paragraph.char_count <= 160 or next_paragraph.char_count <= 160)
        )

    def _source_overlap_for_boundary(
        self,
        previous_paragraphs: list[Paragraph],
        next_paragraphs: list[Paragraph],
    ) -> list[Paragraph]:
        if not self.conditional_overlap_enabled:
            return []
        if not previous_paragraphs or not next_paragraphs:
            return []
        overlap_count = self.default_overlap_paragraphs
        if self._boundary_is_unsafe(previous_paragraphs[-1], next_paragraphs[0]):
            overlap_count = max(overlap_count, self.unsafe_boundary_overlap_paragraphs)
        if overlap_count <= 0:
            return []
        return previous_paragraphs[-overlap_count:]

    def _previous_context(self, previous_paragraphs: list[Paragraph]) -> str | None:
        if not previous_paragraphs:
            return None
        if not self.conditional_overlap_enabled:
            if self.overlap_paragraphs <= 0:
                return None
            selected = previous_paragraphs[-self.overlap_paragraphs :]
            return "\n\n".join(paragraph.text for paragraph in selected) or None
        tail = "\n\n".join(paragraph.text for paragraph in previous_paragraphs)
        if len(tail) > self.boundary_context_chars:
            tail = tail[-self.boundary_context_chars :]
        return tail or None

    def _make_chunk(
        self,
        *,
        index: int,
        novel_id: str,
        paragraphs: list[Paragraph],
        previous_paragraphs: list[Paragraph],
    ) -> TranslationChunk:
        overlap_paragraphs = self._source_overlap_for_boundary(previous_paragraphs, paragraphs)
        paragraph_hashes = [paragraph.source_hash for paragraph in paragraphs]
        paragraph_lineage = [
            {
                "chapter_id": paragraph.chapter_id,
                "paragraph_id": paragraph.paragraph_id,
                "paragraph_index": paragraph.paragraph_index,
                "source_hash": paragraph.source_hash,
                "char_count": paragraph.char_count,
            }
            for paragraph in paragraphs
        ]
        return TranslationChunk(
            chunk_id=f"c{index:04d}",
            novel_id=novel_id,
            chapter_ids=self._ordered_unique(paragraph.chapter_id for paragraph in paragraphs),
            paragraph_ids=[paragraph.paragraph_id for paragraph in paragraphs],
            source_text=self._format_chunk_source(paragraphs, overlap_paragraphs=overlap_paragraphs),
            char_count=sum(paragraph.char_count for paragraph in paragraphs),
            previous_context=self._previous_context(previous_paragraphs),
            paragraph_refs=[(paragraph.chapter_id, paragraph.paragraph_id) for paragraph in paragraphs],
            paragraph_hashes=paragraph_hashes,
            paragraph_lineage=paragraph_lineage,
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

    def _balanced_paragraph_groups(
        self,
        paragraphs: list[Paragraph],
        *,
        chunk_count: int,
        hard_max_chars: int,
    ) -> list[list[Paragraph]]:
        if chunk_count <= 1:
            return [list(paragraphs)] if paragraphs else []

        total_chars = sum(paragraph.char_count for paragraph in paragraphs)
        target = max(1, total_chars / chunk_count)
        groups: list[list[Paragraph]] = []
        pending: list[Paragraph] = []
        pending_chars = 0

        for index, paragraph in enumerate(paragraphs):
            remaining_paragraphs = len(paragraphs) - index - 1
            remaining_groups = chunk_count - len(groups) - 1
            projected = pending_chars + paragraph.char_count
            has_enough_remaining = 1 + remaining_paragraphs >= remaining_groups
            can_close_before = bool(pending) and len(groups) < chunk_count - 1 and has_enough_remaining
            # Boundary priority: scene break > paragraph > sentence > hard split.
            # A scene break is the strongest close signal: close eagerly even if
            # the current group is still well below the per-group target, because
            # a scene break is exactly the kind of natural story boundary the
            # spec wants to preserve.
            scene_boundary = bool(pending) and self._is_scene_separator(pending[-1])
            near_target = can_close_before and abs(pending_chars - target) < abs(projected - target)
            exceeds_hard = can_close_before and projected > hard_max_chars
            # If the next paragraph starts an open quote/parenthesis or is a
            # dialogue-heavy line, prefer not to close before it (let it stay
            # with the prior group) unless the budget is exceeded.
            next_is_dialogue = self._is_short_dialogue(paragraph) and self._quote_balance(paragraph.text) > 0

            close_for_scene = bool(pending) and scene_boundary and not next_is_dialogue
            if can_close_before and (exceeds_hard or close_for_scene or (near_target and not next_is_dialogue)):
                groups.append(pending)
                pending = []
                pending_chars = 0

            pending.append(paragraph)
            pending_chars += paragraph.char_count

        if pending:
            groups.append(pending)
        return groups

    def _adaptive_groups_for_chapter(
        self,
        chapter: _ChapterParagraphs,
        *,
        warnings: list[str],
    ) -> list[list[Paragraph]]:
        groups: list[list[Paragraph]] = []
        segment: list[Paragraph] = []

        def flush_segment() -> None:
            if not segment:
                return
            segment_chars = sum(paragraph.char_count for paragraph in segment)
            chunk_count = max(1, -(-segment_chars // self.adaptive_hard_max_chars))
            while True:
                balanced = self._balanced_paragraph_groups(
                    segment,
                    chunk_count=chunk_count,
                    hard_max_chars=self.adaptive_hard_max_chars,
                )
                if all(sum(paragraph.char_count for paragraph in group) <= self.adaptive_hard_max_chars for group in balanced):
                    groups.extend(balanced)
                    break
                chunk_count += 1
            segment.clear()

        for paragraph in chapter.paragraphs:
            if paragraph.char_count > self.adaptive_hard_max_chars:
                flush_segment()
                splits = self.split_oversized_paragraph(
                    paragraph, budget_chars=self.adaptive_hard_max_chars
                )
                if len(splits) > 1:
                    warnings.append(
                        f"Oversized paragraph {chapter.chapter_id}/{paragraph.paragraph_id} "
                        f"({paragraph.char_count} chars) split into {len(splits)} parts."
                    )
                for group in self._group_splits_into_budget(splits):
                    groups.append(group)
                continue
            segment.append(paragraph)
        flush_segment()
        return groups

    def _group_splits_into_budget(
        self,
        splits: list[Paragraph],
        *,
        budget_chars: int | None = None,
    ) -> list[list[Paragraph]]:
        """Pack split sub-paragraphs into groups that respect the budget.

        Each split is already at-or-under ``budget_chars`` on its own; we
        only need to combine them when the sum stays under the cap.
        """
        cap = budget_chars if budget_chars is not None else self.adaptive_hard_max_chars
        groups: list[list[Paragraph]] = []
        pending: list[Paragraph] = []
        pending_chars = 0
        for split in splits:
            projected = pending_chars + split.char_count
            if pending and projected > cap:
                groups.append(pending)
                pending = []
                pending_chars = 0
            pending.append(split)
            pending_chars += split.char_count
        if pending:
            groups.append(pending)
        return groups

    def _append_adaptive_chapter_chunks(
        self,
        *,
        chapter: _ChapterParagraphs,
        chunks: list[TranslationChunk],
        warnings: list[str],
        previous_paragraphs: list[Paragraph],
    ) -> list[Paragraph]:
        for group in self._adaptive_groups_for_chapter(chapter, warnings=warnings):
            previous_paragraphs, _ = self._flush_chunk(
                chunks=chunks,
                pending=group,
                novel_id=chapter.novel_id,
                previous_paragraphs=previous_paragraphs,
            )
        return previous_paragraphs

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
                splits = self.split_oversized_paragraph(paragraph, budget_chars=self.hard_max_chars)
                if len(splits) > 1:
                    warnings.append(
                        f"Oversized paragraph {chapter.chapter_id}/{paragraph.paragraph_id} "
                        f"({paragraph.char_count} chars) split into {len(splits)} parts."
                    )
                for group in self._group_splits_into_budget(splits, budget_chars=self.hard_max_chars):
                    previous_paragraphs, _ = self._flush_chunk(
                        chunks=chunks,
                        pending=group,
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

    def _pack_chunks_baseline(self, chapters: list[_ChapterParagraphs]) -> tuple[list[TranslationChunk], list[str]]:
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
                    splits = self.split_oversized_paragraph(paragraph, budget_chars=self.hard_max_chars)
                    if len(splits) > 1:
                        warnings.append(
                            f"Oversized paragraph {chapter.chapter_id}/{paragraph.paragraph_id} "
                            f"({paragraph.char_count} chars) split into {len(splits)} parts."
                        )
                    for group in self._group_splits_into_budget(splits, budget_chars=self.hard_max_chars):
                        previous_paragraphs, pending_novel_id = self._flush_chunk(
                            chunks=chunks,
                            pending=group,
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

    def _pack_chunks_adaptive(self, chapters: list[_ChapterParagraphs]) -> tuple[list[TranslationChunk], list[str]]:
        chunks: list[TranslationChunk] = []
        warnings: list[str] = []
        pending: list[Paragraph] = []
        pending_novel_id = chapters[0].novel_id if chapters else "unknown_novel"
        pending_chars = 0
        previous_paragraphs: list[Paragraph] = []

        for chapter in chapters:
            if not chapter.paragraphs:
                continue

            can_single_chunk = chapter.char_count <= self.adaptive_hard_max_chars and all(
                paragraph.char_count <= self.adaptive_hard_max_chars for paragraph in chapter.paragraphs
            )
            can_bundle = self.allow_multi_chapter_bundles and can_single_chunk

            if not can_bundle:
                previous_paragraphs, pending_novel_id = self._flush_chunk(
                    chunks=chunks,
                    pending=pending,
                    novel_id=pending_novel_id,
                    previous_paragraphs=previous_paragraphs,
                )
                pending = []
                pending_chars = 0
                previous_paragraphs = self._append_adaptive_chapter_chunks(
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
            would_exceed_soft_target = bool(pending) and pending_chars + chapter.char_count > self.adaptive_soft_target_chars
            would_exceed_hard_max = bool(pending) and pending_chars + chapter.char_count > self.adaptive_hard_max_chars
            if too_many_chapters or would_exceed_soft_target or would_exceed_hard_max:
                previous_paragraphs, pending_novel_id = self._flush_chunk(
                    chunks=chunks,
                    pending=pending,
                    novel_id=pending_novel_id,
                    previous_paragraphs=previous_paragraphs,
                )
                pending = []
                pending_chars = 0

            pending.extend(chapter.paragraphs)
            pending_chars += chapter.char_count
            pending_novel_id = chapter.novel_id

        self._flush_chunk(
            chunks=chunks,
            pending=pending,
            novel_id=pending_novel_id,
            previous_paragraphs=previous_paragraphs,
        )
        return chunks, warnings

    def _pack_chunks(self, chapters: list[_ChapterParagraphs]) -> tuple[list[TranslationChunk], list[str]]:
        if self.adaptive_chunking_enabled:
            return self._pack_chunks_adaptive(chapters)
        return self._pack_chunks_baseline(chapters)

    def estimate_chapter_chunks(
        self,
        *,
        novel_id: str,
        chapter_id: str,
        text: str,
    ) -> tuple[list[Paragraph], list[TranslationChunk], list[str]]:
        """Return the current single-chapter chunking result without mutating pipeline state."""
        paragraphs = self.split_paragraphs(text, chapter_id=chapter_id)
        chunks, warnings = self._pack_chunks(
            [_ChapterParagraphs(novel_id=novel_id, chapter_id=chapter_id, paragraphs=paragraphs)]
        )
        return paragraphs, chunks, warnings

    async def run(self, context: PipelineState) -> PipelineState:
        chapters = self._chapter_inputs(context)
        paragraphs = [paragraph for chapter in chapters for paragraph in chapter.paragraphs]
        chunks, warnings = self._pack_chunks(chapters)

        context.paragraphs = paragraphs
        context.translation_chunks = chunks
        context.chunks = [chunk.source_text for chunk in chunks]
        context.chunk_states = {
            chunk.chunk_id: {
                "chunk_id": chunk.chunk_id,
                "novel_id": chunk.novel_id,
                "chapter_ids": list(chunk.chapter_ids),
                "paragraph_ids": list(chunk.paragraph_ids),
                "paragraph_hashes": list(chunk.paragraph_hashes),
                "status": ChunkTranslationStatus.PENDING.value,
                "attempt_number": 0,
            }
            for chunk in chunks
        }
        context.metadata["segmentation"] = {
            "stage": "SmartSegmentStage",
            "target_chars_per_chunk": self.target_chars,
            "hard_max_chars_per_chunk": self.hard_max_chars,
            "adaptive_chunking_enabled": self.adaptive_chunking_enabled,
            "adaptive_soft_target_chars": self.adaptive_soft_target_chars,
            "adaptive_hard_max_chars": self.adaptive_hard_max_chars,
            "conditional_overlap_enabled": self.conditional_overlap_enabled,
            "default_overlap_paragraphs": self.default_overlap_paragraphs,
            "unsafe_boundary_overlap_paragraphs": self.unsafe_boundary_overlap_paragraphs,
            "boundary_context_chars": self.boundary_context_chars,
            "paragraph_count": len(paragraphs),
            "chunk_count": len(chunks),
            "warnings": warnings,
        }
        if warnings:
            context.warnings.extend(warnings)
            context.metadata["warnings"] = context.warnings

        logger.info("Segmented %s paragraphs into %s chunks", len(paragraphs), len(chunks))
        if warnings:
            logger.warning("Segmentation warnings: %s", warnings)
        logger.debug("Chunk sizes: %s", [chunk.char_count for chunk in chunks])
        return context


class SegmentStage(SmartSegmentStage):
    """Backward-compatible name for the smart segmenter."""
