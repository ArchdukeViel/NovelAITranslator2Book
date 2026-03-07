from __future__ import annotations

from pathlib import Path

from src.adapters.generic import GenericAdapter
from src.adapters.kakuyomu import KakuyomuAdapter
from src.adapters.registry import AdapterRegistry
from src.adapters.syosetu import SyosetuAdapter
from src.utils import soup_from_html

FIXTURES = Path(__file__).parent / "fixtures"


def _fixture(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def test_registry_detects_syosetu_and_kakuyomu_by_url() -> None:
    registry = AdapterRegistry()

    assert isinstance(
        registry.detect("https://ncode.syosetu.com/n8733gf/1/"),
        SyosetuAdapter,
    )
    assert isinstance(
        registry.detect("https://novel18.syosetu.com/n0813kx/1/"),
        SyosetuAdapter,
    )
    assert isinstance(
        registry.detect("https://kakuyomu.jp/works/16818093001234567890/episodes/16818093001234567999"),
        KakuyomuAdapter,
    )


def test_kakuyomu_adapter_derives_work_and_episode_ids() -> None:
    adapter = KakuyomuAdapter()
    soup = soup_from_html(_fixture("kakuyomu_chapter.html"))

    assert (
        adapter.derive_novel_id("https://kakuyomu.jp/works/822139845959461179/", soup, {})
        == "822139845959461179"
    )
    assert (
        adapter.derive_novel_id(
            "https://kakuyomu.jp/works/822139845959461179/episodes/822139845959540845",
            soup,
            {},
        )
        == "822139845959461179"
    )
    assert (
        adapter.derive_chapter_id(
            "https://kakuyomu.jp/works/822139845959461179/episodes/822139845959540845",
            soup,
            {},
        )
        == "822139845959540845"
    )


def test_syosetu_adapter_preserves_ruby_breaks_and_filters_chrome() -> None:
    adapter = SyosetuAdapter()
    html = _fixture("syosetu_chapter.html")
    soup = soup_from_html(html)

    fragment = adapter.normalize_chapter_html(
        adapter.extract_chapter_body(soup),
        base_url="https://ncode.syosetu.com/n8733gf/1/",
    )

    assert "<ruby>多<rt>おお</rt></ruby>" in fragment
    assert "<br/>" in fragment
    assert "<hr/>" in fragment
    assert "novel_bn" not in fragment
    assert "share nav buttons" not in fragment


def test_kakuyomu_adapter_resolves_images_and_keeps_blockquote() -> None:
    adapter = KakuyomuAdapter()
    html = _fixture("kakuyomu_chapter.html")
    soup = soup_from_html(html)

    fragment = adapter.normalize_chapter_html(
        adapter.extract_chapter_body(soup),
        base_url="https://kakuyomu.jp/works/16818093001234567890/episodes/16818093001234567999",
    )

    assert "<blockquote>「今日は何かが起きる」</blockquote>" in fragment
    assert 'src="https://kakuyomu.jp/images/scene.png"' in fragment
    assert "share buttons" not in fragment


def test_generic_adapter_falls_back_to_article_like_content() -> None:
    adapter = GenericAdapter()
    html = _fixture("generic_chapter.html")
    soup = soup_from_html(html)

    fragment = adapter.normalize_chapter_html(
        adapter.extract_chapter_body(soup),
        base_url="https://example.com/fiction/episode-9",
    )

    assert "<p>One paragraph of story text.</p>" in fragment
    assert "<strong>emphasis</strong>" in fragment
    assert "breadcrumb" not in fragment
    assert "share widget" not in fragment
