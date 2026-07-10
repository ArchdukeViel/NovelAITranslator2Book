from __future__ import annotations

import pytest

from novelai.export.pdf_exporter import PDFExporter


class TestPDFExporter:
    def test_export_raises_not_implemented(self) -> None:
        exporter = PDFExporter()
        with pytest.raises(NotImplementedError, match="PDF export is not yet available"):
            exporter.export(
                novel_id="n1",
                chapters=[{"title": "Ch1", "text": "Hello"}],
                output_path="/tmp/out.pdf",
            )

    def test_export_raises_with_empty_chapters(self) -> None:
        exporter = PDFExporter()
        with pytest.raises(NotImplementedError):
            exporter.export(novel_id="n1", chapters=[], output_path="/tmp/out.pdf")

    def test_export_raises_with_options(self) -> None:
        exporter = PDFExporter()
        with pytest.raises(NotImplementedError):
            exporter.export(
                novel_id="n1",
                chapters=[{"title": "Ch1", "text": "Hello"}],
                output_path="/tmp/out.pdf",
                include_images=True,
                font_size=12,
            )

    def test_is_base_exporter_subclass(self) -> None:
        from novelai.export.base_exporter import BaseExporter

        assert issubclass(PDFExporter, BaseExporter)
