from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class TokenHeuristics:
    """Configurable heuristics for Japanese novel translation estimation."""

    baseline_japanese_characters: int = 10_000
    source_tokens_per_japanese_character: float = 0.87
    english_tokens_per_japanese_character: float = 0.80
    default_prompt_overhead_tokens: int = 500
    default_glossary_overhead_tokens: int = 250
    default_json_input_overhead_tokens: int = 180
    default_json_output_overhead_tokens: int = 120

    def __post_init__(self) -> None:
        if self.baseline_japanese_characters <= 0:
            raise ValueError("baseline_japanese_characters must be greater than 0.")
        if self.source_tokens_per_japanese_character <= 0:
            raise ValueError("source_tokens_per_japanese_character must be greater than 0.")
        if self.english_tokens_per_japanese_character <= 0:
            raise ValueError("english_tokens_per_japanese_character must be greater than 0.")
        for field_name in (
            "default_prompt_overhead_tokens",
            "default_glossary_overhead_tokens",
            "default_json_input_overhead_tokens",
            "default_json_output_overhead_tokens",
        ):
            if getattr(self, field_name) < 0:
                raise ValueError(f"{field_name} must be >= 0.")

    @property
    def baseline_input_tokens(self) -> int:
        return estimate_source_tokens(self.baseline_japanese_characters, self) + self.default_prompt_overhead_tokens

    @property
    def baseline_output_tokens(self) -> int:
        return estimate_output_tokens(self.baseline_japanese_characters, self)


DEFAULT_TOKEN_HEURISTICS = TokenHeuristics()


def estimate_source_tokens(
    japanese_characters: int,
    heuristics: TokenHeuristics = DEFAULT_TOKEN_HEURISTICS,
) -> int:
    """Estimate input tokens contributed by the Japanese source text."""
    if japanese_characters <= 0:
        raise ValueError("japanese_characters must be greater than 0.")
    return round(japanese_characters * heuristics.source_tokens_per_japanese_character)


def estimate_output_tokens(
    japanese_characters: int,
    heuristics: TokenHeuristics = DEFAULT_TOKEN_HEURISTICS,
) -> int:
    """Estimate output tokens contributed by the English translation text."""
    if japanese_characters <= 0:
        raise ValueError("japanese_characters must be greater than 0.")
    return round(japanese_characters * heuristics.english_tokens_per_japanese_character)
