from __future__ import annotations

from typing import Any, Iterable, List

from novelai.pipeline.stages.base import PipelineStage


class TranslationPipeline:
    """Orchestrates a series of transformation stages."""

    def __init__(self, stages: Iterable[PipelineStage]) -> None:
        self.stages: List[PipelineStage] = list(stages)

    async def run(self, initial_context: dict[str, Any]) -> dict[str, Any]:
        """Run the pipeline through all stages.

        The context dictionary is passed along and may be mutated by each stage.
        """
        context = dict(initial_context)
        for stage in self.stages:
            context = await stage.run(context)
        return context
