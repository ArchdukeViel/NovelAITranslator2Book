from __future__ import annotations

from typing import Any

from novelai.pipeline.stages.base import PipelineStage


class ParseStage(PipelineStage):
    """Clean and normalize raw chapter text."""

    async def run(self, context: dict[str, Any]) -> dict[str, Any]:
        raw = context.get("raw_text", "")
        # Basic normalization placeholder; implement real parsing in future.
        normalized = raw.strip()
        context["normalized_text"] = normalized
        return context
