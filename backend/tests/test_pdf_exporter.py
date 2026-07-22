"""Tests for PDF export deprecation (DEBT-007).

PDF export is deprecated and no exporter implementation exists.
``ExportService.export("pdf", ...)`` and
``ExportService.export_pdf()`` raise ``UnsupportedExportFormatError`` with a
safe deprecation message. Historical manifests with ``format: "pdf"`` are
preserved (no manifest rewriting). Non-PDF exporters remain registered.
"""

from __future__ import annotations

import pytest

from novelai.export.registry import available_exporters
from novelai.runtime.bootstrap import bootstrap
from novelai.services.export_service import ExportService, UnsupportedExportFormatError


class TestPDFNotRegistered:
    """After bootstrap, PDF is not in the export registry."""

    def test_pdf_not_in_available_exporters(self) -> None:
        bootstrap()
        available = available_exporters()
        assert "pdf" not in available

    def test_non_pdf_exporters_remain_registered(self) -> None:
        bootstrap()
        available = available_exporters()
        assert "epub" in available
        assert "html" in available
        assert "md" in available


class TestExportServicePDFRejection:
    """ExportService rejects PDF with a controlled UnsupportedExportFormatError."""

    def test_export_pdf_raises_unsupported(self) -> None:
        service = ExportService()
        with pytest.raises(UnsupportedExportFormatError, match="deprecated") as exc_info:
            service.export(
                "pdf",
                novel_id="n1",
                chapters=[{"title": "Ch1", "text": "Hello"}],
                output_path="/tmp/out.pdf",
            )
        assert exc_info.value.format == "pdf"
        assert exc_info.value.error_code == "deprecated_export_format"
        assert "deprecated" in exc_info.value.detail.lower()

    def test_export_pdf_method_raises_unsupported(self) -> None:
        service = ExportService()
        with pytest.raises(UnsupportedExportFormatError, match="deprecated") as exc_info:
            service.export_pdf(
                novel_id="n1",
                chapters=[{"title": "Ch1", "text": "Hello"}],
                output_path="/tmp/out.pdf",
            )
        assert exc_info.value.format == "pdf"

    def test_export_pdf_case_insensitive(self) -> None:
        service = ExportService()
        with pytest.raises(UnsupportedExportFormatError, match="deprecated"):
            service.export(
                "PDF",
                novel_id="n1",
                chapters=[{"title": "Ch1", "text": "Hello"}],
                output_path="/tmp/out.pdf",
            )

    def test_export_unknown_format_raises_unsupported(self) -> None:
        service = ExportService()
        with pytest.raises(UnsupportedExportFormatError, match="not supported") as exc_info:
            service.export(
                "xyz",
                novel_id="n1",
                chapters=[{"title": "Ch1", "text": "Hello"}],
                output_path="/tmp/out.xyz",
            )
        assert exc_info.value.format == "xyz"
        assert exc_info.value.error_code == "unsupported_export_format"

    def test_no_raw_key_error_reaches_caller(self) -> None:
        """Ensure KeyError does not escape from ExportService.export for any format."""
        service = ExportService()
        with pytest.raises(UnsupportedExportFormatError):
            service.export(
                "nonexistent",
                novel_id="n1",
                chapters=[{"title": "Ch1", "text": "Hello"}],
                output_path="/tmp/out.xyz",
            )

    def test_no_raw_not_implemented_error_reaches_caller_for_pdf(self) -> None:
        """Ensure NotImplementedError does not escape from ExportService for PDF."""
        service = ExportService()
        with pytest.raises(UnsupportedExportFormatError):
            service.export(
                "pdf",
                novel_id="n1",
                chapters=[{"title": "Ch1", "text": "Hello"}],
                output_path="/tmp/out.pdf",
            )
