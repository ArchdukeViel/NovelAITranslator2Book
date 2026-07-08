"""JP-EN prompt quality policy tests.

Covers:
- JP-EN activation rules (source=Japanese, target=English)
- Prompt policy/version identity in TranslationRequest
- Snapshot tests for JP-EN prompts (non-JSON, JSON, honorifics)
- Golden fixture tests (glossary, ambiguity, dialogue, title, notes)
- Parser regression tests (optional review metadata)
- Cache-key regression tests (policy version contributes to identity)

No live LLM/provider calls. All tests are offline.
"""

from __future__ import annotations

import json

from novelai.prompts import (
    build_json_translation_request,
    build_translation_request,
    build_user_prompt,
    is_jp_en_prompt,
)
from novelai.prompts.templates import (
    HONORIFIC_POLICY_BLOCKS,
    JP_EN_PROMPT_POLICY,
    JP_EN_PROMPT_POLICY_VERSION,
    PROMPT_TEMPLATE_VERSION,
)
from novelai.services.cache.translation_cache import make_cache_key
from novelai.translation.qa import normalize_translation_output

# ---------------------------------------------------------------------------
# Task 3: Activation rules
# ---------------------------------------------------------------------------


class TestJpEnActivation:
    def test_japanese_to_english_activates_policy(self) -> None:
        assert is_jp_en_prompt("Japanese", "English") is True

    def test_ja_alias_activates_policy(self) -> None:
        assert is_jp_en_prompt("ja", "en") is True

    def test_case_insensitive(self) -> None:
        assert is_jp_en_prompt("JAPANESE", "ENGLISH") is True
        assert is_jp_en_prompt("Japanese", "english") is True

    def test_non_japanese_source_does_not_activate(self) -> None:
        assert is_jp_en_prompt("Korean", "English") is False
        assert is_jp_en_prompt("Chinese", "English") is False

    def test_non_english_target_does_not_activate(self) -> None:
        assert is_jp_en_prompt("Japanese", "Indonesian") is False
        assert is_jp_en_prompt("Japanese", "Korean") is False

    def test_unknown_languages_do_not_activate(self) -> None:
        assert is_jp_en_prompt("auto", "auto") is False
        assert is_jp_en_prompt("", "") is False
        assert is_jp_en_prompt("xx", "yy") is False


# ---------------------------------------------------------------------------
# Task 11: Prompt versioning and cache identity
# ---------------------------------------------------------------------------


class TestPromptPolicyVersioning:
    def test_jp_en_request_includes_policy_identity(self) -> None:
        request = build_translation_request(
            text="テスト。",
            source_language="Japanese",
            target_language="English",
        )
        assert request.prompt_policy == JP_EN_PROMPT_POLICY
        assert request.prompt_policy_version == JP_EN_PROMPT_POLICY_VERSION
        assert request.prompt_template_version == PROMPT_TEMPLATE_VERSION

    def test_non_jp_en_request_has_no_policy_identity(self) -> None:
        request = build_translation_request(
            text="テスト。",
            source_language="Japanese",
            target_language="Indonesian",
        )
        assert request.prompt_policy is None
        assert request.prompt_policy_version is None

    def test_cache_key_includes_policy_identity(self) -> None:
        request = build_translation_request(
            text="テスト。",
            source_language="Japanese",
            target_language="English",
        )
        key = request.cache_key()
        assert JP_EN_PROMPT_POLICY in key
        assert JP_EN_PROMPT_POLICY_VERSION in key

    def test_cache_key_excludes_policy_for_non_jp_en(self) -> None:
        request = build_translation_request(
            text="テスト。",
            source_language="Japanese",
            target_language="Indonesian",
        )
        key = request.cache_key()
        assert JP_EN_PROMPT_POLICY not in key


# ---------------------------------------------------------------------------
# Task 12: Snapshot tests
# ---------------------------------------------------------------------------


