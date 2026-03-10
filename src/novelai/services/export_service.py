from __future__ import annotations

import logging
from typing import Any, Literal

from novelai.export.registry import get_exporter

logger = logging.getLogger(__name__)


class ExportService:
    """High-level export service for generating documents from translated works.
    
    Supports multiple export formats via ExporterRegistry.
    """

    def export(
        self,
        format: str,
        *,
        novel_id: str,
        chapters: list[dict[str, Any]],
        output_path: str,
        **options: Any,
    ) -> str:
        """Export chapters to file in specified format.
        
        Args:
            format: Export format ('epub', 'pdf', 'html', etc.)
            novel_id: Novel identifier
            chapters: List of chapter data dicts (must include 'text' key)
            output_path: Where to save the exported file
            **options: Format-specific options
            
        Returns:
            Path to generated file
            
        Raises:
            KeyError: If format not registered
        """
        logger.info(f"Exporting {len(chapters)} chapters to {format} format from {novel_id}")
        exporter = get_exporter(format)
        logger.debug(f"Using exporter: {exporter.__class__.__name__}")
        result = exporter.export(
            novel_id=novel_id,
            chapters=chapters,
            output_path=output_path,
            **options
        )
        logger.info(f"Export complete: {result}")
        return result

    def export_epub(
        self,
        *,
        novel_id: str,
        chapters: list[dict[str, Any]],
        output_path: str,
    ) -> str:
        """Export chapters to EPUB format."""
        return self.export("epub", novel_id=novel_id, chapters=chapters, output_path=output_path)

    def export_pdf(
        self,
        *,
        novel_id: str,
        chapters: list[dict[str, Any]],
        output_path: str,
    ) -> str:
        """Export chapters to PDF format."""
        return self.export("pdf", novel_id=novel_id, chapters=chapters, output_path=output_path)

    def export_html(
        self,
        *,
        novel_id: str,
        chapters: list[dict[str, Any]],
        output_path: str,
    ) -> str:
        """Export chapters to HTML format."""
        return self.export("html", novel_id=novel_id, chapters=chapters, output_path=output_path)

    def export_markdown(
        self,
        *,
        novel_id: str,
        chapters: list[dict[str, Any]],
        output_path: str,
    ) -> str:
        """Export chapters to Markdown format."""
        return self.export("md", novel_id=novel_id, chapters=chapters, output_path=output_path)
