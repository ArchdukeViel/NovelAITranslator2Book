from __future__ import annotations

import httpx
import pytest

from novelai.core.errors import SourceError
from novelai.infrastructure.http.fetch_service import FetchResult
from novelai.sources.novel18_syosetu import Novel18SyosetuSource
from tests.test_fetch_service import FakeFetchService


def test_novel18_matches_and_normalizes_root_and_chapter_urls() -> None:
    source = Novel18SyosetuSource()

    assert source.can_handle("https://novel18.syosetu.com/n0813kx/")
    assert source.can_handle("https://novel18.syosetu.com/n0813kx/1/")
    assert source.can_handle("https://noc.syosetu.com/n0813kx/")
    assert source.normalize_novel_id("https://novel18.syosetu.com/n0813kx/1/") == "n0813kx"
    assert source._normalize_url("https://noc.syosetu.com/n0813kx/1/") == "https://noc.syosetu.com/n0813kx/"


def test_novel18_builds_adult_confirmation_cookie() -> None:
    source = Novel18SyosetuSource()

    cookies = source._build_request_cookies()

    assert cookies.get("over18", domain="novel18.syosetu.com", path="/") == "yes"


def test_novel18_raises_clear_error_for_age_gate_redirect() -> None:
    source = Novel18SyosetuSource()

    with pytest.raises(SourceError, match="age verification page"):
        source._validate_fetched_page(
            "https://novel18.syosetu.com/n0813kx/",
            httpx.URL(
                "https://nl.syosetu.com/redirect/ageauth/?url=https%3A%2F%2Fnoc.syosetu.com%2Ftop%2Ftop%2F&hash=test"
            ),
            "<html><body>年齢確認 Cookie JavaScript redirect/ageauth/</body></html>",
        )


@pytest.mark.asyncio
async def test_novel18_follows_age_gate_and_parses_only_actual_chapter() -> None:
    chapter_url = "https://novel18.syosetu.com/n0813kx/1/"
    target_url = chapter_url
    gate_url = (
        "https://nl.syosetu.com/redirect/ageauth/?url=https%3A%2F%2Fnovel18.syosetu.com%2Fn0813kx%2F1%2F&hash=test"
    )
    gate_html = """
    <html><head><title>年齢確認</title></head><body>
      <h1>年齢確認</h1>
      <p>18歳未満閲覧禁止ページです。</p>
      <a id="yes18" data-url="https://novel18.syosetu.com/n0813kx/1/">Enter</a>
    </body></html>
    """
    chapter_html = """
    <html><body>
      <div class="p-novel__text p-novel__text--body js-novel-text">
        <p>本文には18歳未満の登場人物についての記述がある。</p>
        <p>これは実際の章本文であり、年齢確認ページではない。</p>
      </div>
    </body></html>
    """
    service = FakeFetchService("")
    responses = [
        FetchResult(
            requested_url=chapter_url,
            final_url=gate_url,
            status_code=200,
            headers={"content-type": "text/html"},
            text=gate_html,
            body=gate_html.encode("utf-8"),
            source_key="novel18_syosetu",
            fetched_at="2026-06-04T00:00:00Z",
        ),
        FetchResult(
            requested_url=target_url,
            final_url=target_url,
            status_code=200,
            headers={"content-type": "text/html"},
            text=chapter_html,
            body=chapter_html.encode("utf-8"),
            source_key="novel18_syosetu",
            fetched_at="2026-06-04T00:00:00Z",
        ),
    ]

    async def sequenced_get_text(
        url: str,
        *,
        source_key: str,
        referer=None,
        headers=None,
        cookies=None,
        on_retry=None,
        profile=None,
        kind="html",
        use_cache=True,
    ) -> FetchResult:
        service.calls.append({"url": url, "referer": referer, "use_cache": use_cache, "cookies": cookies})
        return responses.pop(0)

    service.get_text = sequenced_get_text  # type: ignore[method-assign]
    source = Novel18SyosetuSource(fetch_service=service)

    payload = await source.fetch_chapter_payload(chapter_url)

    assert [call["url"] for call in service.calls] == [chapter_url, target_url]
    assert service.calls[1]["use_cache"] is False
    assert payload["text"] == (
        "本文には18歳未満の登場人物についての記述がある。\n\nこれは実際の章本文であり、年齢確認ページではない。"
    )
    assert "年齢確認" in payload["text"]
    assert "Enter" not in payload["text"]


