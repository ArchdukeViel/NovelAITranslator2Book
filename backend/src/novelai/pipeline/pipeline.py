from __future__ import annotations

from collections.abc import Iterable

from novelai.pipeline.context import PipelineContext
from novelai.pipeline.stages.base import PipelineStage


class TranslationPipeline:
    """Orchestrates a series of transformation stages."""

    def __init__(self, stages: Iterable[PipelineStage]) -> None:
        self.stages = list(stages)

    async def run(self, initial_context: dict[str, object] | PipelineContext) -> PipelineContext:
        """Run the pipeline through all stages.

        The context is converted to a typed PipelineContext instance and passed through
        each stage. This helps make stage inputs/outputs explicit and reduces bugs.
        """
        context = (
            initial_context
            if isinstance(initial_context, PipelineContext)
            else PipelineContext.from_dict(initial_context)
        )

        for stage in self.stages:
            context = await stage.run(context)

        return context
