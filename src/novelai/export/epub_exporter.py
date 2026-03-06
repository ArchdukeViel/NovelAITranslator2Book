from __future__ import annotations

from pathlib import Path
from typing import Any, Sequence

from novelai.export.base_exporter import BaseExporter


class EPUBExporter(BaseExporter):
    """Minimal EPUB exporter implementation."""

    def export(self, *, novel_id: str, chapters: Sequence[dict[str, Any]], output_path: str) -> str:
        """Create a simple EPUB file containing all chapters."""
        # NOTE: This is a placeholder implementation.
        # Replace with a library like ebooklib or mkdocs-epub for real EPUB generation.
        output = Path(output_path)
        output.parent.mkdir(parents=True, exist_ok=True)
        content = [f"# {novel_id}\n"]
        for chapter in chapters:
            content.append(f"## {chapter.get('title', 'Chapter')}\n")
            content.append(chapter.get("text", ""))
            content.append("\n\n")
        output.write_text("\n".join(content), encoding="utf-8")
        return str(output)
