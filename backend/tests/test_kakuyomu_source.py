from __future__ import annotations

import pytest

from novelai.sources.kakuyomu import KakuyomuSource


def test_normalize_novel_id_accepts_work_and_episode_urls() -> None:
    source = KakuyomuSource()

    assert source.normalize_novel_id("https://kakuyomu.jp/works/822139845959461179/") == "822139845959461179"
    assert (
        source.normalize_novel_id("https://kakuyomu.jp/works/822139845959461179/episodes/822139845959540845")
        == "822139845959461179"
    )


def test_parse_metadata_html_collects_episode_links_in_order() -> None:
    source = KakuyomuSource()
    html = """
    <html>
      <body>
        <main id="contentMain">
          <h1 class="widget-workTitle">霧の旅</h1>
          <div class="widget-authorName">作家B</div>
          <section class="widget-toc">
            <a class="widget-toc-episode-episodeTitle" href="/works/822139845959461179/episodes/822139845959540845">
              <span class="widget-toc-episodeTitleLabel">第1話 はじまり</span>
            </a>
            <a class="widget-toc-episode-episodeTitle" href="/works/822139845959461179/episodes/822139845959540999">
              <span class="widget-toc-episodeTitleLabel">第2話 続き</span>
            </a>
            <a class="widget-toc-episode-episodeTitle" href="/works/822139845959461179/episodes/822139845959540845">
              重複リンク
            </a>
          </section>
          <time datetime="2026-03-01T09:00:00+09:00">2026/03/01</time>
          <time datetime="2026-03-03T10:30:00+09:00">2026/03/03</time>
        </main>
      </body>
    </html>
    """

    metadata = source._parse_metadata_html(html, "https://kakuyomu.jp/works/822139845959461179/")

    assert metadata["source"] == "kakuyomu"
    assert metadata["title"] == "霧の旅"
    assert metadata["author"] == "作家B"
    assert metadata["published_at"] == "2026-03-01T09:00:00+09:00"
    assert metadata["updated_at"] == "2026-03-03T10:30:00+09:00"
    assert metadata["chapters"] == [
        {
            "id": "1",
            "num": 1,
            "title": "第1話 はじまり",
            "url": "https://kakuyomu.jp/works/822139845959461179/episodes/822139845959540845",
            "source_episode_id": "822139845959540845",
        },
        {
            "id": "2",
            "num": 2,
            "title": "第2話 続き",
            "url": "https://kakuyomu.jp/works/822139845959461179/episodes/822139845959540999",
            "source_episode_id": "822139845959540999",
        },
    ]


def test_parse_chapter_html_preserves_structure_and_strips_furigana() -> None:
    source = KakuyomuSource()
    html = """
    <html>
      <body>
        <article>
          <div class="widget-episodeBody js-episode-body">
            <p>霧の朝、<em>彼女</em>は目を覚ました。</p>
            <p><ruby>古道具屋<rt>ふるどうぐや</rt></ruby>の前には猫がいた。<br />路地は静かだ。</p>
            <blockquote>「今日は何かが起きる」</blockquote>
            <hr />
            <p>次の場面へ。</p>
          </div>
        </article>
      </body>
    </html>
    """

    chapter_text = source._parse_chapter_html(html)

    assert chapter_text == (
        "霧の朝、彼女は目を覚ました。\n\n"
        "古道具屋の前には猫がいた。\n路地は静かだ。\n\n"
        "「今日は何かが起きる」\n\n"
        "------------------------------------------------------------\n\n"
        "次の場面へ。"
    )


def test_parse_chapter_html_preserves_inline_image_placeholders() -> None:
    source = KakuyomuSource()
    html = """
    <html>
      <body>
        <article>
          <div class="widget-episodeBody js-episode-body">
            <p>Scene setup.</p>
            <figure>
              <img src="https://kakuyomu.jp/images/scene.png" alt="Morning alley" />
            </figure>
            <p>Scene follow-up.</p>
          </div>
        </article>
      </body>
    </html>
    """

    chapter_text = source._parse_chapter_html(html)

    assert chapter_text == (
        "Scene setup.\n\n"
        "[Image: Morning alley]\n\n"
        "Scene follow-up."
    )


