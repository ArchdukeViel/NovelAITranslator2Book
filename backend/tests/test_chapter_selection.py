from __future__ import annotations

from novelai.utils.chapter_selection import (
    ChapterRange,
    is_full_chapter_selection,
    parse_chapter_selection,
    parse_range_segment,
)


class TestIsFullChapterSelection:
    def test_wildcard(self) -> None:
        assert is_full_chapter_selection("*") is True

    def test_all(self) -> None:
        assert is_full_chapter_selection("all") is True

    def test_full(self) -> None:
        assert is_full_chapter_selection("full") is True

    def test_uppercase_all(self) -> None:
        assert is_full_chapter_selection("ALL") is True

    def test_with_whitespace(self) -> None:
        assert is_full_chapter_selection("  all  ") is True

    def test_specific_chapters(self) -> None:
        assert is_full_chapter_selection("1-5") is False

    def test_empty(self) -> None:
        assert is_full_chapter_selection("") is False


class TestParseRangeSegment:
    def test_single_number(self) -> None:
        assert list(parse_range_segment("5")) == [5]

    def test_range(self) -> None:
        assert list(parse_range_segment("3-5")) == [3, 4, 5]

    def test_single_range(self) -> None:
        assert list(parse_range_segment("1-1")) == [1]


class TestParseChapterSelection:
    def test_empty_returns_empty_list(self) -> None:
        assert parse_chapter_selection("") == []

    def test_whitespace_only_returns_empty_list(self) -> None:
        assert parse_chapter_selection("   ") == []

    def test_single_chapter(self) -> None:
        result = parse_chapter_selection("5")
        assert result == [ChapterRange(chapter=5)]

    def test_range(self) -> None:
        result = parse_chapter_selection("1-3")
        assert result == [ChapterRange(chapter=1), ChapterRange(chapter=2), ChapterRange(chapter=3)]

    def test_multiple_ranges_semicolon(self) -> None:
        result = parse_chapter_selection("1-2;4")
        assert result == [
            ChapterRange(chapter=1),
            ChapterRange(chapter=2),
            ChapterRange(chapter=4),
        ]

    def test_subchapters(self) -> None:
        result = parse_chapter_selection("5:1-2")
        assert result == [
            ChapterRange(chapter=5, subchapter=1),
            ChapterRange(chapter=5, subchapter=2),
        ]

    def test_complex_selection(self) -> None:
        result = parse_chapter_selection("1-3;5:1-2,4")
        assert result == [
            ChapterRange(chapter=1),
            ChapterRange(chapter=2),
            ChapterRange(chapter=3),
            ChapterRange(chapter=5, subchapter=1),
            ChapterRange(chapter=5, subchapter=2),
            ChapterRange(chapter=5, subchapter=4),
        ]

    def test_whitespace_handling(self) -> None:
        result = parse_chapter_selection("  1 ; 2-3 ")
        assert result == [ChapterRange(chapter=1), ChapterRange(chapter=2), ChapterRange(chapter=3)]
