# Design: Glossary Revision Translation Invalidation

## Overview

This design connects glossary state to translation artifacts. A translation version should know which glossary revision/hash produced it, cache keys should vary when glossary state changes, and admin screens should be able to identify and retranslate stale chapters.

The design is additive: existing translation versions remain readable, active-version behavior remains unchanged, and public reader output continues to use the active translation version.

## Architecture

### Affected Files

| File | Change type |
|---|---|
| `backend/src/novelai/translation/stages/translate.py` or equivalent `TranslateStage` | Attach glossary revision/hash to translation context/output metadata |
| `backend/src/novelai/translation/cache.py` or equivalent cache helper | Include glossary revision/hash in cache keys |
| `backend/src/novelai/storage/translations.py` | Persist and expose glossary metadata on translation versions; compute stale state |
| `backend/src/novelai/services/orchestration/translation.py` | Add stale detection/retranslate-stale orchestration |
| Glossary service/model code | Ensure glossary revision increments on meaningful approved-term changes |
| Admin/editor API routers and models | Expose glossary freshness fields and retranslate stale operation |
| Admin frontend translation/version UI | Show stale badge and retranslate action |
| `backend/tests/test_glossary_revision_translation_invalidation.py` | New focused tests |

### Files Not Touched

- Public reader routes, unless they already expose admin-only version metadata.
- Source/crawler adapters.
- Raw chapter storage schema.
- Glossary editor business rules beyond revision increment verification.

## Data Model

### Translation Version Metadata

Add fields to every new translation version:

```json
{
  "id": "v3",
  "kind": "machine",
  "provider": "openai",
  "model": "example-model",
  "created_at": "2026-07-07T00:00:00Z",
  "text": "Translated text",
  "glossary_revision": 12,
  "glossary_hash": "sha256:abc123",
  "glossary_term_count": 48,
  "glossary_stale": false
}
```

Compatibility behavior:

- Missing `glossary_revision` means legacy/unknown.
- Missing `glossary_hash` means hash unavailable.
- Missing `glossary_stale` should be computed dynamically on read where possible.

### Current Glossary State

Current glossary state should be resolved from existing DB fields/services:

```python
@dataclass(frozen=True)
class GlossarySnapshot:
    revision: int
    hash: str | None
    approved_term_count: int | None
```

The hash should be stable for semantically meaningful approved glossary content. It should not change due to ordering differences or unrelated metadata timestamps.

Recommended hash input:

- canonical term
- approved translation
- term type
- enforcement level
- aliases if used by prompt injection
- status for approved/enforced terms

Do not include volatile fields like `updated_at` unless the project intentionally wants every edit timestamp to invalidate translations.

## Cache Key Design

Translation output cache keys must include glossary identity.

Existing cache dimensions likely include source text identity, provider, model, source/target language, prompt style/settings, and chunk identity. Add:

```json
{
  "glossary_revision": 12,
  "glossary_hash": "sha256:abc123"
}
```

Rules:

- If `glossary_hash` exists, include it.
- Always include `glossary_revision`.
- Legacy cache entries without glossary revision are not valid when current revision is non-zero.
- Do not delete old cache entries as part of this spec.

## Stale Detection

Add helper:

```python
def compute_glossary_stale(
    version: dict[str, Any],
    current: GlossarySnapshot,
) -> bool:
    version_revision = version.get("glossary_revision")
    version_hash = version.get("glossary_hash")

    if not isinstance(version_revision, int):
        return current.revision > 0

    if version_revision < current.revision:
        return True

    if current.hash and version_hash and version_hash != current.hash:
        return True

    return False
```

Also expose stale reason when useful:

```json
{
  "glossary_stale": true,
  "glossary_stale_reason": "revision_mismatch",
  "version_glossary_revision": 10,
  "current_glossary_revision": 12
}
```

Recommended stale reasons:

- `legacy_missing_revision`
- `revision_mismatch`
- `hash_mismatch`
- `fresh`

## Storage Integration

### Save Translation Version

When saving a translation version:

1. Resolve current glossary snapshot for the novel.
2. Merge glossary metadata into the version payload.
3. Save the version through existing storage helper.
4. Mark `glossary_stale=false` for the new version.

Sketch:

```python
snapshot = glossary_snapshot_service.for_novel(novel_id)
version_payload.update(
    {
        "glossary_revision": snapshot.revision,
        "glossary_hash": snapshot.hash,
        "glossary_term_count": snapshot.approved_term_count,
        "glossary_stale": False,
    }
)
storage.save_translated_chapter(...)
```

