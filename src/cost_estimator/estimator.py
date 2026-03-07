from __future__ import annotations

from collections.abc import Mapping

from src.cost_estimator.heuristics import (
    DEFAULT_TOKEN_HEURISTICS,
    TokenHeuristics,
    estimate_output_tokens,
    estimate_source_tokens,
)
from src.cost_estimator.models import CostEstimate, EstimationOptions, ModelPricing, TokenEstimate
from src.cost_estimator.pricing import (
    calculate_input_cost,
    calculate_output_cost,
    get_model_pricing,
)


def _resolve_overhead(
    *,
    enabled: bool,
    override: int | None,
    default: int,
) -> int:
    if not enabled:
        return 0
    if override is not None:
        return override
    return default


def estimate_tokens(
    options: EstimationOptions,
    heuristics: TokenHeuristics = DEFAULT_TOKEN_HEURISTICS,
) -> TokenEstimate:
    """Estimate input and output token counts from Japanese character count."""
    source_input_tokens = estimate_source_tokens(options.japanese_characters, heuristics)
    translation_output_tokens = estimate_output_tokens(options.japanese_characters, heuristics)

    prompt_overhead_tokens = (
        options.prompt_overhead_tokens
        if options.prompt_overhead_tokens is not None
        else heuristics.default_prompt_overhead_tokens
    )
    glossary_overhead_tokens = _resolve_overhead(
        enabled=options.glossary_enabled,
        override=options.glossary_overhead_tokens,
        default=heuristics.default_glossary_overhead_tokens,
    )
    json_input_overhead_tokens = _resolve_overhead(
        enabled=options.json_mode,
        override=options.json_input_overhead_tokens,
        default=heuristics.default_json_input_overhead_tokens,
    )
    json_output_overhead_tokens = _resolve_overhead(
        enabled=options.json_mode,
        override=options.json_output_overhead_tokens,
        default=heuristics.default_json_output_overhead_tokens,
    )

    total_input_tokens = (
        source_input_tokens
        + prompt_overhead_tokens
        + glossary_overhead_tokens
        + json_input_overhead_tokens
    )
    total_output_tokens = translation_output_tokens + json_output_overhead_tokens

    assumptions: dict[str, str | int | float | bool | None] = {
        "baseline_japanese_characters": heuristics.baseline_japanese_characters,
        "baseline_input_tokens": heuristics.baseline_input_tokens,
        "baseline_output_tokens": heuristics.baseline_output_tokens,
        "source_tokens_per_japanese_character": heuristics.source_tokens_per_japanese_character,
        "english_tokens_per_japanese_character": heuristics.english_tokens_per_japanese_character,
        "source_input_tokens": source_input_tokens,
        "translation_output_tokens": translation_output_tokens,
        "prompt_overhead_tokens": prompt_overhead_tokens,
        "glossary_enabled": options.glossary_enabled,
        "glossary_overhead_tokens": glossary_overhead_tokens,
        "json_mode": options.json_mode,
        "json_input_overhead_tokens": json_input_overhead_tokens,
        "json_output_overhead_tokens": json_output_overhead_tokens,
    }

    return TokenEstimate(
        japanese_characters=options.japanese_characters,
        estimated_input_tokens=total_input_tokens,
        estimated_output_tokens=total_output_tokens,
        assumptions=assumptions,
    )


def estimate_cost(
    model_name: str,
    options: EstimationOptions,
    *,
    pricing_catalog: Mapping[str, ModelPricing] | None = None,
    heuristics: TokenHeuristics = DEFAULT_TOKEN_HEURISTICS,
) -> CostEstimate:
    """Estimate total translation cost for a configured model."""
    pricing = get_model_pricing(model_name, pricing_catalog)
    token_estimate = estimate_tokens(options, heuristics)

    input_cost = calculate_input_cost(token_estimate.estimated_input_tokens, pricing)
    output_cost = calculate_output_cost(token_estimate.estimated_output_tokens, pricing)
    assumptions = dict(token_estimate.assumptions)
    assumptions["input_per_million_usd"] = pricing.input_per_million_usd
    assumptions["output_per_million_usd"] = pricing.output_per_million_usd

    return CostEstimate(
        model_name=pricing.model_name,
        japanese_characters=options.japanese_characters,
        estimated_input_tokens=token_estimate.estimated_input_tokens,
        estimated_output_tokens=token_estimate.estimated_output_tokens,
        estimated_input_cost_usd=input_cost,
        estimated_output_cost_usd=output_cost,
        estimated_total_cost_usd=input_cost + output_cost,
        assumptions=assumptions,
    )
