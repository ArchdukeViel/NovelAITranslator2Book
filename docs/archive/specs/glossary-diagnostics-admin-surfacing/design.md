# Design: Glossary Diagnostics Admin Surfacing

## Overview

This design surfaces compact glossary prompt-injection diagnostics in admin-only views.

The project already has several related observability and state surfaces: glossary prompt injection metadata, glossary revision/hash metadata, activity metadata, runtime-state style admin APIs, catalog/source health patterns, and structured error/status reporting. This spec should reuse those existing surfaces instead of creating a separate diagnostics system.

The goal is to let admins answer practical questions:

- Was glossary injection available for this translation?
- How many glossary terms were available and injected?
- Was the prompt glossary block truncated?
- Were conflicts or warnings detected?
- Which chapters need glossary review?

The design is additive and diagnostic-only. It must not change glossary approval rules, prompt construction rules, term injection selection, scheduler behavior, translation output, active-version selection, or public reader behavior.

## Scope

This spec covers:

- normalizing raw glossary prompt-injection metadata into a compact diagnostics contract,
- persisting diagnostics on new translation versions,
- aggregating diagnostics into translation activity metadata,
- exposing diagnostics in admin APIs,
- displaying diagnostics in admin/editor UI,
- providing lightweight admin filtering and summary counts,
- adding focused backend and frontend tests.

This spec does not cover:

- changing which glossary terms are injected,
- changing prompt templates,
- changing glossary approval workflows,
- changing glossary revision invalidation behavior,
- changing editor QA enforcement,
- adding public reader glossary annotations,
- exposing diagnostics publicly,
- storing full prompt/source/translation text.

## Architecture

### Affected Files

| File | Change type |
|---|---|
| `backend/src/novelai/translation/stages/translate.py` or equivalent `TranslateStage` | Read glossary prompt-injection metadata from translation context and attach normalized diagnostics to version metadata |
| `backend/src/novelai/services/glossary_prompt_injection.py` | Verify emitted metadata shape and safe warning/conflict codes; avoid rule changes unless needed for safe diagnostics |
| `backend/src/novelai/services/glossary_diagnostics.py` | Add compact normalization and aggregation helpers |
| `backend/src/novelai/storage/translations.py` | Persist and expose diagnostics on new translation versions |
| Activity queue/worker/orchestration path | Persist activity-level aggregate diagnostics in activity metadata |
| Admin operations/runtime-state API, if present | Reuse existing diagnostics/status surface for summary fields |
| Admin/editor API routers and response models | Expose diagnostics fields additively |
| Admin frontend translation/activity UI | Show counts, badges, warnings, conflicts, and legacy state |
| `backend/tests/test_glossary_diagnostics_admin_surfacing.py` | Add focused tests |

### Files Not Touched

- Public reader routes.
- Glossary approval/edit business rules.
- Prompt templates, except metadata pass-through if necessary.
- Provider/model scheduler policy.
- Translation cache identity.
- Active-version selection.
- Manual editor QA enforcement.

## Diagnostic Data Contract

### Per-Version Diagnostics

Persist a compact admin-only diagnostics object on new translation versions:

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
    ],
    "diagnostics_available": true
  }
}
```

Rules:

- `warnings` and `conflicts` must be bounded lists.
- Store safe machine-readable codes.
- Store glossary terms only when those terms are already admin-visible glossary entries.
- Do not store full prompt blocks.
- Do not store source chapter text.
- Do not store translated chapter text.
- Do not store provider request/response bodies.
- Do not store secrets or account identifiers.
- Include `diagnostics_available` so legacy/unavailable states are explicit.
- If glossary revision/hash metadata is already produced by glossary revision invalidation, reuse those fields and do not introduce a second source of truth.

### Activity Aggregate Diagnostics

Persist activity-level aggregate metadata:

```json
{
  "glossary_diagnostics_summary": {
    "chapters_with_diagnostics": 42,
    "chapters_missing_diagnostics": 0,
    "chapters_with_conflicts": 3,
    "chapters_with_warnings": 5,
    "chapters_with_truncated_blocks": 2,
    "chapters_with_zero_injected_terms": 1,
    "total_terms_available": 1200,
    "total_terms_injected": 530,
    "warning_count": 8,
    "conflict_count": 4
  }
}
```

This summary must be computed from compact diagnostics objects, not from full prompts or chapter text.

## Normalization Helper

Add a helper in:

```text
backend/src/novelai/services/glossary_diagnostics.py
```

Suggested API:

```python
MAX_GLOSSARY_DIAGNOSTIC_ITEMS = 20
MAX_GLOSSARY_DIAGNOSTIC_TERM_LENGTH = 120

