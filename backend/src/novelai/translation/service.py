from __future__ import annotations

import logging
from typing import Any
from uuid import uuid4

from novelai.sources.base import SourceAdapter
from novelai.translation.pipeline.context import PipelineResult, PipelineState
from novelai.translation.pipeline.pipeline import TranslationPipeline
from novelai.translation.pipeline.stages.fetch import FetchStage
from novelai.translation.pipeline.stages.parse import ParseStage
from novelai.translation.pipeline.stages.post_process import PostProcessStage
from novelai.translation.pipeline.stages.segment import SmartSegmentStage
from novelai.translation.pipeline.stages.translate import TranslateStage
from novelai.translation.pipeline.stages.translation_qa import TranslationQAStage

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
                SmartSegmentStage(),
                TranslateStage(),
                TranslationQAStage(),
                PostProcessStage(),
            ]
        )

    async def translate_chapter(
        self,
        *,
        source_adapter: SourceAdapter | None,
        chapter_url: str,
        job_id: str | None = None,
        activity_id: str | None = None,
        novel_id: str | None = None,
        chapter_id: str | None = None,
        source_key: str | None = None,
        provider_key: str | None = None,
        provider_model: str | None = None,
        platform_novel_id: int | None = None,
        source_language: str | None = None,
        target_language: str | None = None,
        glossary: Any | None = None,
        style_preset: str | None = None,
        consistency_mode: bool = False,
        honorific_policy: str | None = None,
        json_output: bool = False,
        allow_cross_provider_fallback: bool = True,
        force_retranslate: bool = False,
        glossary_revision: int = 0,
        raw_text: str | None = None,
        raw_images: list[dict[str, Any]] | None = None,
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
            job_id=job_id,
            activity_id=activity_id,
            novel_id=novel_id,
            chapter_id=chapter_id,
            source_key=source_key,
            provider_key=provider_key,
            provider_model=provider_model,
        )

        # Store source adapter in metadata so FetchStage can access it
        # (source_adapter is not part of the main state to keep it serializable)
        if source_adapter is not None:
            state.metadata["_source_adapter"] = source_adapter
        if job_id is not None:
            state.metadata["job_id"] = job_id
        if activity_id is not None:
            state.metadata["activity_id"] = activity_id
        state.metadata["translation_run_id"] = job_id or activity_id or f"translation_run_{uuid4().hex}"
        if novel_id is not None:
            state.metadata["novel_id"] = novel_id
        if platform_novel_id is not None:
            state.metadata["platform_novel_id"] = platform_novel_id
        if chapter_id is not None:
            state.metadata["chapter_id"] = chapter_id
        if source_key is not None:
            state.metadata["source_key"] = source_key
        if source_language is not None:
            state.metadata["source_language"] = source_language
        if target_language is not None:
            state.metadata["target_language"] = target_language
        if glossary is not None:
            state.metadata["glossary"] = glossary
        state.metadata["glossary_revision"] = max(0, int(glossary_revision or 0))
        if honorific_policy is not None:
            state.metadata["honorific_policy"] = honorific_policy
        if style_preset is not None:
            state.metadata["style_preset"] = style_preset
        if consistency_mode:
            state.metadata["consistency_mode"] = True
        if json_output:
            state.metadata["json_output"] = True
        if not allow_cross_provider_fallback:
            state.metadata["allow_cross_provider_fallback"] = False
        if force_retranslate:
            state.metadata["force_retranslate"] = True
        if raw_text is not None:
            state.metadata["_prefetched_text"] = raw_text
        if raw_images is not None:
            state.metadata["_prefetched_images"] = raw_images

        # Run pipeline
        logger.debug(f"Running pipeline with stages: {[s.__class__.__name__ for s in self.pipeline.stages]}")
        final_state = await self.pipeline.run(state)

        # Convert to result
        result = PipelineResult.from_state(final_state)
        logger.info(f"Translation pipeline complete: {len(result.final_text)} bytes")
        return result