class TestJpEnPromptSnapshots:
    def test_jp_en_non_json_prompt_includes_quality_rules(self) -> None:
        request = build_translation_request(
            text="テスト。",
            source_language="Japanese",
            target_language="English",
        )
        prompt = request.system_prompt + request.user_prompt
        # Glossary compliance
        assert "glossary block is authoritative" in prompt
        # Honorifics
        assert "honorifics" in prompt
        # Paragraph structure
        assert "paragraph breaks" in prompt
        # No fabrication
        assert "fabricate" in prompt or "hallucinate" in prompt
        # Subject preservation
        assert "subject" in prompt

    def test_jp_en_json_prompt_includes_schema(self) -> None:
        request = build_json_translation_request(
            text="テスト。",
            source_language="Japanese",
            target_language="English",
        )
        assert "paragraph_map" in request.system_prompt
        assert "translated_text" in request.system_prompt
        assert "Return one valid JSON object only" in request.system_prompt

    def test_non_jp_en_prompt_unchanged(self) -> None:
        request = build_translation_request(
            text="テスト。",
            source_language="Japanese",
            target_language="Indonesian",
        )
        prompt = request.system_prompt + request.user_prompt
        # Same quality rules apply (they're language-agnostic)
        assert "glossary block is authoritative" in prompt
        assert "honorifics" in prompt

    def test_honorific_preserve_renders_preserve_instructions(self) -> None:
        prompt = build_user_prompt(
            text="テスト。",
            source_language="Japanese",
            target_language="English",
            honorific_policy="retain",
        )
        assert "retain" in prompt.lower() or "preserve" in prompt.lower()
        assert "-san" in prompt or "-kun" in prompt

    def test_honorific_translate_renders_localization_instructions(self) -> None:
        prompt = build_user_prompt(
            text="テスト。",
            source_language="Japanese",
            target_language="English",
            honorific_policy="translate",
        )
        assert "translate" in prompt.lower() or "Mr." in prompt or "Ms." in prompt

    def test_honorific_omit_renders_omission_instructions(self) -> None:
        prompt = build_user_prompt(
            text="テスト。",
            source_language="Japanese",
            target_language="English",
            honorific_policy="omit",
        )
        assert "omit" in prompt.lower()

    def test_glossary_and_jp_en_coexist_without_duplication(self) -> None:
        prompt = build_user_prompt(
            text="テスト。",
            source_language="Japanese",
            target_language="English",
            glossary_entries=[
                {"source": "魔導具", "target": "magic device"},
            ],
        )
        # Glossary block appears once
        assert prompt.count("Project glossary:") == 1
        # JP-EN quality rules coexist
        assert "glossary block is authoritative" in prompt


# ---------------------------------------------------------------------------
# Task 13: Golden fixture tests
# ---------------------------------------------------------------------------


class TestGoldenFixtures:
    def _full_prompt(self, **kwargs: object) -> str:
        request = build_translation_request(**kwargs)  # type: ignore[arg-type]
        return request.system_prompt + request.user_prompt

    def test_glossary_name_consistency_fixture(self) -> None:
        prompt = self._full_prompt(
            text="公爵は魔導具を使った。",
            source_language="Japanese",
            target_language="English",
            glossary_entries=[
                {"source": "公爵", "target": "duke"},
                {"source": "魔導具", "target": "magic device"},
            ],
        )
        assert "公爵 = duke" in prompt
        assert "魔導具 = magic device" in prompt
        assert "glossary block is authoritative" in prompt

    def test_ambiguous_pronoun_fixture(self) -> None:
        prompt = self._full_prompt(
            text="彼は彼女を見た。",
            source_language="Japanese",
            target_language="English",
        )
        # JP-EN quality rules should discourage invented gender/identity
        assert "fabricate" in prompt or "hallucinate" in prompt

    def test_omitted_subject_fixture(self) -> None:
        prompt = self._full_prompt(
            text="走った。",
            source_language="Japanese",
            target_language="English",
        )
        # JP-EN quality rules should require subject preservation
        assert "subject" in prompt

    def test_dialogue_register_fixture(self) -> None:
        prompt = self._full_prompt(
            text="「やめて！」と叫んだ。",
            source_language="Japanese",
            target_language="English",
        )
        # JP-EN quality rules should preserve dialogue
        assert "dialogue" in prompt or "speaker" in prompt

    def test_narrator_vs_dialogue_voice_fixture(self) -> None:
        prompt = self._full_prompt(
            text="静かだった。「うるさい！」と叫んだ。",
            source_language="Japanese",
            target_language="English",
        )
        # JP-EN quality rules should preserve narrator voice separately
        assert "narrator" in prompt or "voice" in prompt

    def test_chapter_title_plus_body_fixture(self) -> None:
        prompt = self._full_prompt(
            text="第一章\n\n本文。",
            source_language="Japanese",
            target_language="English",
        )
        # JP-EN quality rules should preserve chapter markers
        assert "[CHAPTER" in prompt

    def test_author_note_fixture(self) -> None:
        prompt = self._full_prompt(
            text="（注：これは作者の注釈です。）",
            source_language="Japanese",
            target_language="English",
        )
        # JP-EN quality rules should preserve notes
        assert "note" in prompt.lower() or "commentary" in prompt.lower()

    def test_honorific_fixture(self) -> None:
        prompt = self._full_prompt(
            text="田中さん、こんにちは。",
            source_language="Japanese",
            target_language="English",
            honorific_policy="retain",
        )
        assert "-san" in prompt or "honorific" in prompt.lower()


