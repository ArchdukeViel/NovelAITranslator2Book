from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

AssumptionValue = str | int | float | bool | None


class CurrencyConverter(Protocol):
    """Extension point for non-USD display or reporting."""

    def convert_from_usd(self, amount_usd: float, target_currency: str) -> float:
        """Convert a USD amount into a target currency code."""
        ...


@dataclass(frozen=True, slots=True)
class ModelPricing:
    """Per-model pricing expressed in USD per one million tokens."""

    model_name: str
    input_per_million_usd: float
    output_per_million_usd: float

    def __post_init__(self) -> None:
        if not self.model_name.strip():
            raise ValueError("model_name must not be empty.")
        if self.input_per_million_usd <= 0:
            raise ValueError("input_per_million_usd must be greater than 0.")
        if self.output_per_million_usd <= 0:
            raise ValueError("output_per_million_usd must be greater than 0.")


@dataclass(frozen=True, slots=True)
class EstimationOptions:
    """Inputs and optional overhead overrides for a cost estimate."""

    japanese_characters: int
    glossary_enabled: bool = False
    json_mode: bool = False
    prompt_overhead_tokens: int | None = None
    glossary_overhead_tokens: int | None = None
    json_input_overhead_tokens: int | None = None
    json_output_overhead_tokens: int | None = None

    def __post_init__(self) -> None:
        if self.japanese_characters <= 0:
            raise ValueError("japanese_characters must be greater than 0.")
        for field_name in (
            "prompt_overhead_tokens",
            "glossary_overhead_tokens",
            "json_input_overhead_tokens",
            "json_output_overhead_tokens",
        ):
            value = getattr(self, field_name)
            if value is not None and value < 0:
                raise ValueError(f"{field_name} must be >= 0 when provided.")


@dataclass(frozen=True, slots=True)
class TokenEstimate:
    """Estimated token counts before pricing is applied."""

    japanese_characters: int
    estimated_input_tokens: int
    estimated_output_tokens: int
    assumptions: dict[str, AssumptionValue] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class CostEstimate:
    """Estimated token and cost breakdown for a single model."""

    model_name: str
    japanese_characters: int
    estimated_input_tokens: int
    estimated_output_tokens: int
    estimated_input_cost_usd: float
    estimated_output_cost_usd: float
    estimated_total_cost_usd: float
    assumptions: dict[str, AssumptionValue] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class CostComparison:
    """Comparison result across multiple model estimates."""

    estimates: list[CostEstimate]
    cheapest_model: str
    cost_difference_usd: float
    percentage_difference: float
