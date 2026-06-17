from __future__ import annotations

import json
from typing import Any

from novelai.config.settings import settings

METADATA_TRANSLATION_PROMPT_VERSION = "metadata-literal-v2"


def build_metadata_translation_prompt(source_text: str, field: str) -> str:
    target_language = settings.TRANSLATION_TARGET_LANGUAGE or "English"
    normalized_field = field.strip().lower()
    field_label = {
        "title": "novel title",
        "author": "author name",
        "synopsis": "novel synopsis",
        "chapter_title": "chapter title",
        "glossary_term": "glossary term",
    }.get(normalized_field, "text")
    extra_rules = ""
    if normalized_field == "author":
        extra_rules = "\n- For author names, return only the name; omit labels such as Author or Writer."
    elif normalized_field in {"title", "chapter_title", "glossary_term"}:
        extra_rules = "\n- Keep the result short and title-like; do not expand it into a summary."
    return (
        f"Translate this Japanese web novel {field_label} into {target_language}.\n"
        "Rules:\n"
        "- Return only the translated text.\n"
        "- Do not explain, summarize, continue, rewrite, add alternatives, or add markdown.\n"
        "- Preserve names, numbers, episode markers, and honorifics unless a standard English rendering exists.\n"
        "- If the input is already in the target language, return it unchanged."
        f"{extra_rules}\n"
        "<source_text>\n"
        f"{source_text}\n"
        "</source_text>"
    )


def build_metadata_batch_translation_prompt(items: list[dict[str, Any]]) -> str:
    target_language = settings.TRANSLATION_TARGET_LANGUAGE or "English"
    payload = [
        {
            "id": str(item["id"]),
            "field": str(item.get("field") or "text"),
            "source_text": str(item["source_text"]),
        }
        for item in items
    ]
    return (
        f"Translate these Japanese web novel metadata items into {target_language}.\n"
        "Rules:\n"
        "- Return one JSON object only. No markdown fences, prose, comments, or text outside JSON.\n"
        "- The response object must contain one key: items.\n"
        "- Include every requested id exactly once and preserve each id byte-for-byte.\n"
        "- Each item must be {\"id\":\"...\",\"translation\":\"...\"}.\n"
        "- Preserve names, numbers, episode markers, and honorifics unless a standard English rendering exists.\n"
        "- For author names, return only the name; omit labels such as Author or Writer.\n"
        "- For titles and chapter titles, keep the result short and title-like; do not expand it into a summary.\n"
        "- If an input is already in the target language or cannot be translated safely, copy it unchanged.\n"
        "Expected response shape:\n"
        '{"items":[{"id":"novel_title","translation":"..."},{"id":"chapter:123","translation":"..."}]}\n'
        "<metadata_items>\n"
        f"{json.dumps({'items': payload}, ensure_ascii=False, sort_keys=True)}\n"
        "</metadata_items>"
    )
