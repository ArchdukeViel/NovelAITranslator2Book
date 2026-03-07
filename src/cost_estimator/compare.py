from __future__ import annotations

from collections.abc import Iterable, Mapping

from src.cost_estimator.estimator import estimate_cost
from src.cost_estimator.heuristics import DEFAULT_TOKEN_HEURISTICS, TokenHeuristics
from src.cost_estimator.models import CostComparison, EstimationOptions, ModelPricing


def compare_models(
    model_names: Iterable[str],
    options: EstimationOptions,
    *,
    pricing_catalog: Mapping[str, ModelPricing] | None = None,
    heuristics: TokenHeuristics = DEFAULT_TOKEN_HEURISTICS,
) -> CostComparison:
    """Compare estimated translation cost across one or more models."""
    ordered_models = list(dict.fromkeys(model_names))
    if not ordered_models:
        raise ValueError("At least one model name is required for comparison.")

    estimates = [
        estimate_cost(
            model_name,
            options,
            pricing_catalog=pricing_catalog,
            heuristics=heuristics,
        )
        for model_name in ordered_models
    ]
    cheapest = min(estimates, key=lambda estimate: estimate.estimated_total_cost_usd)
    most_expensive = max(estimates, key=lambda estimate: estimate.estimated_total_cost_usd)
    difference = most_expensive.estimated_total_cost_usd - cheapest.estimated_total_cost_usd
    percentage_difference = (
        (difference / cheapest.estimated_total_cost_usd) * 100
        if cheapest.estimated_total_cost_usd > 0
        else 0.0
    )

    return CostComparison(
        estimates=estimates,
        cheapest_model=cheapest.model_name,
        cost_difference_usd=difference,
        percentage_difference=percentage_difference,
    )
