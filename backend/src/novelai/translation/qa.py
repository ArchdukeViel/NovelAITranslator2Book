from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any

from novelai.translation.pipeline.context import TranslationChunk


@dataclass(frozen=True)
class TranslationQAResult:
    score: float
    passed: bool
    warnings: list[str]
    errors: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "score": self.score,
            "passed": self.passed,
            "warnings": list(self.warnings),
            "errors": list(self.errors),
        }


class TranslationQAError(Exception):
    """Raised when deterministic translation QA rejects provider output."""

    error_code = "translation_qa_failed"
    qa_status = "qa_failed"

    def __init__(self, result: TranslationQAResult, message: str | None = None) -> None:
        self.result = result
        self.details = {"qa_result": result.to_dict()}
        super().__init__(message or "Translation QA failed: " + ", ".join(result.errors))


@dataclass(frozen=True)
class NormalizedTranslationOutput:
    text: str
    paragraph_map: list[dict[str, str]]
    structured: bool


_CHAPTER_MARKER_RE = re.compile(r"^\[CHAPTER\s+([^\]]+)\]\s*$", re.MULTILINE)
_PARAGRAPH_MARKER_RE = re.compile(r"^\[P\s+([^\]]+)\]\s*$", re.MULTILINE)
_MARKER_LINE_RE = re.compile(r"^\[(?:CHAPTER\s+[^\]]+|P\s+[^\]]+)\]\s*$", re.MULTILINE)
_IMAGE_PLACEHOLDER_RE = re.compile(
    r"(\[(?:image|img|illustration|cover)[^\]]*\]|\{\{\s*(?:image|img)[^}]*\}\}|!\[[^\]]*\]\([^)]+\))",
    re.IGNORECASE,
)
_TEXT_PLACEHOLDER_RE = re.compile(r"(\{\{[^{}\n]{1,80}\}\}|\{[^{}\n]{1,80}\}|\[[A-Z][A-Z0-9_:-]{1,80}\])")
_SCENE_BREAK_RE = re.compile(r"(?m)^\s*(?:\*\s*){3,}$|^\s*(?:-\s*){3,}$|^\s*(?:[◇◆]\s*){2,}$")
_REFUSAL_RE = re.compile(
    r"\b("
    r"as an ai language model|i can(?:not|'t)|i am unable|i'm unable|cannot comply|"
    r"content policy|safety policy|blocked by safety|refuse to|refusal"
    r")\b",
    re.IGNORECASE,
)
_PROVIDER_ERROR_RE = re.compile(
    r"\b("
    r"resource_exhausted|quota exceeded|rate limit|retry after|api error|provider error|"
    r"internal server error|model unavailable|invalid model|timeout"
    r")\b",
    re.IGNORECASE,
)
_SUMMARY_RE = re.compile(r"\b(summary|summarize|summarised|summarized|tl;dr)\b", re.IGNORECASE)


def normalize_translation_output(raw_output: str) -> NormalizedTranslationOutput:
    """Parse optional structured translation output while preserving plain text."""

    text = raw_output.strip()
    if not text:
        return NormalizedTranslationOutput(text="", paragraph_map=[], structured=False)

    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return NormalizedTranslationOutput(text=text, paragraph_map=[], structured=False)

    if not isinstance(payload, dict):
        return NormalizedTranslationOutput(text=text, paragraph_map=[], structured=False)

    paragraph_map = _normalize_paragraph_map(payload.get("paragraph_map"))
    translated_text = payload.get("translated_text")
    if isinstance(translated_text, str) and translated_text.strip():
        return NormalizedTranslationOutput(
            text=translated_text.strip(),
            paragraph_map=paragraph_map,
            structured=True,
        )

    if paragraph_map:
        joined = "\n\n".join(item["translated_text"] for item in paragraph_map if item.get("translated_text"))
        return NormalizedTranslationOutput(text=joined.strip(), paragraph_map=paragraph_map, structured=True)

    return NormalizedTranslationOutput(text=text, paragraph_map=[], structured=True)


