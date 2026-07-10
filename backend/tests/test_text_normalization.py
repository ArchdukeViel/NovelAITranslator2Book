from __future__ import annotations

from novelai.utils.text_normalization import normalize_text


class TestNormalizeText:
    def test_crlf_to_lf(self) -> None:
        assert normalize_text("line1\r\nline2") == "line1\nline2"

    def test_cr_to_lf(self) -> None:
        assert normalize_text("line1\rline2") == "line1\nline2"

    def test_trailing_spaces_removed(self) -> None:
        assert normalize_text("line1   \nline2") == "line1\nline2"

    def test_trailing_tabs_removed(self) -> None:
        assert normalize_text("line1\t\nline2") == "line1\nline2"

    def test_collapse_blank_lines(self) -> None:
        assert normalize_text("a\n\n\n\nb") == "a\n\nb"

    def test_strip_leading_trailing_whitespace(self) -> None:
        assert normalize_text("  \n  hello  \n  ") == "hello"

    def test_preserve_single_blank_line(self) -> None:
        assert normalize_text("a\n\nb") == "a\n\nb"

    def test_empty_string(self) -> None:
        assert normalize_text("") == ""

    def test_whitespace_only(self) -> None:
        assert normalize_text("   \n   \n   ") == ""

    def test_multiple_lines(self) -> None:
        text = "line1\n\nline2\nline3"
        assert normalize_text(text) == "line1\n\nline2\nline3"

    def test_japanese_text(self) -> None:
        text = "第一章\n\nこれはテストです。\n\n第二章"
        assert normalize_text(text) == "第一章\n\nこれはテストです。\n\n第二章"
