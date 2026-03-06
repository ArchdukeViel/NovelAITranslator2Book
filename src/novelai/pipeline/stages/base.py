from __future__ import annotations

from abc import ABC, abstractmethod

from novelai.pipeline.context import PipelineContext


class PipelineStage(ABC):
    """Base class for a single pipeline stage."""

    @abstractmethod
    async def run(self, context: PipelineContext) -> PipelineContext:
        """Run stage logic and return the mutated context."""
