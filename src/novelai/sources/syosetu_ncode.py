from __future__ import annotations

from typing import Any, Optional

import httpx
from bs4 import BeautifulSoup

from novelai.core.errors import SourceError
from novelai.sources.base import SourceAdapter


class SyosetuNcodeSource(SourceAdapter):
    """Source adapter for syosetu.com novels (ncode)."""

    @property
    def key(self) -> str:
        return "syosetu_ncode"

    def _normalize_url(self, identifier_or_url: str) -> str:
        # Accept either a full URL or the ncode identifier.
        if identifier_or_url.startswith("http"):
            return identifier_or_url.rstrip("/")
        return f"https://ncode.syosetu.com/{identifier_or_url.strip('/')}/"

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
        import re

        base_path = re.escape(httpx.URL(url).path)
        pattern = re.compile(rf"^{base_path}(\d+)/?$")
        chapter_urls = {}

        base_url = httpx.URL(url)
        base_root = str(base_url.copy_with(path="/"))

        for a in soup.find_all("a", href=True):
            href = a["href"]
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


# Register the adapter
from novelai.sources.registry import register_source

register_source("syosetu_ncode", lambda: SyosetuNcodeSource())
