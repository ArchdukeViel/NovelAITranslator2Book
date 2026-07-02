# Design: Translation QA Hardening

## Overview

Four targeted changes to existing files plus tests. The pipeline stage order is unchanged. No new modules needed. Changes: (1) add CJK residue and repetition checks to `qa.py`, (2) update `qa_status` in chunk output records after QA stage runs, (3) add soft activation gate in `save_translated_chapter`, (4) add glossary term check to `TranslationQAStage`.

## Architecture

### Affected Files

| File | Change type |
|---|---|
| `backend/src/novelai/translation/qa.py` | Add `_check_source_language_residue`, `_check_repetition`, optional `approved_glossary` param to `evaluate_translation_quality` |
| `backend/src/novelai/translation/pipeline/stages/translation_qa.py` | Update chunk output `qa_status` after evaluation; pass glossary terms to `evaluate_translation_quality` |
| `backend/src/novelai/storage/translations.py` | Add `auto_activate: bool = True` parameter to `save_translated_chapter` |
| `backend/src/novelai/config/settings.py` | Add `TRANSLATION_LOW_CONFIDENCE_ACTIVATION_THRESHOLD` setting |
| `backend/src/novelai/services/orchestration/translation.py` | Pass `auto_activate` flag based on confidence score |
| `backend/src/novelai/api/routers/library.py` | Expose `qa_status`, `qa_score`, `qa_warnings`, `qa_errors` in version list response |
| `backend/tests/test_translation_qa_hardening.py` | New |

### Files Not Touched

- `translate.py` — TranslateStage unchanged
- `post_process.py` — PostProcessStage unchanged
- Pipeline stage ordering — unchanged
- Public router — unchanged

## Component Design

### 1. New QA Checks in `qa.py`

#### Constants (top of file)
```python
CJK_RESIDUE_ERROR_THRESHOLD: float = 0.10   # > 10% CJK → error
CJK_RESIDUE_WARNING_THRESHOLD: float = 0.03  # 3–10% CJK → warning
REPETITION_ERROR_THRESHOLD: float = 0.30    # > 30% duplicate lines → error
REPETITION_WARNING_THRESHOLD: float = 0.15  # 15–30% → warning
REPETITION_MIN_LINES: int = 5               # only check when output ≥ 5 lines
```

#### `_check_source_language_residue`
```python
_CJK_RANGES = [
    (0x4E00, 0x9FFF),   # CJK Unified Ideographs
    (0x3040, 0x309F),   # Hiragana
    (0x30A0, 0x30FF),   # Katakana
    (0xF900, 0xFAFF),   # CJK Compatibility Ideographs
]

def _is_cjk(ch: str) -> bool:
    cp = ord(ch)
    return any(lo <= cp <= hi for lo, hi in _CJK_RANGES)

def _check_source_language_residue(
    output_text: str,
    *,
    warnings: list[str],
    errors: list[str],
) -> None:
    if len(output_text) <= 50:
        return
    cjk_count = sum(1 for ch in output_text if _is_cjk(ch))
    ratio = cjk_count / max(1, len(output_text))
    if ratio > CJK_RESIDUE_ERROR_THRESHOLD:
        errors.append("cjk_residue_high")
    elif ratio > CJK_RESIDUE_WARNING_THRESHOLD:
        warnings.append("cjk_residue_moderate")
```

#### `_check_repetition`
```python
_MARKER_LINE_PATTERN = re.compile(r'^\s*\[(?:CHAPTER|P\s+p\d+)', re.IGNORECASE)

def _check_repetition(
    output_text: str,
    *,
    warnings: list[str],
    errors: list[str],
) -> None:
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
```

#### Glossary term check in `evaluate_translation_quality`
```python
def evaluate_translation_quality(
    *,
    source_text: str,
    translated_text: str,
    chunk: TranslationChunk | None = None,
    structured_output: bool = False,
    approved_glossary: list[dict] | None = None,   # NEW
) -> TranslationQAResult:
    ...
    _check_source_language_residue(output_text, warnings=warnings, errors=errors)
    _check_repetition(output_text, warnings=warnings, errors=errors)
    if approved_glossary:
        _check_glossary_terms(source_text, output_text, approved_glossary, warnings=warnings)
    ...
```

```python
_GLOSSARY_MAX_TERMS = 20

def _check_glossary_terms(
    source_text: str,
    output_text: str,
    approved_glossary: list[dict],
    *,
    warnings: list[str],
) -> None:
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
```

### 2. `TranslationQAStage` — Update Chunk Output `qa_status` + Pass Glossary

In `TranslationQAStage.run()`, after updating `context.chunk_states[chunk_id]`, add:
```python
# Best-effort update persisted output record qa_status
try:
    storage.upsert_chunk_state(
        novel_id=context.novel_id,
        chapter_id=context.chapter_id,
        translation_run_id=context.metadata.get("translation_run_id"),
        chunk_id=chunk_id,
        updates={
            "qa_status": "passed" if result.passed else "qa_failed",
            "qa_score": result.score,
            "qa_warnings": list(result.warnings),
            "qa_errors": list(result.errors),
        },
    )
except Exception:
    pass  # audit update, non-blocking
```

