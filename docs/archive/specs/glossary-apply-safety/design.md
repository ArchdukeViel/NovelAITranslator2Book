# Design: Glossary Apply Safety and Reversibility

## Overview

This spec builds on the existing `GlossaryApplyPreviewService` (which classifies replacements as safe/needs_review/blocked) and the existing `storage/translations.py` versioning infrastructure (which already supports multi-version bundles, `glossary_revision`, and `activate_translated_chapter_version`). The missing pieces are: a write-capable apply engine, a new `ChapterVersionKind`, a commit endpoint, a rollback endpoint, and the delta-fraction safety guard wired into both preview and commit.

The dependency direction is preserved: the new orchestration function lives in `services/orchestration/glossary.py`, the router stays thin, and no storage module imports from the API layer.

## Architecture

### Affected Files

| File | Change type |
|---|---|
| `backend/src/novelai/core/chapter_state.py` | Add `GLOSSARY_APPLY` to `ChapterVersionKind` enum |
| `backend/src/novelai/storage/translations.py` | Accept `"glossary_apply"` in `_normalize_version_kind`; add `batch_id` field support to version and edit_history |
| `backend/src/novelai/services/glossary_apply_preview.py` | Add `delta_fraction` computation; pre-classify over-threshold chapters as `blocked` |
| `backend/src/novelai/services/orchestration/glossary.py` | Add `apply_glossary_to_chapters` function |
| `backend/src/novelai/services/novel_orchestration_service.py` | Bind `apply_glossary_to_chapters` onto the service |
| `backend/src/novelai/api/routers/admin_glossary.py` | Add `POST /apply/commit` and `POST /apply/rollback` endpoints |
| `backend/src/novelai/api/routers/admin_chapters.py` (or equivalent) | Add `POST /chapters/{chapter_id}/versions/{version_id}/activate` endpoint |
| `backend/tests/test_glossary_apply_engine.py` | New — apply engine and rollback tests |

### Files Not Touched

- `prompts/` — prompt layer (prompt-translation-hardening spec owns this)
- `storage/glossary.py` — glossary file persistence unchanged
- `api/routers/public.py` — public reader unchanged
- `db/models/` — no new DB tables; `glossary_revision` is already tracked on `novels`

## Component Design

### 1. `ChapterVersionKind.GLOSSARY_APPLY`

Add to `core/chapter_state.py`:
```python
class ChapterVersionKind(str, enum.Enum):
    MACHINE_TRANSLATION = "machine_translation"
    MANUAL_EDIT = "manual_edit"
    ROLLBACK = "rollback"
    GLOSSARY_APPLY = "glossary_apply"   # NEW
    # ... existing values
```

`storage/translations.py::_normalize_version_kind` must accept `"glossary_apply"` and return `ChapterVersionKind.GLOSSARY_APPLY.value`. The function already normalizes unknown values to a default — add `"glossary_apply"` to the recognized set.

### 2. `storage/translations.py` — `batch_id` Support

`save_translated_chapter` must accept an optional `batch_id: str | None = None` parameter. When provided, store it inside the version dict:
```python
if isinstance(batch_id, str) and batch_id.strip():
    translated_payload["batch_id"] = batch_id.strip()
```

`_append_edit_history` must similarly accept and store `batch_id`.

`load_translated_chapter` must include `batch_id` in the returned dict (defaulting to `None`).

`list_translated_chapter_versions` must include `batch_id` per version.

### 3. `GlossaryApplyPreviewService` — Delta Fraction

Extend the per-chapter preview result model:

```python
@dataclass
class ChapterApplyPreview:
    chapter_id: str
    chapter_number: int | None
    replacements: list[ReplacementCandidate]
    status: Literal["safe", "needs_review", "blocked"]
    block_reason: str | None
    delta_fraction: float    # NEW: changed_chars / original_chars
```

Computation:
```python
original_text = active_translation.get("text", "")
simulated_text = _apply_replacements_dry(original_text, safe_replacements)
delta_fraction = (
    len(simulated_text) - len(original_text)
) / max(1, len(original_text))
delta_fraction = abs(delta_fraction)  # use absolute change ratio
```

Pre-classification: if `delta_fraction > max_delta_fraction` (default 0.15), override `status = "blocked"` with `block_reason = "delta_fraction_exceeded"`.

The `ApplyPreviewServiceRequest` must accept `max_delta_fraction: float = 0.15`.

### 4. Apply Engine — `apply_glossary_to_chapters` (Orchestration)

```python
async def apply_glossary_to_chapters(
    self: Any,
    novel_id: str,
    *,
    entry_ids: list[int] | None = None,
    include_all_approved: bool = False,
    chapter_numbers: list[int] | None = None,
    chapter_start: int | None = None,
    chapter_end: int | None = None,
    max_chapters: int | None = None,
    dry_run: bool = True,
    max_delta_fraction: float = 0.15,
    force_needs_review: bool = False,
    batch_id: str | None = None,
) -> ApplyGlossaryResult:
```

