from __future__ import annotations

import httpx
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


def test_decode_page_response_uses_utf8_when_charset_is_missing() -> None:
    response = httpx.Response(
        200,
        content="TS刑事　如月真琴の憂鬱".encode("utf-8"),
        headers={"content-type": "text/html"},
    )

    assert SyosetuNcodeSource._decode_page_response(response) == "TS刑事　如月真琴の憂鬱"


def test_parse_metadata_html_extracts_completed_publication_status() -> None:
    source = SyosetuNcodeSource()
    html = """
    <html>
      <body>
        <h1 class="p-novel__title">Completed Story</h1>
        <table>
          <tr><th>掲載状態</th><td>完結済</td></tr>
        </table>
      </body>
    </html>
    """

    metadata = source._parse_metadata_html(html, "https://ncode.syosetu.com/n8733gf/")

    assert metadata["publication_status"] == "completed"
    assert metadata["status"] == "completed"
    assert metadata["source_publication_status"] == "完結済"


def test_parse_metadata_html_extracts_ongoing_publication_status() -> None:
    source = SyosetuNcodeSource()
    html = """
    <html>
      <body>
        <h1 class="p-novel__title">Ongoing Story</h1>
        <table>
          <tr><th>掲載状態</th><td>連載中</td></tr>
        </table>
      </body>
    </html>
    """

    metadata = source._parse_metadata_html(html, "https://ncode.syosetu.com/n8733gf/")

    assert metadata["publication_status"] == "ongoing"
    assert metadata["status"] == "ongoing"
    assert metadata["source_publication_status"] == "連載中"


def test_parse_metadata_html_leaves_ambiguous_publication_status_unknown() -> None:
    source = SyosetuNcodeSource()
    html = """
    <html>
      <body>
        <h1 class="p-novel__title">Ambiguous Story</h1>
        <table>
          <tr><th>作品種別</th><td>短編</td></tr>
        </table>
      </body>
    </html>
    """

    metadata = source._parse_metadata_html(html, "https://ncode.syosetu.com/n8733gf/")

    assert metadata["publication_status"] == "unknown"
    assert metadata["status"] == "unknown"
    assert "source_publication_status" not in metadata


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


def test_parse_metadata_html_detects_chapter_parts_and_source_dates() -> None:
    source = SyosetuNcodeSource()
    html = """
    <html>
      <body>
        <h1 class="p-novel__title">Long Story</h1>
        <div class="p-novel__author">Author Name</div>
        <div class="chapter_title">Part One: The Eventful First Year</div>
        <dl class="novel_sublist2">
          <dd class="subtitle"><a href="/n8733gf/1/">Prologue</a></dd>
          <dt class="long_update">2025/01/13 20:00</dt>
        </dl>
        <dl class="novel_sublist2">
          <dd class="subtitle"><a href="/n8733gf/2/">Episode 1</a></dd>
          <dt class="long_update">2025/01/14 19:00</dt>
        </dl>
      </body>
    </html>
    """

    metadata = source._parse_metadata_html(html, "https://ncode.syosetu.com/n8733gf/")

    assert metadata["chapters"] == [
        {
            "id": "1",
            "num": 1,
            "title": "Prologue",
            "url": "https://ncode.syosetu.com/n8733gf/1/",
            "part": "Part One: The Eventful First Year",
            "date_added": "2025/01/13 20:00",
        },
        {
            "id": "2",
            "num": 2,
            "title": "Episode 1",
            "url": "https://ncode.syosetu.com/n8733gf/2/",
            "part": "Part One: The Eventful First Year",
            "date_added": "2025/01/14 19:00",
        },
    ]


