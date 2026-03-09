from __future__ import annotations

import math

import pytest

from novelai.cost_estimator.models import CurrencyConverter
from novelai.cost_estimator.pricing import (
    DEFAULT_PRICING,
    calculate_input_cost,
    calculate_output_cost,
    calculate_total_cost,
    convert_from_usd,
    get_model_pricing,
)


class FixedRateConverter:
    def convert_from_usd(self, amount_usd: float, target_currency: str) -> float:
        assert target_currency == "IDR"
        return amount_usd * 15_500


def test_default_pricing_lookup_returns_expected_values() -> None:
    pricing = get_model_pricing("gpt-5.2")

    assert pricing == DEFAULT_PRICING["gpt-5.2"]
    assert pricing.input_per_million_usd == 1.75
    assert pricing.output_per_million_usd == 14.00


def test_pricing_calculations_are_correct() -> None:
    pricing = get_model_pricing("gpt-5.4")

    input_cost = calculate_input_cost(9_200, pricing)
    output_cost = calculate_output_cost(8_000, pricing)
    total_cost = calculate_total_cost(9_200, 8_000, pricing)

    assert math.isclose(input_cost, 0.023, rel_tol=0, abs_tol=1e-12)
    assert math.isclose(output_cost, 0.12, rel_tol=0, abs_tol=1e-12)
    assert math.isclose(total_cost, 0.143, rel_tol=0, abs_tol=1e-12)


def test_pricing_rejects_unknown_models() -> None:
    with pytest.raises(ValueError, match="Unsupported model 'unknown-model'"):
        get_model_pricing("unknown-model")


def test_currency_conversion_uses_injected_converter() -> None:
    converter: CurrencyConverter = FixedRateConverter()

    converted = convert_from_usd(
        0.1281,
        target_currency="idr",
        converter=converter,
    )

    assert math.isclose(converted, 1985.55, rel_tol=0, abs_tol=1e-12)


def test_currency_conversion_rejects_invalid_arguments() -> None:
    converter: CurrencyConverter = FixedRateConverter()

    with pytest.raises(ValueError, match="amount_usd must be >= 0"):
        convert_from_usd(-1.0, target_currency="IDR", converter=converter)
    with pytest.raises(ValueError, match="target_currency must not be empty"):
        convert_from_usd(1.0, target_currency="   ", converter=converter)
