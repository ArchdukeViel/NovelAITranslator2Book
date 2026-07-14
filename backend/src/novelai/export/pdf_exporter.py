from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from novelai.export.base_exporter import BaseExporter


class PDFExporter(BaseExporter):
    """Deprecated PDF exporter stub.

    PDF export is deprecated (DEBT-007). This class is retained for historical
    reference and potential future reintroduction after an approved renderer,
    font policy, security review, and real export tests. It is **not**
    registered in the export registry (see ``runtime.bootstrap.bootstrap_exporters``).

    Calling ``ExportService.export("pdf", ...)`` or ``ExportService.export_pdf()``
    raises ``UnsupportedExportFormatError`` with a safe deprecation message
    instead of a raw ``KeyError`` or ``NotImplementedError``.

    Historical manifests that already record ``format: "pdf"`` are preserved
    and remain readable by the manifest service; no manifest rewriting occurs.
    """

    def export(self, *, novel_id: str, chapters: Sequence[dict[str, Any]], output_path: str, **options: Any) -> str:
        raise NotImplementedError(
            "PDF export is deprecated and not available in this deployment. "
            "This stub is retained for historical reference only."
        )