def test_parse_metadata_html_counts_episodes_not_arc_headings_and_preserves_groups() -> None:
    source = SyosetuNcodeSource()
    html = """
    <html>
      <body>
        <h1 class="p-novel__title">Arc Story</h1>
        <h2 class="chapter_title">Chapter 1: 8 Years Old</h2>
        <a href="/n8733gf/1/">Prologue</a>
        <a href="/n8733gf/2/">First Day</a>
        <h2 class="chapter_title">Chapter 2: 12 Years Old</h2>
        <a href="/n8733gf/3/">Second Arc Opens</a>
        <a href="/n8733gf/4/">Second Arc Continues</a>
      </body>
    </html>
    """

    metadata = source._parse_metadata_html(html, "https://ncode.syosetu.com/n8733gf/")

    assert [chapter["id"] for chapter in metadata["chapters"]] == ["1", "2", "3", "4"]
    assert [chapter["part"] for chapter in metadata["chapters"]] == [
        "Chapter 1: 8 Years Old",
        "Chapter 1: 8 Years Old",
        "Chapter 2: 12 Years Old",
        "Chapter 2: 12 Years Old",
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


def test_parse_chapter_html_preserves_inline_image_placeholders() -> None:
    source = SyosetuNcodeSource()
    html = """
    <html>
      <body>
        <div class="p-novel__text p-novel__text--body js-novel-text">
          <p>Before the illustration.</p>
          <img src="https://example.com/scene.png" alt="Scene illustration" />
          <p>After the illustration.</p>
        </div>
      </body>
    </html>
    """

    chapter_text = source._parse_chapter_html(html)

    assert chapter_text == (
        "Before the illustration.\n\n"
        "[Image: Scene illustration]\n\n"
        "After the illustration."
    )


def test_parse_chapter_payload_extracts_image_metadata() -> None:
    source = SyosetuNcodeSource()
    html = """
    <html>
      <body>
        <div class="p-novel__text p-novel__text--body js-novel-text">
          <p>Before the illustration.</p>
          <img src="/images/scene.png" alt="Scene illustration" />
          <p>After the illustration.</p>
        </div>
      </body>
    </html>
    """

    payload = source._parse_chapter_payload(html, "https://ncode.syosetu.com/n8733gf/1/")

    assert payload["text"] == (
        "Before the illustration.\n\n"
        "[Image: Scene illustration]\n\n"
        "After the illustration."
    )
    assert payload["images"] == [
        {
            "index": 0,
            "placeholder": "[Image: Scene illustration]",
            "original_url": "https://ncode.syosetu.com/images/scene.png",
            "alt": "Scene illustration",
            "title": None,
            "filename": "scene.png",
        }
    ]


def test_parse_chapter_payload_extracts_images_wrapped_in_paragraph() -> None:
    """Images inside <p><a><img/></a></p> must be extracted (regression test)."""
    source = SyosetuNcodeSource()
    html = """
    <html>
      <body>
        <div class="p-novel__text p-novel__text--body js-novel-text">
          <p>Some text before.</p>
          <p><a href="https://mitemin.net/userpageimageview/viewimageid/12345">
            <img src="https://mitemin.net/icode/12345/fitmode/1/fitsrc/1" alt="\u63d2\u7d75(By \u307f\u3066\u307f\u3093)" />
          </a></p>
          <p>Some text after.</p>
        </div>
      </body>
    </html>
    """

    payload = source._parse_chapter_payload(html, "https://novel18.syosetu.com/n0813kx/1/")

    assert "[Image:" in payload["text"]
    assert len(payload["images"]) == 1
    assert payload["images"][0]["original_url"].startswith("https://mitemin.net/")


@pytest.mark.asyncio
async def test_fetch_metadata_collects_all_paginated_chapter_pages() -> None:
    source = SyosetuNcodeSource()
    root_url = "https://ncode.syosetu.com/n8733gf/"
    infotop_url = "https://ncode.syosetu.com/novelview/infotop/ncode/n8733gf/"
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
        infotop_url: """
        <html><body><table><tr><th>掲載状態</th><td>連載中</td></tr></table></body></html>
        """,
    }

    async def fake_fetch_page(url: str) -> str:
        return pages[url]

    source._fetch_page = fake_fetch_page  # type: ignore[method-assign]
    metadata = await source.fetch_metadata(root_url)

    assert [chapter["id"] for chapter in metadata["chapters"]] == ["1", "2", "3", "4"]
    assert metadata["publication_status"] == "ongoing"
    assert metadata["source_publication_status_page"] == infotop_url


