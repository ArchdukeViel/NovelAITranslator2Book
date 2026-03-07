from __future__ import annotations

import re
from typing import Any, Optional

import httpx
from bs4 import BeautifulSoup, Tag

from novelai.core.errors import SourceError
from novelai.sources.base import SourceAdapter


def _attribute_to_str(value: object) -> str | None:
    """Normalize a BeautifulSoup attribute value to a single string."""
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        parts = [part for part in value if isinstance(part, str)]
        return parts[0] if len(parts) == 1 else None
    return None


class SyosetuNcodeSource(SourceAdapter):
    """Source adapter for syosetu.com novels (ncode)."""

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

        if candidate.startswith(("http://", "https://")):
            try:
                path_parts = [part for part in httpx.URL(candidate).path.split("/") if part]
            except Exception:
                return candidate
            if path_parts:
                return path_parts[0]
        return candidate.strip("/")

    def _normalize_url(self, identifier_or_url: str) -> str:
        # Accept either a full URL or the ncode identifier.
        novel_id = self.normalize_novel_id(identifier_or_url)
        return f"https://ncode.syosetu.com/{novel_id.strip('/')}/"

    async def fetch_metadata(self, url: str) -> dict[str, Any]:
        url = self._normalize_url(url)
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
        try:
            async with httpx.AsyncClient(timeout=30, headers=headers) as client:
                resp = await client.get(url)
                resp.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise SourceError(
                f"Failed to fetch metadata from {url} (status={exc.response.status_code}). "
                "Check that the novel ID is correct and the site is accessible."
            ) from exc

        soup = BeautifulSoup(resp.text, "lxml")

        # Title / author (fallbacks for modern Syosetu HTML)
        title = None
        author = None

        title_tag = soup.select_one(".p-novel__title") or soup.find("p", class_="novel_title")
        if title_tag:
            title = title_tag.get_text(strip=True)

        author_tag = soup.select_one(".p-novel__author") or soup.find(id="novel_writername")
        if author_tag:
            author = author_tag.get_text(strip=True)

        # Chapter list: modern Syosetu uses links like /nXXXXXX/1/ /nXXXXXX/2/ ...
        # We'll gather them by regex rather than relying on a specific wrapper.
        base_path = re.escape(httpx.URL(url).path)
        pattern = re.compile(rf"^{base_path}(\d+)/?$")
        chapter_urls: dict[int, dict[str, str | int]] = {}

        base_url = httpx.URL(url)
        base_root = str(base_url.copy_with(path="/"))

        for a in soup.find_all("a", href=True):
            if not isinstance(a, Tag):
                continue
            href = _attribute_to_str(a.get("href"))
            if href is None:
                continue
            match = pattern.match(href)
            if not match:
                # also try full URL variants
                if href.startswith("http"):
                    if href.startswith(base_root):
                        rel = httpx.URL(href).path
                        match = pattern.match(rel)
                if not match:
                    continue

            chap_num = int(match.group(1))
            chapter_urls[chap_num] = {
                "id": str(chap_num),
                "num": chap_num,
                "title": a.get_text(strip=True) or f"Chapter {chap_num}",
                "url": str(httpx.URL(url).join(href)),
            }

        chapters = [chapter_urls[i] for i in sorted(chapter_urls)]

        # Attempt to capture published/updated dates for downstream UI.
        date_text = soup.get_text(separator="|", strip=True)
        dates = re.findall(r"\d{4}/\d{2}/\d{2}", date_text)
        published_at = dates[0] if dates else None
        updated_at = dates[-1] if dates else None

        return {
            "source": "syosetu_ncode",
            "source_url": url,
            "title": title,
            "author": author,
            "published_at": published_at,
            "updated_at": updated_at,
            "chapters": chapters,
        }

    async def fetch_chapter(self, url: str) -> str:
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
        try:
            async with httpx.AsyncClient(timeout=30, headers=headers) as client:
                resp = await client.get(url)
                resp.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise SourceError(
                f"Failed to fetch chapter from {url} (status={exc.response.status_code}). "
                "Check that the chapter URL is correct and accessible."
            ) from exc

        soup = BeautifulSoup(resp.text, "lxml")
        # Modern Syosetu uses `.p-novel__body` as the story body container.
        body = soup.select_one(".p-novel__body")
        if not body:
            raise SourceError("Unable to find chapter text on Syosetu page")

        # Preserve paragraph structure, using newline separation.
        text = body.get_text(separator="\n", strip=True)
        return text


