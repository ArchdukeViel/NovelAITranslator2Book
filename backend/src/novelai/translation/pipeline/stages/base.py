from __future__ import annotations

from abc import ABC, abstractmethod

from novelai.translation.pipeline.context import PipelineState


class PipelineStage(ABC):
    """Base class for a single pipeline stage."""

    @abstractmethod
    async def run(self, context: PipelineState) -> PipelineState:
        """Run stage logic and return the mutated context."""
