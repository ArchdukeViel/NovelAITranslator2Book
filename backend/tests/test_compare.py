from __future__ import annotations

import pytest

from novelai.cost_estimator.compare import compare_models
from novelai.cost_estimator.models import EstimationOptions

MODEL = "gemini-3.5-flash-lite"


def test_compare_models_returns_expected_cheapest_and_difference() -> None:
    comparison = compare_models(
        [MODEL],
        EstimationOptions(japanese_characters=10_000),
    )

    assert comparison.cheapest_model == MODEL
    assert [estimate.model_name for estimate in comparison.estimates] == [MODEL]
    assert comparison.cost_difference_usd == 0.0
    assert comparison.percentage_difference == 0.0


def test_compare_models_deduplicates_names_but_preserves_order() -> None:
    comparison = compare_models(
        [MODEL, MODEL, MODEL],
        EstimationOptions(japanese_characters=5_000),
    )

    assert [estimate.model_name for estimate in comparison.estimates] == [MODEL]


def test_compare_models_requires_at_least_one_model() -> None:
    with pytest.raises(ValueError, match="At least one model name is required"):
        compare_models([], EstimationOptions(japanese_characters=10_000))