Execution sequence:
1. Load novel metadata; resolve DB `novel_id` from `novel_id` slug.
2. Call `GlossaryApplyPreviewService.preview()` with supplied parameters and `max_delta_fraction`. Collect `per_chapter_previews`.
3. Read `current_glossary_revision` from the DB (via `GlossaryRepository` or novel record).
4. If `dry_run=True`, return a result containing all per-chapter previews with `delta_fraction` but no storage writes.
5. If `dry_run=False`, iterate chapters:
   - Skip chapters with `status == "blocked"`.
   - Skip chapters with `status == "needs_review"` unless `force_needs_review=True`.
   - For `status == "safe"` (and allowed `needs_review`):
     - Apply replacements to `active_translation["text"]` using the `safe_replacements` list.
     - Compute final `delta_fraction` on actual replacement result.
     - If `delta_fraction > max_delta_fraction`, mark `blocked` and skip.
     - Call `save_translated_chapter(novel_id, chapter_id, new_text, version_kind=GLOSSARY_APPLY, glossary_revision=current_glossary_revision, batch_id=batch_id, base_version_id=previous_version_id, ...)`.
     - On I/O exception: mark chapter `failed`, log, continue.
6. Return `ApplyGlossaryResult`.

#### `ApplyGlossaryResult` dataclass

```python
@dataclass
class ChapterApplyResult:
    chapter_id: str
    status: Literal["applied", "skipped", "blocked", "failed"]
    replacements_made: int
    delta_fraction: float
    new_version_id: str | None
    previous_version_id: str | None
    block_reason: str | None = None
    error: str | None = None

@dataclass
class ApplyGlossaryResult:
    novel_id: str
    dry_run: bool
    batch_id: str | None
    glossary_revision: int
    chapters: list[ChapterApplyResult]
    total_applied: int
    total_skipped: int
    total_blocked: int
    total_failed: int
```

### 5. Replacement Text Engine

The apply engine needs a deterministic text replacement function. Build it in a new module `services/glossary_rewrite.py`:

```python
def apply_glossary_replacements(
    text: str,
    replacements: list[ReplacementCandidate],
    *,
    protect_markers: bool = True,
) -> tuple[str, int]:
    """Return (rewritten_text, replacement_count).

    Rules:
    - Sort replacements by match_start descending (apply right-to-left to preserve offsets).
    - Each replacement: replace substring at [match_start:match_end] with `replacement_text`.
    - If protect_markers=True, skip any replacement whose span overlaps a [CHAPTER ...] or [P pNNNN] marker span.
    - No replacement may overlap another already-applied span.
    """
```

Protected span detection:
```python
import re
MARKER_PATTERN = re.compile(r'\[(?:CHAPTER\s[^\]]+|P\s+p\d+)\]')

def _marker_spans(text: str) -> list[tuple[int, int]]:
    return [(m.start(), m.end()) for m in MARKER_PATTERN.finditer(text)]
```

Replacement algorithm (right-to-left, safe against offset drift):
1. Collect all `ReplacementCandidate` spans from the preview service.
2. Sort descending by `match_start`.
3. Maintain a set of "committed spans" (initially the marker spans).
4. For each replacement: if its span overlaps any committed span, skip it. Otherwise apply and add to committed spans.
5. Count applied replacements.

Longest-match priority: the preview service's replacement list may already de-duplicate overlapping candidates. If not, sort candidates by span length descending before right-to-left sort so longer matches win ties.

### 6. Router — Commit Endpoint

```python
@router.post(
    "/novels/{novel_id}/glossary/apply/commit",
    response_model=GlossaryApplyCommitResponse,
)
async def commit_glossary_apply(
    novel_id: str,
    body: GlossaryApplyCommitRequest,
    session: Session = Depends(get_db_session),
    storage: StorageService = Depends(get_storage),
    owner=Depends(require_role("owner")),
) -> GlossaryApplyCommitResponse:
```

The handler:
1. Calls `orchestration.apply_glossary_to_chapters(novel_id, ..., dry_run=body.dry_run)`.
2. Maps the result to `GlossaryApplyCommitResponse`.
3. Returns HTTP 200 in all non-exception cases (partial failures are reported in the response body, not as HTTP errors).

`GlossaryApplyCommitRequest`:
```python
class GlossaryApplyCommitRequest(BaseModel):
    entry_ids: list[int] | None = None
    include_all_approved: bool = False
    chapter_numbers: list[int] | None = None
    chapter_start: int | None = None
    chapter_end: int | None = None
    max_chapters: int | None = None
    dry_run: bool = False
    max_delta_fraction: float = Field(default=0.15, ge=0.0, le=1.0)
    force_needs_review: bool = False
    batch_id: str | None = None
```

`GlossaryApplyCommitResponse`:
```python
class GlossaryApplyCommitResponse(BaseModel):
    novel_id: str
    dry_run: bool
    batch_id: str | None
    glossary_revision: int
    chapters: list[GlossaryApplyChapterResult]
    total_applied: int
    total_skipped: int
    total_blocked: int
    total_failed: int

class GlossaryApplyChapterResult(BaseModel):
    chapter_id: str
    status: str  # "applied" | "skipped" | "blocked" | "failed"
    replacements_made: int
    delta_fraction: float
    new_version_id: str | None
    previous_version_id: str | None
    block_reason: str | None
```

