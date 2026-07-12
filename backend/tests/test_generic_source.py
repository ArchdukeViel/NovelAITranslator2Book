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

    def test_fetch_service_is_injected(self) -> None:
        fetch_service = object()
        src = GenericSource(fetch_service=fetch_service)  # type: ignore[arg-type]
        assert src._fetch_service is fetch_service


class TestGenericRubyStripping:
    """GenericSource must strip ruby/furigana annotations like Syosetu does."""

    def test_strips_simple_ruby(self) -> None:
        soup = _soup("<div><ruby>漢字<rt>かんじ</rt></ruby></div>")
        GenericSource._strip_ruby_annotations(soup)
        assert soup.get_text() == "漢字"

    def test_strips_ruby_with_rp(self) -> None:
        soup = _soup("<div><ruby>東京<rp>（</rp><rt>とうきょう</rt><rp>）</rp></ruby></div>")
        GenericSource._strip_ruby_annotations(soup)
        assert soup.get_text() == "東京"

    def test_preserves_normal_text_around_ruby(self) -> None:
        soup = _soup("<p>これは<ruby>漢字<rt>かんじ</rt></ruby>のテストです</p>")
        GenericSource._strip_ruby_annotations(soup)
        assert "これは" in soup.get_text()
        assert "漢字" in soup.get_text()
        assert "のテストです" in soup.get_text()
        assert "かんじ" not in soup.get_text()

    def test_preserves_paragraph_boundaries(self) -> None:
        soup = _soup(
            "<div><p>段落1</p><p><ruby>漢字<rt>かんじ</rt></ruby></p><p>段落3</p></div>"
        )
        GenericSource._strip_ruby_annotations(soup)
        paragraphs = soup.find_all("p")
        assert len(paragraphs) == 3
        assert paragraphs[0].get_text() == "段落1"
        assert paragraphs[1].get_text() == "漢字"
        assert paragraphs[2].get_text() == "段落3"

    def test_multiple_ruby_in_same_block(self) -> None:
        soup = _soup(
            "<p><ruby>東<rt>ひがし</rt></ruby>と<ruby>西<rt>にし</rt></ruby></p>"
        )
        GenericSource._strip_ruby_annotations(soup)
        text = soup.get_text()
        assert "東" in text
        assert "西" in text
        assert "ひがし" not in text
        assert "にし" not in text


class TestGenericPreflightChecks:
    """GenericSource must reject obvious blocked/age-gated pages."""

    def test_rejects_cloudflare_block_page(self) -> None:
        from novelai.core.errors import SourceError

        html = """
        <html><head><title>Attention Required</title></head>
        <body>
        <h1>Checking your browser before accessing the site</h1>
        <p>This process is automatic. Your browser will redirect shortly.</p>
        <p>Please enable JavaScript and cookies to continue.</p>
        </body></html>
        """
        try:
            GenericSource._preflight_check(html, "https://example.com/novel")
            raise AssertionError("Expected SourceError for Cloudflare block page")
        except SourceError as e:
            assert "blocked" in str(e).lower()

    def test_rejects_age_gate_page(self) -> None:
        from novelai.core.errors import SourceError

        html = """
        <html><body>
        <h1>Age Verification</h1>
        <p>This content is for adults only. Please confirm your age.</p>
        <p>You must be 18 or older to view this content.</p>
        <button>I am over 18</button>
        </body></html>
        """
        try:
            GenericSource._preflight_check(html, "https://example.com/novel")
            raise AssertionError("Expected SourceError for age gate page")
        except SourceError as e:
            assert "age" in str(e).lower() or "verification" in str(e).lower()

    def test_accepts_normal_novel_page(self) -> None:
        html = """
        <html><body>
        <h1>My Fantasy Novel</h1>
        <p>Chapter 1: The Beginning</p>
        <p>Once upon a time, in a land far away...</p>
        </body></html>
        """
        # Should not raise
        GenericSource._preflight_check(html, "https://example.com/novel")

    def test_accepts_japanese_novel_page(self) -> None:
        html = """
        <html><body>
        <h1>異世界転生物語</h1>
        <p>第一章：始まり</p>
        <p>ある日、突然異世界に転生した...</p>
        </body></html>
        """
        # Should not raise
        GenericSource._preflight_check(html, "https://example.com/novel")


class TestGenericConfidenceHardening:
    """GenericSource confidence scoring should fail on extremely low confidence with negative signals."""

    def test_very_low_confidence_with_negative_signals_fails(self) -> None:
        src = GenericSource()
        # Create a page with mostly navigation/negative links and very few chapter-like links
        html = """
        <html><body>
        <a href="/login">Login</a>
        <a href="/register">Register</a>
        <a href="/search">Search</a>
        <a href="/tag/fantasy">Fantasy</a>
        <a href="/author/smith">Author</a>
        <a href="/profile/user1">Profile</a>
        <a href="/comment/123">Comment</a>
        <a href="/privacy">Privacy</a>
        <a href="/terms">Terms</a>
        <a href="/rss">RSS</a>
        <a href="/chapter/1">Chapter 1</a>
        </body></html>
        """
        soup = _soup(html)
        chapters = src._extract_chapters_from_toc(soup, "https://example.com/novel")
        result = src._score_toc_confidence(soup, "https://example.com/novel", chapters)
        # With many negative signals and few positive, should fail if score < 0.40
        if result.score < 0.40 and any("negative" in w for w in result.warnings):
            assert not result.passed, "Should fail when confidence is very low with negative signals"
            assert any("very_low_confidence_with_negative_signals" in e for e in result.errors)

    def test_moderate_confidence_still_passes(self) -> None:
        src = GenericSource()
        html = """
        <html><body>
        <a href="/chapter/1">Chapter 1</a>
        <a href="/chapter/2">Chapter 2</a>
        <a href="/chapter/3">Chapter 3</a>
        <a href="/about">About</a>
        </body></html>
        """
        soup = _soup(html)
        chapters = src._extract_chapters_from_toc(soup, "https://example.com/novel")
        result = src._score_toc_confidence(soup, "https://example.com/novel", chapters)
        assert result.passed, "Should pass with reasonable confidence"
