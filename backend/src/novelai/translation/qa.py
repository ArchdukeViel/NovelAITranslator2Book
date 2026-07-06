from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any

from novelai.translation.pipeline.context import TranslationChunk

# --- CJK residue thresholds (REQ-3.7)
CJK_RESIDUE_ERROR_THRESHOLD: float = 0.10
CJK_RESIDUE_WARNING_THRESHOLD: float = 0.03

# --- Repetition thresholds (REQ-4.3, REQ-4.4, REQ-4.5)
REPETITION_ERROR_THRESHOLD: float = 0.30
REPETITION_WARNING_THRESHOLD: float = 0.15
REPETITION_MIN_LINES: int = 5

# --- Glossary check cap (REQ-5.4)
_GLOSSARY_MAX_TERMS = 20

_CJK_RANGES = [
    (0x4E00, 0x9FFF),   # CJK Unified Ideographs
    (0x3040, 0x309F),   # Hiragana
    (0x30A0, 0x30FF),   # Katakana
    (0xF900, 0xFAFF),   # CJK Compatibility Ideographs
]

_MARKER_LINE_PATTERN = re.compile(r'^\s*\[(?:CHAPTER|P\s+p\d+)', re.IGNORECASE)


@dataclass(frozen=True)
class TranslationQAResult:
    score: float
    passed: bool
    warnings: list[str]
    errors: list[str]
    diagnostics: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "score": self.score,
            "passed": self.passed,
            "warnings": list(self.warnings),
            "errors": list(self.errors),
        }
        if self.diagnostics:
            payload["diagnostics"] = dict(self.diagnostics)
        return payload


def _is_cjk(ch: str) -> bool:
    """Return True if *ch* falls in any CJK range (REQ-3.5)."""
    cp = ord(ch)
    return any(lo <= cp <= hi for lo, hi in _CJK_RANGES)


def _check_source_language_residue(
    output_text: str,
    *,
    warnings: list[str],
    errors: list[str],
) -> None:
    """Flag translated text with high CJK residue (REQ-3.1..REQ-3.4)."""
    if len(output_text) <= 50:
        return
    cjk_count = sum(1 for ch in output_text if _is_cjk(ch))
    ratio = cjk_count / max(1, len(output_text))
    if ratio > CJK_RESIDUE_ERROR_THRESHOLD:
        errors.append("cjk_residue_high")
    elif ratio > CJK_RESIDUE_WARNING_THRESHOLD:
        warnings.append("cjk_residue_moderate")


def _check_repetition(
    output_text: str,
    *,
    warnings: list[str],
    errors: list[str],
) -> None:
    """Flag output with excessive duplicated lines (REQ-4.1..REQ-4.5)."""
    lines = [ln for ln in output_text.splitlines() if ln.strip()]
    content_lines = [ln for ln in lines if not _MARKER_LINE_PATTERN.match(ln)]
    total = len(content_lines)
    if total < REPETITION_MIN_LINES:
        return
    unique = len(set(ln.strip() for ln in content_lines))
    dup_fraction = (total - unique) / total
    if dup_fraction > REPETITION_ERROR_THRESHOLD:
        errors.append("repetition_high")
    elif dup_fraction > REPETITION_WARNING_THRESHOLD:
        warnings.append("repetition_moderate")


def _check_glossary_terms(
    source_text: str,
    output_text: str,
    approved_glossary: list[dict],
    *,
    warnings: list[str],
) -> None:
    """Warn when approved glossary terms are missing from output (REQ-5.2)."""
    output_lower = output_text.casefold()
    checked = 0
    for entry in approved_glossary:
        if checked >= _GLOSSARY_MAX_TERMS:
            break
        source_term = entry.get("source", "")
        target_term = entry.get("target", "")
        if not source_term or not target_term:
            continue
        if source_term.casefold() not in source_text.casefold():
            continue  # term not in source — skip
        if target_term.casefold() not in output_lower:
            warnings.append(f"glossary_term_missing:{source_term}")
        checked += 1


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


