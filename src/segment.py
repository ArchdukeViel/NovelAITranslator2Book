from __future__ import annotations

from bs4 import BeautifulSoup, NavigableString, Tag

from src.clean import SCENE_BREAK_TEXT, node_to_plain_text
from src.models import Segment


def segment_fragment(fragment_html: str, chapter_id: str) -> list[Segment]:
    """Split a cleaned fragment into stable block-level segments."""
    soup = BeautifulSoup(f"<div>{fragment_html}</div>", "lxml")
    container = soup.div
    if container is None:
        return []

    segments: list[Segment] = []
    index = 0
    for node in _top_level_nodes(container):
        kind = _segment_kind(node)
        text = _segment_text(node, kind)
        html = str(node)
        segments.append(
            Segment(
                segment_id=f"{chapter_id}:{index:04d}",
                index=index,
                kind=kind,
                html=html,
                text=text,
            )
        )
        index += 1
    return segments


def segments_to_plain_text(segments: list[Segment]) -> str:
    blocks = [segment.text.strip() for segment in segments if segment.text.strip()]
    return "\n\n".join(blocks)


def _top_level_nodes(container: Tag) -> list[Tag]:
    nodes: list[Tag] = []
    buffer: list[Tag | NavigableString] = []

    def flush_buffer() -> None:
        if not buffer:
            return
        paragraph = container.new_tag("p")
        for item in buffer:
            paragraph.append(item)
        if paragraph.get_text(strip=True) or paragraph.find("img"):
            nodes.append(paragraph)
        buffer.clear()

    for child in list(container.contents):
        child.extract()
        if isinstance(child, Tag) and child.name.lower() in {"p", "blockquote", "hr", "img", "ul", "ol"}:
            flush_buffer()
            if child.name.lower() in {"ul", "ol"}:
                for item in child.find_all("li", recursive=False):
                    nodes.append(item)
            else:
                nodes.append(child)
            continue
        if isinstance(child, Tag):
            buffer.append(child)
            continue
        if isinstance(child, NavigableString) and child.strip():
            buffer.append(child)

    flush_buffer()
    return nodes


def _segment_kind(node: Tag) -> str:
    name = node.name.lower()
    if name == "hr":
        return "break"
    if name == "img":
        return "image"
    if name == "p" and node.find("img") and not node.get_text(strip=True):
        return "image"
    if name == "p":
        return "paragraph"
    return "other"


def _segment_text(node: Tag, kind: str) -> str:
    if kind == "break":
        return SCENE_BREAK_TEXT
    if kind == "image":
        image = node if node.name.lower() == "img" else node.find("img")
        if image is not None:
            text = node_to_plain_text(image).strip()
            return text or "[Image]"
        return "[Image]"
    return node_to_plain_text(node).strip()

