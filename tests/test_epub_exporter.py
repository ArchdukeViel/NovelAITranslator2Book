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