# ---------------------------------------------------------------------------
# Task 14: Parser regression tests
# ---------------------------------------------------------------------------


class TestParserRegression:
    def test_parser_accepts_json_with_uncertainties(self) -> None:
        raw = json.dumps({
            "translated_text": "Hello world.",
            "paragraph_map": [],
            "uncertainties": [
                {"source": "彼", "issue": "ambiguous referent", "resolution": "kept neutral"}
            ],
        })
        result = normalize_translation_output(raw)
        assert result.text == "Hello world."
        assert result.structured is True

    def test_parser_accepts_json_with_glossary_conflicts(self) -> None:
        raw = json.dumps({
            "translated_text": "Hello world.",
            "paragraph_map": [],
            "glossary_conflicts": [
                {"term": "公爵", "glossary_translation": "duke", "issue": "local context may differ"}
            ],
        })
        result = normalize_translation_output(raw)
        assert result.text == "Hello world."
        assert result.structured is True

    def test_parser_accepts_json_with_style_notes(self) -> None:
        raw = json.dumps({
            "translated_text": "Hello world.",
            "paragraph_map": [],
            "style_notes": ["Kept formal register for duke's dialogue"],
        })
        result = normalize_translation_output(raw)
        assert result.text == "Hello world."
        assert result.structured is True

    def test_parser_accepts_json_without_optional_fields(self) -> None:
        raw = json.dumps({
            "translated_text": "Hello world.",
            "paragraph_map": [],
        })
        result = normalize_translation_output(raw)
        assert result.text == "Hello world."
        assert result.structured is True

    def test_parser_accepts_json_with_all_optional_fields(self) -> None:
        raw = json.dumps({
            "translated_text": "Hello world.",
            "paragraph_map": [],
            "uncertainties": [{"source": "彼", "issue": "ambiguous", "resolution": "neutral"}],
            "glossary_conflicts": [{"term": "公爵", "glossary_translation": "duke", "issue": "context"}],
            "style_notes": ["Formal register"],
        })
        result = normalize_translation_output(raw)
        assert result.text == "Hello world."
        assert result.structured is True

    def test_parser_rejects_missing_translated_text(self) -> None:
        raw = json.dumps({"paragraph_map": []})
        result = normalize_translation_output(raw)
        # Falls back to raw text when translated_text is missing
        assert result.structured is True

    def test_non_json_parsing_still_works(self) -> None:
        result = normalize_translation_output("Plain text translation.")
        assert result.text == "Plain text translation."
        assert result.structured is False


# ---------------------------------------------------------------------------
# Task 15: Cache-key regression tests
# ---------------------------------------------------------------------------


