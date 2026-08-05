"""Kakuyomu HTML and __NEXT_DATA__ parsing routines."""

from __future__ import annotations

import json
import logging
from typing import Any

from bs4 import BeautifulSoup, Tag

logger = logging.getLogger(__name__)

BODY_SELECTORS = (
    ".widget-episodeBody",
    ".js-episode-body",
    "[data-episode-body]",
    "article [itemprop='articleBody']",
    ".episode-body",
)
TITLE_SELECTORS = (
    ".widget-workTitle",
    ".widget-workCard-title",
    "#workTitle",
    "h1[itemprop='name']",
    "main h1",
)
AUTHOR_SELECTORS = (
    ".widget-authorName",
    "[itemprop='author']",
    "[rel='author']",
    "[data-author-name]",
)
EPISODE_TITLE_SELECTORS = (
    ".widget-toc-episode-episodeTitleLabel",
    ".widget-toc-episode-episodeTitle",
    ".widget-toc-episodeTitleLabel",
    ".widget-toc-episodeTitle",
    ".episode-title",
)
REMOVE_FROM_BODY_SELECTORS = (
    ".widget-episode-actions",
    ".shareButtons",
    ".share-buttons",
    ".widget-share",
    ".js-share",
)
RUBY_REMOVE_SELECTORS = ("rt", "rp")
SEPARATOR_LINE = "-" * 60


def apollo_ref(value: Any) -> str | None:
    if isinstance(value, dict):
        ref = value.get("__ref")
        if isinstance(ref, str) and ref.strip():
            return ref.strip()
    return None


def apollo_record(apollo_state: dict[str, Any], ref_or_key: str | None) -> dict[str, Any] | None:
    if not isinstance(ref_or_key, str) or not ref_or_key.strip():
        return None
    record = apollo_state.get(ref_or_key.strip())
    return record if isinstance(record, dict) else None


def next_data_apollo_state(soup: BeautifulSoup) -> dict[str, Any] | None:
    script = soup.find("script", id="__NEXT_DATA__")
    if not isinstance(script, Tag):
        return None
    raw_json = script.string
    if not isinstance(raw_json, str) or not raw_json.strip():
        return None

    try:
        data = json.loads(raw_json)
    except json.JSONDecodeError:
        return None

    page_props = data.get("props", {}).get("pageProps", {})
    apollo_state = page_props.get("__APOLLO_STATE__")
    return apollo_state if isinstance(apollo_state, dict) else None


def extract_chapters_from_next_data(
    soup: BeautifulSoup,
    work_id: str,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    apollo_state = next_data_apollo_state(soup)
    if apollo_state is None:
        return [], {"metadata_extraction_mode": "html_dom"}

    work = apollo_record(apollo_state, f"Work:{work_id}")
    if work is None:
        root_query = apollo_state.get("ROOT_QUERY")
        if isinstance(root_query, dict):
            for key, val in root_query.items():
                if key.startswith(f'work({{"id":"{work_id}"') or key == f"work:{work_id}":
                    work_ref = apollo_ref(val)
                    work = apollo_record(apollo_state, work_ref)
                    if work:
                        break

    if work is None:
        # Fall back to scanning all Work records in apollo_state
        for key, rec in apollo_state.items():
            if key.startswith("Work:") and isinstance(rec, dict) and rec.get("id") == work_id:
                work = rec
                break

    if work is None:
        return [], {"metadata_extraction_mode": "html_dom", "apollo_record_count": len(apollo_state)}

    toc = work.get("tableOfContentsV2") or work.get("tableOfContents") or work.get("toc")
    if not isinstance(toc, list):
        return [], {"metadata_extraction_mode": "next_data_apollo", "apollo_record_count": len(apollo_state)}

    chapters: list[dict[str, Any]] = []
    seen_episode_ids: set[str] = set()

    for toc_item in toc:
        if isinstance(toc_item, dict):
            ref = apollo_ref(toc_item)
            toc_record = apollo_record(apollo_state, ref) if ref else toc_item
        else:
            toc_record = None
        if toc_record is None:
            continue

        part: str | None = None
        chapter_ref = apollo_ref(toc_record.get("chapter"))
        chapter_record = apollo_record(apollo_state, chapter_ref) if chapter_ref else None
        if chapter_record is not None:
            title = chapter_record.get("title")
            if isinstance(title, str) and title.strip():
                part = title.strip()

        episode_refs = toc_record.get("episodeUnions") or toc_record.get("episodes") or toc_record.get("episodeList")
        if not isinstance(episode_refs, list):
            # Check if toc_item itself is an episode record
            if toc_record.get("__typename") == "Episode":
                episode_refs = [toc_record]
            else:
                continue

        for episode_ref in episode_refs:
            episode_record = (
                apollo_record(apollo_state, apollo_ref(episode_ref))
                if isinstance(episode_ref, dict) and "__ref" in episode_ref
                else (episode_ref if isinstance(episode_ref, dict) else None)
            )
            if episode_record is None:
                continue
            episode_id = str(episode_record.get("id") or "").strip()
            if not episode_id or episode_id in seen_episode_ids:
                continue
            seen_episode_ids.add(episode_id)
            index = len(chapters) + 1
            title = episode_record.get("title")
            chapter: dict[str, Any] = {
                "id": f"kakuyomu:{episode_id}",
                "num": index,
                "sequence_number": index,
                "title": title.strip() if isinstance(title, str) and title.strip() else f"Episode {index}",
                "url": f"https://kakuyomu.jp/works/{work_id}/episodes/{episode_id}",
                "source_episode_id": episode_id,
            }
            if part:
                chapter["part"] = part
            published_at = episode_record.get("publishedAt") or episode_record.get("created")
            if isinstance(published_at, str) and published_at.strip():
                chapter["date_added"] = published_at.strip()
            chapters.append(chapter)

    provenance = {
        "metadata_extraction_mode": "next_data_apollo",
        "chapter_index_extraction_mode": "next_data_apollo",
        "apollo_record_count": len(apollo_state),
        "parser_version": "kakuyomu-v4",
        "fallbacks_used": [],
    }
    return chapters, provenance
