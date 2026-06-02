from __future__ import annotations

import mimetypes
import re
from collections.abc import Sequence
from html import escape
from pathlib import Path
from typing import Any
from uuid import uuid4
from zipfile import ZIP_DEFLATED, ZIP_STORED, ZipFile

from novelai.export.base_exporter import BaseExporter

# Paragraph consisting entirely of repeated separator characters.
_SEPARATOR_RE = re.compile(
    r"^[\-\u30FC\u2500\u2015\u2014\uff0d*\uff0a=\uff1d]{3,}$",
)

# Japanese chapter number prefix: 第N話, 第N章, etc.
_CHAPTER_NUM_RE = re.compile(
    r"^(第[\d一二三四五六七八九十百千]+[話章部回節編幕])([\s\u3000]+)(.+)$",
)


class EPUBExporter(BaseExporter):
    """Minimal EPUB 3 exporter with optional embedded chapter images."""

    def export(self, *, novel_id: str, chapters: Sequence[dict[str, Any]], output_path: str, **options: Any) -> str:
        output = Path(output_path)
        output.parent.mkdir(parents=True, exist_ok=True)

        book_title = options.get("title") or novel_id
        book_author = options.get("author") or ""
        include_toc = bool(options.get("include_toc", False))

        prepared_chapters = [self._prepare_chapter(index, chapter) for index, chapter in enumerate(chapters, start=1)]

        front_matter: list[dict[str, Any]] = []

        # Title page
        title_page = {
            "id": "title_page",
            "href": "title.xhtml",
            "xhtml": self._title_page_document(book_title, book_author),
        }
        front_matter.append(title_page)

        # Optional inline TOC page
        if include_toc:
            toc_page = {
                "id": "toc_page",
                "href": "toc.xhtml",
                "xhtml": self._toc_page_document(book_title, prepared_chapters),
            }
            front_matter.append(toc_page)

        with ZipFile(output, "w") as epub:
            epub.writestr("mimetype", "application/epub+zip", compress_type=ZIP_STORED)
            epub.writestr("META-INF/container.xml", self._container_xml(), compress_type=ZIP_DEFLATED)
            epub.writestr(
                "OEBPS/nav.xhtml",
                self._navigation_document(book_title, prepared_chapters),
                compress_type=ZIP_DEFLATED,
            )
            epub.writestr(
                "OEBPS/content.opf",
                self._package_document(book_title, prepared_chapters, front_matter=front_matter, author=book_author),
                compress_type=ZIP_DEFLATED,
            )

            for page in front_matter:
                epub.writestr(f"OEBPS/{page['href']}", page["xhtml"], compress_type=ZIP_DEFLATED)

            for chapter in prepared_chapters:
                epub.writestr(f"OEBPS/{chapter['href']}", chapter["xhtml"], compress_type=ZIP_DEFLATED)
                for image in chapter["images"]:
                    asset_path = image.get("asset_path")
                    if not isinstance(asset_path, Path) or not asset_path.exists():
                        continue
                    epub.write(asset_path, f"OEBPS/{image['epub_href']}", compress_type=ZIP_DEFLATED)

        return str(output)

    @staticmethod
    def _container_xml() -> str:
        return """<?xml version="1.0" encoding="UTF-8"?>
<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
  <rootfiles>
    <rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/>
  </rootfiles>
</container>
"""

    def _prepare_chapter(self, index: int, chapter: dict[str, Any]) -> dict[str, Any]:
        title = chapter.get("title")
        text = chapter.get("text")
        normalized_title = title if isinstance(title, str) and title.strip() else f"Chapter {index}"
        normalized_text = text if isinstance(text, str) else ""
        images = self._prepare_images(index, chapter.get("images"))
        xhtml = self._chapter_document(normalized_title, normalized_text, images)

        return {
            "id": f"chapter_{index:04d}",
            "href": f"chapters/chapter_{index:04d}.xhtml",
            "title": normalized_title,
            "xhtml": xhtml,
            "images": images,
        }

    def _prepare_images(self, chapter_index: int, raw_images: Any) -> list[dict[str, Any]]:
        prepared: list[dict[str, Any]] = []
        if not isinstance(raw_images, list):
            return prepared

        for image_index, raw_image in enumerate(raw_images, start=1):
            if not isinstance(raw_image, dict):
                continue
            asset_path_value = raw_image.get("asset_path")
            asset_path = Path(asset_path_value) if isinstance(asset_path_value, str) and asset_path_value else None
            if asset_path is None or not asset_path.exists():
                continue

            media_type = self._image_media_type(asset_path, raw_image.get("content_type"))
            suffix = asset_path.suffix.lower() or mimetypes.guess_extension(media_type) or ".bin"
            prepared.append(
                {
                    "id": f"image_{chapter_index:04d}_{image_index:04d}",
                    "placeholder": raw_image.get("placeholder"),
                    "alt": self._image_alt(raw_image),
                    "asset_path": asset_path,
                    "media_type": media_type,
                    "epub_href": f"images/chapter_{chapter_index:04d}_{image_index:04d}{suffix}",
                }
            )

        return prepared

    @staticmethod
    def _image_alt(image: dict[str, Any]) -> str:
        for key in ("alt", "title", "placeholder"):
            value = image.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        return "Image"

    @staticmethod
    def _image_media_type(asset_path: Path, raw_content_type: Any) -> str:
        if isinstance(raw_content_type, str) and raw_content_type.strip():
            return raw_content_type.split(";", 1)[0].strip()
        guessed, _ = mimetypes.guess_type(asset_path.name)
        return guessed or "application/octet-stream"

    @staticmethod
    def _format_title_html(title: str) -> str:
        """Split a Japanese chapter number prefix onto its own line."""
        match = _CHAPTER_NUM_RE.match(title)
        if match:
            num = escape(match.group(1))
            rest = escape(match.group(3))
            return f'{num}<br/>{rest}'
        return escape(title)

    def _chapter_document(self, title: str, text: str, images: list[dict[str, Any]]) -> str:
        body = self._render_chapter_body(text, images)
        title_html = self._format_title_html(title)
        escaped_title = escape(title)
        return (
            "<?xml version=\"1.0\" encoding=\"utf-8\"?>\n"
            "<!DOCTYPE html>\n"
            "<html xmlns=\"http://www.w3.org/1999/xhtml\" xml:lang=\"ja\">\n"
            "<head>\n"
            f"  <title>{escaped_title}</title>\n"
            "  <meta charset=\"utf-8\"/>\n"
            "  <style>"
            "body{font-family:\"Noto Serif CJK JP\",\"Hiragino Mincho Pro\",\"Yu Mincho\",\"MS Mincho\",serif;"
            "font-size:1em;line-height:1.8;margin:1em;}"
            "h1{text-align:center;line-height:1.4;font-size:1.4em;margin-bottom:1em;}"
            "p{margin:0.6em 0;text-indent:1em;}"
            "hr{border:none;border-top:1px solid #ccc;margin:1.5em 0;}"
            "figure{margin:1em 0;text-align:center;}"
            "img{max-width:100%;height:auto;}figcaption{font-size:0.9em;color:#555;}"
            "</style>\n"
            "</head>\n"
            "<body>\n"
            f"<h1>{title_html}</h1>\n"
            f"{body}\n"
            "</body>\n"
            "</html>\n"
        )

    def _render_chapter_body(self, text: str, images: list[dict[str, Any]]) -> str:
        paragraphs = text.replace("\r\n", "\n").replace("\r", "\n").split("\n\n")
        rendered: list[str] = []
        used_indexes: set[int] = set()

        for paragraph in paragraphs:
            stripped = paragraph.strip()
            if not stripped:
                continue
            if _SEPARATOR_RE.match(stripped):
                rendered.append("<hr/>")
                continue
            rendered.append(self._render_paragraph(paragraph, images, used_indexes))

        for index, image in enumerate(images):
            if index in used_indexes:
                continue
            rendered.append(self._image_figure(image))

        return "\n".join(part for part in rendered if part.strip())

    def _render_paragraph(self, paragraph: str, images: list[dict[str, Any]], used_indexes: set[int]) -> str:
        stripped = paragraph.strip()
        for index, image in enumerate(images):
            placeholder = image.get("placeholder")
            if index in used_indexes or not isinstance(placeholder, str):
                continue
            if stripped == placeholder.strip():
                used_indexes.add(index)
                return self._image_figure(image)

        rendered = self._escape_text_with_breaks(paragraph)
        for index, image in enumerate(images):
            placeholder = image.get("placeholder")
            if index in used_indexes or not isinstance(placeholder, str) or not placeholder:
                continue
            escaped_placeholder = escape(placeholder)
            if escaped_placeholder in rendered:
                rendered = rendered.replace(escaped_placeholder, self._inline_image(image), 1)
                used_indexes.add(index)

        return f"<p>{rendered}</p>"

    @staticmethod
    def _escape_text_with_breaks(text: str) -> str:
        return "<br/>".join(escape(line) for line in text.split("\n"))

    @staticmethod
    def _relative_image_href(image: dict[str, Any]) -> str:
        epub_href = str(image["epub_href"])
        return f"../{epub_href}"

    def _inline_image(self, image: dict[str, Any]) -> str:
        return (
            f"<img src=\"{escape(self._relative_image_href(image))}\" "
            f"alt=\"{escape(str(image['alt']))}\"/>"
        )

    def _image_figure(self, image: dict[str, Any]) -> str:
        alt = str(image["alt"])
        figure = [
            "<figure>",
            f"<img src=\"{escape(self._relative_image_href(image))}\" alt=\"{escape(alt)}\"/>",
        ]
        if alt and alt != "Image":
            figure.append(f"<figcaption>{escape(alt)}</figcaption>")
        figure.append("</figure>")
        return "".join(figure)

    def _navigation_document(self, novel_id: str, chapters: list[dict[str, Any]]) -> str:
        nav_items = "\n".join(
            f"<li><a href=\"{escape(chapter['href'])}\">{escape(str(chapter['title']))}</a></li>"
            for chapter in chapters
        )
        return (
            "<?xml version=\"1.0\" encoding=\"utf-8\"?>\n"
            "<!DOCTYPE html>\n"
            "<html xmlns=\"http://www.w3.org/1999/xhtml\" xmlns:epub=\"http://www.idpf.org/2007/ops\">\n"
            "<head>\n"
            f"  <title>{escape(novel_id)}</title>\n"
            "  <meta charset=\"utf-8\"/>\n"
            "</head>\n"
            "<body>\n"
            "  <nav epub:type=\"toc\" id=\"toc\">\n"
            f"    <h1>{escape(novel_id)}</h1>\n"
            "    <ol>\n"
            f"{nav_items}\n"
            "    </ol>\n"
            "  </nav>\n"
            "</body>\n"
            "</html>\n"
        )

    def _title_page_document(self, title: str, author: str) -> str:
        author_html = f"\n<p class=\"author\">{escape(author)}</p>" if author else ""
        return (
            "<?xml version=\"1.0\" encoding=\"utf-8\"?>\n"
            "<!DOCTYPE html>\n"
            "<html xmlns=\"http://www.w3.org/1999/xhtml\" xml:lang=\"ja\">\n"
            "<head>\n"
            f"  <title>{escape(title)}</title>\n"
            "  <meta charset=\"utf-8\"/>\n"
            "  <style>\n"
            "    body{font-family:\"Noto Serif CJK JP\",\"Hiragino Mincho Pro\",\"Yu Mincho\",\"MS Mincho\",serif;"
            "margin:0;padding:0;display:flex;align-items:center;justify-content:center;min-height:95vh;"
            "text-align:center;}\n"
            "    .title-block{padding:2em;}\n"
            "    h1{font-size:2em;line-height:1.4;margin-bottom:0.5em;}\n"
            "    .author{font-size:1.2em;color:#555;margin-top:1em;}\n"
            "  </style>\n"
            "</head>\n"
            "<body>\n"
            "<div class=\"title-block\">\n"
            f"<h1>{escape(title)}</h1>{author_html}\n"
            "</div>\n"
            "</body>\n"
            "</html>\n"
        )

    @staticmethod
    def _toc_entry_label(index: int, raw_title: str) -> str:
        """Build a TOC label like 'Chapter 1  rest of title'."""
        match = _CHAPTER_NUM_RE.match(raw_title)
        if match:
            return f"Chapter {index}\u3000{match.group(3)}"
        return f"Chapter {index}\u3000{raw_title}"

    def _toc_page_document(self, title: str, chapters: list[dict[str, Any]]) -> str:
        toc_items = "\n".join(
            f"<li><a href=\"{escape(chapter['href'])}\">"
            f"{escape(self._toc_entry_label(index, str(chapter['title'])))}</a></li>"
            for index, chapter in enumerate(chapters, start=1)
        )
        return (
            "<?xml version=\"1.0\" encoding=\"utf-8\"?>\n"
            "<!DOCTYPE html>\n"
            "<html xmlns=\"http://www.w3.org/1999/xhtml\" xml:lang=\"ja\">\n"
            "<head>\n"
            f"  <title>Table of Contents — {escape(title)}</title>\n"
            "  <meta charset=\"utf-8\"/>\n"
            "  <style>\n"
            "    body{font-family:\"Noto Serif CJK JP\",\"Hiragino Mincho Pro\",\"Yu Mincho\",\"MS Mincho\",serif;"
            "font-size:1em;line-height:1.8;margin:1em;}\n"
            "    h1{text-align:center;font-size:1.4em;margin-bottom:1em;}\n"
            "    ul{list-style:none;padding-left:0;}\n"
            "    li{margin:0.4em 0;}\n"
            "    a{color:#1a1a1a;text-decoration:none;}\n"
            "  </style>\n"
            "</head>\n"
            "<body>\n"
            "<h1>Table of Contents</h1>\n"
            "<ul>\n"
            f"{toc_items}\n"
            "</ul>\n"
            "</body>\n"
            "</html>\n"
        )

    def _package_document(
        self,
        novel_id: str,
        chapters: list[dict[str, Any]],
        *,
        front_matter: list[dict[str, Any]] | None = None,
        author: str = "",
    ) -> str:
        manifest_items = [
            '<item id="nav" href="nav.xhtml" media-type="application/xhtml+xml" properties="nav"/>',
        ]
        spine_items = []

        for page in front_matter or []:
            manifest_items.append(
                f'<item id="{page["id"]}" href="{page["href"]}" media-type="application/xhtml+xml"/>'
            )
            spine_items.append(f'<itemref idref="{page["id"]}"/>')

        for chapter in chapters:
            manifest_items.append(
                f'<item id="{chapter["id"]}" href="{chapter["href"]}" media-type="application/xhtml+xml"/>'
            )
            spine_items.append(f'<itemref idref="{chapter["id"]}"/>')
            for image in chapter["images"]:
                manifest_items.append(
                    f'<item id="{image["id"]}" href="{image["epub_href"]}" media-type="{image["media_type"]}"/>'
                )

        manifest_xml = "\n    ".join(manifest_items)
        spine_xml = "\n    ".join(spine_items)
        book_id = f"urn:uuid:{uuid4()}"
        author_xml = f"\n    <dc:creator>{escape(author)}</dc:creator>" if author else ""
        return (
            "<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n"
            "<package xmlns=\"http://www.idpf.org/2007/opf\" version=\"3.0\" unique-identifier=\"bookid\">\n"
            "  <metadata xmlns:dc=\"http://purl.org/dc/elements/1.1/\">\n"
            f"    <dc:identifier id=\"bookid\">{escape(book_id)}</dc:identifier>\n"
            f"    <dc:title>{escape(novel_id)}</dc:title>\n"
            "    <dc:language>ja</dc:language>\n"
            f"{author_xml}"
            "  </metadata>\n"
            "  <manifest>\n"
            f"    {manifest_xml}\n"
            "  </manifest>\n"
            "  <spine>\n"
            f"    {spine_xml}\n"
            "  </spine>\n"
            "</package>\n"
        )
