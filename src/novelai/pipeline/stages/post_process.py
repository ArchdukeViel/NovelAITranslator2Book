from __future__ import annotations

from typing import Any

from novelai.pipeline.stages.base import PipelineStage


class PostProcessStage(PipelineStage):
    """Post-process translated text (e.g., glossary enforcement)."""

    async def run(self, context: dict[str, Any]) -> dict[str, Any]:
        translations = context.get("translations", [])
        # Placeholder: implement glossary replacement, formatting rules, etc.
        context["final_text"] = "\n\n".join(translations)
        return context
