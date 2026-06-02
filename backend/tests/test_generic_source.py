"""Tests for the GenericSource adapter (unit-level, no HTTP)."""

from __future__ import annotations

from bs4 import BeautifulSoup

from novelai.sources.generic import GenericSource


def _soup(html: str) -> BeautifulSoup:
    return BeautifulSoup(html, "html.parser")


class TestGenericSourceHelpers:
    def test_key_is_generic(self) -> None:
        src = GenericSource()
        assert src.key == "generic"

    def test_normalize_novel_id_from_url(self) -> None:
        src = GenericSource()
        result = src.normalize_novel_id("https://example.com/novels/123")
        assert "example.com" in result
        assert "123" in result

    def test_normalize_novel_id_plain_string(self) -> None:
        src = GenericSource()
        result = src.normalize_novel_id("some-id")
        assert result == "some-id"

    def test_clean_soup_removes_script(self) -> None:
        soup = _soup("<div><p>text</p><script>evil()</script></div>")
        GenericSource._clean_soup(soup)
        assert soup.find("script") is None
        assert soup.find("p") is not None

    def test_clean_soup_removes_nav_and_footer(self) -> None:
        soup = _soup("<div><nav>nav</nav><p>body</p><footer>ft</footer></div>")
        GenericSource._clean_soup(soup)
        assert soup.find("nav") is None
        assert soup.find("footer") is None

    def test_find_body_with_article(self) -> None:
        soup = _soup("<html><body><article>Story here</article></body></html>")
        body = GenericSource._find_body(soup)
        assert body is not None
        assert body.name == "article"

    def test_find_body_with_main(self) -> None:
        soup = _soup('<html><body><main>content</main></body></html>')
        body = GenericSource._find_body(soup)
        assert body is not None
        assert body.name == "main"

    def test_find_body_falls_back_to_body_tag(self) -> None:
        soup = _soup("<html><body><div>loose text</div></body></html>")
        body = GenericSource._find_body(soup)
        assert body is not None

    def test_extract_title_from_h1(self) -> None:
        soup = _soup("<html><body><h1>My Novel</h1></body></html>")
        title = GenericSource._extract_title(soup)
        assert title == "My Novel"

    def test_extract_title_from_og_meta(self) -> None:
        soup = _soup('<html><head><meta property="og:title" content="OG Title"/></head><body></body></html>')
        title = GenericSource._extract_title(soup)
        assert title == "OG Title"

    def test_extract_title_returns_none_when_missing(self) -> None:
        soup = _soup("<html><body></body></html>")
        assert GenericSource._extract_title(soup) is None

    def test_extract_author_from_meta(self) -> None:
        soup = _soup('<html><head><meta name="author" content="Author Name"/></head><body></body></html>')
        author = GenericSource._extract_author(soup)
        assert author == "Author Name"

    def test_extract_author_returns_none_when_missing(self) -> None:
        soup = _soup("<html><body></body></html>")
        assert GenericSource._extract_author(soup) is None

    def test_request_headers(self) -> None:
        headers = GenericSource._request_headers()
        assert "User-Agent" in headers

    def test_request_headers_with_referer(self) -> None:
        headers = GenericSource._request_headers(referer="https://ref.com")
        assert headers["Referer"] == "https://ref.com"