If `TranslateStage` already computes prompt glossary metadata, pass it through the translation context so storage does not need to recompute everything.

### Load/List Translation Versions

When loading or listing versions:

1. Resolve current glossary snapshot.
2. Add computed `glossary_stale`.
3. Add `current_glossary_revision`.
4. Add `glossary_stale_reason` where useful.

This dynamic computation avoids mass-rewriting version files after every glossary edit.

Persisted stale flags are optional. If implemented, they should be treated as a cache of computed state, not the source of truth.

## Glossary Revision Increment

Verify existing glossary code increments `Novel.glossary_revision` when meaningful approved glossary state changes.

Meaningful changes include:

- approved translation changed,
- approved term created,
- approved term deleted or deactivated,
- enforcement level changed,
- aliases used in prompt injection changed,
- term status changes into or out of approved/enforced state.

If revision increment is incomplete, update glossary write paths to increment it.

## Retranslate Stale Operation

Add or extend an admin operation:

```http
POST /admin/novels/{novel_id}/translations/retranslate-stale
```

Optional request body:

```json
{
  "chapter_ids": ["1", "2"],
  "activate": true,
  "provider": null,
  "model": null
}
```

Behavior:

- Find chapters whose active translation is stale.
- If `chapter_ids` is provided, restrict to those chapters.
- Create a normal translation activity/job using existing translation orchestration.
- Force retranslation only for stale chapters.
- Use current glossary revision/hash.
- Save new versions; do not overwrite old versions.
- Preserve existing active-version behavior.

Response:

```json
{
  "novel_id": "novel-id",
  "stale_chapter_count": 7,
  "scheduled_chapter_count": 7,
  "activity_id": "activity-id"
}
```

If the repository already has a retranslation endpoint, extend it with a `stale_only=true` option instead of adding a new endpoint.

## Admin API Response Shape

Additive fields for version list/detail:

```json
{
  "version_id": "v2",
  "glossary_revision": 10,
  "current_glossary_revision": 12,
  "glossary_hash": "sha256:old",
  "glossary_stale": true,
  "glossary_stale_reason": "revision_mismatch"
}
```

Novel summary may include:

```json
{
  "stale_translation_count": 7,
  "current_glossary_revision": 12
}
```

Update strict response models if needed.

## Admin UI

Add UI affordances:

- stale glossary badge in chapter/version list,
- stale count in novel translation overview,
- tooltip showing version revision vs current revision,
- retranslate stale action,
- post-retranslation fresh status.

Do not add public reader warnings in this spec.

## Migration and Backward Compatibility

- Existing translation versions remain readable.
- Legacy versions missing glossary metadata are reported as legacy/unknown and stale when current glossary revision is non-zero.
- Active version selection is unchanged.
- Old cache entries may remain but are not reused for current glossary revision.
- No DB migration is needed if `Novel.glossary_revision` already exists and is reliable.

## Test Design

Create `backend/tests/test_glossary_revision_translation_invalidation.py`.

Core tests:

- `test_translation_version_stores_glossary_revision`
- `test_translation_version_stores_glossary_hash_when_available`
- `test_cache_key_changes_when_glossary_revision_changes`
- `test_active_version_marked_stale_after_glossary_revision_increment`
- `test_historical_versions_compute_staleness_independently`
- `test_legacy_version_without_glossary_metadata_loads`
- `test_retranslate_stale_creates_new_fresh_version`
- `test_stale_detection_does_not_deactivate_active_version`
- `test_admin_version_response_includes_glossary_freshness`

Frontend tests if UI is changed:

- stale badge renders,
- retranslate stale action calls API,
- stale count appears in novel summary.

## Acceptance Criteria

1. New translation versions store glossary revision metadata.
2. Translation cache keys vary by glossary revision/hash.
3. Active and historical translation versions can be classified as fresh, stale, or legacy/unknown.
4. Glossary edits that increment revision make older translations visibly stale.
5. Admin APIs expose glossary freshness fields additively.
6. Admin can retranslate stale chapters and produce new fresh versions.
7. Stale detection does not automatically deactivate active versions.
8. Existing translation versions without glossary metadata remain loadable.
9. Existing glossary gate and prompt injection behavior remain intact.
10. Focused tests pass.

