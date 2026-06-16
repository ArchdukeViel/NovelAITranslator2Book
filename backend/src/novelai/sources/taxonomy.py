"""Shared taxonomy mapping for source adapters.

Maps source-site genre/category text to internal seeded genre slugs.
Normalizes source keywords/tags into clean lists.

These mappings are intentionally conservative: only map when the source text
unambiguously corresponds to a seeded genre slug. Unmapped values are
preserved as raw source data.
"""

from __future__ import annotations

from typing import Any

# ---------------------------------------------------------------------------
# Syosetu / Novel18 genre text → internal slug mapping
# ---------------------------------------------------------------------------

SYOSETU_GENRE_MAP: dict[str, str] = {
    "異世界転生": "isekai-tensei",
    "異世界転移": "isekai-tenni",
    "ファンタジー": "fantasy",
    "現代ファンタジー": "modern-fantasy",
    "SF": "sf",
    "恋愛": "romance",
    "ホラー": "horror",
    "ミステリー": "mystery",
    "アクション": "action",
    "コメディ": "comedy",
    "ドラマ": "drama",
    "日常": "slice-of-life",
    "歴史": "historical",
    "詩": "poetry",
    "エッセイ": "essay",
    "その他": "other",
}

NOVEL18_GENRE_MAP: dict[str, str] = {
    **SYOSETU_GENRE_MAP,
    "大人向け恋愛": "adult-romance",
    "大人向けファンタジー": "adult-fantasy",
    "大人向けSF": "adult-sf",
    "大人向けその他": "adult-other",
    # Novel18 also uses shorter forms
    "恋愛（R18）": "adult-romance",
    "ファンタジー（R18）": "adult-fantasy",
    "SF（R18）": "adult-sf",
}

# ---------------------------------------------------------------------------
# Kakuyomu genre/category text → internal slug mapping
# ---------------------------------------------------------------------------

KAKUYOMU_GENRE_MAP: dict[str, str] = {
    **SYOSETU_GENRE_MAP,
    # Kakuyomu may use slightly different labels
    "異世界ファンタジー": "fantasy",
    "現代ドラマ": "drama",
    "青春": "drama",
    "ライトノベル": "fantasy",
    "純文学": "other",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def map_genre(source_text: str | None, genre_map: dict[str, str]) -> str | None:
    """Map a source genre text to an internal slug.

    Returns the slug if the text matches exactly (after stripping),
    or None if no safe mapping exists.
    """
    if not source_text or not isinstance(source_text, str):
        return None
    cleaned = source_text.strip()
    if not cleaned:
        return None
    return genre_map.get(cleaned)


def normalize_keywords(raw_items: Any) -> list[str]:
    """Normalize a raw keyword/tag list into clean, deduplicated strings.

    Accepts:
    - A list of strings
    - A single string (split on whitespace, commas, or Japanese commas)
    - None or other types → empty list
    """
    if isinstance(raw_items, list):
        seen: set[str] = set()
        result: list[str] = []
        for item in raw_items:
            if isinstance(item, str):
                cleaned = item.strip()
                if cleaned and cleaned not in seen:
                    seen.add(cleaned)
                    result.append(cleaned)
        return result

    if isinstance(raw_items, str):
        import re
        parts = re.split(r"[,、\s]+", raw_items)
        return normalize_keywords(parts)

    return []
