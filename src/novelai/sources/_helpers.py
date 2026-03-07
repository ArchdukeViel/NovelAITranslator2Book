from __future__ import annotations

from collections.abc import Iterable, Iterator

from bs4 import Tag


def attribute_to_str(value: object) -> str | None:
    """Normalize a BeautifulSoup attribute value to a single string."""
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        parts = [part for part in value if isinstance(part, str)]
        return parts[0] if len(parts) == 1 else None
    return None


def image_placeholder(image: Tag) -> str:
    """Render a deterministic placeholder for inline chapter illustrations."""
    label = (
        attribute_to_str(image.get("alt"))
        or attribute_to_str(image.get("title"))
        or _image_filename(
            attribute_to_str(image.get("src"))
            or attribute_to_str(image.get("data-src"))
            or attribute_to_str(image.get("data-original"))
        )
    )
    if label:
        return f"[Image: {label}]"
    return "[Image]"


def iter_story_blocks(section: Tag, block_names: Iterable[str]) -> Iterator[Tag]:
    """Yield outermost block-like nodes so nested image wrappers are not duplicated."""
    block_name_set = {name.lower() for name in block_names}
    candidates = list(section.find_all(tuple(block_name_set), recursive=True))
    filtered: list[Tag] = []
    for element in candidates:
        if not isinstance(element, Tag):
            continue
        if _has_block_ancestor(element, section, block_name_set):
            continue
        filtered.append(element)
    for element in filtered:
        yield element


def _has_block_ancestor(element: Tag, section: Tag, block_name_set: set[str]) -> bool:
    for parent in element.parents:
        if parent is section:
            return False
        if isinstance(parent, Tag) and isinstance(parent.name, str) and parent.name.lower() in block_name_set:
            return True
    return False


def _image_filename(raw_src: str | None) -> str | None:
    if not raw_src:
        return None
    candidate = raw_src.strip().split("?", 1)[0].rstrip("/")
    if not candidate:
        return None
    filename = candidate.rsplit("/", 1)[-1].strip()
    return filename or None
