from __future__ import annotations

from novelai.pipeline.context import PipelineContext
from novelai.pipeline.stages.base import PipelineStage


class PostProcessStage(PipelineStage):
    """Post-process translated text (e.g., glossary enforcement)."""

    async def run(self, context: PipelineContext) -> PipelineContext:
        # Placeholder: implement glossary replacement, formatting rules, etc.
        context.final_text = "\n\n".join(context.translations)
        return context