@pytest.mark.asyncio
async def test_fetch_metadata_carries_part_heading_between_paginated_pages() -> None:
    source = SyosetuNcodeSource()
    root_url = "https://ncode.syosetu.com/n8733gf/"
    infotop_url = "https://ncode.syosetu.com/novelview/infotop/ncode/n8733gf/"
    pages = {
        root_url: """
        <html>
          <body>
            <h1 class="p-novel__title">Paged Story</h1>
            <div id="novel_writername">Author Name</div>
            <div class="chapter_title">Part One: The Eventful First Year</div>
            <dl class="novel_sublist2">
              <dd class="subtitle"><a href="/n8733gf/1/">Prologue</a></dd>
              <dt class="long_update">2025/01/13 20:00</dt>
            </dl>
            <dl class="novel_sublist2">
              <dd class="subtitle"><a href="/n8733gf/2/">Episode 1</a></dd>
              <dt class="long_update">2025/01/14 19:00</dt>
            </dl>
            <a href="/n8733gf/?p=2">2</a>
          </body>
        </html>
        """,
        f"{root_url}?p=2": """
        <html>
          <body>
            <dl class="novel_sublist2">
              <dd class="subtitle"><a href="/n8733gf/3/">Episode 2</a></dd>
              <dt class="long_update">2025/01/15 19:00</dt>
            </dl>
            <dl class="novel_sublist2">
              <dd class="subtitle"><a href="/n8733gf/4/">Episode 3</a></dd>
              <dt class="long_update">2025/01/16 19:00</dt>
            </dl>
          </body>
        </html>
        """,
        infotop_url: """
        <html><body><table><tr><th>掲載状態</th><td>連載中</td></tr></table></body></html>
        """,
    }

    async def fake_fetch_page(url: str) -> str:
        return pages[url]

    source._fetch_page = fake_fetch_page  # type: ignore[method-assign]
    metadata = await source.fetch_metadata(root_url)

    assert [chapter["part"] for chapter in metadata["chapters"]] == [
        "Part One: The Eventful First Year",
        "Part One: The Eventful First Year",
        "Part One: The Eventful First Year",
        "Part One: The Eventful First Year",
    ]


@pytest.mark.asyncio
async def test_fetch_metadata_stops_after_requested_max_chapter_page() -> None:
    source = SyosetuNcodeSource()
    root_url = "https://ncode.syosetu.com/n8733gf/"
    infotop_url = "https://ncode.syosetu.com/novelview/infotop/ncode/n8733gf/"
    requests: list[str] = []
    pages = {
        root_url: """
        <html>
          <body>
            <h1 class="p-novel__title">Paged Story</h1>
            <div id="novel_writername">Author Name</div>
            <a href="/n8733gf/1/">Chapter One</a>
            <a href="/n8733gf/2/">Chapter Two</a>
            <a href="/n8733gf/?p=2">2</a>
            <a href="/n8733gf/?p=3">3</a>
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
        f"{root_url}?p=3": """
        <html>
          <body>
            <a href="/n8733gf/5/">Chapter Five</a>
            <a href="/n8733gf/6/">Chapter Six</a>
          </body>
        </html>
        """,
        infotop_url: """
        <html><body><table><tr><th>掲載状態</th><td>連載中</td></tr></table></body></html>
        """,
    }

    async def fake_fetch_page(url: str) -> str:
        requests.append(url)
        return pages[url]

    source._fetch_page = fake_fetch_page  # type: ignore[method-assign]
    metadata = await source.fetch_metadata(root_url, max_chapter=4)

    assert requests == [root_url, infotop_url, f"{root_url}?p=2"]
    assert [chapter["id"] for chapter in metadata["chapters"]] == ["1", "2", "3", "4"]


@pytest.mark.asyncio
async def test_fetch_metadata_caps_single_page_toc_without_counting_headings() -> None:
    source = SyosetuNcodeSource()
    root_url = "https://ncode.syosetu.com/n8733gf/"
    infotop_url = "https://ncode.syosetu.com/novelview/infotop/ncode/n8733gf/"

    async def fake_fetch_page(url: str) -> str:
        if url == infotop_url:
            return """
            <html><body><table><tr><th>掲載状態</th><td>連載中</td></tr></table></body></html>
            """
        assert url == root_url
        return """
        <html>
          <body>
            <h1 class="p-novel__title">Single Page Story</h1>
            <h2 class="chapter_title">Part One</h2>
            <a href="/n8733gf/1/">Episode One</a>
            <a href="/n8733gf/2/">Episode Two</a>
            <h2 class="chapter_title">Part Two</h2>
            <a href="/n8733gf/3/">Episode Three</a>
            <a href="/n8733gf/4/">Episode Four</a>
          </body>
        </html>
        """

    source._fetch_page = fake_fetch_page  # type: ignore[method-assign]
    metadata = await source.fetch_metadata(root_url, max_chapter=3)

    assert [chapter["id"] for chapter in metadata["chapters"]] == ["1", "2", "3"]
    assert [chapter["part"] for chapter in metadata["chapters"]] == ["Part One", "Part One", "Part Two"]