def test_parse_chapter_payload_extracts_image_metadata() -> None:
    source = KakuyomuSource()
    html = """
    <html>
      <body>
        <article>
          <div class="widget-episodeBody js-episode-body">
            <p>Scene setup.</p>
            <figure>
              <img src="/images/scene.png" alt="Morning alley" />
            </figure>
            <p>Scene follow-up.</p>
          </div>
        </article>
      </body>
    </html>
    """

    payload = source._parse_chapter_payload(html, "https://kakuyomu.jp/works/822139845959461179/episodes/822139845959540845")

    assert payload["text"] == (
        "Scene setup.\n\n"
        "[Image: Morning alley]\n\n"
        "Scene follow-up."
    )
    assert payload["images"] == [
        {
            "index": 0,
            "placeholder": "[Image: Morning alley]",
            "original_url": "https://kakuyomu.jp/images/scene.png",
            "alt": "Morning alley",
            "title": None,
            "filename": "scene.png",
        }
    ]


@pytest.mark.asyncio
async def test_fetch_metadata_normalizes_episode_url_to_work_root() -> None:
    source = KakuyomuSource()
    episode_url = "https://kakuyomu.jp/works/822139845959461179/episodes/822139845959540845"
    work_url = "https://kakuyomu.jp/works/822139845959461179"

    async def fake_fetch_page(url: str) -> str:
        assert url == work_url
        return """
        <html>
          <body>
            <main>
              <h1 class="widget-workTitle">霧の旅</h1>
              <a href="/works/822139845959461179/episodes/822139845959540845">第1話</a>
            </main>
          </body>
        </html>
        """

    source._fetch_page = fake_fetch_page  # type: ignore[method-assign]
    metadata = await source.fetch_metadata(episode_url)

    assert metadata["source_url"] == work_url
    assert metadata["chapters"][0]["url"] == episode_url


# ---------------------------------------------------------------------------
# Preflight check tests
# ---------------------------------------------------------------------------


class TestKakuyomuPreflightChecks:
    """KakuyomuSource must reject obvious blocked/age-gated pages."""

    def test_rejects_cloudflare_block_page(self) -> None:
        from novelai.core.errors import SourceError

        html = """
        <html><head><title>Attention Required</title></head>
        <body>
        <h1>Checking your browser before accessing the site</h1>
        <p>This process is automatic. Your browser will redirect shortly.</p>
        <p>Please enable JavaScript and cookies to continue.</p>
        <p>cf-ray: 1234567890</p>
        </body></html>
        """
        try:
            KakuyomuSource._preflight_check(html, "https://kakuyomu.jp/works/123")
            assert False, "Expected SourceError for Cloudflare block page"
        except SourceError as e:
            assert "blocked" in str(e).lower()

    def test_rejects_access_denied_page(self) -> None:
        from novelai.core.errors import SourceError

        html = """
        <html><head><title>Access Denied</title></head>
        <body>
        <h1>Access Denied</h1>
        <p>You do not have permission to access this resource.</p>
        </body></html>
        """
        try:
            KakuyomuSource._preflight_check(html, "https://kakuyomu.jp/works/123")
            assert False, "Expected SourceError for access denied page"
        except SourceError as e:
            assert "blocked" in str(e).lower()

    def test_rejects_age_gate_page(self) -> None:
        from novelai.core.errors import SourceError

        html = """
        <html><body>
        <h1>年齢確認</h1>
        <p>このページには成人向けコンテンツが含まれています。</p>
        <p>あなたは18歳以上ですか？</p>
        <button>はい</button>
        </body></html>
        """
        try:
            KakuyomuSource._preflight_check(html, "https://kakuyomu.jp/works/123")
            assert False, "Expected SourceError for age gate page"
        except SourceError as e:
            assert "age" in str(e).lower() or "verification" in str(e).lower()

    def test_accepts_normal_kakuyomu_metadata_page(self) -> None:
        html = """
        <html>
          <body>
            <main>
              <h1 class="widget-workTitle">異世界転生物語</h1>
              <div class="widget-authorName">作家A</div>
              <section class="widget-toc">
                <a href="/works/123/episodes/456">第1話</a>
              </section>
            </main>
          </body>
        </html>
        """
        # Should not raise
        KakuyomuSource._preflight_check(html, "https://kakuyomu.jp/works/123")

    def test_accepts_normal_kakuyomu_chapter_page(self) -> None:
        html = """
        <html>
          <body>
            <article>
              <div class="widget-episodeBody">
                <p>ある日、突然異世界に転生した。</p>
                <p>目の前には美しい草原が広がっていた。</p>
              </div>
            </article>
          </body>
        </html>
        """
        # Should not raise
        KakuyomuSource._preflight_check(html, "https://kakuyomu.jp/works/123/episodes/456")


