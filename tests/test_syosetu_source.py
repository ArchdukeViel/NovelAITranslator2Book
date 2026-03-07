from __future__ import annotations

import pytest

from novelai.sources.syosetu_ncode import SyosetuNcodeSource


def test_normalize_novel_id_accepts_chapter_and_infotop_urls() -> None:
    source = SyosetuNcodeSource()

    assert source.normalize_novel_id("https://ncode.syosetu.com/n8733gf/1/") == "n8733gf"
    assert source.normalize_novel_id("https://ncode.syosetu.com/n6656lw/") == "n6656lw"
    assert (
        source.normalize_novel_id("https://ncode.syosetu.com/novelview/infotop/ncode/n8733gf/")
        == "n8733gf"
    )


def test_parse_metadata_html_detects_multi_chapter_series() -> None:
    source = SyosetuNcodeSource()
    html = """
    <html>
      <body>
        <h1 class="p-novel__title">Long Story</h1>
        <div class="p-novel__author">Author Name</div>
        <a href="/n8733gf/1/">Chapter One</a>
        <a href="/n8733gf/2/">Chapter Two</a>
      </body>
    </html>
    """

    metadata = source._parse_metadata_html(html, "https://ncode.syosetu.com/n8733gf/")

    assert metadata["title"] == "Long Story"
    assert metadata["author"] == "Author Name"
    assert metadata["chapters"] == [
        {
            "id": "1",
            "num": 1,
            "title": "Chapter One",
            "url": "https://ncode.syosetu.com/n8733gf/1/",
        },
        {
            "id": "2",
            "num": 2,
            "title": "Chapter Two",
            "url": "https://ncode.syosetu.com/n8733gf/2/",
        },
    ]


def test_parse_metadata_html_synthesizes_single_chapter_for_one_shot() -> None:
    source = SyosetuNcodeSource()
    html = """
    <html>
      <body>
        <h1 class="p-novel__title">Short Story</h1>
        <div id="novel_writername">Author Name</div>
        <div id="novel_honbun">
          <p>Single chapter text.</p>
        </div>
      </body>
    </html>
    """

    metadata = source._parse_metadata_html(html, "https://ncode.syosetu.com/n6656lw/")

    assert metadata["chapters"] == [
        {
            "id": "1",
            "num": 1,
            "title": "Short Story",
            "url": "https://ncode.syosetu.com/n6656lw/",
        }
    ]


def test_parse_chapter_html_preserves_preface_afterword_and_separator_lines() -> None:
    source = SyosetuNcodeSource()
    html = """
    <html>
      <body>
        <div class="p-novel__text p-novel__text--preface">
          <p>Preface note.</p>
        </div>
        <div class="p-novel__text p-novel__text--body js-novel-text">
          <p><ruby>Kanji<rt>reading</rt></ruby> line one.<br />Line two.</p>
          <p>Second paragraph.</p>
        </div>
        <div class="p-novel__text p-novel__text--afterword">
          <hr />
          <p>Afterword note.</p>
        </div>
      </body>
    </html>
    """

    chapter_text = source._parse_chapter_html(html)

    assert (
        chapter_text
        == "Preface note.\n\nKanji line one.\nLine two.\n\nSecond paragraph.\n\n"
        "------------------------------------------------------------\n\nAfterword note."
    )


@pytest.mark.asyncio
async def test_fetch_metadata_collects_all_paginated_chapter_pages() -> None:
    source = SyosetuNcodeSource()
    root_url = "https://ncode.syosetu.com/n8733gf/"
    pages = {
        root_url: """
        <html>
          <body>
            <h1 class="p-novel__title">Paged Story</h1>
            <div id="novel_writername">Author Name</div>
            <a href="/n8733gf/1/">Chapter One</a>
            <a href="/n8733gf/2/">Chapter Two</a>
            <a href="/n8733gf/?p=2">2</a>
          </body>
        </html>
        """,
        f"{root_url}?p=2": """
        <html>
          <body>
            <a href="/n8733gf/3/">Chapter Three</a>
            <a href="/n8733gf/4/">Chapter Four</a>
          </body>
        </html>
        """,
    }

    async def fake_fetch_page(url: str) -> str:
        return pages[url]

    source._fetch_page = fake_fetch_page  # type: ignore[method-assign]
    metadata = await source.fetch_metadata(root_url)

    assert [chapter["id"] for chapter in metadata["chapters"]] == ["1", "2", "3", "4"]
