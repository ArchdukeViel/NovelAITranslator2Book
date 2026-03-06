from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from novelai.sources.base import SourceAdapter


@dataclass
class PipelineContext:
    """Typed context for the translation pipeline.

    Stages can read from and write to this context object rather than using a
    loose dict. This enables IDE auto-complete and reduces mistakes from
    misspelled keys.
    """

    # Inputs
    source_adapter: SourceAdapter
    chapter_url: str

    # Provider selection (optional override)
    provider_key: Optional[str] = None
    provider_model: Optional[str] = None

    # Intermediate values
    raw_text: Optional[str] = None
    normalized_text: Optional[str] = None
    chunks: List[str] = field(default_factory=list)
    translations: List[str] = field(default_factory=list)

    # Final output
    final_text: Optional[str] = None

    # Additional metadata (for extensibility)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "source_adapter": self.source_adapter,
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
    def from_dict(cls, data: Dict[str, Any]) -> "PipelineContext":
        return cls(
            source_adapter=data["source_adapter"],
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
