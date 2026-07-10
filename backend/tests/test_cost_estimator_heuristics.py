from __future__ import annotations

import pytest

from novelai.cost_estimator.heuristics import (
    DEFAULT_TOKEN_HEURISTICS,
    TokenHeuristics,
    estimate_output_tokens,
    estimate_source_tokens,
)


class TestTokenHeuristics:
    def test_defaults_are_positive(self) -> None:
        h = DEFAULT_TOKEN_HEURISTICS
        assert h.baseline_japanese_characters > 0
        assert h.source_tokens_per_japanese_character > 0
        assert h.english_tokens_per_japanese_character > 0
        assert h.default_prompt_overhead_tokens >= 0
        assert h.default_glossary_overhead_tokens >= 0

    def test_baseline_input_tokens_includes_overhead(self) -> None:
        h = DEFAULT_TOKEN_HEURISTICS
        expected = int(h.baseline_japanese_characters * h.source_tokens_per_japanese_character) + h.default_prompt_overhead_tokens
        assert h.baseline_input_tokens == expected

    def test_baseline_output_tokens(self) -> None:
        h = DEFAULT_TOKEN_HEURISTICS
        expected = int(h.baseline_japanese_characters * h.english_tokens_per_japanese_character)
        assert h.baseline_output_tokens == expected

    def test_zero_baseline_raises(self) -> None:
        with pytest.raises(ValueError, match="baseline_japanese_characters"):
            TokenHeuristics(baseline_japanese_characters=0)

    def test_zero_source_tokens_raises(self) -> None:
        with pytest.raises(ValueError, match="source_tokens_per_japanese_character"):
            TokenHeuristics(source_tokens_per_japanese_character=0)

    def test_zero_english_tokens_raises(self) -> None:
        with pytest.raises(ValueError, match="english_tokens_per_japanese_character"):
            TokenHeuristics(english_tokens_per_japanese_character=0)

    def test_negative_overhead_raises(self) -> None:
        with pytest.raises(ValueError, match="default_prompt_overhead_tokens"):
            TokenHeuristics(default_prompt_overhead_tokens=-1)


class TestEstimateSourceTokens:
    def test_zero_chars_raises(self) -> None:
        with pytest.raises(ValueError, match="japanese_characters must be greater than 0"):
            estimate_source_tokens(0)

    def test_positive_chars(self) -> None:
        h = DEFAULT_TOKEN_HEURISTICS
        result = estimate_source_tokens(1000)
        expected = round(1000 * h.source_tokens_per_japanese_character)
        assert result == expected

    def test_custom_heuristics(self) -> None:
        h = TokenHeuristics(source_tokens_per_japanese_character=1.0)
        assert estimate_source_tokens(1000, h) == 1000


class TestEstimateOutputTokens:
    def test_zero_chars_raises(self) -> None:
        with pytest.raises(ValueError, match="japanese_characters must be greater than 0"):
            estimate_output_tokens(0)

    def test_positive_chars(self) -> None:
        h = DEFAULT_TOKEN_HEURISTICS
        result = estimate_output_tokens(1000)
        expected = round(1000 * h.english_tokens_per_japanese_character)
        assert result == expected

    def test_custom_heuristics(self) -> None:
        h = TokenHeuristics(english_tokens_per_japanese_character=1.0)
        assert estimate_output_tokens(1000, h) == 1000
