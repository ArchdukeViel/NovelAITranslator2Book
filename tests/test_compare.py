from __future__ import annotations

import math

import pytest

from novelai.cost_estimator.compare import compare_models
from novelai.cost_estimator.models import EstimationOptions


def test_compare_models_returns_expected_cheapest_and_difference() -> None:
    comparison = compare_models(
        ["gpt-5.2", "gpt-5.4"],
        EstimationOptions(japanese_characters=10_000),
    )

    assert comparison.cheapest_model == "gpt-5.2"
    assert [estimate.model_name for estimate in comparison.estimates] == ["gpt-5.2", "gpt-5.4"]
    assert math.isclose(comparison.cost_difference_usd, 0.0149, rel_tol=0, abs_tol=1e-12)
    assert math.isclose(comparison.percentage_difference, 11.631537861045, rel_tol=0, abs_tol=1e-9)


def test_compare_models_deduplicates_names_but_preserves_order() -> None:
    comparison = compare_models(
        ["gpt-5.4", "gpt-5.4", "gpt-5.2"],
        EstimationOptions(japanese_characters=5_000),
    )

    assert [estimate.model_name for estimate in comparison.estimates] == ["gpt-5.4", "gpt-5.2"]


def test_compare_models_requires_at_least_one_model() -> None:
    with pytest.raises(ValueError, match="At least one model name is required"):
        compare_models([], EstimationOptions(japanese_characters=10_000))