# ---------------------------------------------------------------------------
# UTF-8 decoding tests
# ---------------------------------------------------------------------------


class TestKakuyomuDecoding:
    """KakuyomuSource must force-decode responses as UTF-8."""

    def test_decode_utf8_body(self) -> None:
        body = "日本語テキスト".encode("utf-8")
        result = KakuyomuSource._decode_page_body(body)
        assert result == "日本語テキスト"

    def test_decode_invalid_bytes_with_replace(self) -> None:
        # Invalid UTF-8 byte sequence
        body = b"\xff\xfe\xfd"
        result = KakuyomuSource._decode_page_body(body)
        # Should produce replacement characters, not crash
        assert "\ufffd" in result

    def test_decode_mixed_valid_invalid(self) -> None:
        body = b"\xe6\x97\xa5\xe6\x9c\xac\xe8\xaa\x9e\xff\xfe"  # "日本語" + invalid
        result = KakuyomuSource._decode_page_body(body)
        assert "日本語" in result


# ---------------------------------------------------------------------------
# Request headers tests
# ---------------------------------------------------------------------------


class TestKakuyomuHeaders:
    """KakuyomuSource must send appropriate request headers."""

    def test_request_headers_include_user_agent(self) -> None:
        headers = KakuyomuSource._request_headers()
        assert "User-Agent" in headers
        assert "Mozilla" in headers["User-Agent"]

    def test_user_agent_is_browser_like(self) -> None:
        headers = KakuyomuSource._request_headers()
        ua = headers["User-Agent"]
        # Should look like a real browser, not a bot
        assert "AppleWebKit" in ua or "Gecko" in ua


# ---------------------------------------------------------------------------
# URL canonicalization tests
# ---------------------------------------------------------------------------


class TestKakuyomuURLCanonicalization:
    """KakuyomuSource must construct work URLs without trailing slashes."""

    def test_normalize_url_has_no_trailing_slash(self) -> None:
        source = KakuyomuSource()
        url = source._normalize_url("822139845959461179")
        assert url == "https://kakuyomu.jp/works/822139845959461179"
        assert not url.endswith("/")

    def test_normalize_url_strips_trailing_slash_from_input(self) -> None:
        source = KakuyomuSource()
        url = source._normalize_url("https://kakuyomu.jp/works/822139845959461179/")
        assert url == "https://kakuyomu.jp/works/822139845959461179"

    def test_normalize_url_handles_episode_input(self) -> None:
        source = KakuyomuSource()
        url = source._normalize_url(
            "https://kakuyomu.jp/works/822139845959461179/episodes/822139845959540845"
        )
        assert url == "https://kakuyomu.jp/works/822139845959461179"
