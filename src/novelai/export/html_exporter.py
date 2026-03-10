"""Simple HTML exporter for quick previews."""

from __future__ import annotations

from html import escape
from pathlib import Path
from typing import Any, Sequence

from novelai.export.base_exporter import BaseExporter


class HTMLExporter(BaseExporter):
    """Export translated chapters as a single self-contained HTML file."""

    def export(self, *, novel_id: str, chapters: Sequence[dict[str, Any]], output_path: str) -> str:
        output = Path(output_path)
        output.parent.mkdir(parents=True, exist_ok=True)

        parts: list[str] = [
            "<!DOCTYPE html>",
            '<html lang="en">',
            "<head>",
            f"  <title>{escape(novel_id)}</title>",
            '  <meta charset="utf-8"/>',
            "  <style>",
            "    body{font-family:serif;max-width:48em;margin:2em auto;padding:0 1em;line-height:1.7;color:#222}",
            "    h1{border-bottom:2px solid #ccc;padding-bottom:.3em}",
            "    h2{margin-top:2em;color:#444}",
            "    .chapter{margin-bottom:3em}",
            "    figure{margin:1em 0;text-align:center}",
            "    img{max-width:100%;height:auto}",
            "    figcaption{font-size:0.9em;color:#555}",
            "  </style>",
            "</head>",
            "<body>",
            f"<h1>{escape(novel_id)}</h1>",
        ]

        for index, chapter in enumerate(chapters, start=1):
            title = chapter.get("title")
            text = chapter.get("text")
            safe_title = escape(title) if isinstance(title, str) and title.strip() else f"Chapter {index}"
            body_html = self._render_body(text if isinstance(text, str) else "")

            parts.append(f'<div class="chapter">')
            parts.append(f"<h2>{safe_title}</h2>")
            parts.append(body_html)
            parts.append("</div>")

        parts.append("</body>")
        parts.append("</html>")

        output.write_text("\n".join(parts), encoding="utf-8")
        return str(output)

    @staticmethod
    def _render_body(text: str) -> str:
        paragraphs = text.replace("\r\n", "\n").replace("\r", "\n").split("\n\n")
        rendered: list[str] = []
        for paragraph in paragraphs:
            stripped = paragraph.strip()
            if not stripped:
                continue
            lines = stripped.split("\n")
            inner = "<br/>".join(escape(line) for line in lines)
            rendered.append(f"<p>{inner}</p>")
        return "\n".join(rendered)
