from __future__ import annotations

import re
from typing import Any


def _extract_ocr_candidate_text(images: list[dict[str, Any]]) -> str | None:
    snippets: list[str] = []
    seen: set[str] = set()
    ordered = sorted(
        [item for item in images if isinstance(item, dict)],
        key=lambda item: int(item.get("index", 0)),
    )

    for image in ordered:
        for field in ("ocr_text", "alt", "title", "caption", "placeholder", "text"):
            value = image.get(field)
            if not isinstance(value, str):
                continue
            cleaned = re.sub(r"\s+", " ", value).strip()
            if not cleaned:
                continue
            key = cleaned.casefold()
            if key in seen:
                continue
            seen.add(key)
            snippets.append(cleaned)

    if not snippets:
        return None

    candidate = "\n".join(f"- {snippet}" for snippet in snippets)
    if len(candidate) > 4000:
        return candidate[:3997] + "..."
    return candidate


async def ingest_ocr_candidates(
    self: Any,
    novel_id: str,
    chapters: str = "all",
    *,
    mark_required: bool = True,
    overwrite: bool = False,
) -> dict[str, Any]:
    """Build OCR candidate text from stored image manifests and persist chapter media state."""
    meta = self.storage.load_metadata(novel_id)
    if not meta:
        raise RuntimeError("Metadata not found; run scrape-metadata first.")

    selected_numbers = self._selected_chapter_numbers(meta, chapters)
    summary: dict[str, Any] = {
        "novel_id": novel_id,
        "selected": len(selected_numbers),
        "updated": 0,
        "skipped_no_images": 0,
        "skipped_reviewed": 0,
        "failed": [],
    }

    for chapter_num in selected_numbers:
        chapter_id = str(chapter_num)
        chapter = self.storage.load_chapter(novel_id, chapter_id)
        if chapter is None:
            summary["failed"].append(
                {
                    "chapter_id": chapter_id,
                    "code": "missing_chapter",
                    "reason": "Raw chapter is missing; scrape chapters first.",
                }
            )
            continue

        media_state = self.storage.load_chapter_media_state(novel_id, chapter_id) or {}
        existing_status = str(media_state.get("ocr_status") or "pending").strip().lower()
        if existing_status == "reviewed" and not overwrite:
            summary["skipped_reviewed"] += 1
            continue

        images = chapter.get("images") if isinstance(chapter.get("images"), list) else []
        if not images:
            summary["skipped_no_images"] += 1
            self.storage.save_chapter_media_state(
                novel_id,
                chapter_id,
                ocr_required=False,
                ocr_status="skipped",
            )
            continue

        candidate = self._extract_ocr_candidate_text(images)
        if not candidate:
            summary["failed"].append(
                {
                    "chapter_id": chapter_id,
                    "code": "missing_candidate",
                    "reason": "No OCR candidate text could be extracted from image metadata.",
                }
            )
            self.storage.save_chapter_media_state(
                novel_id,
                chapter_id,
                ocr_required=mark_required,
                ocr_status="failed",
            )
            continue

        existing_text = media_state.get("ocr_text") if isinstance(media_state.get("ocr_text"), str) else None
        self.storage.save_chapter_media_state(
            novel_id,
            chapter_id,
            ocr_required=mark_required,
            ocr_text=candidate if (overwrite or not existing_text) else existing_text,
            ocr_status="pending" if mark_required else "skipped",
        )
        summary["updated"] += 1

    return summary

