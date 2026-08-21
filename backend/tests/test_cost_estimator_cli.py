from __future__ import annotations

from novelai.cost_estimator.cli import build_parser, main

MODEL = "gemini-3.5-flash-lite"


class TestCostEstimatorCLI:
    def test_build_parser_has_required_chars_arg(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["--chars", "1000"])
        assert args.chars == 1000

    def test_build_parser_has_optional_model_arg(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["--chars", "1000", "--model", MODEL, "--model", MODEL])
        assert args.models == [MODEL, MODEL]

    def test_build_parser_model_defaults_to_none(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["--chars", "1000"])
        assert args.models is None

    def test_build_parser_glossary_flag(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["--chars", "1000", "--glossary"])
        assert args.glossary is True

    def test_build_parser_json_flag(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["--chars", "1000", "--json"])
        assert args.json_mode is True

    def test_build_parser_overrides(self) -> None:
        parser = build_parser()
        args = parser.parse_args(
            [
                "--chars",
                "5000",
                "--prompt-overhead",
                "100",
                "--glossary-overhead",
                "200",
                "--json-input-overhead",
                "50",
                "--json-output-overhead",
                "30",
            ]
        )
        assert args.prompt_overhead == 100
        assert args.glossary_overhead == 200
        assert args.json_input_overhead == 50
        assert args.json_output_overhead == 30

    def test_main_returns_zero_for_valid_args(self, capsys) -> None:
        result = main(["--chars", "1000"])
        assert result == 0
        output = capsys.readouterr().out
        assert "Estimated input tokens:" in output
        assert "Estimated total cost (USD):" in output

    def test_main_with_repeated_supported_model_uses_single_pricing_entry(self, capsys) -> None:
        result = main(["--chars", "1000", "--model", MODEL, "--model", MODEL])
        assert result == 0
        output = capsys.readouterr().out
        assert "Model: gemini-3.5-flash-lite" in output
        assert "Cheapest model:" not in output

    def test_main_with_glossary_flag(self, capsys) -> None:
        result = main(["--chars", "1000", "--glossary"])
        assert result == 0

    def test_main_with_json_flag(self, capsys) -> None:
        result = main(["--chars", "1000", "--json"])
        assert result == 0
