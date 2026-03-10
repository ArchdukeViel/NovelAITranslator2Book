from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, TypedDict


class PipelineMetadata(TypedDict, total=False):
    """Well-known metadata keys passed through the pipeline.

    Stages may read/write these keys on ``PipelineState.metadata``.
    All keys are optional so that callers only provide what they need.
    """

    source_language: str
    target_language: str
    glossary: Any  # Iterable[GlossaryEntryLike] | Glossary | None
    style_preset: str
    consistency_mode: bool
    json_output: bool
    _source_adapter: Any  # SourceAdapter instance (internal)


@dataclass
class PipelineInput:
    """Immutable input parameters for pipeline execution.

    Does NOT include source_adapter (passed separately to stages that need it).
    """

    chapter_url: str
    provider_key: str | None = None
    provider_model: str | None = None


@dataclass
class PipelineState:
    """Mutable working state passed between pipeline stages.

    This is the internal context updated as data flows through stages.
    """

    # Inputs (immutable)
    chapter_url: str
    provider_key: str | None = None
    provider_model: str | None = None

    # Pipeline stages' working state
    raw_text: str | None = None
    normalized_text: str | None = None
    chunks: list[str] = field(default_factory=list)
    translations: list[str] = field(default_factory=list)

    # Final output
    final_text: str | None = None

    # Metadata (extensible for stage-specific data)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "chapter_url": self.chapter_url,
            "provider_key": self.provider_key,
            "provider_model": self.provider_model,
            "raw_text": self.raw_text,
            "normalized_text": self.normalized_text,
            "chunks": self.chunks,
            "translations": self.translations,
            "final_text": self.final_text,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PipelineState:
        return cls(
            chapter_url=data["chapter_url"],
            provider_key=data.get("provider_key"),
            provider_model=data.get("provider_model"),
            raw_text=data.get("raw_text"),
            normalized_text=data.get("normalized_text"),
            chunks=data.get("chunks") or [],
            translations=data.get("translations") or [],
            final_text=data.get("final_text"),
            metadata=data.get("metadata") or {},
        )


@dataclass
class PipelineResult:
    """Result of successful pipeline execution."""

    final_text: str
    chapter_url: str
    provider_key: str | None = None
    provider_model: str | None = None
    raw_text: str | None = None
    normalized_text: str | None = None
    chunks: list[str] = field(default_factory=list)
    translations: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_state(cls, state: PipelineState) -> PipelineResult:
        """Create result from final pipeline state."""
        return cls(
            final_text=state.final_text or "",
            chapter_url=state.chapter_url,
            provider_key=state.provider_key,
            provider_model=state.provider_model,
            raw_text=state.raw_text,
            normalized_text=state.normalized_text,
            chunks=state.chunks,
            translations=state.translations,
            metadata=state.metadata,
        )


# For backwards compatibility, PipelineContext is an alias for PipelineState
PipelineContext = PipelineState
