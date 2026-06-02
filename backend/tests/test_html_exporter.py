"""Tests for the HTML exporter."""

from __future__ import annotations

import shutil
from collections.abc import Iterator
from pathlib import Path
from uuid import uuid4

import pytest

from novelai.export.html_exporter import HTMLExporter

_TMP = Path(__file__).resolve().parent / ".tmp" / "html_export"


@pytest.fixture()
def out_dir() -> Iterator[Path]:
    d = _TMP / uuid4().hex[:8]
    d.mkdir(parents=True, exist_ok=True)
    yield d
    shutil.rmtree(d, ignore_errors=True)


def test_export_produces_valid_html(out_dir: Path) -> None:
    exporter = HTMLExporter()
    chapters = [{"title": "First", "text": "Content here."}]
    out = exporter.export(
        novel_id="my-novel",
        chapters=chapters,
        output_path=str(out_dir / "out.html"),
    )
    html = Path(out).read_text(encoding="utf-8")
    assert "<!DOCTYPE html>" in html
    assert "<title>my-novel</title>" in html
    assert "<h1>my-novel</h1>" in html
    assert "Content here." in html


def test_export_escapes_html_entities(out_dir: Path) -> None:
    exporter = HTMLExporter()
    chapters = [{"title": "<script>alert(1)</script>", "text": "A & B < C"}]
    out = exporter.export(
        novel_id="safe",
        chapters=chapters,
        output_path=str(out_dir / "out.html"),
    )
    html = Path(out).read_text(encoding="utf-8")
    assert "<script>" not in html
    assert "&lt;script&gt;" in html
    assert "A &amp; B &lt; C" in html


def test_export_default_chapter_heading(out_dir: Path) -> None:
    exporter = HTMLExporter()
    chapters = [{"text": "no title given"}]
    out = exporter.export(
        novel_id="x",
        chapters=chapters,
        output_path=str(out_dir / "out.html"),
    )
    html = Path(out).read_text(encoding="utf-8")
    assert "Chapter 1" in html


def test_export_empty_chapters(out_dir: Path) -> None:
    exporter = HTMLExporter()
    out = exporter.export(
        novel_id="empty",
        chapters=[],
        output_path=str(out_dir / "out.html"),
    )
    html = Path(out).read_text(encoding="utf-8")
    assert "<h1>empty</h1>" in html
