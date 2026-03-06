from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class PipelineInput:
    """Immutable input parameters for pipeline execution.
    
    Does NOT include source_adapter (passed separately to stages that need it).
    """

    chapter_url: str
    provider_key: Optional[str] = None
    provider_model: Optional[str] = None


@dataclass
class PipelineState:
    """Mutable working state passed between pipeline stages.
    
    This is the internal context updated as data flows through stages.
    """

    # Inputs (immutable)
    chapter_url: str
    provider_key: Optional[str] = None
    provider_model: Optional[str] = None

    # Pipeline stages' working state
    raw_text: Optional[str] = None
    normalized_text: Optional[str] = None
    chunks: List[str] = field(default_factory=list)
    translations: List[str] = field(default_factory=list)

    # Final output
    final_text: Optional[str] = None

    # Metadata (extensible for stage-specific data)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
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
    def from_dict(cls, data: Dict[str, Any]) -> "PipelineState":
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
    provider_key: Optional[str] = None
    provider_model: Optional[str] = None
    raw_text: Optional[str] = None
    normalized_text: Optional[str] = None
    chunks: List[str] = field(default_factory=list)
    translations: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_state(cls, state: PipelineState) -> "PipelineResult":
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
