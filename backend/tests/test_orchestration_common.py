from __future__ import annotations

from novelai.services.orchestration.common import (
    DEFAULT_GLOSSARY_EXTRACTION_PROMPT,
    GLOSSARY_EXTRACTION_JSON_SCHEMA,
    _utc_now_iso,
)


class TestGlossaryExtractionPrompt:
    def test_prompt_has_placeholders(self) -> None:
        assert "{max_terms}" in DEFAULT_GLOSSARY_EXTRACTION_PROMPT
        assert "{source_language}" in DEFAULT_GLOSSARY_EXTRACTION_PROMPT
        assert "{text}" in DEFAULT_GLOSSARY_EXTRACTION_PROMPT

    def test_prompt_mentions_json(self) -> None:
        assert "JSON" in DEFAULT_GLOSSARY_EXTRACTION_PROMPT

    def test_prompt_mentions_no_translate(self) -> None:
        assert "Do not translate" in DEFAULT_GLOSSARY_EXTRACTION_PROMPT


class TestGlossaryExtractionSchema:
    def test_schema_is_object(self) -> None:
        assert GLOSSARY_EXTRACTION_JSON_SCHEMA["type"] == "object"

    def test_schema_has_terms_array(self) -> None:
        assert "terms" in GLOSSARY_EXTRACTION_JSON_SCHEMA["properties"]
        assert GLOSSARY_EXTRACTION_JSON_SCHEMA["properties"]["terms"]["type"] == "array"

    def test_schema_terms_have_source_string(self) -> None:
        terms_schema = GLOSSARY_EXTRACTION_JSON_SCHEMA["properties"]["terms"]
        item_schema = terms_schema["items"]
        assert item_schema["properties"]["source"]["type"] == "string"
        assert "source" in item_schema["required"]

    def test_schema_requires_terms(self) -> None:
        assert "terms" in GLOSSARY_EXTRACTION_JSON_SCHEMA["required"]


class TestUtcNowIso:
    def test_returns_string(self) -> None:
        result = _utc_now_iso()
        assert isinstance(result, str)

    def test_ends_with_z(self) -> None:
        result = _utc_now_iso()
        assert result.endswith("Z")

    def test_no_plus_offset(self) -> None:
        result = _utc_now_iso()
        assert "+00:00" not in result
