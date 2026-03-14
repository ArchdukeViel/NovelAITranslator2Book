from __future__ import annotations

from pathlib import Path
from typing import Any

from novelai.services.storage_service import StorageService
from novelai.utils.chapter_selection import is_full_chapter_selection, parse_chapter_selection


def _selected_numbers(chapter_selection: str) -> set[int] | None:
    if is_full_chapter_selection(chapter_selection):
        return None
    return {spec.chapter for spec in parse_chapter_selection(chapter_selection)}


def build_export_plan(
    storage: StorageService,
    novel_id: str,
    *,
    chapter_selection: str = "full",
    language: str = "translated",
) -> dict[str, Any]:
    meta = storage.load_metadata(novel_id)
    if not meta:
        raise ValueError("Metadata not found; run scrape/import first.")

    selected_numbers = _selected_numbers(chapter_selection)
    use_source = language.strip().lower() == "source"
    ready: list[dict[str, Any]] = []
    blocked: list[dict[str, str]] = []
    selected_count = 0

    for chapter in meta.get("chapters", []):
        if not isinstance(chapter, dict):
            continue
        chapter_id = str(chapter.get("id"))
        if selected_numbers is not None:
            if not chapter_id.isdigit() or int(chapter_id) not in selected_numbers:
                continue
        selected_count += 1

        chapter_title = chapter.get("translated_title") if not use_source else chapter.get("title")
        normalized_title = chapter_title if isinstance(chapter_title, str) and chapter_title.strip() else f"Chapter {chapter_id}"

        text: str | None = None
        reason: str | None = None
        if use_source:
            raw_data = storage.load_chapter(novel_id, chapter_id)
            raw_text = raw_data.get("text") if isinstance(raw_data, dict) else None
            if not isinstance(raw_text, str) or not raw_text.strip():
                reason = "Source text missing."
            else:
                text = raw_text
        else:
            media_state = storage.load_chapter_media_state(novel_id, chapter_id) or {}
            ocr_required = bool(media_state.get("ocr_required"))
            ocr_status = str(media_state.get("ocr_status") or "").strip().lower()
            if ocr_required and ocr_status != "reviewed":
                reason = "OCR review pending."
            translated = storage.load_translated_chapter(novel_id, chapter_id)
            translated_text = translated.get("text") if isinstance(translated, dict) else None
            if reason is None and (not isinstance(translated_text, str) or not translated_text.strip()):
                reason = "Translated text missing."
            elif reason is None:
                text = translated_text

        if reason is not None:
            blocked.append(
                {
                    "chapter_id": chapter_id,
                    "title": normalized_title,
                    "reason": reason,
                }
            )
            continue

        ready.append(
            {
                "chapter_id": chapter_id,
                "title": normalized_title,
                "text": text,
                "images": storage.load_chapter_export_images(novel_id, chapter_id),
            }
        )

    return {
        "ready": ready,
        "blocked": blocked,
        "selected_count": selected_count,
    }


def collect_export_chapters(
    storage: StorageService,
    novel_id: str,
    *,
    chapter_selection: str = "full",
    language: str = "translated",
) -> list[dict[str, Any]]:
    plan = build_export_plan(
        storage,
        novel_id,
        chapter_selection=chapter_selection,
        language=language,
    )
    chapters = [
        {
            "title": row["title"],
            "text": row["text"],
            "images": row["images"],
        }
        for row in plan["ready"]
    ]

    if not chapters:
        raise ValueError(f"No {language} chapters available for export.")
    return chapters


def build_export_output_path(
    storage: StorageService,
    novel_id: str,
    export_format: str,
    output_dir: str | None,
    chapter_selection: str,
    language: str,
) -> str:
    base_path = Path(storage.build_export_path(novel_id, export_format, output_dir or None))
    name = base_path.stem
    if language == "source":
        name = f"{name}_source"
    if not is_full_chapter_selection(chapter_selection):
        suffix = chapter_selection.replace(" ", "").replace(",", "_").replace("-", "to")
        name = f"{name}_ch{suffix}"
    return str(base_path.with_name(f"{name}.{export_format}"))
