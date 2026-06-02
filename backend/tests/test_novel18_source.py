from __future__ import annotations

import httpx
import pytest

from novelai.core.errors import SourceError
from novelai.sources.novel18_syosetu import Novel18SyosetuSource


def test_novel18_matches_and_normalizes_root_and_chapter_urls() -> None:
    source = Novel18SyosetuSource()

    assert source.matches_url("https://novel18.syosetu.com/n0813kx/")
    assert source.matches_url("https://novel18.syosetu.com/n0813kx/1/")
    assert source.matches_url("https://noc.syosetu.com/n0813kx/")
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


@pytest.mark.asyncio
async def test_novel18_fetch_metadata_uses_novel18_domain() -> None:
    source = Novel18SyosetuSource()
    seen_urls: list[str] = []

    async def fake_fetch_page(url: str) -> str:
        seen_urls.append(url)
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

    assert seen_urls == ["https://novel18.syosetu.com/n0813kx/"]
    assert metadata["source"] == "novel18_syosetu"
    assert metadata["title"] == "夜の物語"
    assert metadata["chapters"][0]["url"] == "https://novel18.syosetu.com/n0813kx/1/"
