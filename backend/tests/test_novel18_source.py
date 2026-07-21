from __future__ import annotations

import httpx
import pytest

from novelai.core.errors import SourceError
from novelai.sources.novel18_syosetu import Novel18SyosetuSource


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
                "https://nl.syosetu.com/redirect/ageauth/"
                "?url=https%3A%2F%2Fnoc.syosetu.com%2Ftop%2Ftop%2F&hash=test"
            ),
            "<html><body>年齢確認 Cookie JavaScript redirect/ageauth/</body></html>",
        )


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
    assert metadata["status"] == "completed"
    assert metadata["source_publication_status"] == "完結済"


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
    assert metadata["status"] == "ongoing"
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
    assert metadata["status"] == "unknown"
    assert "source_publication_status" not in metadata


@pytest.mark.asyncio
async def test_novel18_fetch_metadata_uses_novel18_domain() -> None:
    source = Novel18SyosetuSource()
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
    source = Novel18SyosetuSource()
    root_url = "https://novel18.syosetu.com/n0813kx/"
    infotop_url = "https://novel18.syosetu.com/novelview/infotop/ncode/n0813kx/"

    async def fake_fetch_page(url: str, on_retry=None) -> str:
        if url == infotop_url:
            return """
            <html><body><table><tr><th>掲載状態</th><td>連載中</td></tr></table></body></html>
            """
        assert url == root_url
        links = "\n".join(
            f'<a href="/n0813kx/{index}/">Episode {index}</a>'
            for index in range(1, 13)
        )
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
