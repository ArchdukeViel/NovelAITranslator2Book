from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class PipelineStage(ABC):
    """Base class for a single pipeline stage."""

    @abstractmethod
    async def run(self, context: dict[str, Any]) -> dict[str, Any]:
        """Run stage logic and return the mutated context."""
