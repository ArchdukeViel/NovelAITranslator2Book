from __future__ import annotations

import pytest

from novelai.cost_estimator.compare import compare_models
from novelai.cost_estimator.models import EstimationOptions


def test_compare_models_returns_expected_cheapest_and_difference() -> None:
    comparison = compare_models(
        ["gemini-3.1-flash-lite", "gemma-4-31b-it"],
        EstimationOptions(japanese_characters=10_000),
    )

    assert comparison.cheapest_model == "gemini-3.1-flash-lite"
    assert [estimate.model_name for estimate in comparison.estimates] == [
        "gemini-3.1-flash-lite",
        "gemma-4-31b-it",
    ]
    assert comparison.cost_difference_usd == 0.0
    assert comparison.percentage_difference == 0.0


def test_compare_models_deduplicates_names_but_preserves_order() -> None:
    comparison = compare_models(
        ["gemma-4-31b-it", "gemma-4-31b-it", "gemini-3.1-flash-lite"],
        EstimationOptions(japanese_characters=5_000),
    )

    assert [estimate.model_name for estimate in comparison.estimates] == [
        "gemma-4-31b-it",
        "gemini-3.1-flash-lite",
    ]


def test_compare_models_requires_at_least_one_model() -> None:
    with pytest.raises(ValueError, match="At least one model name is required"):
        compare_models([], EstimationOptions(japanese_characters=10_000))
