from __future__ import annotations

import logging
from typing import Any

from novelai.pipeline.context import PipelineResult, PipelineState
from novelai.pipeline.pipeline import TranslationPipeline
from novelai.pipeline.stages.fetch import FetchStage
from novelai.pipeline.stages.parse import ParseStage
from novelai.pipeline.stages.post_process import PostProcessStage
from novelai.pipeline.stages.segment import SegmentStage
from novelai.pipeline.stages.translate import TranslateStage
from novelai.sources.base import SourceAdapter

logger = logging.getLogger(__name__)


class TranslationService:
    """Service responsible for orchestrating translation jobs.

    Runs text through a pipeline of transformation stages:
    1. Fetch: Get raw text from source
    2. Parse: Normalize and clean text
    3. Segment: Split into chunks
    4. Translate: Translate each chunk
    5. PostProcess: Apply glossary and formatting
    """

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
        source_adapter: SourceAdapter,
        chapter_url: str,
        provider_key: str | None = None,
        provider_model: str | None = None,
        source_language: str | None = None,
        target_language: str | None = None,
        glossary: Any | None = None,
        style_preset: str | None = None,
        consistency_mode: bool = False,
        json_output: bool = False,
    ) -> PipelineResult:
        """Run the translation pipeline for a single chapter.

        Args:
            source_adapter: Source adapter to fetch raw text
            chapter_url: URL or identifier for the chapter
            provider_key: Override default provider
            provider_model: Override default model

        Returns:
            PipelineResult with final_text and metadata
        """
        logger.info(f"Starting translation pipeline for {chapter_url}")

        # Create pipeline state (internal working context)
        state = PipelineState(
            chapter_url=chapter_url,
            provider_key=provider_key,
            provider_model=provider_model,
        )

        # Store source adapter in metadata so FetchStage can access it
        # (source_adapter is not part of the main state to keep it serializable)
        state.metadata["_source_adapter"] = source_adapter
        if source_language is not None:
            state.metadata["source_language"] = source_language
        if target_language is not None:
            state.metadata["target_language"] = target_language
        if glossary is not None:
            state.metadata["glossary"] = glossary
        if style_preset is not None:
            state.metadata["style_preset"] = style_preset
        if consistency_mode:
            state.metadata["consistency_mode"] = True
        if json_output:
            state.metadata["json_output"] = True

        # Run pipeline
        logger.debug(f"Running pipeline with stages: {[s.__class__.__name__ for s in self.pipeline.stages]}")
        final_state = await self.pipeline.run(state)

        # Convert to result
        result = PipelineResult.from_state(final_state)
        logger.info(f"Translation pipeline complete: {len(result.final_text)} bytes")
        return result
