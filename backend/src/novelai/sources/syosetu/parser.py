"""Syosetu HTML parsing routines for metadata, chapter index, and story bodies."""

from __future__ import annotations

import logging
import re
from typing import Any

import httpx
from bs4 import BeautifulSoup, Tag

from novelai.sources._helpers import (
    attribute_to_str,
    image_placeholder,
    iter_story_blocks,
)
from novelai.sources.source_layout import source_blocks_from_text_blocks
from novelai.utils.text_normalization import normalize_text

logger = logging.getLogger(__name__)

PART_HEADING_CLASSES = {
    "chapter_title",
    "p-eplist__chapter-title",
    "p-eplist__volume-title",
    "p-eplist__part-title",
    "p-eplist__group-title",
}
CHAPTER_ROW_CLASSES = {
    "novel_sublist2",
    "p-eplist__sublist",
    "p-eplist__episode",
    "p-eplist__item",
}
BODY_SELECTORS = (
    "#novel_honbun",
    ".p-novel__text--body",
    ".js-novel-text",
    ".p-novel__body .p-novel__text",
    ".p-novel__body",
    ".p-novel__text",
    ".novel_view",
)
PREFACE_SELECTORS = (
    "#novel_p",
    ".p-novel__text--preface",
    ".p-novel__preface",
)
AFTERWORD_SELECTORS = (
    "#novel_a",
    ".p-novel__text--afterword",
    ".p-novel__afterword",
)
REMOVE_FROM_SECTION_SELECTORS = (".novel_bn",)
RUBY_REMOVE_SELECTORS = ("rt", "rp")
SEPARATOR_LINE = "-" * 60
PUBLICATION_STATUS_LABEL_MARKERS = (
    "掲載状態",
    "連載状態",
    "状態",
    "ステータス",
    "作品種別",
    "種別",
)
PUBLICATION_STATUS_VALUE_MARKERS = (
    "完結済",
    "連載終了",
    "完結",
    "完了",
    "連載中",
    "更新中",
    "休載",
    "一時停止",
    "停止",
    "中断",
)
SOURCE_DATE_PATTERN = re.compile(r"\d{4}/\d{1,2}/\d{1,2}(?:\s+\d{1,2}:\d{2})?")
NOVEL_ID_PATTERN = re.compile(r"^n\d{4}[a-z]{2}$", re.IGNORECASE)
NOVEL_ID_PATH_PATTERN = re.compile(r"/(n\d{4}[a-z]{2})(?:/|$)", re.IGNORECASE)


def normalize_syosetu_novel_id(identifier_or_url: str) -> str:
    candidate = identifier_or_url.strip().rstrip("/")
    if not candidate:
        return candidate
    if NOVEL_ID_PATTERN.fullmatch(candidate):
        return candidate.lower()
    if candidate.startswith(("http://", "https://")):
        try:
            parsed_url = httpx.URL(candidate)
        except Exception:
            return candidate
        path = parsed_url.path
        match = NOVEL_ID_PATH_PATTERN.search(path)
        if match:
            return match.group(1).lower()
        path_parts = [part for part in path.split("/") if part]
        for part in path_parts:
            if NOVEL_ID_PATTERN.fullmatch(part):
                return part.lower()
    return candidate.strip("/")


def classes_of(tag: Tag) -> set[str]:
    raw_classes = tag.get("class") or []
    values = raw_classes if isinstance(raw_classes, list) else [raw_classes]
    return {str(value).strip() for value in values if str(value).strip()}


def is_part_heading(tag: Tag) -> bool:
    cls = classes_of(tag)
    if cls.intersection(PART_HEADING_CLASSES):
        return True
    if tag.name.lower() not in {"h2", "h3", "h4", "div", "p"}:
        return False
    if tag.find("a", href=True):
        return False
    text = tag.get_text(" ", strip=True)
    if not text:
        return False
    lowered = text.lower()
    if "chapter" in lowered or "part" in lowered or "arc" in lowered:
        return True
    return bool(re.search(r"(?:^|\s)(?:第?[0-9０-９一二三四五六七八九十百]+[章部編]|[0-9０-９]+章)(?:\s|　|$)", text))


