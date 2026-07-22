"""Snapshot and regression tests for prompt templates, builders, and related.

Tests cover template rendering, honorific policy, conflict suppression,
glossary locked/advisory rendering, cache key invalidation, and
workflow defaults normalization.
"""

from __future__ import annotations

import pytest

from novelai.glossary.glossary import GlossaryTerm
from novelai.prompts.builders import (
    _format_additional_instructions,
    _format_honorific_block,
    _normalize_honorific_policy,
    build_json_system_prompt,
    build_json_user_prompt,
    build_system_prompt,
    build_translation_request,
    build_user_prompt,
)
from novelai.prompts.templates import (
    HONORIFIC_POLICY_BLOCKS,
    PROMPT_TEMPLATE_VERSION,
    STYLE_PRESET_SYSTEM_SUFFIX_TEMPLATES,
    STYLE_PRESET_TEMPLATES,
)
from novelai.services.translation_cache import build_translation_cache_key

# ============================================================================
# Snapshot: constants
# ============================================================================


class TestConstants:
    def test_prompt_template_version(self) -> None:
        assert PROMPT_TEMPLATE_VERSION == "v2"

    def test_style_preset_templates_keys(self) -> None:
        assert set(STYLE_PRESET_TEMPLATES) == {"fantasy", "romance", "action", "comedy"}

    def test_style_preset_system_suffix_templates_keys(self) -> None:
        assert set(STYLE_PRESET_SYSTEM_SUFFIX_TEMPLATES) == {"fantasy", "romance", "action", "comedy"}

    def test_honorific_policy_blocks_keys(self) -> None:
        assert set(HONORIFIC_POLICY_BLOCKS) == {"retain", "translate", "omit"}


# ============================================================================
# Snapshot: system prompt rendering
# ============================================================================


class TestSystemPrompt:
    def test_basic_system_prompt(self) -> None:
        prompt = build_system_prompt("Japanese", "English")
        assert "Japanese" in prompt
        assert "English" in prompt
        assert PROMPT_TEMPLATE_VERSION not in prompt  # version is metadata, not prompt text

    def test_system_prompt_style_suffix(self) -> None:
        prompt = build_system_prompt("Japanese", "English", style_preset="fantasy")
        assert "fantasy fiction" in prompt.casefold()

    def test_system_prompt_invalid_style(self) -> None:
        with pytest.raises(ValueError, match="style preset"):
            build_system_prompt("Japanese", "English", style_preset="bogus")

    def test_json_system_prompt(self) -> None:
        prompt = build_json_system_prompt("Japanese", "English")
        assert "JSON" in prompt or "json" in prompt

    def test_json_system_prompt_style_suffix(self) -> None:
        prompt = build_json_system_prompt("Japanese", "English", style_preset="romance")
        assert "romance fiction" in prompt.casefold()

    def test_system_prompt_contains_anti_hallucination(self) -> None:
        prompt = build_system_prompt("Japanese", "English")
        assert "fabricate" in prompt.casefold()

    def test_system_prompt_contains_subject_rule(self) -> None:
        prompt = build_system_prompt("Japanese", "English")
        assert "grammatical subject" in prompt.casefold()

    def test_system_prompt_contains_glossary_authority(self) -> None:
        prompt = build_system_prompt("Japanese", "English")
        assert "authoritative" in prompt.casefold()


# ============================================================================
# Snapshot: user prompt rendering
# ============================================================================


class TestUserPrompt:
    def test_basic_user_prompt(self) -> None:
        prompt = build_user_prompt("Hello world", "Japanese", "English")
        assert "Hello world" in prompt
        assert "Japanese" in prompt
        assert "English" in prompt

    def test_user_prompt_glossary_authority(self) -> None:
        prompt = build_user_prompt("Hello", "Japanese", "English")
        assert "authoritative" in prompt.casefold()

    def test_user_prompt_with_honorific(self) -> None:
        prompt = build_user_prompt("Hello", "Japanese", "English", honorific_policy="retain")
        assert "-san" in prompt

    def test_user_prompt_consistency_mode(self) -> None:
        prompt = build_user_prompt("Hello", "Japanese", "English", consistency_mode=True)
        assert "consistent" in prompt.casefold()

    def test_user_prompt_json(self) -> None:
        prompt = build_json_user_prompt("Hello world", "Japanese", "English")
        assert "Hello world" in prompt
        assert "authoritative" in prompt.casefold()

    def test_user_prompt_json_with_honorific(self) -> None:
        prompt = build_json_user_prompt("Hello", "Japanese", "English", honorific_policy="omit")
        assert "omit" in prompt.casefold()


