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


def source_candidate_response(item: dict[str, Any]) -> dict[str, Any]:
    response = dict(item)
    if "url" in response:
        response["source_url"] = response["url"]
    return response


def request_response(item: dict[str, Any]) -> dict[str, Any]:
    response = dict(item)
    if "id" in response:
        response["request_id"] = response["id"]
    candidates = response.get("source_candidates")
    if isinstance(candidates, list):
        response["source_candidates"] = [
            source_candidate_response(candidate)
            for candidate in candidates
            if isinstance(candidate, dict)
        ]
    return response


def request_list_response(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [request_response(item) for item in items]
