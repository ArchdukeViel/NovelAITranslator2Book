from __future__ import annotations

import re
from collections.abc import Iterable, Sequence

from bs4 import BeautifulSoup, Comment, NavigableString, Tag
from bs4.element import PageElement

from src.utils import resolve_url

ALLOWED_TAGS = {
    "blockquote",
    "br",
    "em",
    "hr",
    "i",
    "img",
    "li",
    "ol",
    "p",
    "rp",
    "rt",
    "ruby",
    "strong",
    "ul",
}
DROP_TAGS = {
    "button",
    "canvas",
    "form",
    "iframe",
    "input",
    "noscript",
    "script",
    "select",
    "style",
    "svg",
    "textarea",
}
UNWRAP_TAGS = {
    "a",
    "article",
    "body",
    "div",
    "figure",
    "figcaption",
    "html",
    "main",
    "picture",
    "section",
    "source",
    "span",
}
BLOCK_TAGS = {"blockquote", "hr", "img", "li", "ol", "p", "ul"}
NOISE_KEYWORDS = (
    "ad",
    "ads",
    "breadcrumb",
    "comment",
    "footer",
    "header",
    "menu",
    "nav",
    "pager",
    "pagination",
    "ranking",
    "recommend",
    "related",
    "share",
    "sidebar",
    "sns",
    "toolbar",
    "widget-share",
)
SCENE_BREAK_TEXT = "----------"


def clean_chapter_html(
    node_or_nodes: Tag | Sequence[PageElement] | str,
    *,
    base_url: str | None = None,
) -> str:
    """Normalize chapter content into a safe HTML fragment."""
    output = BeautifulSoup("", "lxml")
    container = output.new_tag("div")

    for node in _iter_nodes(node_or_nodes):
        for cleaned in _sanitize_node(node, output, base_url):
            container.append(cleaned)

    _wrap_loose_nodes(container, output)
    _drop_empty_blocks(container)
    return "".join(str(child) for child in container.contents)


def node_to_plain_text(node: PageElement) -> str:
    """Render readable plain text while preserving paragraph boundaries."""
    if isinstance(node, NavigableString):
        return _normalize_text(str(node))

    if not isinstance(node, Tag):
        return ""

    name = node.name.lower()
    if name in {"rt", "rp"}:
        return ""
    if name == "br":
        return "\n"
    if name == "hr":
        return SCENE_BREAK_TEXT
    if name == "img":
        alt = node.get("alt")
        if isinstance(alt, str) and alt.strip():
            return f"[Image: {alt.strip()}]"
        return "[Image]"
    if name == "ruby":
        return "".join(node_to_plain_text(child) for child in node.contents if not _is_ruby_annotation(child))

    parts = [node_to_plain_text(child) for child in node.contents]
    text = "".join(parts)
    if name in {"p", "blockquote", "li"}:
        return text.strip()
    return text


def fragment_to_plain_text(fragment_html: str) -> str:
    soup = BeautifulSoup(f"<div>{fragment_html}</div>", "lxml")
    container = soup.div
    if container is None:
        return ""

    blocks: list[str] = []
    for child in container.contents:
        text = node_to_plain_text(child).strip()
        if text:
            blocks.append(text)
    return "\n\n".join(blocks)


def _iter_nodes(node_or_nodes: Tag | Sequence[PageElement] | str) -> Iterable[PageElement]:
    if isinstance(node_or_nodes, str):
        soup = BeautifulSoup(node_or_nodes, "lxml")
        root = soup.body or soup
        return list(root.contents)
    if isinstance(node_or_nodes, Tag):
        return [node_or_nodes]
    return list(node_or_nodes)