# ============================================================================
# Honorific policy
# ============================================================================


class TestHonorificPolicy:
    def test_normalize_valid(self) -> None:
        assert _normalize_honorific_policy("retain") == "retain"
        assert _normalize_honorific_policy("  Translate  ") == "translate"
        assert _normalize_honorific_policy("OMIT") == "omit"

    def test_normalize_none(self) -> None:
        assert _normalize_honorific_policy(None) is None

    def test_normalize_invalid(self) -> None:
        with pytest.raises(ValueError, match="honorific policy"):
            _normalize_honorific_policy("bogus")

    def test_format_block_all_values(self) -> None:
        for policy in ("retain", "translate", "omit"):
            block = _format_honorific_block(policy)
            assert block
            assert block.startswith("Honorific policy:")
            assert policy in block.casefold()

    def test_format_block_none(self) -> None:
        assert _format_honorific_block(None) == ""


# ============================================================================
# TranslationRequest model fields
# ============================================================================


class TestTranslationRequest:
    def test_new_fields_default(self) -> None:
        req = build_translation_request(
            text="Hello",
            source_language="Japanese",
            target_language="English",
        )
        assert req.prompt_template_version == PROMPT_TEMPLATE_VERSION
        assert req.honorific_policy is None
        assert req.runtime_glossary_conflict_warnings == ()

    def test_honorific_policy_set(self) -> None:
        req = build_translation_request(
            text="Hello",
            source_language="Japanese",
            target_language="English",
            honorific_policy="retain",
        )
        assert req.honorific_policy == "retain"

    def test_runtime_glossary_conflict_warnings(self) -> None:
        terms = [GlossaryTerm(source="foo", target="bar")]
        block = "Custom glossary block text"
        req = build_translation_request(
            text="Hello",
            source_language="Japanese",
            target_language="English",
            glossary_entries=terms,
            prompt_glossary_block=block,
        )
        assert "conflict_suppressed_db_glossary_block" in req.runtime_glossary_conflict_warnings

    def test_cache_key_includes_new_fields(self) -> None:
        req1 = build_translation_request(
            text="Hello",
            source_language="Japanese",
            target_language="English",
        )
        req2 = build_translation_request(
            text="Hello",
            source_language="Japanese",
            target_language="English",
            honorific_policy="retain",
        )
        assert req1.cache_key() != req2.cache_key()

    def test_json_translation_request(self) -> None:
        from novelai.prompts.builders import build_json_translation_request

        req = build_json_translation_request(
            text="Hello",
            source_language="Japanese",
            target_language="English",
        )
        assert req.json_output is True
        assert req.prompt_template_version == PROMPT_TEMPLATE_VERSION


# ============================================================================
# Conflict suppression
# ============================================================================


class TestConflictSuppression:
    def test_no_conflict_no_warnings(self) -> None:
        additional, warnings = _format_additional_instructions(
            target_language="English",
        )
        assert additional == ""
        assert warnings == []

    def test_prompt_glossary_block_suppresses_db(self) -> None:
        terms = [GlossaryTerm(source="foo", target="bar")]
        additional, warnings = _format_additional_instructions(
            glossary_entries=terms,
            prompt_glossary_block="Custom block text",
            target_language="English",
        )
        assert "conflict_suppressed_db_glossary_block" in warnings
        # DB glossary should NOT appear in the output
        assert "foo => bar" not in additional
        assert "Custom block text" in additional

    def test_multiple_conflicts_all_reported(self) -> None:
        terms = [GlossaryTerm(source="a", target="b"), GlossaryTerm(source="c", target="d")]
        _, warnings = _format_additional_instructions(
            glossary_entries=terms,
            prompt_glossary_block="Block",
            target_language="English",
        )
        assert len(warnings) == 1  # only one conflict type for block suppression
        assert "conflict_suppressed_db_glossary_block" in warnings

    def test_only_db_glossary_no_conflict(self) -> None:
        terms = [GlossaryTerm(source="foo", target="bar")]
        additional, warnings = _format_additional_instructions(
            glossary_entries=terms,
            target_language="English",
        )
        assert warnings == []
        assert "Project glossary:" in additional
        assert "- foo = bar" in additional


# ============================================================================
# Glossary locked / advisory rendering
# ============================================================================


