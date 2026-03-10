"""Simple HTML exporter for quick previews."""

from __future__ import annotations

from collections.abc import Sequence
from html import escape
from pathlib import Path
from typing import Any

from novelai.export.base_exporter import BaseExporter
from novelai.export.epub_exporter import _CHAPTER_NUM_RE, _SEPARATOR_RE


class HTMLExporter(BaseExporter):
    """Export translated chapters as a single self-contained HTML file."""

    def export(self, *, novel_id: str, chapters: Sequence[dict[str, Any]], output_path: str, **options: Any) -> str:
        output = Path(output_path)
        output.parent.mkdir(parents=True, exist_ok=True)

        parts: list[str] = [
            "<!DOCTYPE html>",
            '<html lang="ja">',
            "<head>",
            f"  <title>{escape(novel_id)}</title>",
            '  <meta charset="utf-8"/>',
            "  <style>",
            "    body{font-family:\"Noto Serif CJK JP\",\"Hiragino Mincho Pro\",\"Yu Mincho\",\"MS Mincho\",serif;max-width:48em;margin:2em auto;padding:0 1em;font-size:1em;line-height:1.8;color:#222}",
            "    h1{border-bottom:2px solid #ccc;padding-bottom:.3em}",
            "    h2{margin-top:2em;color:#444;text-align:center;line-height:1.4}",
            "    .chapter{margin-bottom:3em}",
            "    figure{margin:1em 0;text-align:center}",
            "    img{max-width:100%;height:auto}",
            "    figcaption{font-size:0.9em;color:#555}",
            "    hr.separator{border:none;border-top:1px solid #ccc;margin:1.5em 0}",
            "  </style>",
            "</head>",
            "<body>",
            f"<h1>{escape(novel_id)}</h1>",
        ]

        for index, chapter in enumerate(chapters, start=1):
            title = chapter.get("title")
            text = chapter.get("text")
            raw_title = title if isinstance(title, str) and title.strip() else f"Chapter {index}"
            heading_html = self._format_heading(raw_title)
            body_html = self._render_body(text if isinstance(text, str) else "")

            parts.append('<div class="chapter">')
            parts.append(heading_html)
            parts.append(body_html)
            parts.append("</div>")

        parts.append("</body>")
        parts.append("</html>")

        output.write_text("\n".join(parts), encoding="utf-8")
        return str(output)

    @staticmethod
    def _format_heading(title: str) -> str:
        match = _CHAPTER_NUM_RE.match(title)
        if match:
            num = escape(match.group(1))
            rest = escape(match.group(3))
            return f"<h2>{num}<br/>{rest}</h2>"
        return f"<h2>{escape(title)}</h2>"

    @staticmethod
    def _render_body(text: str) -> str:
        paragraphs = text.replace("\r\n", "\n").replace("\r", "\n").split("\n\n")
        rendered: list[str] = []
        for paragraph in paragraphs:
            stripped = paragraph.strip()
            if not stripped:
                continue
            if _SEPARATOR_RE.match(stripped):
                rendered.append('<hr class="separator"/>')
                continue
            lines = stripped.split("\n")
            inner = "<br/>".join(escape(line) for line in lines)
            rendered.append(f"<p>{inner}</p>")
        return "\n".join(rendered)