def evaluate_translation_quality(
    *,
    source_text: str,
    translated_text: str,
    chunk: TranslationChunk | None = None,
    structured_output: bool = False,
) -> TranslationQAResult:
    normalized = normalize_translation_output(translated_text)
    output_text = normalized.text
    warnings: list[str] = []
    errors: list[str] = []

    _check_basic_text(source_text, output_text, warnings=warnings, errors=errors)
    _check_placeholders(source_text, output_text, warnings=warnings, errors=errors)
    _check_marker_coverage(source_text, output_text, chunk=chunk, warnings=warnings, errors=errors)
    _check_paragraph_map(
        normalized.paragraph_map,
        chunk=chunk,
        structured_output=structured_output or normalized.structured,
        warnings=warnings,
        errors=errors,
    )

    if _uses_multiple_provider_models(chunk):
        warnings.append("model_switch_warning")

    score = _score(warnings=warnings, errors=errors)
    return TranslationQAResult(score=score, passed=not errors and score >= 0.75, warnings=warnings, errors=errors)


def normalized_translation_text(raw_output: str) -> str:
    return normalize_translation_output(raw_output).text


def _normalize_paragraph_map(value: Any) -> list[dict[str, str]]:
    if not isinstance(value, list):
        return []
    normalized: list[dict[str, str]] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        paragraph_id = item.get("paragraph_id")
        translated = item.get("translated_text", item.get("translated"))
        if paragraph_id is None or translated is None:
            continue
        payload = {
            "paragraph_id": str(paragraph_id),
            "translated_text": str(translated),
        }
        chapter_id = item.get("chapter_id")
        if chapter_id is not None:
            payload["chapter_id"] = str(chapter_id)
        normalized.append(payload)
    return normalized


def _strip_markers(text: str) -> str:
    return _MARKER_LINE_RE.sub("", text or "").strip()


def _compact(text: str) -> str:
    return re.sub(r"\s+", "", text or "").casefold()


def _check_basic_text(source_text: str, output_text: str, *, warnings: list[str], errors: list[str]) -> None:
    if not output_text.strip():
        errors.append("translation_empty")
        return

    source_core = _strip_markers(source_text)
    output_core = _strip_markers(output_text)
    if source_core.strip() and _compact(source_core) == _compact(output_core):
        errors.append("translation_same_as_source")

    source_len = max(1, len(source_core.strip()))
    output_len = len(output_core.strip())
    ratio = output_len / source_len
    if source_len >= 80 and ratio < 0.08:
        errors.append("translation_too_short")
    elif source_len >= 80 and ratio < 0.20:
        warnings.append("translation_too_short")
    if source_len >= 40 and ratio > 8.0:
        errors.append("translation_too_long")
    elif source_len >= 40 and ratio > 4.5:
        warnings.append("translation_too_long")

    lowered = output_text.casefold()
    if _PROVIDER_ERROR_RE.search(lowered):
        errors.append("provider_error_text_detected")
    if _REFUSAL_RE.search(lowered):
        errors.append("provider_refusal_detected")
    if source_len >= 80 and _SUMMARY_RE.search(lowered) and ratio < 0.35:
        errors.append("translation_probably_summary")
    if output_core.rstrip().endswith(("...", "…")) and source_len >= 80:
        errors.append("translation_probably_truncated")


def _unique_matches(pattern: re.Pattern[str], text: str) -> list[str]:
    seen: set[str] = set()
    values: list[str] = []
    for match in pattern.findall(text or ""):
        value = match if isinstance(match, str) else match[0]
        if value in seen:
            continue
        seen.add(value)
        values.append(value)
    return values


def _check_placeholders(source_text: str, output_text: str, *, warnings: list[str], errors: list[str]) -> None:
    for placeholder in _unique_matches(_IMAGE_PLACEHOLDER_RE, source_text):
        if placeholder not in output_text:
            errors.append("image_placeholder_missing")
            break

    source_placeholders = [
        value
        for value in _unique_matches(_TEXT_PLACEHOLDER_RE, source_text)
        if not value.startswith("[CHAPTER ") and not value.startswith("[P ") and not _IMAGE_PLACEHOLDER_RE.fullmatch(value)
    ]
    for placeholder in source_placeholders:
        if placeholder not in output_text:
            errors.append("placeholder_missing")
            break

    for scene_break in _unique_matches(_SCENE_BREAK_RE, source_text):
        if scene_break.strip() and scene_break.strip() not in output_text:
            errors.append("scene_break_missing")
            break