### 7. Router — Rollback Endpoints

**Single-chapter rollback:**
```python
@router.post(
    "/novels/{novel_id}/chapters/{chapter_id}/versions/{version_id}/activate",
    response_model=ChapterVersionActivateResponse,
)
async def activate_chapter_version(
    novel_id: str,
    chapter_id: str,
    version_id: str,
    storage: StorageService = Depends(get_storage),
    _owner=Depends(require_role("owner")),
) -> ChapterVersionActivateResponse:
```

Calls `storage.activate_translated_chapter_version(novel_id, chapter_id, version_id)`. Returns 404 if version not found.

**Bulk rollback by batch_id:**
```python
@router.post(
    "/novels/{novel_id}/glossary/apply/rollback",
    response_model=GlossaryApplyRollbackResponse,
)
async def rollback_glossary_apply(
    novel_id: str,
    body: GlossaryApplyRollbackRequest,  # {"batch_id": "..."}
    storage: StorageService = Depends(get_storage),
    _owner=Depends(require_role("owner")),
) -> GlossaryApplyRollbackResponse:
```

Algorithm:
1. List all chapter IDs for the novel (from metadata or storage).
2. For each chapter: load version list, find the version whose `batch_id` matches.
3. If found: call `activate_translated_chapter_version` with the `base_version_id` of that version (the version before apply).
4. Return per-chapter rollback result.

This does not need an orchestration function — it is thin enough to live in the router with direct storage calls, since it is purely a storage operation with no business logic.

### 8. Test Design

`tests/test_glossary_apply_engine.py` uses fixtures with fake chapter bundles (no provider calls, no real storage):

**Apply engine tests:**
- `test_apply_all_safe_chapters` — 3 chapters, all safe, verify 3 versions written with `kind=glossary_apply`
- `test_apply_skips_needs_review_by_default` — 2 safe + 1 needs_review → needs_review not written
- `test_apply_force_needs_review` — same setup with `force_needs_review=True` → needs_review written
- `test_apply_never_writes_blocked` — 1 blocked chapter even with `force_needs_review=True` → not written
- `test_delta_fraction_guard` — chapter where replacement would change >15% → blocked, not written
- `test_partial_failure` — 2nd chapter raises IOError → 1st and 3rd succeed, 2nd marked failed
- `test_dry_run_no_writes` — `dry_run=True` → no storage calls made, result contains delta_fraction
- `test_batch_id_stored_in_version` — apply with `batch_id="run-001"` → version `batch_id` field = `"run-001"`

**Rollback tests:**
- `test_single_chapter_rollback` — activate a previous version, assert `active_translation_version_id` updated
- `test_rollback_returns_404_for_unknown_version`
- `test_bulk_rollback_by_batch_id` — 2 chapters with `batch_id="run-001"`, rollback → both chapters back to `base_version_id`
- `test_bulk_rollback_skips_chapters_without_batch_id`

**Preview delta_fraction tests:**
- `test_preview_includes_delta_fraction` — assert field present in response
- `test_preview_blocks_chapter_over_threshold` — delta > 0.15 → `status = "blocked"`, `block_reason = "delta_fraction_exceeded"`

**Overlap and marker protection tests:**
- `test_longer_match_wins_over_shorter` — term "Akira Sensei" and term "Akira" both match → only "Akira Sensei" replacement applied
- `test_marker_text_not_replaced` — chapter marker `[P p001]` contains text that matches a glossary term → marker not altered
- `test_no_double_replacement` — two terms whose replacements create a new occurrence of a third term → third not replaced

## Migration and Backward Compatibility

- `ChapterVersionKind.GLOSSARY_APPLY` is an additive enum value.
- `save_translated_chapter` gains an optional `batch_id` parameter — all existing call sites are unaffected.
- `GlossaryApplyPreviewService` result gains `delta_fraction` — existing callers that don't read this field are unaffected.
- No DB schema changes.
- No storage file format changes — `batch_id` is an optional field in the version dict; old readers ignore unknown fields.

## Acceptance Criteria

1. `POST /novels/{novel_id}/glossary/apply/commit` with `dry_run=false` writes new chapter versions with `kind="glossary_apply"`, `glossary_revision`, `batch_id`, and `base_version_id` for each applied chapter.
2. No chapter classified as `blocked` is ever written, regardless of request flags.
3. A chapter whose replacement delta exceeds `max_delta_fraction` is blocked and not written.
4. `[CHAPTER ...]` and `[P pNNNN]` markers are never altered by any replacement.
5. `POST /novels/{novel_id}/glossary/apply/rollback` with a `batch_id` reverts all chapters written in that apply run to their pre-apply versions.
6. `POST /novels/{novel_id}/chapters/{chapter_id}/versions/{version_id}/activate` returns 404 for an unknown version_id and correctly activates a valid version.
7. All new tests pass.
