from __future__ import annotations

from typing import Any

from novelai.prompts.models import TranslationRequest

JSON_TRANSLATION_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "paragraphs": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "index": {"type": "integer"},
                    "translation": {"type": "string"},
                },
                "required": ["index", "translation"],
            },
        }
    },
    "required": ["paragraphs"],
}


def _build_message(role: str, text: str) -> dict[str, Any]:
    return {
        "role": role,
        "content": [
            {
                "type": "input_text",
                "text": text,
            }
        ],
    }


def build_basic_responses_payload(
    model: str,
    user_prompt: str,
    *,
    system_prompt: str | None = None,
    max_output_tokens: int | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "model": model,
        "input": [],
    }
    if system_prompt:
        payload["input"].append(_build_message("system", system_prompt))
    payload["input"].append(_build_message("user", user_prompt))
    if max_output_tokens is not None:
        payload["max_output_tokens"] = max_output_tokens
    return payload


def build_translation_responses_payload(
    model: str,
    request: TranslationRequest,
    *,
    max_output_tokens: int | None = None,
) -> dict[str, Any]:
    payload = build_basic_responses_payload(
        model,
        request.user_prompt,
        system_prompt=request.system_prompt,
        max_output_tokens=max_output_tokens,
    )
    if request.json_output:
        payload["text"] = {
            "format": {
                "type": "json_schema",
                "name": "translation_output",
                "schema": JSON_TRANSLATION_SCHEMA,
                "strict": True,
            }
        }
    return payload
