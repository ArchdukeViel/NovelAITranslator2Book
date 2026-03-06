from __future__ import annotations

from typing import Any

from novelai.pipeline.stages.base import PipelineStage


class SegmentStage(PipelineStage):
    """Split normalized text into chunks for translation."""

    async def run(self, context: dict[str, Any]) -> dict[str, Any]:
        text = context.get("normalized_text", "")
        # Simple chunking: split by paragraphs.
        chunks = [chunk.strip() for chunk in text.split("\n\n") if chunk.strip()]
        context["chunks"] = chunks
        return context
