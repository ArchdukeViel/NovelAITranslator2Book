from __future__ import annotations

import logging

from novelai.pipeline.context import PipelineContext
from novelai.pipeline.stages.base import PipelineStage

logger = logging.getLogger(__name__)


class SegmentStage(PipelineStage):
    """Split normalized text into chunks for translation."""

    async def run(self, context: PipelineContext) -> PipelineContext:
        text = context.normalized_text or ""
        # Simple chunking: split by paragraphs.
        context.chunks = [chunk.strip() for chunk in text.split("\n\n") if chunk.strip()]
        logger.info(f"Segmented into {len(context.chunks)} chunks")
        logger.debug(f"Chunk sizes: {[len(c) for c in context.chunks]}")
        return context