def extract_unambiguous_json_object(raw_output: str) -> str:
    """Return the only parseable top-level JSON object in provider output."""

    text = (raw_output or "").strip()
    if not text:
        raise ValueError("JSON response is empty.")

    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        pass
    else:
        if isinstance(payload, dict):
            return text
        raise ValueError("JSON response must be an object.")

    candidates: list[str] = []
    start: int | None = None
    depth = 0
    in_string = False
    escaped = False
    for index, char in enumerate(text):
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
            continue
        if char == "{":
            if depth == 0:
                start = index
            depth += 1
        elif char == "}" and depth:
            depth -= 1
            if depth == 0 and start is not None:
                candidates.append(text[start : index + 1])
                start = None

    parseable: list[str] = []
    for candidate in candidates:
        try:
            payload = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            parseable.append(candidate)

    if len(parseable) == 1:
        return parseable[0]
    if len(parseable) > 1:
        raise ValueError("JSON response contains multiple parseable objects.")
    raise ValueError("JSON response does not contain a valid object.")


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
    r"as an ai language model|"
    r"(?:i\s+)?can(?:not|'t)\s+(?:comply|assist|help|provide|translate|fulfill|continue)|"
    r"i\s+(?:am|['’]m)\s+unable\s+to\s+(?:comply|assist|help|provide|translate|fulfill|continue)|"
    r"i\s+(?:must\s+)?refuse\s+to\s+(?:comply|assist|help|provide|translate|fulfill|continue)|"
    r"cannot comply|content policy|safety policy|blocked by safety"
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


def normalize_translation_output(raw_output: str, *, structured_output: bool = False) -> NormalizedTranslationOutput:
    """Parse optional structured translation output while preserving plain text."""

    text = raw_output.strip()
    if not text:
        return NormalizedTranslationOutput(text="", paragraph_map=[], structured=False)

    try:
        payload = json.loads(extract_unambiguous_json_object(text))
    except (json.JSONDecodeError, ValueError) as e:
        if structured_output:
            raise ValueError(f"structured_output_required: {e}") from e
        return NormalizedTranslationOutput(text=text, paragraph_map=[], structured=False)

    if not isinstance(payload, dict):
        if structured_output:
            raise ValueError("structured_output_required: JSON response must be an object")
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
    approved_glossary: list[dict] | None = None,
) -> TranslationQAResult:
    try:
        normalized = normalize_translation_output(translated_text, structured_output=structured_output)
    except ValueError as e:
        return TranslationQAResult(
            score=0.0,
            passed=False,
            warnings=[],
            errors=[str(e)],
            diagnostics={},
        )
    output_text = normalized.text
    warnings: list[str] = []
    errors: list[str] = []
    diagnostics: dict[str, Any] = {}

    # When structured_output is explicitly requested, validate the structure
    if structured_output:
        if not normalized.structured:
            errors.append("structured_output_required")
        elif not normalized.text.strip():
            errors.append("translated_text_required")
        elif not normalized.paragraph_map:
            errors.append("paragraph_map_required")

    _check_basic_text(source_text, output_text, warnings=warnings, errors=errors)
    _check_source_language_residue(output_text, warnings=warnings, errors=errors)
    _check_repetition(output_text, warnings=warnings, errors=errors)
    _check_placeholders(source_text, output_text, warnings=warnings, errors=errors)
    _check_marker_coverage(
        source_text,
        output_text,
        chunk=chunk,
        warnings=warnings,
        errors=errors,
        diagnostics=diagnostics,
    )
    _check_paragraph_map(
        normalized.paragraph_map,
        chunk=chunk,
        structured_output=structured_output or normalized.structured,
        warnings=warnings,
        errors=errors,
        diagnostics=diagnostics,
    )

    if _uses_multiple_provider_models(chunk):
        warnings.append("model_switch_warning")

    if approved_glossary:
        _check_glossary_terms(source_text, output_text, approved_glossary, warnings=warnings)

    score = _score(warnings=warnings, errors=errors)
    return TranslationQAResult(
        score=score,
        passed=not errors and score >= 0.75,
        warnings=warnings,
        errors=errors,
        diagnostics=diagnostics,
    )


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


def _ref_id(ref: tuple[str, str]) -> str:
    chapter_id, paragraph_id = ref
    return f"{chapter_id}:{paragraph_id}" if chapter_id else paragraph_id


