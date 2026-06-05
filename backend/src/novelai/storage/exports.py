from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from novelai.core.security import validate_storage_identifier

logger = logging.getLogger(__name__)

def build_export_path(
    self: Any,
    novel_id: str,
    export_format: str,
    output_dir: str | Path | None = None,
) -> Path:
    """Resolve where an export should be written."""
    safe_novel_id = validate_storage_identifier(str(novel_id), "novel_id")
    safe_export_format = validate_storage_identifier(str(export_format), "export_format")
    if output_dir is not None:
        custom_dir = Path(output_dir).expanduser()
        custom_dir.mkdir(parents=True, exist_ok=True)
        return custom_dir / f"{safe_novel_id}.{safe_export_format}"

    novel_dir = self._novel_dir(safe_novel_id)
    novel_dir.mkdir(parents=True, exist_ok=True)
    return novel_dir / f"full_novel.{safe_export_format}"


def get_chapters_ready_for_export(self: Any, novel_id: str) -> list[str]:
    """Get all chapters that have been translated (ready for export)."""
    from novelai.core.chapter_state import ChapterState

    results = (
        self.query_chapters(novel_id)
        .by_states([ChapterState.TRANSLATED, ChapterState.EXPORTED])
        .sort_by("updated")
        .execute()
    )
    logger.info(f"Found {len(results)} chapters ready for export in {novel_id}")
    return [r.chapter_id for r in results]