def _marker_refs(text: str, chunk: TranslationChunk | None) -> list[tuple[str, str]]:
    refs: list[tuple[str, str]] = []
    current_chapter: str | None = None
    fallback_chapter = chunk.chapter_ids[0] if chunk and len(chunk.chapter_ids) == 1 else None
    for line in (text or "").splitlines():
        chapter_match = re.fullmatch(r"\[CHAPTER\s+([^\]]+)\]", line.strip())
        if chapter_match:
            current_chapter = chapter_match.group(1)
            continue
        paragraph_match = re.fullmatch(r"\[P\s+([^\]]+)\]", line.strip())
        if paragraph_match:
            chapter_id = current_chapter or fallback_chapter or ""
            refs.append((chapter_id, paragraph_match.group(1)))
    return refs


def _expected_refs(chunk: TranslationChunk | None) -> list[tuple[str, str]]:
    if chunk is None:
        return []
    if chunk.paragraph_refs:
        return list(chunk.paragraph_refs)
    if len(chunk.chapter_ids) == 1:
        return [(chunk.chapter_ids[0], paragraph_id) for paragraph_id in chunk.paragraph_ids]
    return []


def _check_marker_coverage(
    source_text: str,
    output_text: str,
    *,
    chunk: TranslationChunk | None,
    warnings: list[str],
    errors: list[str],
) -> None:
    expected = _expected_refs(chunk)
    output_refs = _marker_refs(output_text, chunk)
    source_had_markers = bool(_PARAGRAPH_MARKER_RE.search(source_text))
    if not expected or not source_had_markers:
        return
    if not output_refs:
        warnings.append("paragraph_mapping_unavailable")
        return

    if len(set(output_refs)) != len(output_refs):
        errors.append("paragraph_duplicate")
    missing = [ref for ref in expected if ref not in output_refs]
    unexpected = [ref for ref in output_refs if ref not in expected]
    if missing:
        errors.append("paragraph_missing")
    if unexpected:
        errors.append("paragraph_unexpected")
    if [ref for ref in output_refs if ref in expected] != expected:
        warnings.append("paragraph_order_mismatch")

    expected_chapters = [chapter_id for chapter_id in dict.fromkeys(chapter_id for chapter_id, _ in expected)]
    output_chapters = [chapter_id for chapter_id in dict.fromkeys(chapter_id for chapter_id, _ in output_refs)]
    if len(expected_chapters) > 1 and output_chapters != expected_chapters:
        errors.append("chapter_mapping_invalid")


def _check_paragraph_map(
    paragraph_map: list[dict[str, str]],
    *,
    chunk: TranslationChunk | None,
    structured_output: bool,
    warnings: list[str],
    errors: list[str],
) -> None:
    expected = _expected_refs(chunk)
    if not expected:
        return

    multi_chapter = len({chapter_id for chapter_id, _ in expected}) > 1
    if not paragraph_map:
        if structured_output:
            errors.append("paragraph_missing")
        elif multi_chapter:
            errors.append("chapter_mapping_invalid")
        return

    normalized_refs: list[tuple[str, str]] = []
    for item in paragraph_map:
        paragraph_id = item.get("paragraph_id", "")
        chapter_id = item.get("chapter_id")
        if not chapter_id and chunk is not None and len(chunk.chapter_ids) == 1:
            chapter_id = chunk.chapter_ids[0]
        if not chapter_id:
            errors.append("chapter_mapping_invalid")
            continue
        if not str(item.get("translated_text") or "").strip():
            errors.append("translation_empty")
        normalized_refs.append((str(chapter_id), str(paragraph_id)))

    if len(set(normalized_refs)) != len(normalized_refs):
        errors.append("paragraph_duplicate")
    if [ref for ref in normalized_refs if ref in expected] != expected:
        warnings.append("paragraph_order_mismatch")
    missing = [ref for ref in expected if ref not in normalized_refs]
    unexpected = [ref for ref in normalized_refs if ref not in expected]
    if missing:
        errors.append("paragraph_missing")
    if unexpected:
        errors.append("paragraph_unexpected")
    if multi_chapter and any(ref not in expected for ref in normalized_refs):
        errors.append("chapter_mapping_invalid")


def _score(*, warnings: list[str], errors: list[str]) -> float:
    score = 1.0 - (0.08 * len(set(warnings))) - (0.30 * len(set(errors)))
    return max(0.0, min(1.0, round(score, 3)))


def _uses_multiple_provider_models(chunk: TranslationChunk | None) -> bool:
    return False
