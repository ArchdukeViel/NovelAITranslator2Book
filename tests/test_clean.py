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


# ---------------------------------------------------------------------------
# Edge-case / security tests
# ---------------------------------------------------------------------------


def test_clean_removes_nested_and_obfuscated_script_tags() -> None:
    """Script elements must be stripped even when nested or nested in allowed tags."""
    raw = """
    <div>
      <p>safe text</p>
      <script>alert('xss')</script>
      <p><script>nested</script>after</p>
      <style>body{display:none}</style>
    </div>
    """
    fragment = clean_chapter_html(raw)

    assert "<script" not in fragment
    assert "alert" not in fragment
    assert "<style" not in fragment
    assert "safe text" in fragment
    assert "after" in fragment


def test_clean_strips_event_handler_attributes() -> None:
    """Inline event handlers (onclick, onerror, etc.) must not survive cleaning."""
    raw = '<p onclick="alert(1)">text</p><img src="x.png" onerror="alert(2)" alt="ok"/>'
    fragment = clean_chapter_html(raw, base_url="https://example.com")

    assert "onclick" not in fragment
    assert "onerror" not in fragment
    assert "text" in fragment


def test_clean_handles_malformed_html_gracefully() -> None:
    """Unclosed or broken tags should not crash the cleaner."""
    raw = "<p>unclosed paragraph<br><p>second paragraph</p>"
    fragment = clean_chapter_html(raw)
    assert "unclosed paragraph" in fragment
    assert "second paragraph" in fragment


def test_clean_removes_iframe_and_form_elements() -> None:
    """Dangerous elements like iframes and forms must be stripped."""
    raw = """
    <div>
      <iframe src="https://evil.com"></iframe>
      <form action="/steal"><input type="text"/></form>
      <p>content</p>
    </div>
    """
    fragment = clean_chapter_html(raw)

    assert "<iframe" not in fragment
    assert "<form" not in fragment
    assert "<input" not in fragment
    assert "content" in fragment


def test_clean_strips_hidden_elements() -> None:
    """Elements with hidden attribute or display:none style should be removed."""
    raw = """
    <p>visible</p>
    <div hidden>hidden content</div>
    <div style="display:none">invisible</div>
    <p>also visible</p>
    """
    fragment = clean_chapter_html(raw)

    assert "visible" in fragment
    assert "hidden content" not in fragment
    assert "invisible" not in fragment


def test_clean_handles_empty_and_whitespace_only_input() -> None:
    """Empty or whitespace-only input should produce an empty fragment."""
    assert clean_chapter_html("") == ""
    assert clean_chapter_html("   \n\t  ") == ""


def test_fragment_to_plain_text_handles_image_without_alt() -> None:
    """Images without alt text should produce a generic [Image] placeholder."""
    fragment = '<p><img src="pic.png"/></p>'
    text = fragment_to_plain_text(fragment)
    assert "[Image]" in text

