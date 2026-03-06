from __future__ import annotations

from typing import Any

from novelai.pipeline.context import PipelineContext
from novelai.pipeline.pipeline import TranslationPipeline
from novelai.pipeline.stages.fetch import FetchStage
from novelai.pipeline.stages.parse import ParseStage
from novelai.pipeline.stages.post_process import PostProcessStage
from novelai.pipeline.stages.segment import SegmentStage
from novelai.pipeline.stages.translate import TranslateStage


class TranslationService:
    """Service responsible for orchestrating translation jobs."""

    def __init__(self, pipeline: TranslationPipeline | None = None) -> None:
        self.pipeline = pipeline or TranslationPipeline(
            stages=[
                FetchStage(),
                ParseStage(),
                SegmentStage(),
                TranslateStage(),
                PostProcessStage(),
            ]
        )

    async def translate_chapter(
        self,
        *,
        source_adapter: Any,
        chapter_url: str,
        provider_key: str | None = None,
        provider_model: str | None = None,
    ) -> PipelineContext:
        """Run the translation pipeline for a single chapter."""
        context = PipelineContext(
            source_adapter=source_adapter,
            chapter_url=chapter_url,
            provider_key=provider_key,
            provider_model=provider_model,
        )
        return await self.pipeline.run(context)
