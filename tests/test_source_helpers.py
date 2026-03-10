"""Tests for source helper utilities."""

from __future__ import annotations

from bs4 import BeautifulSoup, Tag

from novelai.sources._helpers import (
    attribute_to_str,
    image_placeholder,
    image_source_url,
    iter_story_blocks,
)


def _tag(html: str) -> Tag:
    soup = BeautifulSoup(html, "html.parser")
    tag = soup.find()
    assert isinstance(tag, Tag)
    return tag


class TestAttributeToStr:
    def test_string(self) -> None:
        assert attribute_to_str("hello") == "hello"

    def test_single_item_list(self) -> None:
        assert attribute_to_str(["one"]) == "one"

    def test_multi_item_list_returns_none(self) -> None:
        assert attribute_to_str(["a", "b"]) is None

    def test_none_returns_none(self) -> None:
        assert attribute_to_str(None) is None


class TestImagePlaceholder:
    def test_uses_alt(self) -> None:
        img = _tag('<img alt="hero" />')
        assert image_placeholder(img) == "[Image: hero]"

    def test_uses_title_when_no_alt(self) -> None:
        img = _tag('<img title="titletext" />')
        assert image_placeholder(img) == "[Image: titletext]"

    def test_uses_filename_when_no_alt_or_title(self) -> None:
        img = _tag('<img src="https://cdn.example.com/pic.jpg" />')
        assert image_placeholder(img) == "[Image: pic.jpg]"

    def test_fallback_plain(self) -> None:
        img = _tag("<img />")
        assert image_placeholder(img) == "[Image]"


class TestImageSourceUrl:
    def test_extracts_src(self) -> None:
        img = _tag('<img src="https://example.com/a.jpg" />')
        assert image_source_url(img) == "https://example.com/a.jpg"

    def test_extracts_data_src(self) -> None:
        img = _tag('<img data-src="https://example.com/b.jpg" />')
        assert image_source_url(img) == "https://example.com/b.jpg"

    def test_returns_none_when_no_src(self) -> None:
        img = _tag("<img />")
        assert image_source_url(img) is None


class TestIterStoryBlocks:
    def test_yields_top_level_blocks(self) -> None:
        html = "<div><p>A</p><p>B</p></div>"
        section = _tag(html)
        blocks = list(iter_story_blocks(section, ("p",)))
        assert len(blocks) == 2

    def test_skips_nested_duplicates(self) -> None:
        html = "<div><blockquote><p>inner</p></blockquote></div>"
        section = _tag(html)
        blocks = list(iter_story_blocks(section, ("blockquote", "p")))
        # Only the outer blockquote should appear, not the nested p
        assert len(blocks) == 1
        assert blocks[0].name == "blockquote"
