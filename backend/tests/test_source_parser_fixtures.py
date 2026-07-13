from __future__ import annotations

from pathlib import Path

import pytest

from novelai.core.errors import SourceError
from novelai.sources.generic import GenericSource
from novelai.sources.kakuyomu import KakuyomuSource
from novelai.sources.novel18_syosetu import Novel18SyosetuSource
from novelai.sources.syosetu_ncode import SyosetuNcodeSource

FIXTURES = Path(__file__).parent / "fixtures" / "sources"


def _fixture(source: str, name: str) -> str:
    return (FIXTURES / source / name).read_text(encoding="utf-8")


def test_syosetu_fixture_url_matching_and_normalization() -> None:
    source = SyosetuNcodeSource()

    assert source.matches_url("https://ncode.syosetu.com/n1234ab/")
    assert source.normalize_novel_id("https://ncode.syosetu.com/n1234ab/2/") == "n1234ab"


def test_syosetu_fixture_metadata_and_chapter_ordering() -> None:
    source = SyosetuNcodeSource()
    metadata = source._parse_metadata_html(
        _fixture("syosetu", "metadata_page_ongoing.html"),
        "https://ncode.syosetu.com/n1234ab/",
    )

    assert metadata["title"] == "Ongoing Fixture Story"
    assert metadata["author"] == "Fixture Author"
    assert metadata["synopsis"] == "A compact synopsis for parser tests."
    assert [chapter["id"] for chapter in metadata["chapters"]] == ["1", "2"]
    assert [chapter["part"] for chapter in metadata["chapters"]] == ["Arc One", "Arc One"]
    assert [chapter["date_added"] for chapter in metadata["chapters"]] == [
        "2026/01/01 12:00",
        "2026/01/02 12:00",
    ]


def test_syosetu_fixture_completed_one_shot_synthesizes_chapter() -> None:
    source = SyosetuNcodeSource()
    metadata = source._parse_metadata_html(
        _fixture("syosetu", "metadata_page_completed.html"),
        "https://ncode.syosetu.com/n9999zz/",
    )

    assert metadata["title"] == "Completed Fixture Story"
    assert metadata["chapters"] == [
        {
            "id": "1",
            "num": 1,
            "title": "Completed Fixture Story",
            "url": "https://ncode.syosetu.com/n9999zz/",
        }
    ]


def test_syosetu_fixture_preface_body_afterword_and_ruby() -> None:
    source = SyosetuNcodeSource()

    preface = source._parse_chapter_html(_fixture("syosetu", "chapter_with_preface.html"))
    afterword = source._parse_chapter_html(_fixture("syosetu", "chapter_with_afterword.html"))
    ruby = source._parse_chapter_html(_fixture("syosetu", "chapter_with_ruby.html"))
    preface_payload = source._parse_chapter_payload(
        _fixture("syosetu", "chapter_with_preface.html"),
        "https://ncode.syosetu.com/n1234ab/1/",
    )
    afterword_payload = source._parse_chapter_payload(
        _fixture("syosetu", "chapter_with_afterword.html"),
        "https://ncode.syosetu.com/n1234ab/1/",
    )

    assert preface == "Preface fixture note.\n\nMain body first line.\nMain body second line."
    assert preface_payload["source_blocks"] == [
        {
            "type": "line",
            "source_block_id": "s0001",
            "paragraph_id": "p0001",
            "text": "Preface fixture note.",
            "source_order": 1,
        },
        {"type": "break", "source_block_id": "b0001", "source_order": 2},
        {
            "type": "line",
            "source_block_id": "s0002",
            "paragraph_id": "p0002",
            "text": "Main body first line.\nMain body second line.",
            "source_order": 3,
        },
    ]
    assert afterword == (
        "Main body paragraph.\n\n"
        "------------------------------------------------------------\n\n"
        "Afterword fixture note."
    )
    assert afterword_payload["source_blocks"] == [
        {
            "type": "line",
            "source_block_id": "s0001",
            "paragraph_id": "p0001",
            "text": "Main body paragraph.",
            "source_order": 1,
        },
        {"type": "break", "source_block_id": "b0001", "source_order": 2},
        {
            "type": "line",
            "source_block_id": "s0002",
            "paragraph_id": "p0002",
            "text": "Afterword fixture note.",
            "source_order": 3,
        },
    ]
    assert ruby == "魔導具が光った。"
    assert "まどうぐ" not in ruby


def test_syosetu_fixture_image_extraction_and_placeholder() -> None:
    source = SyosetuNcodeSource()
    payload = source._parse_chapter_payload(
        _fixture("syosetu", "chapter_with_images.html"),
        "https://ncode.syosetu.com/n1234ab/1/",
    )

    assert payload["text"] == "Before image.\n\n[Image: Scene fixture]\n\nAfter image."
    assert payload["source_blocks"] == [
        {"type": "line", "source_block_id": "s0001", "paragraph_id": "p0001", "text": "Before image.", "source_order": 1},
        {
            "type": "line",
            "source_block_id": "s0002",
            "paragraph_id": "p0002",
            "text": "[Image: Scene fixture]",
            "source_order": 2,
        },
        {"type": "line", "source_block_id": "s0003", "paragraph_id": "p0003", "text": "After image.", "source_order": 3},
    ]
    assert payload["images"] == [
        {
            "index": 0,
            "placeholder": "[Image: Scene fixture]",
            "original_url": "https://ncode.syosetu.com/images/scene.png",
            "alt": "Scene fixture",
            "title": None,
            "filename": "scene.png",
        }
    ]


