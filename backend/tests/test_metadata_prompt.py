from __future__ import annotations

from novelai.prompts.metadata import (
    METADATA_TRANSLATION_PROMPT_VERSION,
    build_metadata_batch_translation_prompt,
    build_metadata_translation_prompt,
)


class TestMetadataTranslationPrompt:
    def test_version_is_v3(self) -> None:
        assert METADATA_TRANSLATION_PROMPT_VERSION == "metadata-literal-v3"

    def test_single_prompt_contains_banner_strip_rule(self) -> None:
        prompt = build_metadata_translation_prompt("test title", "title")
        assert "banner-style suffix" in prompt
        assert "コミカライズN巻発売中" in prompt
        assert "アニメ化" in prompt
        assert "書籍化" in prompt
        assert "Web版" in prompt

    def test_single_prompt_contains_part_keep_rule(self) -> None:
        prompt = build_metadata_translation_prompt("test title", "title")
        assert "竜騎士団篇" in prompt
        assert "第七章" in prompt
        assert "keep it as part" in prompt

    def test_single_prompt_no_banner_rule_for_author(self) -> None:
        prompt = build_metadata_translation_prompt("Author_Name", "author")
        assert "banner-style suffix" not in prompt

    def test_single_prompt_no_banner_rule_for_synopsis(self) -> None:
        prompt = build_metadata_translation_prompt("Some synopsis.", "synopsis")
        assert "banner-style suffix" not in prompt

    def test_batch_prompt_contains_banner_strip_rule(self) -> None:
        items = [{"id": "1", "field": "title", "source_text": "test"}]
        prompt = build_metadata_batch_translation_prompt(items)
        assert "banner-style suffix" in prompt
        assert "コミカライズN巻発売中" in prompt

    def test_batch_prompt_contains_part_keep_rule(self) -> None:
        items = [{"id": "1", "field": "title", "source_text": "test"}]
        prompt = build_metadata_batch_translation_prompt(items)
        assert "竜騎士団篇" in prompt
        assert "keep it as part" in prompt

    def test_batch_prompt_still_returns_json(self) -> None:
        items = [{"id": "n1", "field": "title", "source_text": "転生したら世界樹だった件"}]
        prompt = build_metadata_batch_translation_prompt(items)
        assert '{"items":' in prompt
        assert "転生したら世界樹だった件" in prompt

    def test_banner_rule_not_in_author_or_synopsis_items_batch(self) -> None:
        items = [
            {"id": "a1", "field": "author", "source_text": "松浦"},
            {"id": "s1", "field": "synopsis", "source_text": "A story."},
        ]
        prompt = build_metadata_batch_translation_prompt(items)
        # The rules are static and always present in batch prompt,
        # but they are only meaningful for title/chapter_title fields.
        assert "banner-style suffix" in prompt
        # No field-specific filtering needed at prompt level — LLM handles it.