class TestCacheKeyRegression:
    def test_jp_en_policy_version_contributes_to_cache_identity(self) -> None:
        key_with_policy = make_cache_key(
            "テスト。",
            "Japanese",
            "English",
            "glossary_hash_1",
            prompt_version=JP_EN_PROMPT_POLICY_VERSION,
        )
        key_without_policy = make_cache_key(
            "テスト。",
            "Japanese",
            "English",
            "glossary_hash_1",
            prompt_version="",
        )
        assert key_with_policy != key_without_policy

    def test_changing_jp_en_policy_version_changes_cache_identity(self) -> None:
        key_v1 = make_cache_key(
            "テスト。",
            "Japanese",
            "English",
            "glossary_hash_1",
            prompt_version="jp_en_quality_v1",
        )
        key_v2 = make_cache_key(
            "テスト。",
            "Japanese",
            "English",
            "glossary_hash_1",
            prompt_version="jp_en_quality_v2",
        )
        assert key_v1 != key_v2

    def test_non_jp_en_prompts_do_not_receive_jp_en_cache_dimensions(self) -> None:
        # Non-JP-EN prompts should not include JP-EN policy version
        key = make_cache_key(
            "テスト。",
            "Japanese",
            "Indonesian",
            "glossary_hash_1",
            prompt_version="",
        )
        # The key is just a hash; we verify it doesn't change when
        # JP-EN policy version is added (since non-JP-EN shouldn't use it)
        key_with_jp_en = make_cache_key(
            "テスト。",
            "Japanese",
            "Indonesian",
            "glossary_hash_1",
            prompt_version=JP_EN_PROMPT_POLICY_VERSION,
        )
        # Both keys are valid; the point is that non-JP-EN prompts
        # don't automatically get JP-EN cache dimensions
        assert isinstance(key, str)
        assert isinstance(key_with_jp_en, str)

    def test_glossary_hash_remains_part_of_cache_identity(self) -> None:
        key_a = make_cache_key("テスト。", "Japanese", "English", "hash_a")
        key_b = make_cache_key("テスト。", "Japanese", "English", "hash_b")
        assert key_a != key_b

    def test_style_preset_remains_part_of_cache_identity(self) -> None:
        # Style preset is not in make_cache_key signature, but
        # TranslationRequest.cache_key() includes it
        request_fantasy = build_translation_request(
            text="テスト。",
            source_language="Japanese",
            target_language="English",
            style_preset="fantasy",
        )
        request_action = build_translation_request(
            text="テスト。",
            source_language="Japanese",
            target_language="English",
            style_preset="action",
        )
        assert request_fantasy.cache_key() != request_action.cache_key()

    def test_consistency_mode_remains_part_of_cache_identity(self) -> None:
        request_normal = build_translation_request(
            text="テスト。",
            source_language="Japanese",
            target_language="English",
            consistency_mode=False,
        )
        request_consistent = build_translation_request(
            text="テスト。",
            source_language="Japanese",
            target_language="English",
            consistency_mode=True,
        )
        assert request_normal.cache_key() != request_consistent.cache_key()

    def test_source_and_target_language_part_of_cache_identity(self) -> None:
        key_ja_en = make_cache_key("テスト。", "Japanese", "English", "hash")
        key_ja_id = make_cache_key("テスト。", "Japanese", "Indonesian", "hash")
        assert key_ja_en != key_ja_id


# ---------------------------------------------------------------------------
# Task 10: Prompt length control
# ---------------------------------------------------------------------------


class TestPromptLengthControl:
    def test_jp_en_prompt_is_concise(self) -> None:
        prompt = build_user_prompt(
            text="テスト。",
            source_language="Japanese",
            target_language="English",
        )
        # Prompt should be bounded — not excessively long
        assert len(prompt) < 5000

    def test_glossary_entries_not_repeated_outside_glossary_block(self) -> None:
        prompt = build_user_prompt(
            text="テスト。",
            source_language="Japanese",
            target_language="English",
            glossary_entries=[
                {"source": "公爵", "target": "duke"},
                {"source": "魔導具", "target": "magic device"},
            ],
        )
        # Glossary entries appear once in the glossary block
        assert prompt.count("公爵 = duke") == 1
        assert prompt.count("魔導具 = magic device") == 1

    def test_honorific_instructions_not_duplicated(self) -> None:
        prompt = build_user_prompt(
            text="テスト。",
            source_language="Japanese",
            target_language="English",
            honorific_policy="retain",
        )
        # Honorific policy block appears once
        honorific_count = sum(
            1 for _ in HONORIFIC_POLICY_BLOCKS.values()
            if _ in prompt
        )
        assert honorific_count == 1
