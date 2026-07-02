from __future__ import annotations

import logging
from typing import TYPE_CHECKING, cast

from novelai.glossary.glossary import Glossary
from novelai.translation.pipeline.context import PipelineContext
from novelai.translation.pipeline.stages.base import PipelineStage

if TYPE_CHECKING:
    from novelai.services.glossary.suggestion_extractor import SuggestionExtractor
    from novelai.services.glossary.suggestion_service import GlossarySuggestionService

from novelai.services.glossary.suggestion_service import SuggestionSource

logger = logging.getLogger(__name__)


class PostProcessStage(PipelineStage):
    """Post-process translated text.

    Applies:
    - Glossary term substitutions (for consistent terminology)
    - Text formatting rules
    - Suggestion extraction for glossary candidates
    """

    def __init__(
        self,
        glossary: Glossary | None = None,
        suggestion_extractor: SuggestionExtractor | None = None,
        suggestion_service: GlossarySuggestionService | None = None,
    ) -> None:
        self.glossary = glossary
        self.suggestion_extractor = suggestion_extractor
        self.suggestion_service = suggestion_service

    async def run(self, context: PipelineContext) -> PipelineContext:
        text = "\n\n".join(context.translations)
        logger.info("Post-processing %d translated chunks", len(context.translations))

        if self.glossary:
            logger.debug("Applying glossary substitutions")
            text = self.glossary.translate(text)
            logger.debug("Glossary applied, final text: %d bytes", len(text))
        else:
            logger.debug("No glossary configured, skipping substitutions")

        context.final_text = text
        logger.info("Post-processing complete: %d bytes", len(text))

        self._extract_suggestions(context)

        return context

    def _extract_suggestions(self, context: PipelineContext) -> None:
        if not self.suggestion_extractor or not self.suggestion_service:
            return
        novel_id = context.novel_id or context.metadata.get("platform_novel_id", "")
        if not novel_id:
            return

        chapter_id = context.chapter_id or ""
        translated_text = context.final_text or ""
        if not translated_text:
            return

        try:
            suggestions = self.suggestion_extractor.extract(
                novel_id,
                [{"chapter_id": chapter_id, "translated_text": translated_text}],
            )
            if suggestions:
                from novelai.services.glossary.suggestion_service import GlossarySuggestion

                _Source = SuggestionSource

                models = [
                    GlossarySuggestion(
                        id="",
                        source_term=s.source_term,
                        occurrence_count=s.occurrence_count,
                        chapter_count=s.chapter_count,
                        context_snippets=list(s.context_snippets),
                        source=cast(_Source, s.source),
                        term_type=s.term_type,
                        confidence=s.confidence,
                    )
                    for s in suggestions
                ]
                self.suggestion_service.add_suggestions(novel_id, models)
                logger.info("Extracted %d glossary suggestions for %s", len(models), novel_id)
        except Exception as exc:
            logger.warning("Suggestion extraction failed for %s: %s", novel_id, exc)
