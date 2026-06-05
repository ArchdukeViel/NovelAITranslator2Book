from __future__ import annotations

from typing import Any


def translation_provider_response(item: dict[str, Any]) -> dict[str, Any]:
    response = dict(item)
    if "provider" in response:
        response["provider_key"] = response["provider"]
    if "model" in response:
        response["provider_model"] = response["model"]
    return response


def translated_chapter_response(novel_id: str, chapter_id: str, translated: dict[str, Any]) -> dict[str, Any]:
    return {
        "novel_id": novel_id,
        "chapter_id": chapter_id,
        **translation_provider_response(translated),
    }