def normalize_glossary_diagnostics(
    metadata: Mapping[str, Any],
) -> dict[str, Any]:
    ...
```

Behavior:

- Accept raw `TranslationContext.metadata`, glossary prompt injection metadata, or existing normalized diagnostics.
- Return a compact dict matching the diagnostics contract.
- Return explicit unavailable state when diagnostics cannot be derived.
- Default missing counts to `0`.
- Default booleans to `False`.
- Bound warning and conflict lists to `MAX_GLOSSARY_DIAGNOSTIC_ITEMS`.
- Truncate or omit terms longer than `MAX_GLOSSARY_DIAGNOSTIC_TERM_LENGTH`.
- Omit free-form messages unless already safe, bounded, and admin-appropriate.
- Never include full prompt/source/translation text.

Unavailable-state example:

```json
{
  "diagnostics_available": false,
  "term_count_available": 0,
  "term_count_injected": 0,
  "prompt_block_truncated": false,
  "warning_count": 0,
  "conflict_count": 0,
  "warnings": [],
  "conflicts": []
}
```

## Translation Pipeline Integration

At translation completion or immediately before saving a translation version:

1. Read raw glossary prompt-injection metadata from `TranslationContext.metadata`.
2. Normalize it with `normalize_glossary_diagnostics`.
3. Attach the normalized object to the translation version payload under `glossary_diagnostics`.
4. Reuse existing top-level `glossary_revision`, `glossary_hash`, and `glossary_term_count` fields if glossary invalidation already provides them.
5. Do not duplicate glossary revision/hash source-of-truth logic.
6. Save through existing translation version storage.

Sketch:

```python
diagnostics = normalize_glossary_diagnostics(context.metadata)

version_metadata["glossary_diagnostics"] = diagnostics

if "glossary_revision" not in version_metadata:
    version_metadata["glossary_revision"] = diagnostics.get("glossary_revision")

if "glossary_hash" not in version_metadata:
    version_metadata["glossary_hash"] = diagnostics.get("glossary_hash")

if "glossary_term_count" not in version_metadata:
    version_metadata["glossary_term_count"] = diagnostics.get("term_count_available")
```

## Activity Aggregation

Aggregate diagnostics into activity metadata after each chapter result or at activity completion.

Preferred helper:

```python
def aggregate_glossary_diagnostics(
    diagnostics_items: Iterable[Mapping[str, Any]],
) -> dict[str, Any]:
    ...