def extract_source_date_from_text(text: str) -> str | None:
    match = SOURCE_DATE_PATTERN.search(text)
    return match.group(0) if match else None


def extract_source_date_from_node(node: Tag) -> str | None:
    for time_node in node.find_all("time"):
        if not isinstance(time_node, Tag):
            continue
        datetime_value = time_node.get("datetime")
        if isinstance(datetime_value, str) and datetime_value.strip():
            source_date = extract_source_date_from_text(datetime_value)
            if source_date:
                return source_date
            return datetime_value.strip()
        source_date = extract_source_date_from_text(time_node.get_text(" ", strip=True))
        if source_date:
            return source_date

    source_date = extract_source_date_from_text(node.get_text(" ", strip=True))
    if source_date:
        return source_date

    title_value = node.get("title")
    if isinstance(title_value, str):
        return extract_source_date_from_text(title_value)
    return None


def chapter_row_container(anchor: Tag) -> Tag | None:
    current: Tag | None = anchor
    for _ in range(5):
        if current is None:
            break
        if classes_of(current).intersection(CHAPTER_ROW_CLASSES):
            return current
        parent = current.parent
        current = parent if isinstance(parent, Tag) else None
    return anchor.parent if isinstance(anchor.parent, Tag) else None


def extract_chapter_date(anchor: Tag) -> str | None:
    candidates: list[Tag] = []
    row = chapter_row_container(anchor)
    if row is not None:
        candidates.append(row)
    if isinstance(anchor.parent, Tag):
        candidates.append(anchor.parent)
        for sibling in list(anchor.parent.next_siblings)[:4] + list(anchor.parent.previous_siblings)[-4:]:
            if isinstance(sibling, Tag):
                candidates.append(sibling)
    if row is not None:
        for sibling in list(row.next_siblings)[:3] + list(row.previous_siblings)[-3:]:
            if isinstance(sibling, Tag):
                candidates.append(sibling)

    for candidate in candidates:
        source_date = extract_source_date_from_node(candidate)
        if source_date:
            return source_date
    return None


def extract_chapter_part(anchor: Tag, current_part: str | None) -> str | None:
    if current_part:
        return current_part
    if isinstance(anchor.parent, Tag):
        for sibling in reversed(list(anchor.parent.previous_siblings)[-8:]):
            if isinstance(sibling, Tag) and is_part_heading(sibling):
                text = sibling.get_text(" ", strip=True)
                if text:
                    return text
    return None


def extract_chapters(
    soup: BeautifulSoup,
    url: str,
    title: str | None,
    *,
    initial_part: str | None = None,
) -> list[dict[str, Any]]:
    base_url = httpx.URL(url)
    novel_id = normalize_syosetu_novel_id(url)
    chapter_pattern = re.compile(rf"^/{re.escape(novel_id)}/(\d+)/?$", re.IGNORECASE)
    chapter_urls: dict[int, dict[str, Any]] = {}
    current_part = initial_part.strip() if isinstance(initial_part, str) and initial_part.strip() else None

    for node in soup.find_all(["div", "section", "h2", "h3", "h4", "p", "li", "a"], recursive=True):
        if not isinstance(node, Tag):
            continue

        if is_part_heading(node):
            text = node.get_text(" ", strip=True)
            if text:
                current_part = text
            continue

        if node.name.lower() != "a":
            continue

        href = attribute_to_str(node.get("href"))
        if href is None:
            continue

        absolute_url = str(base_url.join(href))
        match = chapter_pattern.match(httpx.URL(absolute_url).path)
        if not match:
            continue

        chapter_number = int(match.group(1))
        chapter: dict[str, Any] = {
            "id": str(chapter_number),
            "num": chapter_number,
            "title": node.get_text(strip=True) or f"Chapter {chapter_number}",
            "url": absolute_url,
        }
        part = extract_chapter_part(node, current_part)
        if part:
            chapter["part"] = part
        date_added = extract_chapter_date(node)
        if date_added:
            chapter["date_added"] = date_added
        existing = chapter_urls.get(chapter_number)
        if existing is not None:
            if part and not existing.get("part"):
                existing["part"] = part
            if date_added and not existing.get("date_added"):
                existing["date_added"] = date_added
            continue
        chapter_urls[chapter_number] = chapter

    if chapter_urls:
        return [chapter_urls[index] for index in sorted(chapter_urls)]

    if find_story_body(soup) is None:
        return []

    return [
        {
            "id": "1",
            "num": 1,
            "title": title or "Chapter 1",
            "url": str(base_url),
        }
    ]