def _duplicate_refs(refs: list[tuple[str, str]]) -> list[tuple[str, str]]:
    seen: set[tuple[str, str]] = set()
    duplicates: list[tuple[str, str]] = []
    for ref in refs:
        if ref in seen and ref not in duplicates:
            duplicates.append(ref)
        seen.add(ref)
    return duplicates


def _paragraph_diagnostics(
    *,
    expected: list[tuple[str, str]],
    actual: list[tuple[str, str]],
) -> dict[str, Any]:
    missing = [ref for ref in expected if ref not in actual]
    unexpected = [ref for ref in actual if ref not in expected]
    matching_order = [ref for ref in actual if ref in expected]
    return {
        "expected_count": len(expected),
        "output_count": len(actual),
        "missing_count": len(missing),
        "unexpected_count": len(unexpected),
        "duplicate_count": len(_duplicate_refs(actual)),
        "missing_ids": [_ref_id(ref) for ref in missing],
        "unexpected_ids": [_ref_id(ref) for ref in unexpected],
        "duplicate_ids": [_ref_id(ref) for ref in _duplicate_refs(actual)],
        "order_matches_expected": matching_order == expected,
    }


def _check_marker_coverage(
    source_text: str,
    output_text: str,
    *,
    chunk: TranslationChunk | None,
    warnings: list[str],
    errors: list[str],
    diagnostics: dict[str, Any],
) -> None:
    expected = _expected_refs(chunk)
    output_refs = _marker_refs(output_text, chunk)
    source_had_markers = bool(_PARAGRAPH_MARKER_RE.search(source_text))
    if not expected or not source_had_markers:
        return
    if not output_refs:
        warnings.append("paragraph_mapping_unavailable")
        diagnostics["marker_coverage"] = _paragraph_diagnostics(expected=expected, actual=output_refs)
        return

    marker_diagnostics = _paragraph_diagnostics(expected=expected, actual=output_refs)
    diagnostics["marker_coverage"] = marker_diagnostics
    if marker_diagnostics["duplicate_count"]:
        errors.append("paragraph_duplicate")
    if marker_diagnostics["missing_count"]:
        errors.append("paragraph_missing")
    if marker_diagnostics["unexpected_count"]:
        errors.append("paragraph_unexpected")
    if not marker_diagnostics["order_matches_expected"]:
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
    diagnostics: dict[str, Any],
) -> None:
    expected = _expected_refs(chunk)
    if not expected:
        return

    multi_chapter = len({chapter_id for chapter_id, _ in expected}) > 1
    if not paragraph_map:
        if structured_output:
            errors.append("paragraph_missing")
            diagnostics["paragraph_map"] = _paragraph_diagnostics(expected=expected, actual=[])
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

    map_diagnostics = _paragraph_diagnostics(expected=expected, actual=normalized_refs)
    diagnostics["paragraph_map"] = map_diagnostics
    if map_diagnostics["duplicate_count"]:
        errors.append("paragraph_duplicate")
    if not map_diagnostics["order_matches_expected"]:
        if structured_output:
            errors.append("paragraph_order_mismatch")
        else:
            warnings.append("paragraph_order_mismatch")
    if map_diagnostics["missing_count"]:
        errors.append("paragraph_missing")
    if map_diagnostics["unexpected_count"]:
        errors.append("paragraph_unexpected")
    if multi_chapter and any(ref not in expected for ref in normalized_refs):
        errors.append("chapter_mapping_invalid")
    elif not multi_chapter and expected and normalized_refs:
        # Single chapter: verify chapter_id matches if provided
        expected_chapter = expected[0][0]
        for ref in normalized_refs:
            if ref[0] != expected_chapter:
                errors.append("chapter_mapping_invalid")
                break


def _score(*, warnings: list[str], errors: list[str]) -> float:
    score = 1.0 - (0.08 * len(set(warnings))) - (0.30 * len(set(errors)))
    return max(0.0, min(1.0, round(score, 3)))


def _uses_multiple_provider_models(chunk: TranslationChunk | None) -> bool:
    return False
