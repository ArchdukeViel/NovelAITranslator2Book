from __future__ import annotations

from typing import Any, Dict

from novelai.pipeline.pipeline import TranslationPipeline
from novelai.pipeline.stages.fetch import FetchStage
from novelai.pipeline.stages.parse import ParseStage
from novelai.pipeline.stages.segment import SegmentStage
from novelai.pipeline.stages.translate import TranslateStage
from novelai.pipeline.stages.post_process import PostProcessStage


class TranslationService:
    """Service responsible for orchestrating translation jobs."""

    def __init__(self) -> None:
        self.pipeline = TranslationPipeline(
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
    ) -> Dict[str, Any]:
        """Run the translation pipeline for a single chapter."""
        context = {
            "source_adapter": source_adapter,
            "chapter_url": chapter_url,
            "provider_key": provider_key,
            "provider_model": provider_model,
        }
        return await self.pipeline.run(context)
