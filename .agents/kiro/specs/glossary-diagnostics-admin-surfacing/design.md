# Design: Glossary Diagnostics Admin Surfacing

## Overview

This design persists and surfaces compact glossary prompt-injection diagnostics for admin users. The translation pipeline already knows useful facts about glossary injection. This feature turns those facts into stable metadata for activity views, chapter/version review screens, and issue filtering.

The design is additive and diagnostic-only. It does not change which glossary terms are injected, how prompts are built, or how translations are selected for the public reader.

## Architecture

### Affected Files

| File | Change type |
|---|---|
| `backend/src/novelai/translation/stages/translate.py` or equivalent `TranslateStage` | Collect raw glossary diagnostics from translation context |
| `backend/src/novelai/services/glossary_prompt_injection.py` | Confirm emitted diagnostic metadata shape; no rule changes unless needed for safe codes |
| `backend/src/novelai/storage/translations.py` | Persist compact diagnostics on translation versions |
| `backend/src/novelai/activity/queue.py` or activity worker path | Persist activity-level aggregate diagnostics |
| Admin/editor API routers and models | Expose diagnostics fields additively |
| Admin frontend translation/activity UI | Show badges, counts, warnings, links |
| `backend/tests/test_glossary_diagnostics_admin_surfacing.py` | New focused tests |

### Files Not Touched

- Public reader routes.
- Glossary approval/edit business rules.
- Translation prompt templates, except diagnostic metadata pass-through if necessary.
- Provider/model scheduling.

## Diagnostic Data Contract

### Compact Per-Chapter Diagnostics

Persist a compact dict like:

```json
{
  "glossary_diagnostics": {
    "glossary_revision": 12,
    "glossary_hash": "sha256:abc123",
    "term_count_available": 48,
    "term_count_injected": 21,
    "prompt_block_truncated": false,
    "conflict_count": 1,
    "warning_count": 2,
    "warnings": [
      {
        "code": "duplicate_translation",
        "term": "王都"
      }
    ],
    "conflicts": [
      {
        "code": "conflicting_approved_translation",
        "term": "魔王"
      }
    ]
  }
}
```

Rules:

- `warnings` and `conflicts` are bounded lists.
- Store safe codes and glossary terms only when those terms are already admin-visible glossary entries.
- Do not store full prompt blocks by default.
- Do not store source chapter text or translated chapter text in diagnostics.

### Activity Aggregate Diagnostics

Persist activity-level aggregate metadata like:

```json
{
  "glossary_diagnostics_summary": {
    "chapters_with_diagnostics": 42,
    "chapters_with_conflicts": 3,
    "chapters_with_truncated_blocks": 2,
    "chapters_with_zero_injected_terms": 1,
    "total_terms_available": 1200,
    "total_terms_injected": 530,
    "warning_count": 8,
    "conflict_count": 4
  }
}
```

This summary should be based on compact per-chapter diagnostics, not full prompt text.

## Normalization Helper

Add a helper that converts raw translation metadata into the compact diagnostics contract.

Suggested module location:

- `backend/src/novelai/services/glossary_diagnostics.py`, or
- a small helper near `TranslateStage` if the project keeps translation metadata helpers local.

API:

```python
MAX_GLOSSARY_DIAGNOSTIC_ITEMS = 20

def normalize_glossary_diagnostics(
    metadata: Mapping[str, Any],
) -> dict[str, Any]:
    ...
```

Behavior:

- Accept raw `context.metadata` or glossary prompt injection metadata.
- Return a compact dict.
- Missing values return `None`, `0`, or `false` according to field semantics.
- Warning/conflict lists are bounded to `MAX_GLOSSARY_DIAGNOSTIC_ITEMS`.
- Free-form messages are omitted unless already safe and bounded.

## Translation Pipeline Integration

At the end of translation or before saving the translation version:

1. Read raw glossary metadata from `TranslationContext.metadata`.
2. Normalize it.
3. Attach it to the translation version payload under `glossary_diagnostics`.
4. Include high-level fields directly if existing version list UI benefits from them:
   - `glossary_revision`
   - `glossary_hash`
   - `glossary_term_count`

Sketch:

```python
diagnostics = normalize_glossary_diagnostics(context.metadata)
version_metadata["glossary_diagnostics"] = diagnostics
version_metadata["glossary_revision"] = diagnostics.get("glossary_revision")
version_metadata["glossary_hash"] = diagnostics.get("glossary_hash")
```

