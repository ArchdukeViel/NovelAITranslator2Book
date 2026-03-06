from __future__ import annotations

import logging
from typing import Optional

from novelai.glossary.glossary import Glossary
from novelai.pipeline.context import PipelineContext
from novelai.pipeline.stages.base import PipelineStage

logger = logging.getLogger(__name__)


class PostProcessStage(PipelineStage):
    """Post-process translated text.
    
    Applies:
    - Glossary term substitutions (for consistent terminology)
    - Text formatting rules
    - Any other post-processing needed
    """

    def __init__(self, glossary: Optional[Glossary] = None) -> None:
        """
        Args:
            glossary: Optional glossary for term substitutions
        """
        self.glossary = glossary

    async def run(self, context: PipelineContext) -> PipelineContext:
        # Join translations from all chunks
        text = "\n\n".join(context.translations)
        logger.info(f"Post-processing {len(context.translations)} translated chunks")
        
        # Apply glossary substitutions if available
        if self.glossary:
            logger.debug("Applying glossary substitutions")
            text = self.glossary.translate(text)
            logger.debug(f"Glossary applied, final text: {len(text)} bytes")
        else:
            logger.debug("No glossary configured, skipping substitutions")
        
        context.final_text = text
        logger.info(f"Post-processing complete: {len(text)} bytes")
        return context
