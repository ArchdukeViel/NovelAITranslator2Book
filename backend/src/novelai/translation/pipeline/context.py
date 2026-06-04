from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, TypedDict


@dataclass(frozen=True)
class Paragraph:
    """Normalized paragraph prepared for translation."""

    paragraph_id: str
    chapter_id: str
    text: str
    char_count: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "paragraph_id": self.paragraph_id,
            "chapter_id": self.chapter_id,
            "text": self.text,
            "char_count": self.char_count,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Paragraph:
        return cls(
            paragraph_id=str(data["paragraph_id"]),
            chapter_id=str(data["chapter_id"]),
            text=str(data.get("text") or ""),
            char_count=int(data.get("char_count") or len(str(data.get("text") or ""))),
        )


@dataclass(frozen=True)
class TranslationChunk:
    """Temporary provider request unit with paragraph lineage preserved."""

    chunk_id: str
    novel_id: str
    chapter_ids: list[str]
    paragraph_ids: list[str]
    source_text: str
    char_count: int
    previous_context: str | None = None
    paragraph_refs: list[tuple[str, str]] = field(default_factory=list)

    def __str__(self) -> str:
        return self.source_text

    def to_dict(self) -> dict[str, Any]:
        return {
            "chunk_id": self.chunk_id,
            "novel_id": self.novel_id,
            "chapter_ids": list(self.chapter_ids),
            "paragraph_ids": list(self.paragraph_ids),
            "source_text": self.source_text,
            "char_count": self.char_count,
            "previous_context": self.previous_context,
            "paragraph_refs": [
                {"chapter_id": chapter_id, "paragraph_id": paragraph_id}
                for chapter_id, paragraph_id in self.paragraph_refs
            ],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TranslationChunk:
        raw_refs = data.get("paragraph_refs")
        paragraph_refs: list[tuple[str, str]] = []
        if isinstance(raw_refs, list):
            for ref in raw_refs:
                if isinstance(ref, dict):
                    chapter_id = ref.get("chapter_id")
                    paragraph_id = ref.get("paragraph_id")
                    if chapter_id is not None and paragraph_id is not None:
                        paragraph_refs.append((str(chapter_id), str(paragraph_id)))
                elif isinstance(ref, (list, tuple)) and len(ref) == 2:
                    paragraph_refs.append((str(ref[0]), str(ref[1])))

        return cls(
            chunk_id=str(data["chunk_id"]),
            novel_id=str(data.get("novel_id") or "unknown_novel"),
            chapter_ids=[str(value) for value in data.get("chapter_ids", [])],
            paragraph_ids=[str(value) for value in data.get("paragraph_ids", [])],
            source_text=str(data.get("source_text") or ""),
            char_count=int(data.get("char_count") or len(str(data.get("source_text") or ""))),
            previous_context=str(data["previous_context"]) if data.get("previous_context") is not None else None,
            paragraph_refs=paragraph_refs,
        )


class PipelineMetadata(TypedDict, total=False):
    """Well-known metadata keys passed through the pipeline.

    Stages may read/write these keys on ``PipelineState.metadata``.
    All keys are optional so that callers only provide what they need.
    """

    source_language: str
    target_language: str
    glossary: Any  # Iterable[GlossaryEntryLike] | Glossary | None
    glossary_max_entries: int
    glossary_max_context_chars: int
    glossary_runtime_state: list[dict[str, Any]]
    style_preset: str
    consistency_mode: bool
    json_output: bool
    _source_adapter: Any  # SourceAdapter instance (internal)
    _prefetched_text: str
    _prefetched_images: list[dict[str, Any]]
    _normalized_chapters: list[dict[str, Any]]


@dataclass
class PipelineInput:
    """Immutable input parameters for pipeline execution.

    Does NOT include source_adapter (passed separately to stages that need it).
    """

    chapter_url: str
    novel_id: str | None = None
    chapter_id: str | None = None
    provider_key: str | None = None
    provider_model: str | None = None


@dataclass
class PipelineState:
    """Mutable working state passed between pipeline stages.

    This is the internal context updated as data flows through stages.
    """

    # Inputs (immutable)
    chapter_url: str
    novel_id: str | None = None
    chapter_id: str | None = None
    provider_key: str | None = None
    provider_model: str | None = None

    # Pipeline stages' working state
    raw_text: str | None = None
    normalized_text: str | None = None
    chunks: list[str] = field(default_factory=list)
    paragraphs: list[Paragraph] = field(default_factory=list)
    translation_chunks: list[TranslationChunk] = field(default_factory=list)
    translations: list[str] = field(default_factory=list)

    # Final output
    final_text: str | None = None

    # Metadata (extensible for stage-specific data)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "chapter_url": self.chapter_url,
            "novel_id": self.novel_id,
            "chapter_id": self.chapter_id,
            "provider_key": self.provider_key,
            "provider_model": self.provider_model,
            "raw_text": self.raw_text,
            "normalized_text": self.normalized_text,
            "chunks": self.chunks,
            "paragraphs": [paragraph.to_dict() for paragraph in self.paragraphs],
            "translation_chunks": [chunk.to_dict() for chunk in self.translation_chunks],
            "translations": self.translations,
            "final_text": self.final_text,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PipelineState:
        raw_paragraphs = data.get("paragraphs")
        paragraphs = [
            Paragraph.from_dict(paragraph)
            for paragraph in raw_paragraphs
            if isinstance(paragraph, dict)
        ] if isinstance(raw_paragraphs, list) else []

        raw_translation_chunks = data.get("translation_chunks")
        translation_chunks = [
            TranslationChunk.from_dict(chunk)
            for chunk in raw_translation_chunks
            if isinstance(chunk, dict)
        ] if isinstance(raw_translation_chunks, list) else []

        return cls(
            chapter_url=data["chapter_url"],
            novel_id=data.get("novel_id"),
            chapter_id=data.get("chapter_id"),
            provider_key=data.get("provider_key"),
            provider_model=data.get("provider_model"),
            raw_text=data.get("raw_text"),
            normalized_text=data.get("normalized_text"),
            chunks=data.get("chunks") or [],
            paragraphs=paragraphs,
            translation_chunks=translation_chunks,
            translations=data.get("translations") or [],
            final_text=data.get("final_text"),
            metadata=data.get("metadata") or {},
        )


@dataclass
class PipelineResult:
    """Result of successful pipeline execution."""

    final_text: str
    chapter_url: str
    novel_id: str | None = None
    chapter_id: str | None = None
    provider_key: str | None = None
    provider_model: str | None = None
    raw_text: str | None = None
    normalized_text: str | None = None
    chunks: list[str] = field(default_factory=list)
    paragraphs: list[Paragraph] = field(default_factory=list)
    translation_chunks: list[TranslationChunk] = field(default_factory=list)
    translations: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_state(cls, state: PipelineState) -> PipelineResult:
        """Create result from final pipeline state."""
        return cls(
            final_text=state.final_text or "",
            chapter_url=state.chapter_url,
            novel_id=state.novel_id,
            chapter_id=state.chapter_id,
            provider_key=state.provider_key,
            provider_model=state.provider_model,
            raw_text=state.raw_text,
            normalized_text=state.normalized_text,
            chunks=state.chunks,
            paragraphs=state.paragraphs,
            translation_chunks=state.translation_chunks,
            translations=state.translations,
            metadata=state.metadata,
        )


# For backwards compatibility, PipelineContext is an alias for PipelineState
PipelineContext = PipelineState