class TestGlossaryRendering:
    def test_glossary_prompt_injection_service_imports(self) -> None:
        """Verify the service module loads without error."""
        from novelai.services.glossary_prompt_injection import (
            GlossaryPromptInjectionService,
            PromptGlossaryBlock,
        )

        assert GlossaryPromptInjectionService is not None
        assert PromptGlossaryBlock is not None

    def test_prompt_glossary_block_has_locked_term_count(self) -> None:
        from novelai.services.glossary_prompt_injection import PromptGlossaryBlock

        block = PromptGlossaryBlock(
            rendered_text="test",
            included_terms=(),
            skipped_terms=(),
            warnings=(),
            conflict_warnings=(),
            empty=False,
            truncated=False,
            locked_term_count=0,
        )
        assert block.locked_term_count == 0


# ============================================================================
# Cache key
# ============================================================================


class TestCacheKey:
    def test_prompt_template_version_invalidates(self) -> None:
        key1 = build_translation_cache_key(
            source_text="hello",
            provider_key="gemini",
            provider_model="gemini-2.0-flash",
            prompt_template_version="v1",
        )
        key2 = build_translation_cache_key(
            source_text="hello",
            provider_key="gemini",
            provider_model="gemini-2.0-flash",
            prompt_template_version="v2",
        )
        assert key1 != key2

    def test_honorific_policy_invalidates(self) -> None:
        key1 = build_translation_cache_key(
            source_text="hello",
            provider_key="gemini",
            provider_model="gemini-2.0-flash",
            honorific_policy="retain",
        )
        key2 = build_translation_cache_key(
            source_text="hello",
            provider_key="gemini",
            provider_model="gemini-2.0-flash",
            honorific_policy="omit",
        )
        assert key1 != key2

    def test_existing_fields_still_invalidate(self) -> None:
        key1 = build_translation_cache_key(
            source_text="hello",
            provider_key="gemini",
            provider_model="gemini-2.0-flash",
            style_preset="fantasy",
        )
        key2 = build_translation_cache_key(
            source_text="hello",
            provider_key="gemini",
            provider_model="gemini-2.0-flash",
            style_preset="romance",
        )
        assert key1 != key2


# ============================================================================
# Workflow profiles
# ============================================================================


class TestWorkflowDefaults:
    def test_default_workflow_defaults(self) -> None:
        from novelai.config.workflow_profiles import default_workflow_defaults

        defaults = default_workflow_defaults()
        assert defaults == {
            "style_preset": None,
            "consistency_mode": False,
            "honorific_policy": None,
        }

    def test_normalize_workflow_defaults_empty(self) -> None:
        from novelai.config.workflow_profiles import normalize_workflow_defaults

        result = normalize_workflow_defaults({})
        assert result["style_preset"] is None
        assert result["consistency_mode"] is False
        assert result["honorific_policy"] is None

    def test_normalize_workflow_defaults_valid(self) -> None:
        from novelai.config.workflow_profiles import normalize_workflow_defaults

        result = normalize_workflow_defaults(
            {
                "style_preset": "  Fantasy  ",
                "consistency_mode": True,
                "honorific_policy": "RETAIN",
            }
        )
        assert result["style_preset"] == "fantasy"
        assert result["consistency_mode"] is True
        assert result["honorific_policy"] == "retain"

    def test_normalize_workflow_defaults_invalid_ignored(self) -> None:
        from novelai.config.workflow_profiles import normalize_workflow_defaults

        result = normalize_workflow_defaults(
            {
                "style_preset": "bogus",
                "consistency_mode": "not_a_bool",
                "honorific_policy": "invalid",
            }
        )
        assert result["style_preset"] is None
        assert result["consistency_mode"] is False
        assert result["honorific_policy"] is None

    def test_normalize_workflow_profiles_with_defaults(self) -> None:
        from novelai.config.workflow_profiles import normalize_workflow_profiles

        result = normalize_workflow_profiles(
            {
                "body_translation": {
                    "provider_key": "gemini",
                    "provider_model": "gemini-2.0-flash",
                },
                "defaults": {"style_preset": "fantasy", "honorific_policy": "retain"},
            }
        )
        assert "steps" in result
        assert "defaults" in result
        assert result["steps"]["body_translation"]["provider_key"] == "gemini"
        assert result["defaults"]["style_preset"] == "fantasy"
        assert result["defaults"]["honorific_policy"] == "retain"

    def test_normalize_workflow_profiles_rejects_legacy_provider_fields(self) -> None:
        from novelai.config.workflow_profiles import normalize_workflow_profiles

        with pytest.raises(ValueError, match="Unsupported workflow profile fields"):
            normalize_workflow_profiles({"body_translation": {"provider": "gemini", "model": "legacy"}})
