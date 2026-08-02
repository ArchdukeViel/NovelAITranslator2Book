"""Shared contracts and helpers for guest-accessible public reader routes.

Provides the public reader surface (architecture.md §20):
- GET /api/public/catalog        — paginated novel list with search/filter
- GET /api/public/novels/{slug}  — novel detail
- GET /api/public/novels/{slug}/chapters — chapter list
- GET /api/public/novels/{slug}/chapters/{chapter_id} — translated chapter reader

Endpoints live in three canonical router files:
- ``public_catalog.py`` — catalog browse + genres
- ``public_novel.py`` — novel detail + chapter list
- ``public_chapter.py`` — chapter reader + tags search

This module holds only shared Pydantic models, constants, and helpers.
"""

from __future__ import annotations

import logging
import re
from datetime import datetime
from typing import Any

from pydantic import BaseModel

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

VALID_SORT_FIELDS = {"added_at", "updated_at", "title", "chapter_count"}
VALID_ORDER_VALUES = {"asc", "desc"}
DEFAULT_SORT_BY = "added_at"
DEFAULT_ORDER = "desc"
PUBLIC_SLUG_MAX_LENGTH = 160
PUBLIC_PROTOCOL_MARKER_RE = re.compile(
    r"^\s*(?:\[CHAPTER[^\]]*\]|\[P\s+p\d{4}\])\s*",
    re.IGNORECASE,
)
PUBLIC_PARAGRAPH_MARKER_RE = re.compile(
    r"^\s*\[P\s+p\d{4}\]\s*",
    re.IGNORECASE,
)

VALID_UNAVAILABLE_POLICIES = {"hard_404", "chapter_shell", "latest_version"}
DEFAULT_UNAVAILABLE_POLICY = "hard_404"

# --- DEBT-059 / REQ-9 public reader caching + REQ-7 annotation cap ------------
# Short edge TTL for safe, published, guest-visible responses. Keeps repeat reads
# fast while ensuring takedown / unpublish propagation within minutes. Personal
# or session-derived responses (auth/user routes) MUST NOT reuse this header.
PUBLIC_CACHE_MAX_AGE_SECONDS = 60

# Hard cap on glossary annotations embedded in a public chapter payload. Caps
# client-side render cost; extras are silently dropped by the router.
PUBLIC_GLOSSARY_ANNOTATIONS_MAX = 50


# ---------------------------------------------------------------------------
# Response models
# ---------------------------------------------------------------------------


class PublicGenreInfo(BaseModel):
    """Lightweight genre object embedded in novel payloads.

    Carries slug for filtering/links plus localized display names.
    This is the single canonical genre contract — no parallel slug array.
    """

    slug: str
    name_ja: str
    name_en: str | None = None


class PublicTagName(BaseModel):
    """Localized tag name pair embedded in novel payloads.

    Carries both romanised name and optional Japanese reading so the
    frontend can render a tooltip or secondary label without an extra
    /tags/search query.
    """

    name: str
    name_ja: str | None = None


class PublicNovelSummary(BaseModel):
    novel_id: str
    slug: str
    title: str
    source_title: str | None = None
    author: str | None = None
    language: str | None = None
    synopsis: str | None = None
    publication_status: str = "unknown"
    chapter_count: int = 0
    translated_count: int = 0
    added_at: str | None = None
    latest_chapter_id: str | None = None
    latest_chapter_number: int | None = None
    latest_chapter_title: str | None = None
    latest_chapter_updated_at: str | None = None
    genres: list[PublicGenreInfo] = []
    tags: list[PublicTagName] = []


class PublicChapterSummary(BaseModel):
    chapter_id: str
    title: str | None = None
    chapter_number: int | None = None
    translated: bool = False
    availability_status: str = "not_translated"
    part: str | None = None


class PublicCatalogResponse(BaseModel):
    novels: list[PublicNovelSummary]
    total: int
    page: int
    page_size: int
    degraded: bool = False


class PublicGenreResponse(BaseModel):
    slug: str
    name_ja: str
    name_en: str | None = None


class PublicTagSearchResult(BaseModel):
    name: str
    name_ja: str | None = None


class PublicReviewItem(BaseModel):
    id: int
    rating: int | None
    body: str | None
    created_at: datetime


class PublicReviewListResponse(BaseModel):
    items: list[PublicReviewItem]
    next_cursor: str | None = None


# ---------------------------------------------------------------------------
# Cross-router helpers
# ---------------------------------------------------------------------------


def _optional_str(value: Any) -> str | None:
    return value.strip() if isinstance(value, str) and value.strip() else None


def _parse_csv_filter(value: str | None) -> list[str]:
    """Parse comma-separated filter value, trim whitespace, drop empties."""
    if not value:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


def _datetime_to_public_string(value: datetime | None) -> str | None:
    return value.isoformat() if isinstance(value, datetime) else None
