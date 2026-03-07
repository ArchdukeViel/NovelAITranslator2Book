from __future__ import annotations

import re
from typing import Any

import httpx
from bs4 import BeautifulSoup, Tag

from novelai.core.errors import SourceError
from novelai.sources._helpers import attribute_to_str, image_placeholder, iter_story_blocks
from novelai.sources.base import SourceAdapter


class SyosetuNcodeSource(SourceAdapter):
    """Source adapter for syosetu.com novels (ncode)."""

    NOVEL_ID_PATTERN = re.compile(r"^n\d{4}[a-z]{2}$", re.IGNORECASE)
    NOVEL_ID_PATH_PATTERN = re.compile(r"/(n\d{4}[a-z]{2})(?:/|$)", re.IGNORECASE)
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
    REMOVE_FROM_SECTION_SELECTORS = (
        ".novel_bn",
    )
    RUBY_REMOVE_SELECTORS = ("rt", "rp")
    SEPARATOR_LINE = "-" * 60

    @property
    def key(self) -> str:
        return "syosetu_ncode"

    def matches_url(self, identifier_or_url: str) -> bool:
        candidate = identifier_or_url.strip()
        if not candidate.startswith(("http://", "https://")):
            return False

        try:
            host = httpx.URL(candidate).host or ""
        except Exception:
            return False

        return host.lower() == "ncode.syosetu.com"

    def normalize_novel_id(self, identifier_or_url: str) -> str:
        candidate = identifier_or_url.strip().rstrip("/")
        if not candidate:
            return candidate

        if self.NOVEL_ID_PATTERN.fullmatch(candidate):
            return candidate.lower()

        if candidate.startswith(("http://", "https://")):
            try:
                parsed_url = httpx.URL(candidate)
            except Exception:
                return candidate
            path = parsed_url.path
            match = self.NOVEL_ID_PATH_PATTERN.search(path)
            if match:
                return match.group(1).lower()
            path_parts = [part for part in path.split("/") if part]
            for part in path_parts:
                if self.NOVEL_ID_PATTERN.fullmatch(part):
                    return part.lower()
        return candidate.strip("/")

    def _normalize_url(self, identifier_or_url: str) -> str:
        # Accept either a full URL or the ncode identifier.
        novel_id = self.normalize_novel_id(identifier_or_url)
        return f"https://ncode.syosetu.com/{novel_id.strip('/')}/"

    def _build_request_cookies(self) -> httpx.Cookies | None:
        return None

    def _validate_fetched_page(self, requested_url: str, final_url: httpx.URL, html: str) -> None:
        return None

    async def _fetch_page(self, url: str) -> str:
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
        try:
            async with httpx.AsyncClient(
                timeout=30,
                headers=headers,
                cookies=self._build_request_cookies(),
                follow_redirects=True,
            ) as client:
                resp = await client.get(url)
                resp.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise SourceError(
                f"Failed to fetch Syosetu page from {url} (status={exc.response.status_code}). "
                "Check that the novel or chapter URL is correct and the site is accessible."
            ) from exc
        except httpx.HTTPError as exc:
            raise SourceError(f"Failed to fetch Syosetu page from {url}: {exc}") from exc
        self._validate_fetched_page(url, resp.url, resp.text)
        return resp.text

    def _extract_title(self, soup: BeautifulSoup) -> str | None:
        title_tag = (
            soup.select_one(".p-novel__title")
            or soup.select_one("h1.p-novel__title")
            or soup.find("p", class_="novel_title")
            or soup.find("h1", class_="novel_title")
        )
        if not title_tag:
            return None
        return title_tag.get_text(strip=True) or None

    def _extract_author(self, soup: BeautifulSoup) -> str | None:
        author_tag = soup.select_one(".p-novel__author") or soup.find(id="novel_writername")
        if not author_tag:
            return None
        return author_tag.get_text(strip=True) or None

    def _extract_page_numbers(self, soup: BeautifulSoup, url: str) -> list[int]:
        base_url = httpx.URL(url)
        novel_id = self.normalize_novel_id(url)
        page_numbers = {1}

        for anchor in soup.find_all("a", href=True):
            if not isinstance(anchor, Tag):
                continue
            href = attribute_to_str(anchor.get("href"))
            if href is None:
                continue

            absolute_url = base_url.join(href)
            candidate = httpx.URL(str(absolute_url))
            if self.normalize_novel_id(str(candidate)) != novel_id:
                continue
            if candidate.path.rstrip("/") != f"/{novel_id}":
                continue

            page_number = candidate.params.get("p")
            if page_number and page_number.isdigit():
                page_numbers.add(int(page_number))

        return sorted(page_numbers)

    def _extract_chapters(self, soup: BeautifulSoup, url: str, title: str | None) -> list[dict[str, str | int]]:
        base_url = httpx.URL(url)
        novel_id = self.normalize_novel_id(url)
        chapter_pattern = re.compile(rf"^/{re.escape(novel_id)}/(\d+)/?$", re.IGNORECASE)
        chapter_urls: dict[int, dict[str, str | int]] = {}

        for anchor in soup.find_all("a", href=True):
            if not isinstance(anchor, Tag):
                continue
            href = attribute_to_str(anchor.get("href"))
            if href is None:
                continue

            absolute_url = str(base_url.join(href))
            match = chapter_pattern.match(httpx.URL(absolute_url).path)
            if not match:
                continue

            chapter_number = int(match.group(1))
            chapter_urls[chapter_number] = {
                "id": str(chapter_number),
                "num": chapter_number,
                "title": anchor.get_text(strip=True) or f"Chapter {chapter_number}",
                "url": absolute_url,
            }

        if chapter_urls:
            return [chapter_urls[index] for index in sorted(chapter_urls)]

        if self._find_story_body(soup) is None:
            return []

        return [
            {
                "id": "1",
                "num": 1,
                "title": title or "Chapter 1",
                "url": str(base_url),
            }
        ]

    def _is_story_body(self, candidate: Tag) -> bool:
        classes = {
            value.lower()
            for value in candidate.get("class", [])
            if isinstance(value, str)
        }
        if "p-novel__text--preface" in classes or "p-novel__text--afterword" in classes:
            return False
        if candidate.get("id") in {"novel_p", "novel_a"}:
            return False
        return True

    def _prepare_story_section(self, section: Tag) -> Tag | None:
        section_soup = BeautifulSoup(str(section), "lxml")
        prepared = section_soup.select_one(section.name)
        if not isinstance(prepared, Tag):
            return None

        for removable in self.REMOVE_FROM_SECTION_SELECTORS:
            for tag in prepared.select(removable):
                tag.decompose()

        for ruby_selector in self.RUBY_REMOVE_SELECTORS:
            for tag in prepared.find_all(ruby_selector):
                tag.decompose()
        for ruby in prepared.find_all("ruby"):
            ruby.unwrap()

        if not prepared.get_text(separator="\n", strip=True) and not prepared.find(["hr", "img"]):
            return None
        return prepared

    def _normalize_story_text(self, text: str) -> str:
        text = text.replace("\r\n", "\n").replace("\r", "\n")
        lines = [line.strip(" \t") for line in text.split("\n")]
        normalized: list[str] = []

        for line in lines:
            if line:
                normalized.append(line)
                continue
            if normalized and normalized[-1] != "":
                normalized.append("")

        return "\n".join(normalized).strip()

    def _extract_text_from_tag(self, tag: Tag) -> str:
        if tag.name.lower() == "img":
            return image_placeholder(tag)

        for image in tag.find_all("img"):
            image.replace_with(image_placeholder(image))
        for hr in tag.find_all("hr"):
            hr.replace_with(f"\n\n{self.SEPARATOR_LINE}\n\n")
        for br in tag.find_all("br"):
            br.replace_with("\n")
        return self._normalize_story_text(tag.get_text(separator="", strip=False))

    def _render_story_section(self, section: Tag) -> str:
        blocks: list[str] = []
        for element in iter_story_blocks(section, ("p", "blockquote", "figure", "hr", "img")):
            if not isinstance(element, Tag):
                continue
            if element.name.lower() == "hr":
                blocks.append(self.SEPARATOR_LINE)
                continue
            block = self._extract_text_from_tag(element)
            if block:
                blocks.append(block)

        if blocks:
            return "\n\n".join(blocks)
        return self._extract_text_from_tag(section)

    def _find_story_section(self, soup: BeautifulSoup, selectors: tuple[str, ...]) -> Tag | None:
        for selector in selectors:
            for candidate in soup.select(selector):
                if not isinstance(candidate, Tag):
                    continue
                if selector in self.BODY_SELECTORS and not self._is_story_body(candidate):
                    continue
                prepared = self._prepare_story_section(candidate)
                if prepared is not None:
                    return prepared
        return None

    def _find_story_body(self, soup: BeautifulSoup) -> Tag | None:
        return self._find_story_section(soup, self.BODY_SELECTORS)

    def _find_story_sections(self, soup: BeautifulSoup) -> list[Tag]:
        sections: list[Tag] = []
        preface = self._find_story_section(soup, self.PREFACE_SELECTORS)
        body = self._find_story_body(soup)
        afterword = self._find_story_section(soup, self.AFTERWORD_SELECTORS)

        for section in (preface, body, afterword):
            if section is not None:
                sections.append(section)
        return sections

    def _extract_dates(self, soup: BeautifulSoup) -> tuple[str | None, str | None]:
        date_text = soup.get_text(separator="|", strip=True)
        dates = re.findall(r"\d{4}/\d{2}/\d{2}", date_text)
        published_at = dates[0] if dates else None
        updated_at = dates[-1] if dates else None
        return published_at, updated_at

    def _parse_metadata_html(self, html: str, url: str) -> dict[str, Any]:
        soup = BeautifulSoup(html, "lxml")
        title = self._extract_title(soup)
        author = self._extract_author(soup)
        chapters = self._extract_chapters(soup, url, title)
        published_at, updated_at = self._extract_dates(soup)

        return {
            "source": self.key,
            "source_url": url,
            "title": title,
            "author": author,
            "published_at": published_at,
            "updated_at": updated_at,
            "chapters": chapters,
        }

    def _parse_chapter_html(self, html: str) -> str:
        soup = BeautifulSoup(html, "lxml")
        sections = self._find_story_sections(soup)
        if not sections:
            raise SourceError("Unable to find chapter text on Syosetu page")

        text = "\n\n".join(
            rendered
            for rendered in (self._render_story_section(section) for section in sections)
            if rendered
        )
        text = re.sub(r"\n{3,}", "\n\n", text)
        if not text:
            raise SourceError("Chapter text was empty on Syosetu page")
        return text

    async def fetch_metadata(self, url: str, *, max_chapter: int | None = None) -> dict[str, Any]:
        url = self._normalize_url(url)
        html = await self._fetch_page(url)
        metadata = self._parse_metadata_html(html, url)
        soup = BeautifulSoup(html, "lxml")
        page_numbers = self._extract_page_numbers(soup, url)
        if len(page_numbers) == 1:
            return metadata

        chapters_by_number = {
            int(chapter["num"]): chapter
            for chapter in metadata.get("chapters", [])
            if isinstance(chapter, dict) and isinstance(chapter.get("num"), int)
        }
        if max_chapter is not None and chapters_by_number:
            highest_known_chapter = max(chapters_by_number)
            if highest_known_chapter >= max_chapter:
                metadata["chapters"] = [
                    chapter
                    for number, chapter in sorted(chapters_by_number.items())
                    if number <= max_chapter
                ]
                return metadata

        for page_number in page_numbers[1:]:
            page_url = f"{url}?p={page_number}"
            page_html = await self._fetch_page(page_url)
            page_soup = BeautifulSoup(page_html, "lxml")
            for chapter in self._extract_chapters(page_soup, url, metadata.get("title")):
                if isinstance(chapter.get("num"), int):
                    chapters_by_number[int(chapter["num"])] = chapter
            if max_chapter is not None and chapters_by_number and max(chapters_by_number) >= max_chapter:
                break

        metadata["chapters"] = [
            chapters_by_number[number]
            for number in sorted(chapters_by_number)
            if max_chapter is None or number <= max_chapter
        ]
        return metadata

    async def fetch_chapter(self, url: str) -> str:
        html = await self._fetch_page(url)
        return self._parse_chapter_html(html)


