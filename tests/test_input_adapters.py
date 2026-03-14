from __future__ import annotations

import importlib.util
import shutil
from pathlib import Path
from uuid import uuid4
from zipfile import ZipFile

import pytest

from novelai.inputs.cbz import CBZDocumentAdapter
from novelai.inputs.epub import EPUBDocumentAdapter
from novelai.inputs.image_folder import ImageFolderDocumentAdapter
from novelai.inputs.pdf import PDFDocumentAdapter
from novelai.inputs.text import TextDocumentAdapter
from novelai.inputs.web import WebDocumentAdapter
from tests.conftest import TESTS_TMP_ROOT


@pytest.fixture
def temp_root() -> Path:
    TESTS_TMP_ROOT.mkdir(parents=True, exist_ok=True)
    root = TESTS_TMP_ROOT / f"inputs_{uuid4().hex}"
    root.mkdir(parents=True, exist_ok=False)
    yield root
    shutil.rmtree(root, ignore_errors=True)


@pytest.mark.asyncio
async def test_text_adapter_imports_directory_in_sorted_order(temp_root: Path) -> None:
    adapter = TextDocumentAdapter()
    source_dir = temp_root / "text-docs"
    source_dir.mkdir()
    (source_dir / "02_second.txt").write_text("Second chapter", encoding="utf-8")
    (source_dir / "01_first.md").write_text("# First chapter", encoding="utf-8")

    document = await adapter.import_document(source_dir)

    assert document.document_type in {"text", "markdown"}
    assert [unit.unit_id for unit in document.units] == ["1", "2"]
    assert document.units[0].source_ref is not None


def _build_epub(path: Path) -> None:
    with ZipFile(path, "w") as archive:
        archive.writestr(
            "META-INF/container.xml",
            """<?xml version="1.0"?>
            <container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
              <rootfiles>
                <rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/>
              </rootfiles>
            </container>
            """,
        )
        archive.writestr(
            "OEBPS/content.opf",
            """<?xml version="1.0" encoding="utf-8"?>
            <package xmlns="http://www.idpf.org/2007/opf" version="3.0">
              <metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
                <dc:title>Sample EPUB</dc:title>
                <dc:creator>Example Author</dc:creator>
              </metadata>
              <manifest>
                <item id="chap1" href="chap1.xhtml" media-type="application/xhtml+xml"/>
              </manifest>
              <spine>
                <itemref idref="chap1"/>
              </spine>
            </package>
            """,
        )
        archive.writestr(
            "OEBPS/chap1.xhtml",
            """<html xmlns="http://www.w3.org/1999/xhtml"><head><title>Chapter One</title></head>
            <body><h1>Chapter One</h1><p>Hello EPUB world.</p></body></html>""",
        )


@pytest.mark.asyncio
async def test_epub_adapter_reads_spine_documents(temp_root: Path) -> None:
    adapter = EPUBDocumentAdapter()
    epub_path = temp_root / "sample.epub"
    _build_epub(epub_path)

    document = await adapter.import_document(epub_path)

    assert document.title == "Sample EPUB"
    assert document.author == "Example Author"
    assert len(document.units) == 1
    assert "Hello EPUB world." in document.units[0].text


@pytest.mark.asyncio
async def test_image_folder_adapter_marks_units_as_ocr_required(temp_root: Path) -> None:
    adapter = ImageFolderDocumentAdapter()
    image_dir = temp_root / "pages"
    image_dir.mkdir()
    (image_dir / "001.png").write_bytes(b"png")

    document = await adapter.import_document(image_dir)

    assert len(document.units) == 1
    assert document.units[0].ocr_required is True
    assert document.units[0].images[0].content == b"png"


@pytest.mark.asyncio
async def test_cbz_adapter_imports_images(temp_root: Path) -> None:
    adapter = CBZDocumentAdapter()
    cbz_path = temp_root / "comic.cbz"
    with ZipFile(cbz_path, "w") as archive:
        archive.writestr("001.png", b"png-data")
        archive.writestr("002.jpg", b"jpg-data")

    document = await adapter.import_document(cbz_path)

    assert len(document.units) == 2
    assert document.units[1].images[0].content == b"jpg-data"


@pytest.mark.asyncio
async def test_pdf_adapter_requires_optional_dependency_when_missing(temp_root: Path) -> None:
    adapter = PDFDocumentAdapter()
    pdf_path = temp_root / "sample.pdf"
    pdf_path.write_bytes(b"%PDF-1.4")

    if importlib.util.find_spec("pypdf") is None:
        with pytest.raises(RuntimeError, match="pypdf"):
            await adapter.import_document(pdf_path)


class _StubWebSource:
    key = "stub"

    async def fetch_metadata(self, url: str, *, max_chapter: int | None = None) -> dict[str, object]:
        return {
            "title": "Web Title",
            "author": "Web Author",
            "source_language": "Japanese",
            "chapters": [
                {"id": "1", "title": "One", "url": f"{url}/1"},
            ],
        }

    async def fetch_chapter_payload(self, url: str) -> dict[str, object]:
        return {"text": "Body", "images": []}


@pytest.mark.asyncio
async def test_web_adapter_wraps_registered_sources(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("novelai.inputs.web.detect_source", lambda source: "stub")
    monkeypatch.setattr("novelai.inputs.web.get_source", lambda key: _StubWebSource())
    adapter = WebDocumentAdapter()

    document = await adapter.import_document("https://example.com/story")

    assert document.title == "Web Title"
    assert document.units[0].text == "Body"
