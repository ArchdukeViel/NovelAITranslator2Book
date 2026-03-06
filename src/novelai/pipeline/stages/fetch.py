from __future__ import annotations

from novelai.pipeline.context import PipelineContext
from novelai.pipeline.stages.base import PipelineStage


class FetchStage(PipelineStage):
    """Fetch text from a source adapter."""

    async def run(self, context: PipelineContext) -> PipelineContext:
        raw_text = await context.source_adapter.fetch_chapter(context.chapter_url)
        context.raw_text = raw_text
        return context
