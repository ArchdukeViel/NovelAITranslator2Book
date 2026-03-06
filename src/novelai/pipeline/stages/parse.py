from __future__ import annotations

from novelai.pipeline.context import PipelineContext
from novelai.pipeline.stages.base import PipelineStage


class ParseStage(PipelineStage):
    """Clean and normalize raw chapter text."""

    async def run(self, context: PipelineContext) -> PipelineContext:
        raw = context.raw_text or ""
        # Basic normalization placeholder; implement real parsing in future.
        context.normalized_text = raw.strip()
        return context
