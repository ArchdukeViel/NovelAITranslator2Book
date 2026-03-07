from __future__ import annotations

import argparse
from typing import Sequence

from src.cost_estimator.compare import compare_models
from src.cost_estimator.models import EstimationOptions
from src.cost_estimator.pricing import list_supported_models
from src.utils import format_usd


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Estimate Japanese-to-English translation cost for supported GPT models.",
    )
    parser.add_argument(
        "--chars",
        type=int,
        required=True,
        help="Japanese character count for the chapter or segment.",
    )
    parser.add_argument(
        "--model",
        action="append",
        dest="models",
        help="Model to estimate. Repeat to compare multiple models. Defaults to all supported models.",
    )
    parser.add_argument(
        "--glossary",
        action="store_true",
        help="Include glossary block overhead in the estimate.",
    )
    parser.add_argument(
        "--json",
        dest="json_mode",
        action="store_true",
        help="Include JSON mode request and response overhead.",
    )
    parser.add_argument(
        "--prompt-overhead",
        type=int,
        default=None,
        help="Override base prompt overhead tokens.",
    )
    parser.add_argument(
        "--glossary-overhead",
        type=int,
        default=None,
        help="Override glossary overhead tokens.",
    )
    parser.add_argument(
        "--json-input-overhead",
        type=int,
        default=None,
        help="Override JSON-mode input overhead tokens.",
    )
    parser.add_argument(
        "--json-output-overhead",
        type=int,
        default=None,
        help="Override JSON-mode output overhead tokens.",
    )
    return parser


def _render_estimate_block(model_name: str, comparison_output: str) -> str:
    return f"Model: {model_name}\n{comparison_output}"


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    models = args.models or list(list_supported_models())

    options = EstimationOptions(
        japanese_characters=args.chars,
        glossary_enabled=args.glossary,
        json_mode=args.json_mode,
        prompt_overhead_tokens=args.prompt_overhead,
        glossary_overhead_tokens=args.glossary_overhead,
        json_input_overhead_tokens=args.json_input_overhead,
        json_output_overhead_tokens=args.json_output_overhead,
    )
    comparison = compare_models(models, options)

    blocks: list[str] = []
    for estimate in comparison.estimates:
        lines = [
            f"Estimated input tokens: {estimate.estimated_input_tokens}",
            f"Estimated output tokens: {estimate.estimated_output_tokens}",
            f"Estimated input cost (USD): {format_usd(estimate.estimated_input_cost_usd)}",
            f"Estimated output cost (USD): {format_usd(estimate.estimated_output_cost_usd)}",
            f"Estimated total cost (USD): {format_usd(estimate.estimated_total_cost_usd)}",
        ]
        blocks.append(_render_estimate_block(estimate.model_name, "\n".join(lines)))

    print("\n\n".join(blocks))
    if len(comparison.estimates) > 1:
        print()
        print(f"Cheapest model: {comparison.cheapest_model}")
        print(f"Difference: {format_usd(comparison.cost_difference_usd)}")
        print(f"Percentage difference: {comparison.percentage_difference:.2f}%")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
