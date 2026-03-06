from __future__ import annotations

import logging
import re
import unicodedata

from novelai.pipeline.context import PipelineContext
from novelai.pipeline.stages.base import PipelineStage

logger = logging.getLogger(__name__)


class ParseStage(PipelineStage):
    """Clean and normalize raw chapter text for Japanese web novels.
    
    Handles:
    - Unicode normalization (NFC)
    - HTML entity decoding (if present)
    - Whitespace normalization
    - Removal of common web artifacts
    """

    @staticmethod
    def _normalize_unicode(text: str) -> str:
        """Normalize Unicode to NFC form (standard for Japanese)."""
        return unicodedata.normalize("NFC", text)

    @staticmethod
    def _decode_html_entities(text: str) -> str:
        """Decode HTML entities like &nbsp; &lt; etc."""
        import html
        return html.unescape(text)

    @staticmethod
    def _remove_ruby_text(text: str) -> str:
        """Remove ruby annotation text (Japanese furigana markup).
        
        Removes patterns like: <ruby>漢字<rt>かんじ</rt></ruby>
        Keeps the main character/word, removes the ruby/furigana.
        """
        # Remove <rt>...</rt> and <rb>...</rb> tags but keep other content
        text = re.sub(r"<rt[^>]*>.*?</rt>", "", text, flags=re.DOTALL)
        text = re.sub(r"<ruby[^>]*>", "", text)
        text = re.sub(r"</ruby>", "", text)
        return text

    @staticmethod
    def _normalize_whitespace(text: str) -> str:
        """Normalize various whitespace issues.
        
        - Remove leading/trailing whitespace
        - Collapse multiple spaces to single space (within lines)
        - Normalize line endings to \\n
        - Remove excessive blank lines
        """
        # Normalize line endings
        text = text.replace("\r\n", "\n").replace("\r", "\n")
        
        # Collapse multiple consecutive blank lines to max 2
        text = re.sub(r"\n\n\n+", "\n\n", text)
        
        # Remove trailing whitespace from each line
        text = "\n".join(line.rstrip() for line in text.split("\n"))
        
        # Strip overall
        text = text.strip()
        
        return text

    async def run(self, context: PipelineContext) -> PipelineContext:
        raw = context.raw_text or ""
        logger.info(f"Parsing {len(raw)} bytes of raw text")
        
        # Apply normalization pipeline
        text = raw
        text = self._decode_html_entities(text)
        text = self._remove_ruby_text(text)
        text = self._normalize_whitespace(text)
        text = self._normalize_unicode(text)
        
        context.normalized_text = text
        logger.debug(f"Normalized to {len(text)} bytes")
        return context
