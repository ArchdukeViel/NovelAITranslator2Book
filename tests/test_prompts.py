from __future__ import annotations

import pytest

from novelai.prompts import (
    build_json_translation_request,
    build_system_prompt,
    build_translation_request,
    build_user_prompt,
    build_translation_responses_payload,
    format_glossary_block,
)


def test_build_system_prompt_is_multilingual() -> None:
    prompt = build_system_prompt("Japanese", "Indonesian")

    assert "Japanese fiction text" in prompt
    assert "natural, fluent Indonesian" in prompt


def test_build_user_prompt_includes_glossary_and_style_and_preserves_paragraphs() -> None:
    text = "第一段落。\n\n第二段落。"

    prompt = build_user_prompt(
        text,
        "Japanese",
        "English",
        glossary_entries=[
            {"source": "魔導具", "target": "magic tool"},
            {"source": " 公爵 ", "target": "duke"},
            {"source": "魔導具", "target": "magic device"},
        ],
        style_preset="fantasy",
    )

    assert "Project glossary:" in prompt
    assert "- 公爵 = duke" in prompt
    assert "- 魔導具 = magic device" in prompt
    assert "Treat fantasy and worldbuilding terminology carefully." in prompt
    assert "第一段落。\n\n第二段落。" in prompt


def test_build_user_prompt_supports_strong_consistency_mode() -> None:
    prompt = build_user_prompt(
        "これはテストです。",
        "Japanese",
        "English",
        consistency_mode=True,
    )

    assert "prior established usage" in prompt
    assert "If a recurring term appears" in prompt


def test_build_json_translation_request_sets_json_mode_and_payload_schema() -> None:
    request = build_json_translation_request(
        text="段落一。\n\n段落二。",
        source_language="Japanese",
        target_language="English",
        glossary_entries=[{"source": "聖騎士", "target": "holy knight"}],
        style_preset="action",
        consistency_mode=True,
    )
    payload = build_translation_responses_payload("gpt-5.4", request)

    assert request.json_output is True
    assert "Return valid JSON only." in request.system_prompt
    assert "paragraphs" in request.system_prompt
    assert payload["input"][0]["role"] == "system"
    assert payload["input"][1]["role"] == "user"
    assert payload["input"][1]["content"][0]["type"] == "input_text"
    assert payload["text"]["format"]["type"] == "json_schema"


def test_format_glossary_block_is_deterministic_and_last_duplicate_wins() -> None:
    block = format_glossary_block(
        [
            {"source": "beta", "target": "B"},
            {"source": " alpha ", "target": "A1"},
            {"source": "alpha", "target": "A2"},
        ]
    )

    assert block == "Project glossary:\n- alpha = A2\n- beta = B"


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"text": "", "source_language": "Japanese", "target_language": "English"}, "text cannot be empty."),
        ({"text": "x", "source_language": "", "target_language": "English"}, "source_language cannot be empty."),
        ({"text": "x", "source_language": "Japanese", "target_language": ""}, "target_language cannot be empty."),
    ],
)
def test_build_translation_request_validates_required_fields(kwargs: dict[str, str], message: str) -> None:
    with pytest.raises(ValueError, match=message):
        build_translation_request(**kwargs)


def test_build_translation_request_rejects_unsupported_style_preset() -> None:
    with pytest.raises(ValueError, match="Unsupported style preset"):
        build_translation_request(
            text="test",
            source_language="Japanese",
            target_language="English",
            style_preset="horror",
        )
