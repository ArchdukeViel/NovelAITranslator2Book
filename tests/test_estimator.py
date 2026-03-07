from __future__ import annotations

import math

import pytest

from src.cost_estimator.estimator import estimate_cost, estimate_tokens
from src.cost_estimator.models import EstimationOptions


def test_baseline_estimation_for_10000_characters() -> None:
    options = EstimationOptions(japanese_characters=10_000)

    token_estimate = estimate_tokens(options)
    cost_estimate = estimate_cost("gpt-5.2", options)

    assert token_estimate.estimated_input_tokens == 9_200
    assert token_estimate.estimated_output_tokens == 8_000
    assert cost_estimate.estimated_input_tokens == 9_200
    assert cost_estimate.estimated_output_tokens == 8_000
    assert math.isclose(cost_estimate.estimated_input_cost_usd, 0.0161, rel_tol=0, abs_tol=1e-12)
    assert math.isclose(cost_estimate.estimated_output_cost_usd, 0.1120, rel_tol=0, abs_tol=1e-12)
    assert math.isclose(cost_estimate.estimated_total_cost_usd, 0.1281, rel_tol=0, abs_tol=1e-12)


def test_glossary_adjustment_adds_input_overhead_only() -> None:
    baseline = estimate_tokens(EstimationOptions(japanese_characters=10_000))
    with_glossary = estimate_tokens(
        EstimationOptions(japanese_characters=10_000, glossary_enabled=True)
    )

    assert with_glossary.estimated_input_tokens == baseline.estimated_input_tokens + 250
    assert with_glossary.estimated_output_tokens == baseline.estimated_output_tokens
    assert with_glossary.assumptions["glossary_overhead_tokens"] == 250


def test_json_mode_adjustment_adds_input_and_output_overhead() -> None:
    baseline = estimate_tokens(EstimationOptions(japanese_characters=10_000))
    json_mode = estimate_tokens(EstimationOptions(japanese_characters=10_000, json_mode=True))

    assert json_mode.estimated_input_tokens == baseline.estimated_input_tokens + 180
    assert json_mode.estimated_output_tokens == baseline.estimated_output_tokens + 120
    assert json_mode.assumptions["json_input_overhead_tokens"] == 180
    assert json_mode.assumptions["json_output_overhead_tokens"] == 120


def test_custom_overhead_overrides_are_used() -> None:
    options = EstimationOptions(
        japanese_characters=10_000,
        glossary_enabled=True,
        json_mode=True,
        prompt_overhead_tokens=650,
        glossary_overhead_tokens=400,
        json_input_overhead_tokens=220,
        json_output_overhead_tokens=160,
    )

    estimate = estimate_tokens(options)

    assert estimate.estimated_input_tokens == 8_700 + 650 + 400 + 220
    assert estimate.estimated_output_tokens == 8_000 + 160


@pytest.mark.parametrize(
    "kwargs",
    [
        {"japanese_characters": 0},
        {"japanese_characters": -10},
        {"japanese_characters": 1_000, "prompt_overhead_tokens": -1},
        {"japanese_characters": 1_000, "glossary_overhead_tokens": -1},
        {"japanese_characters": 1_000, "json_input_overhead_tokens": -1},
        {"japanese_characters": 1_000, "json_output_overhead_tokens": -1},
    ],
)
def test_invalid_estimation_options_raise_value_error(kwargs: dict[str, int]) -> None:
    with pytest.raises(ValueError):
        EstimationOptions(**kwargs)


def test_unsupported_model_name_raises_clear_error() -> None:
    options = EstimationOptions(japanese_characters=10_000)

    with pytest.raises(ValueError, match="Unsupported model 'gpt-5.9'"):
        estimate_cost("gpt-5.9", options)