If `glossary-revision-translation-invalidation` is already implemented, reuse its glossary revision/hash fields rather than duplicating source-of-truth logic.

## Activity Aggregation

For each translated chapter, accumulate diagnostics into activity metadata.

Possible approach:

- Store per-chapter diagnostics in translation version metadata.
- During translation activity completion, compute a summary from chapter results and write `metadata.glossary_diagnostics_summary`.

If activity worker already receives per-chapter result objects, aggregate there. If not, compute a summary from saved versions after translation completes.

Aggregation rules:

```python
chapters_with_conflicts += diagnostics["conflict_count"] > 0
chapters_with_truncated_blocks += diagnostics["prompt_block_truncated"] is True
chapters_with_zero_injected_terms += (
    diagnostics["term_count_available"] > 0
    and diagnostics["term_count_injected"] == 0
)
```

## Admin API Integration

Expose diagnostics additively in:

- activity detail response,
- translation activity metadata,
- chapter translation detail,
- chapter version list/detail,
- novel translation summary if aggregate count is available.

Example version response:

```json
{
  "version_id": "v4",
  "provider": "openai",
  "model": "example-model",
  "glossary_revision": 12,
  "glossary_hash": "sha256:abc123",
  "glossary_diagnostics": {
    "term_count_available": 48,
    "term_count_injected": 21,
    "prompt_block_truncated": false,
    "conflict_count": 1,
    "warning_count": 2
  }
}
```

If strict Pydantic models are used, update them to preserve these fields.

Do not expose diagnostics through public reader endpoints.

## Filtering Strategy

Preferred first implementation:

- API can filter or summarize by:
  - `has_glossary_conflicts`,
  - `has_truncated_glossary_block`,
  - `zero_injected_glossary_terms`.

If efficient filtering requires scanning many translation files, begin with aggregate counts in activity/novel summaries and leave deep filtering for a later optimization.

Do not implement frontend-only filtering that requires loading full chapter text.

## Admin UI Design

Show compact diagnostics in admin-only surfaces:

### Activity Detail

- Glossary diagnostics summary panel.
- Counts for conflicts, truncations, zero-injection chapters.
- Link to glossary management when conflicts exist.

### Chapter/Version Review

- Badge: `Glossary injected`.
- Badge: `Glossary conflict`.
- Badge: `Glossary block truncated`.
- Show term counts: `21 / 48 terms injected`.
- Show glossary revision/hash when available.
- Show bounded warning/conflict list.

### Empty/Legacy State

For old versions:

```text
Glossary diagnostics not available for this version.
```

## Security and Size Controls

Diagnostics must stay compact:

- No full prompt text.
- No source/translated chapter text.
- No provider secrets.
- Bounded warning/conflict lists.
- Safe codes preferred over free-form messages.
- Admin-only exposure.

Recommended bounds:

```python
MAX_GLOSSARY_DIAGNOSTIC_ITEMS = 20
MAX_GLOSSARY_DIAGNOSTIC_TERM_LENGTH = 120
```

## Migration and Backward Compatibility

- Existing translation versions without diagnostics remain loadable.
- Existing activity records without diagnostics remain loadable.
- Admin UI shows "not available" for legacy versions.
- Response fields are additive.
- Public reader behavior is unchanged.

## Test Design

Create `backend/tests/test_glossary_diagnostics_admin_surfacing.py`.

Core tests:

- `test_normalize_glossary_diagnostics_full_metadata`
- `test_normalize_glossary_diagnostics_missing_fields`
- `test_normalize_glossary_diagnostics_bounds_warning_lists`
- `test_translation_version_persists_glossary_diagnostics`
- `test_activity_metadata_includes_glossary_diagnostics_summary`
- `test_admin_version_response_includes_glossary_diagnostics`
- `test_public_reader_response_excludes_glossary_diagnostics`
- `test_legacy_translation_without_diagnostics_loads`

Frontend tests if UI is changed:

- activity summary renders,
- conflict badge renders,
- truncation badge renders,
- legacy version fallback renders.

## Acceptance Criteria

1. Per-chapter glossary diagnostics are persisted for new translations.
2. Activity-level glossary diagnostics summary is available when translation activity completes.
3. Admin activity and chapter/version APIs expose diagnostics additively.
4. Admin UI shows injection counts, truncation warnings, and conflict indicators.
5. Diagnostics are bounded and do not store full prompt/source/translation text.
6. Public reader APIs do not expose admin diagnostics.
7. Legacy translations and activities without diagnostics remain compatible.
8. Focused tests pass.

