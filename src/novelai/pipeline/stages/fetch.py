from __future__ import annotations

import logging

from novelai.core.errors import PipelineStageError
from novelai.pipeline.context import PipelineContext
from novelai.pipeline.stages.base import PipelineStage

logger = logging.getLogger(__name__)


class FetchStage(PipelineStage):
    """Fetch raw text from a source adapter.

    Expects source_adapter in context.metadata["_source_adapter"].
    """

    async def run(self, context: PipelineContext) -> PipelineContext:
        source_adapter = context.metadata.get("_source_adapter")
        if not source_adapter:
            raise PipelineStageError(
                "FetchStage requires source_adapter in context.metadata['_source_adapter']"
            )

        logger.info(f"Fetching chapter from {context.chapter_url}")
        try:
            raw_text = await source_adapter.fetch_chapter(context.chapter_url)
            context.raw_text = raw_text
            logger.debug(f"Fetched {len(raw_text)} bytes")
        except Exception as e:
            logger.error(f"Failed to fetch chapter: {e}", exc_info=True)
            raise PipelineStageError(f"Failed to fetch chapter: {e}") from e

        return context
