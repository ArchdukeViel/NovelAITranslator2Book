from __future__ import annotations

from novelai.pipeline.context import PipelineContext
from novelai.pipeline.stages.base import PipelineStage


class SegmentStage(PipelineStage):
    """Split normalized text into chunks for translation."""

    async def run(self, context: PipelineContext) -> PipelineContext:
        text = context.normalized_text or ""
        # Simple chunking: split by paragraphs.
        context.chunks = [chunk.strip() for chunk in text.split("\n\n") if chunk.strip()]
        return context
