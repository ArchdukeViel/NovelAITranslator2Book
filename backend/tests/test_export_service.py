"""Tests for the export registry and ExportService."""

from __future__ import annotations

import shutil
from pathlib import Path
from uuid import uuid4

import pytest

from novelai.export.base_exporter import BaseExporter
from novelai.export.registry import (
    _EXPORTER_REGISTRY,
    available_exporters,
    get_exporter,
    register_exporter,
)
from novelai.services.export_service import ExportService

_TMP = Path(__file__).resolve().parent / ".tmp" / "export_svc"


class _StubExporter(BaseExporter):
    def export(self, *, novel_id, chapters, output_path, **options):  # type: ignore[override]
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        Path(output_path).write_text(f"stub:{novel_id}", encoding="utf-8")
        return output_path


class TestExportRegistry:
    def setup_method(self) -> None:
        self._saved = dict(_EXPORTER_REGISTRY)

    def teardown_method(self) -> None:
        _EXPORTER_REGISTRY.clear()
        _EXPORTER_REGISTRY.update(self._saved)

    def test_register_and_get(self) -> None:
        register_exporter("stub", _StubExporter)
        exp = get_exporter("stub")
        assert isinstance(exp, _StubExporter)

    def test_get_raises_for_unknown(self) -> None:
        with pytest.raises(KeyError, match="No exporter"):
            get_exporter("nonexistent")

    def test_available_exporters(self) -> None:
        register_exporter("fmt_a", _StubExporter)
        assert "fmt_a" in available_exporters()


class TestExportService:
    def setup_method(self) -> None:
        self._saved = dict(_EXPORTER_REGISTRY)
        register_exporter("stub", _StubExporter)

    def teardown_method(self) -> None:
        _EXPORTER_REGISTRY.clear()
        _EXPORTER_REGISTRY.update(self._saved)

    def test_export_delegates_to_registry(self) -> None:
        svc = ExportService()
        out_dir = _TMP / uuid4().hex[:8]
        out_dir.mkdir(parents=True, exist_ok=True)
        result = svc.export(
            "stub",
            novel_id="n1",
            chapters=[{"text": "hi"}],
            output_path=str(out_dir / "out.txt"),
        )
        assert Path(result).read_text(encoding="utf-8") == "stub:n1"
        shutil.rmtree(out_dir, ignore_errors=True)

    def test_export_raises_for_unknown_format(self) -> None:
        svc = ExportService()
        with pytest.raises(KeyError):
            svc.export("nope", novel_id="x", chapters=[], output_path="x")