@pytest.mark.asyncio
async def test_novel18_age_gate_retry_is_bounded_and_reports_unresolved_gate() -> None:
    chapter_url = "https://novel18.syosetu.com/n0813kx/1/"
    gate_url = (
        "https://nl.syosetu.com/redirect/ageauth/?url=https%3A%2F%2Fnovel18.syosetu.com%2Fn0813kx%2F1%2F&hash=test"
    )
    gate_html = f'<html><body><h1>年齢確認</h1><a id="yes18" data-url="{chapter_url}">Enter</a></body></html>'
    service = FakeFetchService("")
    responses = [
        FetchResult(
            requested_url=chapter_url,
            final_url=gate_url,
            status_code=200,
            headers={},
            text=gate_html,
            body=gate_html.encode("utf-8"),
            source_key="novel18_syosetu",
            fetched_at="2026-06-04T00:00:00Z",
        ),
        FetchResult(
            requested_url=chapter_url,
            final_url=gate_url,
            status_code=200,
            headers={},
            text=gate_html,
            body=gate_html.encode("utf-8"),
            source_key="novel18_syosetu",
            fetched_at="2026-06-04T00:00:00Z",
        ),
    ]

    async def sequenced_get_text(
        url: str,
        *,
        source_key: str,
        referer=None,
        headers=None,
        cookies=None,
        on_retry=None,
        profile=None,
        kind="html",
        use_cache=True,
    ) -> FetchResult:
        service.calls.append({"url": url, "use_cache": use_cache})
        return responses.pop(0)

    service.get_text = sequenced_get_text  # type: ignore[method-assign]
    source = Novel18SyosetuSource(fetch_service=service)

    with pytest.raises(SourceError, match="bounded public confirmation flow"):
        await source.fetch_chapter_payload(chapter_url)

    assert len(service.calls) == 2


def test_novel18_parse_metadata_html_extracts_completed_publication_status() -> None:
    source = Novel18SyosetuSource()
    html = """
    <html>
      <body>
        <h1 class="p-novel__title">Completed Adult Work</h1>
        <table>
          <tr><th>掲載状態</th><td>完結済</td></tr>
        </table>
      </body>
    </html>
    """

    metadata = source._parse_metadata_html(html, "https://novel18.syosetu.com/n0813kx/")

    assert metadata["publication_status"] == "completed"
    assert metadata["source_publication_status"] == "完結済"


def test_novel18_parse_metadata_html_keeps_work_metadata_separate_from_age_notice() -> None:
    source = Novel18SyosetuSource()
    html = """
    <html>
      <head><title>年齢確認</title></head>
      <body>
        <section class="age-gate">
          <h1>年齢確認</h1>
          <p>18歳未満閲覧禁止ページです。</p>
          <button id="yes18">Enter</button>
        </section>
        <main>
          <h1 class="p-novel__title">  Canonical Adult Story  </h1>
          <div id="novel_writername">  Canonical Adult Author  </div>
          <div id="novel_ex">
            Actual synopsis line. <br />


            Second actual synopsis line.
          </div>
          <a href="/n0813kx/1/">First chapter</a>
        </main>
      </body>
    </html>
    """

    metadata = source._parse_metadata_html(html, "https://novel18.syosetu.com/n0813kx/")

    assert metadata["title"] == "Canonical Adult Story"
    assert metadata["author"] == "Canonical Adult Author"
    assert metadata["synopsis"] == "Actual synopsis line.\nSecond actual synopsis line."
    assert "年齢確認" not in metadata["title"]
    assert "年齢確認" not in metadata["synopsis"]


def test_novel18_flat_episode_titles_preserve_numeric_prefixes_and_no_sections() -> None:
    source = Novel18SyosetuSource()
    html = """
    <html>
      <body>
        <h1 class="p-novel__title">Flat Adult Story</h1>
        <a href="/n3266mn/1/">1話　聖水要員</a>
        <a href="/n3266mn/2/">2話　鉄級の聖水女</a>
      </body>
    </html>
    """

    metadata = source._parse_metadata_html(html, "https://novel18.syosetu.com/n3266mn/")

    assert metadata["work_structure"] == "episodes"
    assert [chapter["title"] for chapter in metadata["chapters"]] == ["1話　聖水要員", "2話　鉄級の聖水女"]
    assert all("section_title" not in chapter for chapter in metadata["chapters"])


def test_novel18_reuses_structural_section_metadata_without_adult_specific_hierarchy() -> None:
    source = Novel18SyosetuSource()
    html = """
    <html>
      <body>
        <h1 class="p-novel__title">Sectioned Adult Story</h1>
        <div class="p-eplist__chapter-title">第一部　地下迷宮</div>
        <a href="/n0813kx/1/">プロローグ</a>
        <a href="/n0813kx/2/">第一話</a>
      </body>
    </html>
    """

    metadata = source._parse_metadata_html(html, "https://novel18.syosetu.com/n0813kx/")

    assert [chapter["section_title"] for chapter in metadata["chapters"]] == ["第一部　地下迷宮"] * 2
    assert all(chapter["section_source_id"] is None for chapter in metadata["chapters"])
    assert [chapter["section_ordinal"] for chapter in metadata["chapters"]] == [1, 1]


