"""Tests for the Markdown exporter."""

from __future__ import annotations

import shutil
from collections.abc import Iterator
from pathlib import Path
from uuid import uuid4

import pytest

from novelai.export.markdown_exporter import MarkdownExporter

_TMP = Path(__file__).resolve().parent / ".tmp" / "markdown_export"


@pytest.fixture()
def out_dir() -> Iterator[Path]:
    d = _TMP / uuid4().hex[:8]
    d.mkdir(parents=True, exist_ok=True)
    yield d
    shutil.rmtree(d, ignore_errors=True)


def test_export_writes_markdown_with_titles(out_dir: Path) -> None:
    exporter = MarkdownExporter()
    chapters = [
        {"title": "First Chapter", "text": "Hello world."},
        {"title": "Second Chapter", "text": "Goodbye world."},
    ]
    out = exporter.export(
        novel_id="test-novel",
        chapters=chapters,
        output_path=str(out_dir / "output.md"),
    )
    content = Path(out).read_text(encoding="utf-8")
    assert "# test-novel" in content
    assert "## First Chapter" in content
    assert "## Second Chapter" in content
    assert "Hello world." in content
    assert "---" in content


def test_export_uses_default_chapter_heading_when_title_missing(out_dir: Path) -> None:
    exporter = MarkdownExporter()
    chapters = [{"text": "Body only."}]
    out = exporter.export(
        novel_id="novel-x",
        chapters=chapters,
        output_path=str(out_dir / "output.md"),
    )
    content = Path(out).read_text(encoding="utf-8")
    assert "## Chapter 1" in content
    assert "Body only." in content


def test_export_handles_empty_chapters(out_dir: Path) -> None:
    exporter = MarkdownExporter()
    out = exporter.export(
        novel_id="empty",
        chapters=[],
        output_path=str(out_dir / "output.md"),
    )
    content = Path(out).read_text(encoding="utf-8")
    assert "# empty" in content
