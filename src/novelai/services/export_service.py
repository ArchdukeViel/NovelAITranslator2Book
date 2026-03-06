from __future__ import annotations

from typing import Any

from novelai.export.epub_exporter import EPUBExporter
from novelai.export.pdf_exporter import PDFExporter


class ExportService:
    """High-level export service for generating EPUB/PDF from translated works."""

    def __init__(self) -> None:
        self.epub_exporter = EPUBExporter()
        self.pdf_exporter = PDFExporter()

    def export_epub(self, *, novel_id: str, chapters: list[dict[str, Any]], output_path: str) -> str:
        return self.epub_exporter.export(novel_id=novel_id, chapters=chapters, output_path=output_path)

    def export_pdf(self, *, novel_id: str, chapters: list[dict[str, Any]], output_path: str) -> str:
        return self.pdf_exporter.export(novel_id=novel_id, chapters=chapters, output_path=output_path)