def test_novel18_narrative_synopsis_retains_adult_story_prose() -> None:
    source = Novel18SyosetuSource()
    html = """
    <html>
      <body>
        <h1 class="p-novel__title">Adult Story</h1>
        <div id="novel_writername">Author</div>
        <div id="novel_ex">
          18歳の主人公は女冒険者を聖水要員として扱っていた。<br />
          彼女は迷宮で彼の運命を変える。<br />
          ※更新に関するお知らせ。
        </div>
        <a href="/n0813kx/1/">Chapter One</a>
      </body>
    </html>
    """

    metadata = source._parse_metadata_html(html, "https://novel18.syosetu.com/n0813kx/")

    assert metadata["narrative_synopsis"] == (
        "18歳の主人公は女冒険者を聖水要員として扱っていた。\n彼女は迷宮で彼の運命を変える。"
    )
    assert "18歳" in metadata["narrative_synopsis"]
    assert "聖水要員" in metadata["narrative_synopsis"]


def test_novel18_parse_metadata_html_extracts_ongoing_publication_status() -> None:
    source = Novel18SyosetuSource()
    html = """
    <html>
      <body>
        <h1 class="p-novel__title">Ongoing Adult Work</h1>
        <table>
          <tr><th>掲載状態</th><td>連載中</td></tr>
        </table>
      </body>
    </html>
    """

    metadata = source._parse_metadata_html(html, "https://novel18.syosetu.com/n0813kx/")

    assert metadata["publication_status"] == "ongoing"
    assert metadata["source_publication_status"] == "連載中"


def test_novel18_parse_metadata_html_leaves_ambiguous_publication_status_unknown() -> None:
    source = Novel18SyosetuSource()
    html = """
    <html>
      <body>
        <h1 class="p-novel__title">Ambiguous Adult Work</h1>
        <table>
          <tr><th>作品種別</th><td>短編</td></tr>
        </table>
      </body>
    </html>
    """

    metadata = source._parse_metadata_html(html, "https://novel18.syosetu.com/n0813kx/")

    assert metadata["publication_status"] == "unknown"
    assert "source_publication_status" not in metadata


@pytest.mark.asyncio
async def test_novel18_fetch_metadata_uses_novel18_domain() -> None:
    source = Novel18SyosetuSource(fetch_service=FakeFetchService(""))
    seen_urls: list[str] = []
    infotop_url = "https://novel18.syosetu.com/novelview/infotop/ncode/n0813kx/"

    async def fake_fetch_page(url: str, on_retry=None) -> str:
        seen_urls.append(url)
        if url == infotop_url:
            return """
            <html><body><table><tr><th>掲載状態</th><td>完結済</td></tr></table></body></html>
            """
        return """
        <html>
          <body>
            <h1 class="p-novel__title">夜の物語</h1>
            <div id="novel_writername">作者C</div>
            <a href="/n0813kx/1/">第一話</a>
          </body>
        </html>
        """

    source._fetch_page = fake_fetch_page  # type: ignore[method-assign]
    metadata = await source.fetch_metadata("https://novel18.syosetu.com/n0813kx/1/")

    assert seen_urls == ["https://novel18.syosetu.com/n0813kx/", infotop_url]
    assert metadata["source_key"] == "novel18_syosetu"
    assert metadata["title"] == "夜の物語"
    assert metadata["chapters"][0]["url"] == "https://novel18.syosetu.com/n0813kx/1/"
    assert metadata["publication_status"] == "completed"


@pytest.mark.asyncio
async def test_novel18_fetch_metadata_caps_single_page_flat_toc() -> None:
    source = Novel18SyosetuSource(fetch_service=FakeFetchService(""))
    root_url = "https://novel18.syosetu.com/n0813kx/"
    infotop_url = "https://novel18.syosetu.com/novelview/infotop/ncode/n0813kx/"

    async def fake_fetch_page(url: str, on_retry=None) -> str:
        if url == infotop_url:
            return """
            <html><body><table><tr><th>掲載状態</th><td>連載中</td></tr></table></body></html>
            """
        assert url == root_url
        links = "\n".join(f'<a href="/n0813kx/{index}/">Episode {index}</a>' for index in range(1, 13))
        return f"""
        <html>
          <body>
            <h1 class="p-novel__title">Night Story</h1>
            <div id="novel_writername">Author C</div>
            {links}
          </body>
        </html>
        """

    source._fetch_page = fake_fetch_page  # type: ignore[method-assign]
    full = await source.fetch_metadata(root_url)
    capped = await source.fetch_metadata(root_url, max_chapter=3)

    assert len(full["chapters"]) == 12
    assert [chapter["id"] for chapter in capped["chapters"]] == ["1", "2", "3"]
    assert all("part" not in chapter for chapter in full["chapters"])
