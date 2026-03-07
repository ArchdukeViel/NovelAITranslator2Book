from __future__ import annotations

import pytest

from novelai.sources.novel18_syosetu import Novel18SyosetuSource


def test_novel18_matches_and_normalizes_root_and_chapter_urls() -> None:
    source = Novel18SyosetuSource()

    assert source.matches_url("https://novel18.syosetu.com/n0813kx/")
    assert source.matches_url("https://novel18.syosetu.com/n0813kx/1/")
    assert source.normalize_novel_id("https://novel18.syosetu.com/n0813kx/1/") == "n0813kx"


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
