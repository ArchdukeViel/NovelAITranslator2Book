from __future__ import annotations

import logging
from typing import Any

from novelai.export.registry import get_exporter

logger = logging.getLogger(__name__)

_PDF_DEPRECATED_MESSAGE = "PDF export is deprecated and is not available in this deployment."


class UnsupportedExportFormatError(Exception):
    """Raised when an export format is not supported or deprecated.

    Carries a safe ``error_code`` and ``detail`` suitable for translation to
    an HTTP error response by the API layer.
    """

    def __init__(self, format: str, detail: str, *, error_code: str = "unsupported_export_format") -> None:
        self.format = format
        self.detail = detail
        self.error_code = error_code
        super().__init__(detail)


class ExportService:
    """High-level export service for generating documents from translated works.

    Supports multiple export formats via ExporterRegistry.

    PDF export is deprecated (DEBT-007). Calling ``export("pdf", ...)`` or
    ``export_pdf()`` raises ``UnsupportedExportFormatError`` with a safe
    deprecation message instead of a raw ``KeyError`` or ``NotImplementedError``.
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
            format: Export format ('epub', 'html', 'md', etc.)
            novel_id: Novel identifier
            chapters: List of chapter data dicts (must include 'text' key)
            output_path: Where to save the exported file
            **options: Format-specific options

        Returns:
            Path to generated file

        Raises:
            UnsupportedExportFormatError: If format is not registered or is deprecated (e.g. 'pdf')
        """
        normalized = format.strip().lower() if isinstance(format, str) else format
        if normalized == "pdf":
            raise UnsupportedExportFormatError(
                "pdf",
                _PDF_DEPRECATED_MESSAGE,
                error_code="deprecated_export_format",
            )
        logger.info(f"Exporting {len(chapters)} chapters to {normalized} format from {novel_id}")
        try:
            exporter = get_exporter(normalized)
        except KeyError:
            raise UnsupportedExportFormatError(
                normalized,
                f"Export format '{normalized}' is not supported.",
                error_code="unsupported_export_format",
            ) from None
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
        """Export chapters to PDF format.

        PDF export is deprecated. This method always raises
        ``UnsupportedExportFormatError`` with a safe deprecation message.
        """
        raise UnsupportedExportFormatError(
            "pdf",
            _PDF_DEPRECATED_MESSAGE,
            error_code="deprecated_export_format",
        )

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
