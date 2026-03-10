from __future__ import annotations

import shutil
from uuid import uuid4
from zipfile import ZIP_STORED, ZipFile

from novelai.export.epub_exporter import EPUBExporter
from tests.conftest import TESTS_TMP_ROOT


def test_epub_exporter_embeds_chapter_images_and_references_them() -> None:
    TESTS_TMP_ROOT.mkdir(parents=True, exist_ok=True)
    temp_dir = TESTS_TMP_ROOT / f"epub_export_{uuid4().hex}"
    temp_dir.mkdir(parents=True, exist_ok=False)

    image_path = temp_dir / "scene.png"
    image_path.write_bytes(b"\x89PNG\r\n\x1a\nfakepng")

    exporter = EPUBExporter()
    output_path = temp_dir / "illustrated.epub"

    try:
        result = exporter.export(
            novel_id="novel-1",
            chapters=[
                {
                    "title": "Chapter 1",
                    "text": "Intro\n\n[Image: Scene illustration]\n\nOutro",
                    "images": [
                        {
                            "placeholder": "[Image: Scene illustration]",
                            "alt": "Scene illustration",
                            "asset_path": str(image_path),
                            "content_type": "image/png",
                        }
                    ],
                }
            ],
            output_path=str(output_path),
        )

        assert result == str(output_path)
        assert output_path.exists()

        with ZipFile(output_path) as epub:
            assert epub.getinfo("mimetype").compress_type == ZIP_STORED
            assert "META-INF/container.xml" in epub.namelist()
            assert "OEBPS/content.opf" in epub.namelist()
            assert "OEBPS/nav.xhtml" in epub.namelist()
            assert "OEBPS/chapters/chapter_0001.xhtml" in epub.namelist()
            assert "OEBPS/images/chapter_0001_0001.png" in epub.namelist()

            chapter_document = epub.read("OEBPS/chapters/chapter_0001.xhtml").decode("utf-8")
            assert "../images/chapter_0001_0001.png" in chapter_document
            assert "Scene illustration" in chapter_document
            assert "<img " in chapter_document
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def test_epub_exporter_converts_separator_to_hr() -> None:
    """Separator characters like ーーーーー should become <hr/> in EPUB."""
    exporter = EPUBExporter()
    chapter = {"title": "Ch1", "text": "Before\n\nーーーーー\n\nAfter"}
    prepared = exporter._prepare_chapter(1, chapter)
    assert "<hr/>" in prepared["xhtml"]
    assert "ーーーーー" not in prepared["xhtml"]


def test_epub_exporter_splits_japanese_chapter_title() -> None:
    """第1話　タイトル should render chapter number and title on separate lines."""
    exporter = EPUBExporter()
    chapter = {"title": "第1話　結婚式＆ウェディングドレス編　前編", "text": "Hello"}
    prepared = exporter._prepare_chapter(1, chapter)
    assert "第1話<br/>" in prepared["xhtml"]
    assert "結婚式" in prepared["xhtml"]
