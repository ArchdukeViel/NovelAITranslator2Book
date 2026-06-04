from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse


@dataclass(frozen=True)
class QualityGateResult:
    passed: bool
    score: float
    warnings: list[str]
    errors: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "passed": self.passed,
            "score": self.score,
            "warnings": list(self.warnings),
            "errors": list(self.errors),
        }


_JAPANESE_SOURCE_KEYS = {"syosetu_ncode", "novel18_syosetu", "kakuyomu", "narou"}
_BLOCK_PAGE_RE = re.compile(
    r"(cloudflare|checking your browser|access denied|captcha|cf-ray|error\s+403|error\s+404|"
    r"service unavailable|temporarily unavailable|enable javascript)",
    re.IGNORECASE,
)
_AGE_GATE_RE = re.compile(
    r"(ageauth|over18|18\+|adult verification|age verification|年齢確認|年齢認証|"
    r"18歳未満|18才未満|未成年)",
    re.IGNORECASE,
)
_NAV_WORDS = {
    "home",
    "top",
    "next",
    "previous",
    "prev",
    "profile",
    "login",
    "logout",
    "register",
    "search",
    "tag",
    "tags",
    "comment",
    "comments",
    "menu",
    "share",
    "follow",
    "author",
}
_IMAGE_PLACEHOLDER_RE = re.compile(r"\[(?:Image|Img|Illustration|Cover)(?::[^\]]*)?\]", re.IGNORECASE)


def evaluate_metadata_quality(
    metadata: dict[str, Any],
    *,
    source_key: str,
    novel_id: str | None = None,
    expected_episode_count: int | None = None,
) -> QualityGateResult:
    warnings: list[str] = []
    errors: list[str] = []

    title = metadata.get("title")
    if not isinstance(title, str) or not title.strip():
        errors.append("metadata_title_missing")

    source_url = metadata.get("source_url")
    if not isinstance(source_url, str) or not source_url.strip():
        errors.append("metadata_source_url_missing")

    metadata_source_key = metadata.get("source_key") or metadata.get("source")
    if not isinstance(metadata_source_key, str) or not metadata_source_key.strip():
        errors.append("metadata_source_key_missing")
    elif metadata_source_key != source_key:
        warnings.append("metadata_source_key_mismatch")

    source_novel_id = metadata.get("source_novel_id") or metadata.get("novel_id") or novel_id
    if source_key != "generic" and (not isinstance(source_novel_id, str) or not source_novel_id.strip()):
        warnings.append("metadata_novel_id_missing")

    chapters = metadata.get("chapters")
    if not isinstance(chapters, list) or len(chapters) == 0:
        errors.append("metadata_chapter_count_empty")
        return _result(warnings, errors)

    urls: list[str] = []
    nums: list[int] = []
    for chapter in chapters:
        if not isinstance(chapter, dict):
            warnings.append("metadata_chapter_invalid")
            continue
        url = chapter.get("url")
        if isinstance(url, str) and url.strip():
            urls.append(url.strip())
        else:
            warnings.append("metadata_chapter_url_missing")
        num = chapter.get("num")
        if isinstance(num, int):
            nums.append(num)
        elif isinstance(chapter.get("id"), str) and str(chapter["id"]).isdigit():
            nums.append(int(str(chapter["id"])))

    if len(urls) != len(set(urls)):
        warnings.append("metadata_duplicate_chapter_url")
    if nums and nums != sorted(nums):
        warnings.append("metadata_chapter_order_unsorted")
    if len(set(nums)) != len(nums):
        warnings.append("metadata_duplicate_chapter_number")
    if expected_episode_count is not None and expected_episode_count != len(chapters):
        warnings.append("metadata_episode_count_mismatch")

    return _result(warnings, errors)


def evaluate_chapter_quality(
    text: str,
    *,
    source_key: str,
    url: str | None = None,
    images: list[dict[str, Any]] | None = None,
    duplicate_hashes: set[str] | None = None,
) -> QualityGateResult:
    warnings: list[str] = []
    errors: list[str] = []
    normalized = text.strip() if isinstance(text, str) else ""

    if not normalized:
        errors.append("chapter_text_empty")
        return _result(warnings, errors)

    if detect_age_gate_text(normalized):
        errors.append("age_gate")
    if detect_block_page_text(normalized):
        errors.append("blocked_or_gate")

    if len(normalized) < 5:
        errors.append("chapter_text_too_short")
    elif len(normalized) < 80:
        warnings.append("chapter_text_short")

    if _nav_boilerplate_ratio(normalized) >= 0.65:
        errors.append("chapter_navigation_boilerplate")
    elif _nav_boilerplate_ratio(normalized) >= 0.35:
        warnings.append("chapter_navigation_boilerplate")

    if source_key in _JAPANESE_SOURCE_KEYS and len(normalized) >= 120:
        ratio = _japanese_ratio(normalized)
        if ratio < 0.02:
            warnings.append("chapter_japanese_ratio_low")

    expected_placeholders = {
        str(image.get("placeholder"))
        for image in images or []
        if isinstance(image, dict) and isinstance(image.get("placeholder"), str)
    }
    present_placeholders = set(_IMAGE_PLACEHOLDER_RE.findall(normalized))
    if expected_placeholders and not expected_placeholders.issubset(present_placeholders):
        warnings.append("chapter_image_placeholder_mismatch")

    if duplicate_hashes is not None:
        digest = chapter_content_hash(normalized)
        if digest in duplicate_hashes:
            warnings.append("chapter_duplicate_content_hash")

    if url and _looks_like_asset_url(url):
        errors.append("chapter_url_looks_like_asset")

    return _result(warnings, errors)


def detect_age_gate_text(text: str) -> bool:
    return bool(_AGE_GATE_RE.search(text or ""))


def detect_block_page_text(text: str) -> bool:
    return bool(_BLOCK_PAGE_RE.search(text or ""))


def chapter_content_hash(text: str) -> str:
    normalized = re.sub(r"\s+", "\n", text.strip())
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def _result(warnings: list[str], errors: list[str]) -> QualityGateResult:
    score = max(0.0, min(1.0, 1.0 - len(set(errors)) * 0.35 - len(set(warnings)) * 0.08))
    return QualityGateResult(
        passed=not errors,
        score=round(score, 3),
        warnings=list(dict.fromkeys(warnings)),
        errors=list(dict.fromkeys(errors)),
    )


def _nav_boilerplate_ratio(text: str) -> float:
    lines = [line.strip().lower() for line in re.split(r"[\n|]+", text) if line.strip()]
    if not lines:
        return 0.0
    nav_like = 0
    for line in lines:
        tokens = re.findall(r"[a-zA-Z]+", line)
        if not tokens:
            continue
        if len(tokens) <= 4 and sum(1 for token in tokens if token.lower() in _NAV_WORDS) >= max(1, len(tokens) // 2):
            nav_like += 1
    return nav_like / len(lines)


def _japanese_ratio(text: str) -> float:
    chars = [char for char in text if not char.isspace()]
    if not chars:
        return 0.0
    japanese = sum(1 for char in chars if "\u3040" <= char <= "\u30ff" or "\u4e00" <= char <= "\u9fff")
    return japanese / len(chars)


def _looks_like_asset_url(url: str) -> bool:
    path = urlparse(url).path.lower()
    return path.endswith((".jpg", ".jpeg", ".png", ".gif", ".webp", ".css", ".js", ".svg"))
