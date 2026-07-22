from __future__ import annotations

from novelai.cost_estimator.cli import build_parser, main


class TestCostEstimatorCLI:
    def test_build_parser_has_required_chars_arg(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["--chars", "1000"])
        assert args.chars == 1000

    def test_build_parser_has_optional_model_arg(self) -> None:
        parser = build_parser()
        args = parser.parse_args(
            ["--chars", "1000", "--model", "gemini-3.1-flash-lite", "--model", "gemma-4-31b-it"]
        )
        assert args.models == ["gemini-3.1-flash-lite", "gemma-4-31b-it"]

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
        args = parser.parse_args([
            "--chars", "5000",
            "--prompt-overhead", "100",
            "--glossary-overhead", "200",
            "--json-input-overhead", "50",
            "--json-output-overhead", "30",
        ])
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

    def test_main_with_multiple_models_shows_comparison(self, capsys) -> None:
        result = main(
            ["--chars", "1000", "--model", "gemini-3.1-flash-lite", "--model", "gemma-4-31b-it"]
        )
        assert result == 0
        output = capsys.readouterr().out
        assert "Cheapest model:" in output
        assert "Percentage difference:" in output

    def test_main_with_glossary_flag(self, capsys) -> None:
        result = main(["--chars", "1000", "--glossary"])
        assert result == 0

    def test_main_with_json_flag(self, capsys) -> None:
        result = main(["--chars", "1000", "--json"])
        assert result == 0
