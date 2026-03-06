from __future__ import annotations

from typing import Any

from novelai.pipeline.stages.base import PipelineStage


class FetchStage(PipelineStage):
    """Fetch text from a source adapter."""

    async def run(self, context: dict[str, Any]) -> dict[str, Any]:
        source = context["source_adapter"]
        chapter_url = context["chapter_url"]
        raw_text = await source.fetch_chapter(chapter_url)
        context["raw_text"] = raw_text
        return context
