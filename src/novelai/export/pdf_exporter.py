from __future__ import annotations

from typing import Any, Sequence

from novelai.export.base_exporter import BaseExporter


class PDFExporter(BaseExporter):
    """PDF exporter placeholder.

    Not yet implemented. Requires a PDF generation library such as
    reportlab or weasyprint to produce real PDF output.
    """

    def export(self, *, novel_id: str, chapters: Sequence[dict[str, Any]], output_path: str, **options: Any) -> str:
        raise NotImplementedError(
            "PDF export is not yet available. "
            "Install a PDF library (e.g. reportlab) and implement PDFExporter.export()."
        )