def _sanitize_node(node: PageElement, output: BeautifulSoup, base_url: str | None) -> list[PageElement]:
    if isinstance(node, Comment):
        return []

    if isinstance(node, NavigableString):
        text = _normalize_text(str(node))
        if not text:
            return []
        return [output.new_string(text)]

    if not isinstance(node, Tag):
        return []

    tag_name = node.name.lower()
    if tag_name in DROP_TAGS or _is_noise(node):
        return []
    if tag_name in {"aside", "footer", "header", "nav"}:
        return []
    if tag_name == "img":
        image = _sanitize_image(node, output, base_url)
        return [image] if image is not None else []
    if tag_name == "b":
        tag_name = "strong"
    if tag_name in {"br", "hr"}:
        return [output.new_tag(tag_name)]
    if tag_name in UNWRAP_TAGS or tag_name not in ALLOWED_TAGS:
        return _sanitize_children(node, output, base_url)

    clean_tag = output.new_tag(tag_name)
    for child in _sanitize_children(node, output, base_url):
        clean_tag.append(child)

    if tag_name in {"p", "blockquote", "li"} and not clean_tag.get_text(strip=True) and not clean_tag.find("img"):
        return []
    return [clean_tag]


def _sanitize_children(node: Tag, output: BeautifulSoup, base_url: str | None) -> list[PageElement]:
    cleaned: list[PageElement] = []
    for child in node.contents:
        cleaned.extend(_sanitize_node(child, output, base_url))
    return cleaned


def _sanitize_image(node: Tag, output: BeautifulSoup, base_url: str | None) -> Tag | None:
    raw_src = node.get("src") or node.get("data-src") or node.get("data-original")
    if not isinstance(raw_src, str) or not raw_src.strip():
        return None

    image = output.new_tag("img")
    image["src"] = resolve_url(base_url, raw_src) or raw_src.strip()
    for attr in ("alt", "title"):
        value = node.get(attr)
        if isinstance(value, str) and value.strip():
            image[attr] = value.strip()
    return image


def _is_noise(node: Tag) -> bool:
    if node.has_attr("hidden"):
        return True
    style = node.get("style")
    if isinstance(style, str) and "display:none" in style.replace(" ", "").lower():
        return True

    fields: list[str] = []
    for attr in ("class", "id", "role", "aria-label"):
        value = node.get(attr)
        if isinstance(value, list):
            fields.extend(str(part).lower() for part in value)
        elif isinstance(value, str):
            fields.append(value.lower())

    return any(keyword in field for field in fields for keyword in NOISE_KEYWORDS)


def _normalize_text(text: str) -> str:
    text = text.replace("\u00a0", " ").replace("\r\n", "\n").replace("\r", "\n")
    text = text.replace("\n", " ")
    text = re.sub(r"[ \t\f\v]+", " ", text)
    return text.strip(" ")


def _is_ruby_annotation(node: PageElement) -> bool:
    return isinstance(node, Tag) and node.name.lower() in {"rt", "rp"}


def _wrap_loose_nodes(container: Tag, output: BeautifulSoup) -> None:
    new_children: list[PageElement] = []
    buffer: list[PageElement] = []

    def flush_buffer() -> None:
        if not buffer:
            return
        paragraph = output.new_tag("p")
        for item in buffer:
            paragraph.append(item)
        if paragraph.get_text(strip=True) or paragraph.find("img"):
            new_children.append(paragraph)
        buffer.clear()

    for child in list(container.contents):
        child.extract()
        if isinstance(child, Tag) and child.name.lower() in BLOCK_TAGS:
            flush_buffer()
            new_children.append(child)
            continue
        if isinstance(child, NavigableString) and not child.strip():
            continue
        buffer.append(child)

    flush_buffer()
    container.clear()
    for child in new_children:
        container.append(child)


def _drop_empty_blocks(container: Tag) -> None:
    for tag in list(container.find_all(["p", "blockquote", "li", "ul", "ol"])):
        if tag.name in {"ul", "ol"}:
            if not tag.find("li", recursive=False):
                tag.decompose()
            continue
        if not tag.get_text(strip=True) and not tag.find("img"):
            tag.decompose()

