from __future__ import annotations

from collections.abc import Mapping

from src.cost_estimator.models import CurrencyConverter, ModelPricing

TOKENS_PER_MILLION = 1_000_000

DEFAULT_PRICING: dict[str, ModelPricing] = {
    "gpt-5.2": ModelPricing(
        model_name="gpt-5.2",
        input_per_million_usd=1.75,
        output_per_million_usd=14.00,
    ),
    "gpt-5.4": ModelPricing(
        model_name="gpt-5.4",
        input_per_million_usd=2.50,
        output_per_million_usd=15.00,
    ),
}


def list_supported_models(
    pricing_catalog: Mapping[str, ModelPricing] | None = None,
) -> tuple[str, ...]:
    catalog = pricing_catalog or DEFAULT_PRICING
    return tuple(catalog.keys())


def get_model_pricing(
    model_name: str,
    pricing_catalog: Mapping[str, ModelPricing] | None = None,
) -> ModelPricing:
    """Resolve pricing configuration for a supported model."""
    catalog = pricing_catalog or DEFAULT_PRICING
    try:
        return catalog[model_name]
    except KeyError as exc:
        supported = ", ".join(list_supported_models(catalog))
        raise ValueError(
            f"Unsupported model '{model_name}'. Supported models: {supported}."
        ) from exc


def _validate_tokens(tokens: int) -> None:
    if tokens < 0:
        raise ValueError("tokens must be >= 0.")


def calculate_input_cost(tokens: int, pricing: ModelPricing) -> float:
    """Calculate input-token cost using raw, unrounded USD values."""
    _validate_tokens(tokens)
    return (tokens / TOKENS_PER_MILLION) * pricing.input_per_million_usd


def calculate_output_cost(tokens: int, pricing: ModelPricing) -> float:
    """Calculate output-token cost using raw, unrounded USD values."""
    _validate_tokens(tokens)
    return (tokens / TOKENS_PER_MILLION) * pricing.output_per_million_usd


def calculate_total_cost(
    input_tokens: int,
    output_tokens: int,
    pricing: ModelPricing,
) -> float:
    """Calculate total cost using raw, unrounded USD values."""
    return calculate_input_cost(input_tokens, pricing) + calculate_output_cost(output_tokens, pricing)


def convert_from_usd(
    amount_usd: float,
    *,
    target_currency: str,
    converter: CurrencyConverter,
) -> float:
    """Convert USD using an injected converter implementation."""
    if amount_usd < 0:
        raise ValueError("amount_usd must be >= 0.")
    currency = target_currency.strip().upper()
    if not currency:
        raise ValueError("target_currency must not be empty.")
    if currency == "USD":
        return amount_usd
    return converter.convert_from_usd(amount_usd, currency)