For glossary terms, extract from `context.metadata.get("glossary_prompt_blocks", [])`:
```python
approved_glossary = _extract_glossary_terms_from_context(context)
result = evaluate_translation_quality(
    ...,
    approved_glossary=approved_glossary,
)
```

```python
def _extract_glossary_terms_from_context(context: PipelineContext) -> list[dict] | None:
    blocks = context.metadata.get("glossary_prompt_blocks")
    if not isinstance(blocks, list) or not blocks:
        return None
    # The blocks list contains per-chunk records; use the first block's injected terms list
    # context.metadata.get("glossary_injected_terms") may also hold a consolidated list
    # Fall back to parsing the rendered block — keep it simple: use the raw list if available
    terms = context.metadata.get("glossary_approved_terms")  # if TranslateStage populates this
    if isinstance(terms, list):
        return terms
    return None
```

If `context.metadata` does not already carry a consolidated glossary term list, `TranslateStage` should be updated (in a follow-up or in this same task) to set `context.metadata["glossary_approved_terms"]` from the `PromptGlossaryBlock.included_terms`.

### 3. `save_translated_chapter` — `auto_activate` Parameter

```python
def save_translated_chapter(
    self: Any,
    novel_id: str,
    chapter_id: str,
    text: str,
    ...,
    auto_activate: bool = True,   # NEW
) -> Path:
    ...
    versions.append(translated_payload)
    payload["translation_versions"] = versions
    if auto_activate:
        self._set_active_translation_version(payload, translated_payload)
    else:
        logger.warning(
            "Chapter %s/%s saved with auto_activate=False — version %s not activated.",
            novel_id, chapter_id, translated_payload["id"],
        )
    return self._persist_chapter_bundle(novel_id, chapter_id, payload)
```

### 4. `settings.py` — New Constant

```python
TRANSLATION_LOW_CONFIDENCE_ACTIVATION_THRESHOLD: float = float(
    os.getenv("TRANSLATION_LOW_CONFIDENCE_ACTIVATION_THRESHOLD", "0.55")
)
```

### 5. Orchestration — Pass `auto_activate`

In `orchestration/translation.py`, the call to `self.storage.save_translated_chapter(...)` or the equivalent in `TranslationService` output handling:
```python
confidence = context.metadata.get("confidence_score")
auto_activate = (
    confidence is None
    or not isinstance(confidence, float)
    or confidence >= settings.TRANSLATION_LOW_CONFIDENCE_ACTIVATION_THRESHOLD
)
self.storage.save_translated_chapter(
    ...,
    auto_activate=auto_activate,
)
if not auto_activate:
    logger.warning("Chapter %s saved with low confidence (%s), not activated.", chapter_id, confidence)
```

### 6. Admin Library — Expose QA Fields in Version List

`list_translated_chapter_versions` already returns all version dict fields. The admin version list response model must include:
```python
class TranslationVersionSummary(BaseModel):
    version_id: str
    version_kind: str
    active: bool
    provider: str | None
    model: str | None
    translated_at: str | None
    confidence_score: float | None
    qa_status: str | None = None     # NEW
    qa_score: float | None = None    # NEW
    qa_warnings: list[str] = []     # NEW
    qa_errors: list[str] = []       # NEW
```

These fields come from the version dict returned by `list_translated_chapter_versions`. They default to `None`/`[]` for legacy versions.

### 7. Test Design

`test_translation_qa_hardening.py` — all unit tests against `evaluate_translation_quality` and `save_translated_chapter` with temp fixtures:

- CJK residue tests: construct strings with known CJK ratios using `"あ"` (hiragana) characters
- Repetition tests: construct outputs with known duplicate line counts
- Activation tests: call `save_translated_chapter` with low/high `confidence_score` and assert `active_translation_version_id` is/isn't set
- `qa_status` update test: mock `upsert_chunk_state`, run `TranslationQAStage`, assert mock called with `qa_status="passed"` or `"qa_failed"`

## Migration and Backward Compatibility

- `save_translated_chapter` gains `auto_activate=True` (default). All existing call sites that don't pass it continue to activate normally — no regression.
- `evaluate_translation_quality` gains `approved_glossary=None` (default). All existing call sites continue to work.
- New QA errors (`cjk_residue_high`, `repetition_high`) will cause previously-passing translations to fail QA. This is intentional. Operators should review affected chapters and may need to re-translate.
- `qa_status` update in chunk output records is best-effort and non-blocking.

## Acceptance Criteria

1. A translation output with >10% CJK characters fails QA with `errors=["cjk_residue_high"]`.
2. A translation with 40% duplicate lines (≥5 lines) fails QA with `errors=["repetition_high"]`.
3. A chapter with `confidence_score=0.40` is saved but its version is not active; `activate_translated_chapter_version` can promote it.
4. After `TranslationQAStage` runs, chunk output records have `qa_status="passed"` or `"qa_failed"` (not `"pending"`).
5. When approved glossary terms are in context, a missing target term produces `"glossary_term_missing:{term}"` in warnings.
6. All 13 tests pass.