def is_story_body(candidate: Tag) -> bool:
    raw_classes = candidate.get("class") or []
    classes = {
        value.lower()
        for value in (raw_classes if isinstance(raw_classes, list) else [raw_classes])
        if isinstance(value, str)
    }
    if "p-novel__text--preface" in classes or "p-novel__text--afterword" in classes:
        return False
    return candidate.get("id") not in {"novel_p", "novel_a"}


def prepare_story_section(section: Tag) -> Tag | None:
    section_soup = BeautifulSoup(str(section), "lxml")
    prepared = section_soup.select_one(section.name)
    if not isinstance(prepared, Tag):
        return None

    for removable in REMOVE_FROM_SECTION_SELECTORS:
        for tag in prepared.select(removable):
            tag.decompose()

    for ruby_selector in RUBY_REMOVE_SELECTORS:
        for tag in prepared.find_all(ruby_selector):
            tag.decompose()
    for ruby in prepared.find_all("ruby"):
        ruby.unwrap()

    if not prepared.get_text(separator="\n", strip=True) and not prepared.find(["hr", "img"]):
        return None
    return prepared


def extract_text_from_tag(tag: Tag) -> str:
    if tag.name.lower() == "img":
        return image_placeholder(tag)

    for image in tag.find_all("img"):
        image.replace_with(image_placeholder(image))
    for hr in tag.find_all("hr"):
        hr.replace_with(f"\n\n{SEPARATOR_LINE}\n\n")
    for br in tag.find_all("br"):
        br.replace_with("\n")
    return normalize_text(tag.get_text(separator="", strip=False))


def render_story_section(section: Tag) -> str:
    blocks: list[str] = []
    for element in iter_story_blocks(section, ("p", "blockquote", "figure", "hr", "img")):
        if not isinstance(element, Tag):
            continue
        if element.name.lower() == "hr":
            blocks.append(SEPARATOR_LINE)
            continue
        block = extract_text_from_tag(element)
        if block:
            blocks.append(block)

    if blocks:
        return "\n\n".join(blocks)
    return extract_text_from_tag(section)


def extract_source_blocks_from_section(section: Tag) -> list[dict[str, Any]]:
    blocks: list[str] = []
    for element in iter_story_blocks(section, ("p", "blockquote", "figure", "hr", "img")):
        if not isinstance(element, Tag):
            continue
        if element.name.lower() == "hr":
            blocks.append("")
            continue
        block = extract_text_from_tag(element)
        if block:
            blocks.append(block)

    if blocks:
        return source_blocks_from_text_blocks(blocks)
    fallback = extract_text_from_tag(section)
    return source_blocks_from_text_blocks([fallback] if fallback else [])


def find_story_section(soup: BeautifulSoup, selectors: tuple[str, ...]) -> Tag | None:
    for selector in selectors:
        for candidate in soup.select(selector):
            if not isinstance(candidate, Tag):
                continue
            if selector in BODY_SELECTORS and not is_story_body(candidate):
                continue
            prepared = prepare_story_section(candidate)
            if prepared is not None:
                return prepared
    return None


def find_story_body(soup: BeautifulSoup) -> Tag | None:
    return find_story_section(soup, BODY_SELECTORS)


def find_story_sections(soup: BeautifulSoup) -> list[Tag]:
    sections: list[Tag] = []
    preface = find_story_section(soup, PREFACE_SELECTORS)
    body = find_story_body(soup)
    afterword = find_story_section(soup, AFTERWORD_SELECTORS)

    for section in (preface, body, afterword):
        if section is not None:
            sections.append(section)
    return sections