@pytest.mark.asyncio
async def test_syosetu_fixture_paginated_toc_uses_offline_pages() -> None:
    source = SyosetuNcodeSource()
    root_url = "https://ncode.syosetu.com/n1234ab/"
    pages = {
        root_url: _fixture("syosetu", "paginated_toc_page_1.html"),
        f"{root_url}?p=2": _fixture("syosetu", "paginated_toc_page_2.html"),
    }

    async def fake_fetch_page(url: str, on_retry=None) -> str:
        return pages.get(url, pages[root_url])

    source._fetch_page = fake_fetch_page  # type: ignore[method-assign]
    metadata = await source.fetch_metadata(root_url)

    assert [chapter["id"] for chapter in metadata["chapters"]] == ["1", "2", "3", "4"]


def test_novel18_fixture_age_gate_detection() -> None:
    source = Novel18SyosetuSource()

    with pytest.raises(SourceError, match=r"age gate|auth redirect"):
        source._parse_chapter_payload(
            "<html><body>redirect/ageauth/ 年齢確認 18歳未満 over18</body></html>",
            "https://novel18.syosetu.com/n1234ab/1/",
        )


def test_kakuyomu_fixture_url_matching_and_work_metadata() -> None:
    source = KakuyomuSource()

    assert source.matches_url("https://kakuyomu.jp/works/16818093000000000000/")
    assert (
        source.normalize_novel_id(
            "https://kakuyomu.jp/works/16818093000000000000/episodes/16818093000000000001"
        )
        == "16818093000000000000"
    )

    metadata = source._parse_metadata_html(
        _fixture("kakuyomu", "work_page.html"),
        "https://kakuyomu.jp/works/16818093000000000000/",
    )
    assert metadata["title"] == "Kakuyomu Fixture Work"
    assert metadata["author"] == "Kakuyomu Author"
    assert [chapter["source_episode_id"] for chapter in metadata["chapters"]] == [
        "16818093000000000001",
        "16818093000000000002",
    ]


def test_kakuyomu_fixture_episode_body_and_separator() -> None:
    source = KakuyomuSource()

    episode_payload = source._parse_chapter_payload(_fixture("kakuyomu", "episode_page.html"), "https://kakuyomu.jp/")
    episode = str(episode_payload.get("text", ""))
    with_hr_payload = source._parse_chapter_payload(_fixture("kakuyomu", "episode_with_hr.html"), "https://kakuyomu.jp/")
    with_hr = str(with_hr_payload.get("text", ""))

    assert episode == "Episode first paragraph.\n\nEpisode second paragraph."
    assert episode_payload["source_blocks"] == [
        {"type": "line", "source_block_id": "s0001", "paragraph_id": "p0001", "text": "Episode first paragraph.", "source_order": 1},
        {"type": "line", "source_block_id": "s0002", "paragraph_id": "p0002", "text": "Episode second paragraph.", "source_order": 2},
    ]
    assert with_hr == (
        "Before separator.\n\n"
        "------------------------------------------------------------\n\n"
        "After separator."
    )
    assert with_hr_payload["source_blocks"] == [
        {"type": "line", "source_block_id": "s0001", "paragraph_id": "p0001", "text": "Before separator.", "source_order": 1},
        {"type": "break", "source_block_id": "b0001", "source_order": 2},
        {"type": "line", "source_block_id": "s0002", "paragraph_id": "p0002", "text": "After separator.", "source_order": 3},
    ]


def test_kakuyomu_fixture_image_extraction() -> None:
    source = KakuyomuSource()
    payload = source._parse_chapter_payload(
        _fixture("kakuyomu", "episode_with_images.html"),
        "https://kakuyomu.jp/works/16818093000000000000/episodes/16818093000000000001",
    )

    assert payload["text"] == "Before image.\n\n[Image: Kakuyomu scene]\n\nAfter image."
    assert payload["images"][0]["original_url"] == "https://kakuyomu.jp/images/kaku.png"
    assert payload["images"][0]["placeholder"] == "[Image: Kakuyomu scene]"


@pytest.mark.asyncio
async def test_generic_fixture_valid_toc_confidence_and_duplicate_normalization() -> None:
    source = GenericSource()

    async def fake_fetch_page(url: str, on_retry=None) -> str:
        return _fixture("generic", "valid_toc.html")

    source._fetch_page = fake_fetch_page  # type: ignore[method-assign]
    metadata = await source.fetch_metadata("https://example.com/novel")

    assert [chapter["url"] for chapter in metadata["chapters"]] == [
        "https://example.com/novel/chapter-1",
        "https://example.com/novel/chapter-2",
    ]
    assert metadata["generic_confidence"]["score"] >= 0.75
    assert metadata["source_quality_status"] == "passed"


@pytest.mark.asyncio
async def test_generic_fixture_nav_heavy_page_is_low_confidence() -> None:
    source = GenericSource()

    async def fake_fetch_page(url: str, on_retry=None) -> str:
        return _fixture("generic", "nav_heavy_page.html")

    source._fetch_page = fake_fetch_page  # type: ignore[method-assign]
    metadata = await source.fetch_metadata("https://example.com/novel")

    assert metadata["source_quality_status"] == "needs_review"
    assert "generic_low_confidence" in metadata["generic_confidence"]["warnings"]


@pytest.mark.asyncio
async def test_generic_fixture_low_confidence_page_warns() -> None:
    source = GenericSource()

    async def fake_fetch_page(url: str, on_retry=None) -> str:
        return _fixture("generic", "low_confidence_page.html")

    source._fetch_page = fake_fetch_page  # type: ignore[method-assign]
    metadata = await source.fetch_metadata("https://example.com/novel")

    assert metadata["generic_confidence"]["score"] < 0.75
    assert metadata["source_quality_status"] == "needs_review"
