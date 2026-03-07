from __future__ import annotations

from src.clean import clean_chapter_html, fragment_to_plain_text


def test_clean_chapter_html_preserves_semantic_markup_and_removes_noise() -> None:
    raw = """
    <div class="chapter-body">
      <script>alert(1)</script>
      <p>第一段落<ruby>漢<rt>かん</rt></ruby><br/>改行</p>
      <div class="share-buttons">share me</div>
      <blockquote>引用</blockquote>
      <p><img src="/images/test.png" alt="挿絵" /></p>
    </div>
    """

    fragment = clean_chapter_html(raw, base_url="https://example.com/chapter/1")

    assert "<script" not in fragment
    assert "share me" not in fragment
    assert "<ruby>漢<rt>かん</rt></ruby>" in fragment
    assert "<blockquote>引用</blockquote>" in fragment
    assert 'src="https://example.com/images/test.png"' in fragment


def test_fragment_to_plain_text_keeps_paragraph_boundaries_and_scene_breaks() -> None:
    fragment = (
        "<p>一段落目。</p>"
        "<hr/>"
        "<p>二段落目。<br/>改行あり。</p>"
        '<p><img src="https://example.com/image.png" alt="場面絵"/></p>'
    )

    plain_text = fragment_to_plain_text(fragment)

    assert "一段落目。" in plain_text
    assert "----------" in plain_text
    assert "二段落目。\n改行あり。" in plain_text
    assert "[Image: 場面絵]" in plain_text

