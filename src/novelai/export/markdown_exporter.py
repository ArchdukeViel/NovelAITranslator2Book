"""Markdown exporter for plain-text previews and documentation."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Sequence

from novelai.export.base_exporter import BaseExporter


class MarkdownExporter(BaseExporter):
    """Export translated chapters as a single Markdown file."""

    def export(self, *, novel_id: str, chapters: Sequence[dict[str, Any]], output_path: str) -> str:
        output = Path(output_path)
        output.parent.mkdir(parents=True, exist_ok=True)

        lines: list[str] = [f"# {novel_id}", ""]

        for index, chapter in enumerate(chapters, start=1):
            title = chapter.get("title")
            text = chapter.get("text")
            heading = title if isinstance(title, str) and title.strip() else f"Chapter {index}"
            body = text if isinstance(text, str) else ""

            lines.append(f"## {heading}")
            lines.append("")
            lines.append(body.strip())
            lines.append("")
            lines.append("---")
            lines.append("")

        output.write_text("\n".join(lines), encoding="utf-8")
        return str(output)
