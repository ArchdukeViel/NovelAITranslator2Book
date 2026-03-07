from __future__ import annotations

import hashlib
import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

import httpx
from bs4 import BeautifulSoup, Tag

logger = logging.getLogger(__name__)


def utc_now_iso() -> str:
    """Return an ISO-8601 timestamp in UTC with a trailing Z."""
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def stable_digest(value: str, length: int = 12) -> str:
    return hashlib.sha1(value.encode("utf-8")).hexdigest()[:length]


def safe_filename(value: str, default: str = "item") -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "-", value.strip())
    cleaned = cleaned.strip("-._")
    return cleaned or default


def storage_key(*parts: str) -> str:
    return "__".join(safe_filename(part) for part in parts if part)


def soup_from_html(html: str) -> BeautifulSoup:
    return BeautifulSoup(html, "lxml")


def inner_html(tag: Tag) -> str:
    return "".join(str(child) for child in tag.contents)


def first_text(soup: BeautifulSoup, selectors: Iterable[str]) -> str | None:
    for selector in selectors:
        node = soup.select_one(selector)
        if node is None:
            continue
        text = node.get_text(" ", strip=True)
        if text:
            return text
    return None


def meta_content(soup: BeautifulSoup, *, name: str | None = None, prop: str | None = None) -> str | None:
    attrs: dict[str, str] = {}
    if name:
        attrs["name"] = name
    if prop:
        attrs["property"] = prop
    if not attrs:
        return None
    tag = soup.find("meta", attrs=attrs)
    if tag is None:
        return None
    content = tag.get("content")
    return content.strip() if isinstance(content, str) and content.strip() else None


def resolve_url(base_url: str | None, maybe_relative: str | None) -> str | None:
    if not maybe_relative:
        return None
    value = maybe_relative.strip()
    if not value:
        return None
    if base_url is None:
        return value
    try:
        return str(httpx.URL(base_url).join(value))
    except Exception:
        logger.debug("Could not resolve URL '%s' against '%s'.", value, base_url)
        return value


def domain_for_url(url: str) -> str:
    try:
        return (httpx.URL(url).host or "").lower()
    except Exception:
        return ""