```

Aggregation rules:

```python
chapters_with_diagnostics += diagnostics["diagnostics_available"] is True
chapters_missing_diagnostics += diagnostics["diagnostics_available"] is not True
chapters_with_conflicts += diagnostics["conflict_count"] > 0
chapters_with_warnings += diagnostics["warning_count"] > 0
chapters_with_truncated_blocks += diagnostics["prompt_block_truncated"] is True
chapters_with_zero_injected_terms += (
    diagnostics["term_count_available"] > 0
    and diagnostics["term_count_injected"] == 0
)
total_terms_available += diagnostics["term_count_available"]
total_terms_injected += diagnostics["term_count_injected"]
warning_count += diagnostics["warning_count"]
conflict_count += diagnostics["conflict_count"]
```

Rules:

- Use activity metadata update helpers already used by other observability specs.
- Preserve existing activity metadata keys.
- Do not overwrite crawl/fetch, scheduler, or glossary QA activity metadata.
- Aggregation must be safe under parallel chapter translation.
- If per-chapter results are not available in memory, compute summary from saved translation versions at completion.

## Admin API Integration

Expose diagnostics additively in admin-only APIs:

- translation activity detail,
- translation activity metadata,
- chapter translation detail,
- chapter version list/detail,
- novel translation summary if aggregate counts are available,
- operations/runtime-state or diagnostics route if one already exists.

Example version response:

```json
{
  "version_id": "v4",
  "provider": "openai",
  "model": "example-model",
  "glossary_revision": 12,
  "glossary_hash": "sha256:abc123",
  "glossary_diagnostics": {
    "diagnostics_available": true,
    "term_count_available": 48,
    "term_count_injected": 21,
    "prompt_block_truncated": false,
    "conflict_count": 1,
    "warning_count": 2
  }
}
```

If strict response models are used, update them to preserve these fields.

Public reader endpoints must not expose glossary diagnostics.

## Filtering Strategy

First implementation should support lightweight admin filtering and summary counts.

Supported filter flags:

- `has_glossary_conflicts`
- `has_glossary_warnings`
- `has_truncated_glossary_block`
- `zero_injected_glossary_terms`
- `missing_glossary_diagnostics`

Rules:

- Prefer filtering from saved version metadata.
- Avoid loading full chapter text.
- If scanning many translation files is too expensive, expose aggregate counts first and leave deep filtering for later optimization.
- Do not implement frontend-only filtering that requires loading full chapter or prompt text.

## Admin UI Design

### Activity Detail

Show:

- glossary diagnostics summary panel,
- chapters with diagnostics,
- missing diagnostics count,
- conflict count,
- warning count,
- truncated glossary block count,
- zero-injection chapter count,
- link to glossary management when conflicts exist.

### Chapter/Version Review

Show badges:

- `Glossary diagnostics available`
- `Glossary injected`
- `Glossary conflict`
- `Glossary warning`
- `Glossary block truncated`
- `No glossary terms injected`
- `Diagnostics unavailable`

Show details:

- term counts: `21 / 48 terms injected`,
- glossary revision/hash when available,
- bounded warning list,
- bounded conflict list,
- legacy/unavailable explanatory text.

### Empty/Legacy State

For old versions:

```text
Glossary diagnostics not available for this version.
```

## Security and Size Controls

Diagnostics must stay compact and admin-only.

Rules:

- No full prompt text.
- No source chapter text.
- No translated chapter text.
- No provider secrets.
- No raw provider responses.
- No account identifiers.
- Bounded warning/conflict lists.
- Safe codes preferred over free-form messages.
- Admin-only API exposure.
- Public reader exclusion must be tested.

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
- Glossary revision/hash fields are reused when already present.
- Existing crawl/fetch, scheduler, and editor QA metadata remain intact.

## Test Design

Create:

```text
backend/tests/test_glossary_diagnostics_admin_surfacing.py
```

Backend tests:

- `test_normalize_glossary_diagnostics_full_metadata`
- `test_normalize_glossary_diagnostics_missing_fields`
- `test_normalize_glossary_diagnostics_unavailable_state`
- `test_normalize_glossary_diagnostics_bounds_warning_lists`
- `test_normalize_glossary_diagnostics_truncates_long_terms`
- `test_translation_version_persists_glossary_diagnostics`
- `test_activity_metadata_includes_glossary_diagnostics_summary`
- `test_activity_summary_does_not_overwrite_other_observability_metadata`
- `test_admin_version_response_includes_glossary_diagnostics`
- `test_admin_activity_response_includes_glossary_diagnostics_summary`
- `test_public_reader_response_excludes_glossary_diagnostics`
- `test_legacy_translation_without_diagnostics_loads`

Frontend tests if UI is changed:

- activity summary renders,
- conflict badge renders,
- warning badge renders,
- truncation badge renders,
- zero-injection badge renders,
- legacy version fallback renders,
- diagnostics unavailable state renders.

## Acceptance Criteria

1. Per-version glossary diagnostics are persisted for new translations.
2. Activity-level glossary diagnostics summary is available when translation activity completes.
3. Admin activity and chapter/version APIs expose diagnostics additively.
4. Admin UI shows injection counts, truncation warnings, conflict indicators, and unavailable states.
5. Diagnostics are bounded and do not store full prompt/source/translation text.
6. Diagnostics reuse existing glossary revision/hash metadata when available.
7. Public reader APIs do not expose admin diagnostics.
8. Legacy translations and activities without diagnostics remain compatible.
9. Existing crawl/fetch, scheduler, editor QA, and activity metadata remain intact.
10. Focused backend and frontend tests pass.