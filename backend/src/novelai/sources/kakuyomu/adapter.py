"""Kakuyomu source adapter implementation."""

from __future__ import annotations

import logging
import re
from collections.abc import Callable
from typing import Any

import httpx
from bs4 import BeautifulSoup, Tag

from novelai.core.errors import SourceError
from novelai.infrastructure.http.fetch_service import FetchService, get_default_fetch_service
from novelai.infrastructure.http.profiles import PROFILE_ASSETS, PROFILE_KAKUYOMU_HTML
from novelai.sources._helpers import (
    attribute_to_str,
    extract_image_references,
    image_placeholder,
    iter_story_blocks,
)
from novelai.sources.base import SourceAdapter
from novelai.sources.html_parsers import HTMLParserMixin
from novelai.sources.kakuyomu.parser import (
    BODY_SELECTORS,
    REMOVE_FROM_BODY_SELECTORS,
    TITLE_SELECTORS,
    extract_chapters_from_next_data,
    next_data_apollo_state,
)
from novelai.sources.quality import detect_age_gate_page, detect_block_page_text
from novelai.sources.status import publication_status_payload
from novelai.sources.synopsis import normalize_synopsis_metadata
from novelai.utils.text_normalization import normalize_text

logger = logging.getLogger(__name__)


class KakuyomuSource(SourceAdapter):
    source_key = "kakuyomu"
    """Source adapter for Kakuyomu works and episodes."""

    WORK_ID_PATTERN = re.compile(r"^\d{12,}$")
    WORK_PATH_PATTERN = re.compile(r"/works/([^/?#]+)(?:/|$)", re.IGNORECASE)
    EPISODE_PATH_PATTERN = re.compile(r"/works/([^/]+)/episodes/([^/?#]+)", re.IGNORECASE)
    BODY_SELECTORS = BODY_SELECTORS
    TITLE_SELECTORS = TITLE_SELECTORS
    AUTHOR_SELECTORS = (
        "[class*='WorkAuthorBox_'] a[href^='/users/']",
        ".widget-authorName",
        "[itemprop='author']",
        "[rel='author']",
        "[data-author-name]",
    )
    TOC_ROOT_SELECTORS = (
        ".widget-toc",
        ".widget-toc-main",
        "[data-work-toc]",
        "#contentMain",
        "main",
    )
    STRUCTURAL_TOC_ROOT_SELECTORS = (
        ".widget-toc",
        ".widget-toc-main",
        "[data-work-toc]",
    )
    EPISODE_TITLE_SELECTORS = (
        ".widget-toc-episode-episodeTitleLabel",
        ".widget-toc-episode-episodeTitle",
        ".widget-toc-episodeTitleLabel",
        ".widget-toc-episodeTitle",
        ".episode-title",
    )
    REMOVE_FROM_BODY_SELECTORS = REMOVE_FROM_BODY_SELECTORS
    RUBY_REMOVE_SELECTORS = ("rt", "rp")
    SEPARATOR_LINE = "-" * 60
    USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
    PUBLICATION_STATUS_TEXT_MARKERS = (
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
    UI_RANGE_LABEL_PATTERN = re.compile(r"^\s*\d+\s*[〜~]\s*\d+\s*$")
    LAZY_TOC_LABELS = (
        "show more",
        "load more",
        "もっと見る",
        "さらに表示",
        "続きを読む",
    )

    def __init__(self, fetch_service: FetchService | None = None) -> None:
        self._fetch_service = fetch_service or get_default_fetch_service()

    def can_handle(self, identifier_or_url: str) -> bool:
        candidate = identifier_or_url.strip()
        if not candidate.startswith(("http://", "https://")):
            return False

        try:
            parsed_url = httpx.URL(candidate)
        except Exception:
            return False

        host = (parsed_url.host or "").lower()
        return host == "kakuyomu.jp" and self.WORK_PATH_PATTERN.search(parsed_url.path) is not None

    def normalize_novel_id(self, identifier_or_url: str) -> str:
        candidate = identifier_or_url.strip().rstrip("/")
        if not candidate:
            return candidate

        if self.WORK_ID_PATTERN.fullmatch(candidate):
            return candidate

        if not candidate.startswith(("http://", "https://")):
            return candidate

        try:
            parsed_url = httpx.URL(candidate)
        except Exception:
            return candidate

        match = self.EPISODE_PATH_PATTERN.search(parsed_url.path)
        if match:
            return match.group(1)

        match = self.WORK_PATH_PATTERN.search(parsed_url.path)
        if match:
            return match.group(1)

        return candidate.strip("/")

    def _normalize_url(self, identifier_or_url: str) -> str:
        work_id = self.normalize_novel_id(identifier_or_url)
        return f"https://kakuyomu.jp/works/{work_id.strip('/')}"

    @staticmethod
    def _request_headers() -> dict[str, str]:
        return {"User-Agent": KakuyomuSource.USER_AGENT}

    @staticmethod
    def _decode_page_body(body: bytes) -> str:
        return body.decode("utf-8", errors="replace")

    @staticmethod
    def _preflight_check(html: str, url: str) -> None:
        if detect_block_page_text(html):
            raise SourceError(f"Kakuyomu page at {url} appears to be blocked (Cloudflare, CAPTCHA, or bot challenge).")
        if detect_age_gate_page(html, final_url=url):
            raise SourceError(f"Kakuyomu page at {url} appears to require age verification or adult confirmation.")

    async def _fetch_page(self, url: str, *, on_retry: Callable[[int, Exception], None] | None = None) -> str:
        try:
            result = await self._fetch_service.get_text(
                url,
                source_key=self.source_key,
                headers=self._request_headers(),
                profile=PROFILE_KAKUYOMU_HTML,
                on_retry=on_retry,
            )
        except SourceError as exc:
            raise SourceError(f"Failed to fetch Kakuyomu page from {url}: {exc}") from exc
        html = self._decode_page_body(result.body)
        self._preflight_check(html, url)
        return html

    async def fetch_asset(self, url: str, *, referer: str | None = None) -> dict[str, Any]:
        try:
            result = await self._fetch_service.get_bytes(
                url,
                source_key=self.source_key,
                referer=referer,
                profile=PROFILE_ASSETS,
            )
        except SourceError as exc:
            raise SourceError(f"Failed to fetch Kakuyomu asset from {url}: {exc}") from exc

        return {
            "url": result.final_url,
            "content": result.body,
            "content_type": result.headers.get("content-type"),
        }

    def _first_text(self, soup: BeautifulSoup | Tag, selectors: tuple[str, ...]) -> str | None:
        for selector in selectors:
            node = soup.select_one(selector)
            if not isinstance(node, Tag):
                continue
            text = node.get_text(" ", strip=True)
            if text:
                return text
        return None

    def _extract_work_title(self, soup: BeautifulSoup) -> str | None:
        return HTMLParserMixin.extract_title(soup, self.TITLE_SELECTORS)

    def _extract_author(self, soup: BeautifulSoup) -> str | None:
        author = HTMLParserMixin.extract_author(soup, self.AUTHOR_SELECTORS)
        if author:
            return author
        meta = soup.find("meta", attrs={"name": "author"})
        content = meta.get("content") if isinstance(meta, Tag) else None
        return content.strip() if isinstance(content, str) and content.strip() else None

    @staticmethod
    def _text_blocks(node: Tag) -> list[str]:
        text = node.get_text("\n", strip=True)
        return [normalized for normalized in (normalize_text(line) for line in text.splitlines()) if normalized]

    def _overview_region(self, soup: BeautifulSoup) -> Tag | None:
        heading = next(
            (
                candidate
                for candidate in soup.find_all(("h2", "h3"))
                if isinstance(candidate, Tag) and candidate.get_text(" ", strip=True) == "概要"
            ),
            None,
        )
        if not isinstance(heading, Tag) or not isinstance(heading.parent, Tag):
            return None

        heading_wrapper = heading.parent
        parent = heading_wrapper.parent
        if not isinstance(parent, Tag):
            return None
        children = [child for child in parent.find_all(recursive=False) if isinstance(child, Tag)]
        try:
            heading_index = children.index(heading_wrapper)
        except ValueError:
            return None

        following = children[heading_index + 1 :]
        if not following:
            return None
        # The first sibling after the 概要 heading is the overview content;
        # status, author, reviews, and related works follow it in the page DOM.
        return following[0]

    def _extract_synopsis_blocks(self, soup: BeautifulSoup) -> list[dict[str, str]]:
        region = self._overview_region(soup)
        if region is None:
            return []

        nodes: list[tuple[Tag, str]] = []
        for node in region.select("[class*='WorkIntroductionBox_catch_']"):
            if isinstance(node, Tag):
                nodes.append((node, "promotion"))
        for node in region.select("[class*='CollapseTextWithKakuyomuLinks_']"):
            if isinstance(node, Tag):
                nodes.append((node, "narrative"))

        if nodes:
            descendants = list(region.descendants)
            nodes.sort(key=lambda item: descendants.index(item[0]) if item[0] in descendants else len(descendants))
            blocks: list[dict[str, str]] = []
            for node, classification in nodes:
                for text in self._text_blocks(node):
                    blocks.append(
                        {
                            "id": f"b{len(blocks) + 1:04d}",
                            "text": text,
                            "classification": classification,
                        }
                    )
            if blocks:
                return blocks

        # DOM fixtures and older Kakuyomu layouts may expose ordinary
        # paragraphs without the current hashed component classes.  Restrict
        # the fallback to the overview region so reviews and related works are
        # never mistaken for synopsis text.
        blocks = []
        for node in region.find_all(("p", "blockquote")):
            if not isinstance(node, Tag):
                continue
            for text in self._text_blocks(node):
                blocks.append({"id": f"b{len(blocks) + 1:04d}", "text": text})
        return blocks

    def _extract_synopsis_metadata(self, soup: BeautifulSoup) -> dict[str, Any]:
        blocks = self._extract_synopsis_blocks(soup)
        if blocks:
            raw = "\n".join(block["text"] for block in blocks)
            return normalize_synopsis_metadata(
                raw,
                source_key=self.source_key,
                blocks=blocks,
                separator="\n",
            )

        for selector in (
            ".widget-workSynopsis",
            ".widget-work-introduction",
            "[itemprop='description']",
            "meta[name='description']",
            "meta[property='og:description']",
        ):
            node = soup.select_one(selector)
            if not isinstance(node, Tag):
                continue
            content = node.get("content")
            if isinstance(content, str) and content.strip():
                return normalize_synopsis_metadata(content, source_key=self.source_key)
            text = node.get_text("\n", strip=True)
            if text:
                return normalize_synopsis_metadata(text, source_key=self.source_key)
        return {}

    def _extract_synopsis(self, soup: BeautifulSoup) -> str | None:
        metadata = self._extract_synopsis_metadata(soup)
        value = metadata.get("narrative_synopsis") or metadata.get("source_synopsis")
        return value if isinstance(value, str) and value.strip() else None

    def _extract_episode_title(self, anchor: Tag, fallback_index: int) -> str:
        title = self._first_text(anchor, self.EPISODE_TITLE_SELECTORS)
        if title:
            return title
        text = anchor.get_text(" ", strip=True)
        return text or f"Episode {fallback_index}"

    @classmethod
    def _is_ui_range_label(cls, text: str) -> bool:
        return cls.UI_RANGE_LABEL_PATTERN.fullmatch(text) is not None

    @classmethod
    def _dom_incomplete_indicators(cls, soup: BeautifulSoup) -> tuple[list[str], list[str]]:
        range_labels: list[str] = []
        for element in soup.find_all(True):
            if not isinstance(element, Tag):
                continue
            text = element.get_text(" ", strip=True)
            if text and cls._is_ui_range_label(text) and text not in range_labels:
                range_labels.append(text)

        lazy_labels: list[str] = []
        for element in soup.find_all(["button", "a"]):
            if not isinstance(element, Tag):
                continue
            text = element.get_text(" ", strip=True)
            if (
                text
                and text.casefold() in {label.casefold() for label in cls.LAZY_TOC_LABELS}
                and text not in lazy_labels
            ):
                lazy_labels.append(text)
        return range_labels, lazy_labels

    def _extract_chapters_from_html(self, soup: BeautifulSoup, url: str) -> list[dict[str, Any]]:
        work_id = self.normalize_novel_id(url)
        toc_roots: list[tuple[Tag, bool]] = []
        for selector in self.TOC_ROOT_SELECTORS:
            node = soup.select_one(selector)
            if isinstance(node, Tag):
                toc_roots.append((node, selector in self.STRUCTURAL_TOC_ROOT_SELECTORS))
        if not toc_roots:
            toc_roots.append((soup, False))

        chapters: list[dict[str, Any]] = []
        seen_urls: set[str] = set()
        base_url = httpx.URL(url)
        current_section_title: str | None = None
        current_section_ordinal: int | None = None
        episodes_seen_since_section = False

        for root, is_structural_toc_root in toc_roots:
            for element in root.find_all(["a", "h2", "h3", "h4", "div", "li", "span"], recursive=True):
                if not isinstance(element, Tag):
                    continue

                if element.name.lower() in {"h2", "h3", "h4", "div", "li", "span"}:
                    cls_list = element.get("class") or []
                    cls_str = " ".join(cls_list if isinstance(cls_list, list) else [str(cls_list)])
                    if (
                        "widget-toc-chapter" in cls_str
                        or "widget-toc-heading" in cls_str
                        or "chapter-title" in cls_str
                        or (is_structural_toc_root and element.name.lower() in {"h2", "h3", "h4"})
                    ):
                        heading_text = element.get_text(" ", strip=True)
                        if heading_text and not self._is_ui_range_label(heading_text):
                            if current_section_title is None:
                                current_section_ordinal = 1
                            elif heading_text != current_section_title or episodes_seen_since_section:
                                current_section_ordinal = (current_section_ordinal or 0) + 1
                            current_section_title = heading_text
                            episodes_seen_since_section = False
                        continue

                if element.name.lower() != "a":
                    continue

                href = attribute_to_str(element.get("href"))
                if href is None:
                    continue

                try:
                    abs_url = str(base_url.join(href))
                    parsed = httpx.URL(abs_url)
                except Exception:
                    continue

                match = self.EPISODE_PATH_PATTERN.search(parsed.path)
                if not match:
                    continue
                if match.group(1) != work_id:
                    continue

                canonical_url = f"https://kakuyomu.jp/works/{work_id}/episodes/{match.group(2)}"
                if canonical_url in seen_urls:
                    # A broad root can contain the same episode more than once.
                    # Enrich an ungrouped first sighting, but never let a later
                    # duplicate overwrite the source-order grouping.
                    if current_section_title:
                        for existing_ch in chapters:
                            if existing_ch.get("url") == canonical_url and not existing_ch.get("section_title"):
                                existing_ch["part"] = current_section_title
                                existing_ch["section_title"] = current_section_title
                                existing_ch["section_source_id"] = None
                                existing_ch["section_ordinal"] = current_section_ordinal or 1
                    continue
                seen_urls.add(canonical_url)

                index = len(chapters) + 1
                ep_id = match.group(2)
                chapter_item: dict[str, Any] = {
                    "id": f"kakuyomu:{ep_id}",
                    "num": index,
                    "sequence_number": index,
                    "title": self._extract_episode_title(element, index),
                    "url": canonical_url,
                    "source_episode_id": ep_id,
                }
                if current_section_title:
                    chapter_item["part"] = current_section_title
                    chapter_item["section_title"] = current_section_title
                    chapter_item["section_source_id"] = None
                    chapter_item["section_ordinal"] = current_section_ordinal or 1
                chapters.append(chapter_item)
                episodes_seen_since_section = True

        return chapters

    def _extract_chapters(self, soup: BeautifulSoup, url: str) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        chapters, provenance = extract_chapters_from_next_data(soup, self.normalize_novel_id(url))
        expected_count = provenance.get("expected_episode_count")
        if chapters and provenance.get("apollo_complete", True):
            return chapters, provenance

        html_chapters = self._extract_chapters_from_html(soup, url)
        range_labels, lazy_labels = self._dom_incomplete_indicators(soup)
        html_count = len(html_chapters)
        if isinstance(expected_count, int) and html_count < expected_count:
            raise SourceError(
                "Kakuyomu chapter index is incomplete: "
                f"expected {expected_count} public episodes but enumerated {html_count} from the available page data."
            )
        if (range_labels or lazy_labels) and not isinstance(expected_count, int):
            indicators = ", ".join(range_labels + lazy_labels)
            raise SourceError(
                "Kakuyomu chapter index appears to be lazy or UI-paginated "
                f"({indicators}); complete episode enumeration is unavailable."
            )

        if chapters and provenance.get("apollo_structurally_valid") and expected_count is None:
            return chapters, provenance

        fallback_provenance = {
            "metadata_extraction_mode": "html_dom",
            "chapter_index_extraction_mode": "html_dom",
            "apollo_state_present": bool(provenance.get("apollo_state_present")),
            "apollo_structurally_valid": bool(provenance.get("apollo_structurally_valid")),
            "expected_episode_count": expected_count,
            "extracted_episode_count": html_count,
            "fallbacks_used": ["html_dom"],
        }
        return html_chapters, fallback_provenance

    def _extract_publication_status_text(self, soup: BeautifulSoup) -> str | None:
        apollo_state = next_data_apollo_state(soup)
        if apollo_state:
            for key, rec in apollo_state.items():
                if key.startswith("Work:") and isinstance(rec, dict):
                    status = rec.get("serialStatus") or rec.get("publicationStatus") or rec.get("status")
                    if isinstance(status, str) and status.strip():
                        return status.strip()

        status_selectors = (
            ".widget-workHeader-status",
            ".widget-work-status",
            "[data-work-status]",
            ".work-status",
        )
        for selector in status_selectors:
            node = soup.select_one(selector)
            if isinstance(node, Tag):
                text = node.get_text(" ", strip=True)
                if text:
                    return text

        for container in soup.find_all(["dl", "div", "p", "li", "span"]):
            if not isinstance(container, Tag):
                continue
            text = container.get_text(" ", strip=True)
            if not text or len(text) > 200:
                continue
            for marker in self.PUBLICATION_STATUS_TEXT_MARKERS:
                if marker in text:
                    return text
        return None

    def _extract_dates(self, soup: BeautifulSoup) -> tuple[str | None, str | None]:
        time_tags = soup.find_all("time")
        published_at: str | None = None
        updated_at: str | None = None
        for tag in time_tags:
            dt = tag.get("datetime") or tag.get_text(strip=True)
            if dt and isinstance(dt, str):
                if published_at is None:
                    published_at = dt.strip()
                updated_at = dt.strip()
        return published_at, updated_at

    def _extract_genre_and_tags(self, soup: BeautifulSoup) -> tuple[str | None, list[str]]:
        """Extract genre and tags from Kakuyomu HTML (DOM fallback)."""
        genre_name: str | None = None
        tags: list[str] = []

        # Try widget-workGenre selector
        genre_node = soup.select_one(".widget-workGenre")
        if isinstance(genre_node, Tag):
            text = genre_node.get_text(" ", strip=True)
            if text:
                genre_name = text

        # Fallback: work-genre link
        if genre_name is None:
            genre_node = soup.select_one(".work-genre a")
            if isinstance(genre_node, Tag):
                text = genre_node.get_text(" ", strip=True)
                if text:
                    genre_name = text

        # Tags: widget-workTag links
        for tag_node in soup.select(".widget-workTag a"):
            if isinstance(tag_node, Tag):
                text = tag_node.get_text(" ", strip=True)
                if text:
                    tags.append(text)

        return genre_name, tags

    def _parse_metadata_html(self, html: str, url: str) -> dict[str, Any]:
        soup = BeautifulSoup(html, "html.parser")
        novel_id = self.normalize_novel_id(url)
        title = self._extract_work_title(soup) or f"Work {novel_id}"
        author = self._extract_author(soup)
        synopsis_metadata = self._extract_synopsis_metadata(soup)
        synopsis = synopsis_metadata.get("synopsis")
        if not isinstance(synopsis, str) or not synopsis.strip():
            synopsis = None
        chapters, provenance = self._extract_chapters(soup, url)
        status_text = self._extract_publication_status_text(soup)
        published_at, updated_at = self._extract_dates(soup)

        # Genre and tags (DOM fallback when Apollo unavailable)
        genre_name, tags = self._extract_genre_and_tags(soup)

        res = {
            "source_key": self.source_key,
            "source_url": url,
            "source_novel_id": novel_id,
            "novel_id": novel_id,
            "title": title,
            "author": author,
            "synopsis": synopsis,
            **synopsis_metadata,
            "chapters": chapters,
            **provenance,
            **publication_status_payload(status_text),
        }
        if published_at:
            res["published_at"] = published_at
        if updated_at:
            res["updated_at"] = updated_at
        if genre_name:
            res["source_genre_name"] = genre_name
            from novelai.sources.taxonomy import KAKUYOMU_GENRE_MAP, map_genre

            slug = map_genre(genre_name, KAKUYOMU_GENRE_MAP)
            if slug:
                res["genre_slug"] = slug
        else:
            res["source_genre_name"] = None
            res["genre_slug"] = None
        if tags:
            res["source_tags"] = tags
        else:
            res["source_tags"] = []
        return res

    async def fetch_metadata(self, url: str, *, max_chapter: int | None = None) -> dict[str, Any]:
        full_url = self._normalize_url(url)
        html = await self._fetch_page(full_url, on_retry=None)
        metadata = self._parse_metadata_html(html, full_url)
        if max_chapter is not None and isinstance(metadata.get("chapters"), list):
            metadata["chapters"] = [
                ch
                for ch in metadata["chapters"]
                if isinstance(ch, dict) and isinstance(ch.get("num"), int) and ch["num"] <= max_chapter
            ]
        return metadata

    def _parse_chapter_payload(self, html: str, url: str) -> dict[str, Any]:
        soup = BeautifulSoup(html, "html.parser")
        body_node = soup.select_one(", ".join(self.BODY_SELECTORS))
        if not isinstance(body_node, Tag):
            raise SourceError(f"Unable to find episode body at {url}")

        for sel in self.REMOVE_FROM_BODY_SELECTORS:
            for tag in body_node.select(sel):
                tag.decompose()

        for ruby in body_node.find_all("ruby"):
            rt = ruby.find("rt")
            rt_text = rt.get_text(strip=True) if rt else ""
            for rp in ruby.find_all("rp"):
                rp.decompose()
            if rt:
                rt.decompose()
            base_text = ruby.get_text(strip=True)
            if rt_text and base_text:
                ruby.replace_with(f"{base_text}《{rt_text}》")
            else:
                ruby.unwrap()

        images = extract_image_references(body_node, base_url=url)
        for img in body_node.find_all("img"):
            img.replace_with(image_placeholder(img))

        for hr in body_node.find_all("hr"):
            p_hr = soup.new_tag("p")
            p_hr.string = self.SEPARATOR_LINE
            p_hr["data-kakuyomu-separator"] = "1"
            hr.replace_with(p_hr)

        for br in body_node.find_all("br"):
            br.replace_with("\n")

        raw_blocks: list[str] = []
        separator_indices: set[int] = set()
        for element in iter_story_blocks(body_node, ("p", "blockquote", "figure", "hr", "img")):
            if isinstance(element, Tag):
                text = normalize_text(element.get_text(separator="", strip=False))
                if element.get("data-kakuyomu-separator") is not None:
                    # HR separator: keep text for the plain-text projection but
                    # type it as a structural break in source blocks.
                    raw_blocks.append(text or self.SEPARATOR_LINE)
                    separator_indices.add(len(raw_blocks) - 1)
                elif text:
                    raw_blocks.append(text)

        if not raw_blocks:
            text = normalize_text(body_node.get_text(separator="", strip=False))
            if text:
                raw_blocks.append(text)

        full_text = "\n\n".join(raw_blocks)

        from novelai.sources.source_layout import normalize_source_blocks

        raw_block_records: list[dict[str, Any]] = []
        for index, block in enumerate(raw_blocks):
            if index in separator_indices:
                raw_block_records.append({"type": "break"})
            elif block.strip():
                raw_block_records.append({"type": "line", "text": block})
        source_blocks = normalize_source_blocks(raw_block_records)

        return {
            "text": full_text,
            "images": images,
            "source_blocks": source_blocks,
        }

    def _parse_chapter_html(self, html: str, url: str = "https://kakuyomu.jp/") -> str:
        payload = self._parse_chapter_payload(html, url)
        return str(payload.get("text", ""))

    async def fetch_chapter_payload(
        self,
        url: str,
        *,
        on_retry: Callable[[int, Exception], None] | None = None,
    ) -> dict[str, Any]:
        html = await self._fetch_page(url, on_retry=on_retry)
        return self._parse_chapter_payload(html, url)

    async def fetch_chapter(self, url: str) -> str:
        payload = await self.fetch_chapter_payload(url)
        return str(payload.get("text", ""))
