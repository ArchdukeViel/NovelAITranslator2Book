from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Any, TypedDict

from novelai.shared.pipeline import PipelineEvent


def normalize_paragraph_source_for_hash(text: str) -> str:
    """Normalize harmless line-ending differences before hashing source paragraphs."""
    return text.replace("\r\n", "\n").replace("\r", "\n")


def paragraph_source_hash(text: str) -> str:
    normalized = normalize_paragraph_source_for_hash(text)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class Paragraph:
    """Normalized paragraph prepared for translation."""

    paragraph_id: str
    chapter_id: str
    text: str
    char_count: int
    paragraph_index: int = 0
    source_hash: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "paragraph_id": self.paragraph_id,
            "chapter_id": self.chapter_id,
            "text": self.text,
            "char_count": self.char_count,
            "paragraph_index": self.paragraph_index,
            "source_hash": self.source_hash or paragraph_source_hash(self.text),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Paragraph:
        text = str(data.get("text") or "")
        return cls(
            paragraph_id=str(data["paragraph_id"]),
            chapter_id=str(data["chapter_id"]),
            text=text,
            char_count=int(data.get("char_count") or len(text)),
            paragraph_index=int(data.get("paragraph_index") or 0),
            source_hash=str(data.get("source_hash") or paragraph_source_hash(text)),
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
    paragraph_hashes: list[str] = field(default_factory=list)
    paragraph_lineage: list[dict[str, Any]] = field(default_factory=list)

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
            "paragraph_hashes": list(self.paragraph_hashes),
            "paragraph_lineage": [dict(item) for item in self.paragraph_lineage],
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
        raw_hashes = data.get("paragraph_hashes")
        paragraph_hashes = [str(value) for value in raw_hashes] if isinstance(raw_hashes, list) else []
        raw_lineage = data.get("paragraph_lineage")
        paragraph_lineage = [dict(item) for item in raw_lineage if isinstance(item, dict)] if isinstance(raw_lineage, list) else []

        return cls(
            chunk_id=str(data["chunk_id"]),
            novel_id=str(data.get("novel_id") or "unknown_novel"),
            chapter_ids=[str(value) for value in data.get("chapter_ids", [])],
            paragraph_ids=[str(value) for value in data.get("paragraph_ids", [])],
            source_text=str(data.get("source_text") or ""),
            char_count=int(data.get("char_count") or len(str(data.get("source_text") or ""))),
            previous_context=str(data["previous_context"]) if data.get("previous_context") is not None else None,
            paragraph_refs=paragraph_refs,
            paragraph_hashes=paragraph_hashes,
            paragraph_lineage=paragraph_lineage,
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
    job_id: str | None = None
    activity_id: str | None = None
    novel_id: str | None = None
    chapter_id: str | None = None
    source_key: str | None = None
    provider_key: str | None = None
    provider_model: str | None = None
    current_stage: str | None = None

    # Pipeline stages' working state
    raw_text: str | None = None
    normalized_text: str | None = None
    chunks: list[str] = field(default_factory=list)
    paragraphs: list[Paragraph] = field(default_factory=list)
    translation_chunks: list[TranslationChunk] = field(default_factory=list)
    translations: list[str] = field(default_factory=list)
    pipeline_events: list[dict[str, Any]] = field(default_factory=list)
    chunk_states: dict[str, dict[str, Any]] = field(default_factory=dict)
    scheduler_state: dict[str, Any] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    errors: list[dict[str, Any]] = field(default_factory=list)
    data: dict[str, Any] = field(default_factory=dict)

    # Final output
    final_text: str | None = None

    # Metadata (extensible for stage-specific data)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "chapter_url": self.chapter_url,
            "job_id": self.job_id,
            "activity_id": self.activity_id,
            "novel_id": self.novel_id,
            "chapter_id": self.chapter_id,
            "source_key": self.source_key,
            "provider_key": self.provider_key,
            "provider_model": self.provider_model,
            "current_stage": self.current_stage,
            "raw_text": self.raw_text,
            "normalized_text": self.normalized_text,
            "chunks": self.chunks,
            "paragraphs": [paragraph.to_dict() for paragraph in self.paragraphs],
            "translation_chunks": [chunk.to_dict() for chunk in self.translation_chunks],
            "translations": self.translations,
            "pipeline_events": list(self.pipeline_events),
            "chunk_states": dict(self.chunk_states),
            "scheduler_state": dict(self.scheduler_state),
            "warnings": list(self.warnings),
            "errors": list(self.errors),
            "data": dict(self.data),
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
        raw_pipeline_events = data.get("pipeline_events")
        pipeline_events: list[dict[str, Any]] = [
            dict(event) for event in raw_pipeline_events if isinstance(event, dict)
        ] if isinstance(raw_pipeline_events, list) else []
        raw_chunk_states = data.get("chunk_states")
        chunk_states: dict[str, dict[str, Any]] = {
            str(key): dict(value)
            for key, value in raw_chunk_states.items()
            if isinstance(value, dict)
        } if isinstance(raw_chunk_states, dict) else {}
        raw_scheduler_state = data.get("scheduler_state")
        scheduler_state: dict[str, Any] = dict(raw_scheduler_state) if isinstance(raw_scheduler_state, dict) else {}
        raw_warnings = data.get("warnings")
        warnings: list[str] = [str(item) for item in raw_warnings] if isinstance(raw_warnings, list) else []
        raw_errors = data.get("errors")
        errors: list[dict[str, Any]] = [
            dict(item) for item in raw_errors if isinstance(item, dict)
        ] if isinstance(raw_errors, list) else []
        raw_data = data.get("data")
        context_data: dict[str, Any] = dict(raw_data) if isinstance(raw_data, dict) else {}

        return cls(
            chapter_url=data["chapter_url"],
            job_id=data.get("job_id"),
            activity_id=data.get("activity_id"),
            novel_id=data.get("novel_id"),
            chapter_id=data.get("chapter_id"),
            source_key=data.get("source_key"),
            provider_key=data.get("provider_key"),
            provider_model=data.get("provider_model"),
            current_stage=data.get("current_stage"),
            raw_text=data.get("raw_text"),
            normalized_text=data.get("normalized_text"),
            chunks=data.get("chunks") or [],
            paragraphs=paragraphs,
            translation_chunks=translation_chunks,
            translations=data.get("translations") or [],
            pipeline_events=pipeline_events,
            chunk_states=chunk_states,
            scheduler_state=scheduler_state,
            warnings=warnings,
            errors=errors,
            data=context_data,
            final_text=data.get("final_text"),
            metadata=data.get("metadata") or {},
        )

    def trace_event(
        self,
        *,
        stage_name: str,
        status_before: str | None = None,
        status_after: str | None = None,
        chunk_id: str | None = None,
        warning_code: str | None = None,
        error_code: str | None = None,
        message: str | None = None,
    ) -> dict[str, Any]:
        event = PipelineEvent(
            job_id=self.job_id,
            activity_id=self.activity_id,
            novel_id=self.novel_id,
            chapter_id=self.chapter_id,
            source_key=self.source_key,
            provider_key=self.provider_key,
            provider_model=self.provider_model,
            credential_id=self.metadata.get("credential_id") if isinstance(self.metadata.get("credential_id"), str) else None,
            credential_owner_user_id=self.metadata.get("credential_owner_user_id") if isinstance(self.metadata.get("credential_owner_user_id"), str) else None,
            requesting_user_id=self.metadata.get("requesting_user_id") if isinstance(self.metadata.get("requesting_user_id"), str) else None,
            chunk_id=chunk_id,
            stage_name=stage_name,
            status_before=status_before,
            status_after=status_after,
            warning_code=warning_code,
            error_code=error_code,
            message=message,
        ).to_dict()
        return event


@dataclass
class PipelineResult:
    """Result of successful pipeline execution."""

    final_text: str
    chapter_url: str
    job_id: str | None = None
    activity_id: str | None = None
    novel_id: str | None = None
    chapter_id: str | None = None
    source_key: str | None = None
    provider_key: str | None = None
    provider_model: str | None = None
    current_stage: str | None = None
    raw_text: str | None = None
    normalized_text: str | None = None
    chunks: list[str] = field(default_factory=list)
    paragraphs: list[Paragraph] = field(default_factory=list)
    translation_chunks: list[TranslationChunk] = field(default_factory=list)
    translations: list[str] = field(default_factory=list)
    pipeline_events: list[dict[str, Any]] = field(default_factory=list)
    chunk_states: dict[str, dict[str, Any]] = field(default_factory=dict)
    scheduler_state: dict[str, Any] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    errors: list[dict[str, Any]] = field(default_factory=list)
    data: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_state(cls, state: PipelineState) -> PipelineResult:
        """Create result from final pipeline state."""
        return cls(
            final_text=state.final_text or "",
            chapter_url=state.chapter_url,
            job_id=state.job_id,
            activity_id=state.activity_id,
            novel_id=state.novel_id,
            chapter_id=state.chapter_id,
            source_key=state.source_key,
            provider_key=state.provider_key,
            provider_model=state.provider_model,
            current_stage=state.current_stage,
            raw_text=state.raw_text,
            normalized_text=state.normalized_text,
            chunks=state.chunks,
            paragraphs=state.paragraphs,
            translation_chunks=state.translation_chunks,
            translations=state.translations,
            pipeline_events=state.pipeline_events,
            chunk_states=state.chunk_states,
            scheduler_state=state.scheduler_state,
            warnings=state.warnings,
            errors=state.errors,
            data=state.data,
            metadata=state.metadata,
        )
