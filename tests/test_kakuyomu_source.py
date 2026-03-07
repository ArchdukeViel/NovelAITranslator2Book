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


@pytest.mark.asyncio
async def test_fetch_metadata_normalizes_episode_url_to_work_root() -> None:
    source = KakuyomuSource()
    episode_url = "https://kakuyomu.jp/works/822139845959461179/episodes/822139845959540845"
    work_url = "https://kakuyomu.jp/works/822139845959461179/"

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
