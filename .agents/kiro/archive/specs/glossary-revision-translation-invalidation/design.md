# Design: Glossary Revision Translation Invalidation

## Overview

This design connects glossary freshness to translation versions, queued translation jobs, and admin retranslation decisions.

Glossary revision counters, glossary cache invalidation, prompt glossary injection, and translation cache identity may already exist. This spec must not redo those systems. Instead, it builds on them and focuses on:

* detecting stale translated versions after glossary changes,
* exposing freshness state to admin surfaces,
* invalidating or marking queued translation work when glossary state changes,
* giving admins safe choices for retranslation,
* preserving active-version behavior until an admin explicitly changes it.

The design is additive. Existing translation versions remain readable, public reader output continues to use the selected active translation version, and stale detection does not automatically deactivate or replace active versions.

## Scope

This spec covers:

* glossary metadata on new translation versions,
* computed stale/fresh/legacy state for active and historical versions,
* stale translated-version detection,
* queued translation job invalidation when glossary state changes,
* admin API fields for glossary freshness,
* admin retranslation choices for stale chapters,
* focused backend and admin UI tests.

This spec does not cover:

* redesigning glossary revision counters,
* rebuilding glossary cache invalidation,
* changing glossary-first onboarding,
* changing prompt glossary injection,
* changing public reader rendering,
* automatically replacing active versions,
* deleting old translations or old cache entries.

## Architecture

### Affected Files

| File                                                                                 | Change type                                                                                                     |
| ------------------------------------------------------------------------------------ | --------------------------------------------------------------------------------------------------------------- |
| `backend/src/novelai/translation/stages/translate.py` or equivalent `TranslateStage` | Ensure current glossary revision/hash is attached to translation output metadata                                |
| `backend/src/novelai/translation/cache.py` or equivalent cache helper                | Verify glossary revision/hash is already part of cache identity; add regression tests if complete               |
| `backend/src/novelai/storage/translations.py`                                        | Persist glossary metadata on new versions and compute freshness on load/list                                    |
| `backend/src/novelai/services/orchestration/translation.py`                          | Detect stale active versions and schedule stale-only retranslation                                              |
| Translation job scheduler/queue module                                               | Mark or invalidate queued jobs when glossary snapshot changes before execution                                  |
| Glossary service/model code                                                          | Verify meaningful approved-term changes expose current revision/hash; avoid reimplementing counters if complete |
| Admin/editor API routers and response models                                         | Expose freshness fields and stale retranslation choices additively                                              |
| Admin frontend translation/version UI                                                | Show stale badges, stale counts, stale reasons, and retranslation choices                                       |
| `backend/tests/test_glossary_revision_translation_invalidation.py`                   | Add focused regression tests                                                                                    |

### Files Not Touched

* Public reader routes.
* Source/crawler adapters.
* Raw chapter storage schema.
* Glossary onboarding state machine.
* Glossary prompt injection rules, except for metadata plumbing if missing.
* Existing active-version selection rules.
* Existing translation cache cleanup policy.

## Data Model

### Translation Version Glossary Metadata

Every newly saved translation version should include the glossary snapshot used to produce it:

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
  "glossary_term_count": 48
}
```

Rules:

* `glossary_revision` is required for new machine translation versions when available.
* `glossary_hash` should be stored when the glossary service can provide it.
* `glossary_term_count` is diagnostic and optional.
* `glossary_stale` does not need to be persisted.
* Freshness should be computed dynamically on read/list so old files do not need mass rewrites.

### Current Glossary Snapshot

Use the existing glossary service/model as the source of truth.

```python
@dataclass(frozen=True)
class GlossarySnapshot:
    revision: int
    hash: str | None
    approved_term_count: int | None
```

Rules:

* Do not add a second revision counter if `Novel.glossary_revision` or equivalent already exists.
* Do not duplicate glossary cache invalidation if it is already implemented.
* The snapshot must reflect the glossary state that prompt injection uses.
* The hash, when present, must be stable for semantically meaningful approved glossary content.

Recommended hash inputs, if hash computation still needs verification:

* canonical source term,
* approved translation,
* term type,
* enforcement level,
* aliases used by prompt injection,
* approved/enforced status.

Do not include volatile fields like `updated_at` unless the system intentionally invalidates translations on every timestamp-only edit.

## Freshness States

A translation version can be classified as:

| State            | Meaning                                                           |
| ---------------- | ----------------------------------------------------------------- |
| `fresh`          | Version was produced with the current glossary revision/hash      |
| `stale`          | Version was produced with an older or different glossary snapshot |
| `legacy_unknown` | Version has no glossary metadata, so freshness cannot be proven   |
| `unknown`        | Current glossary snapshot cannot be resolved                      |

Recommended response fields:

```json
{
  "glossary_revision": 10,
  "current_glossary_revision": 12,
  "glossary_hash": "sha256:old",
  "current_glossary_hash": "sha256:new",
  "glossary_freshness": "stale",
  "glossary_stale": true,
  "glossary_stale_reason": "revision_mismatch"
}
```

Recommended stale reasons:

* `fresh`
* `legacy_missing_revision`
* `revision_mismatch`
* `hash_mismatch`
* `current_snapshot_unavailable`

`glossary_stale` is retained as a simple boolean for UI convenience, while `glossary_freshness` and `glossary_stale_reason` provide detail.

## Stale Detection

Add or centralize a helper:

```python
def compute_glossary_freshness(
    version: dict[str, Any],
    current: GlossarySnapshot | None,
) -> dict[str, Any]:
    if current is None:
        return {
            "glossary_freshness": "unknown",
            "glossary_stale": False,
            "glossary_stale_reason": "current_snapshot_unavailable",
            "current_glossary_revision": None,
            "current_glossary_hash": None,
        }

    version_revision = version.get("glossary_revision")
    version_hash = version.get("glossary_hash")

    if not isinstance(version_revision, int):
        return {
            "glossary_freshness": "legacy_unknown",
            "glossary_stale": current.revision > 0,
            "glossary_stale_reason": "legacy_missing_revision",
            "current_glossary_revision": current.revision,
            "current_glossary_hash": current.hash,
        }

    if version_revision < current.revision:
        return {
            "glossary_freshness": "stale",
            "glossary_stale": True,
            "glossary_stale_reason": "revision_mismatch",
            "current_glossary_revision": current.revision,
            "current_glossary_hash": current.hash,
        }

    if current.hash and version_hash and version_hash != current.hash:
        return {
            "glossary_freshness": "stale",
            "glossary_stale": True,
            "glossary_stale_reason": "hash_mismatch",
            "current_glossary_revision": current.revision,
            "current_glossary_hash": current.hash,
        }

    return {
        "glossary_freshness": "fresh",
        "glossary_stale": False,
        "glossary_stale_reason": "fresh",
        "current_glossary_revision": current.revision,
        "current_glossary_hash": current.hash,
    }
```

Rules:

* Missing version metadata must not break loading.
* Legacy versions should remain readable.
* Stale detection must not deactivate active versions.
* Hash mismatch should only be used when both current and version hashes are available.
* Dynamic computation is preferred over rewriting stored translation files.

## Storage Integration

### Saving Translation Versions

When saving a new translation version:

1. Resolve the current glossary snapshot for the novel.
2. Attach snapshot metadata to the version payload.
3. Save through the existing translation storage helper.
4. Do not overwrite older versions.
5. Do not automatically activate the new version unless the existing translation flow requests activation.

Example payload merge:

```python
snapshot = glossary_snapshot_service.for_novel(novel_id)

version_payload.update(
    {
        "glossary_revision": snapshot.revision,
        "glossary_hash": snapshot.hash,
        "glossary_term_count": snapshot.approved_term_count,
    }
)
```

If `TranslateStage` already has prompt glossary metadata, pass that metadata through the translation context instead of recomputing it in storage.

### Loading and Listing Versions

When loading or listing translation versions:

1. Resolve the current glossary snapshot.
2. Compute freshness for each version.
3. Add freshness fields to the returned dict.
4. Leave stored version files unchanged.

This applies to:

* active translation detail,
* historical version list,
* admin chapter translation detail,
* admin version comparison views.

Public reader responses should not expose admin-only glossary freshness fields unless they already expose version metadata through an authenticated admin path.

## Cache Identity Verification

Translation cache keys should already vary by glossary identity after prompt/cache hardening. This spec verifies and protects that behavior.

Expected cache dimensions include:

```json
{
  "glossary_revision": 12,
  "glossary_hash": "sha256:abc123"
}
```

Rules:

* If cache keys already include glossary revision/hash, do not reimplement.
* Add regression tests to prevent accidental removal.
* If `glossary_hash` exists, include it.
* Always include `glossary_revision` when available.
* Legacy cache entries without glossary identity must not be reused for a non-zero current glossary revision.
* Do not delete old cache entries as part of this spec.

## Queued Translation Job Invalidation

A queued translation job may become stale before it starts if the glossary changes after scheduling.

Each queued translation job should record the glossary snapshot it was scheduled with:

```json
{
  "job_id": "job-123",
  "novel_id": "novel-id",
  "chapter_ids": ["1", "2"],
  "scheduled_glossary_revision": 12,
  "scheduled_glossary_hash": "sha256:abc123"
}
```

Before execution, the worker should compare the scheduled snapshot to the current glossary snapshot.

### Job Behavior Options

| Condition                               | Behavior                                                                                            |
| --------------------------------------- | --------------------------------------------------------------------------------------------------- |
| Snapshot unchanged                      | Run normally                                                                                        |
| Revision/hash changed before job starts | Mark job as stale-before-run and use configured behavior                                            |
| Job already running                     | Continue with the snapshot used at execution start; saved versions record actual execution snapshot |
| Job completed before glossary change    | Existing versions become stale through normal stale detection                                       |

Recommended default for queued jobs:

```text
cancel_and_reschedule
```

Allowed behaviors:

| Behavior                      | Meaning                                                                       |
| ----------------------------- | ----------------------------------------------------------------------------- |
| `cancel_and_reschedule`       | Cancel stale queued job and schedule a fresh job with current glossary        |
| `run_with_current_glossary`   | Update job context immediately before execution and run with current glossary |
| `run_with_scheduled_glossary` | Run anyway and mark produced versions with scheduled/used glossary snapshot   |
| `fail_requires_admin`         | Mark job blocked and require admin action                                     |

The default should prefer correctness and avoid producing new translations with known-stale glossary state.

If the project already has job checkpoint/resume semantics, integrate with that instead of creating a parallel scheduler state machine.

## Admin Retranslation Choices

Admins need explicit choices when stale translations are detected.

### Stale Detection Summary

Admin novel or translation overview may include:

```json
{
  "novel_id": "novel-id",
  "current_glossary_revision": 12,
  "stale_active_translation_count": 7,
  "legacy_unknown_translation_count": 3,
  "fresh_active_translation_count": 42
}
```

### Version Detail Fields

Admin version list/detail responses should include:

```json
{
  "version_id": "v2",
  "glossary_revision": 10,
  "current_glossary_revision": 12,
  "glossary_hash": "sha256:old",
  "current_glossary_hash": "sha256:new",
  "glossary_freshness": "stale",
  "glossary_stale": true,
  "glossary_stale_reason": "revision_mismatch"
}
```

### Retranslate Stale Operation

If no existing endpoint exists, add:

```http
POST /admin/novels/{novel_id}/translations/retranslate-stale
```

If an existing retranslation endpoint exists, extend it with `stale_only=true` instead of adding a new endpoint.

Optional request body:

```json
{
  "chapter_ids": ["1", "2"],
  "include_legacy_unknown": true,
  "activate": false,
  "provider": null,
  "model": null,
  "reason": "glossary_revision_changed"
}
```

Behavior:

* Find chapters whose active translation is stale.
* Optionally include legacy/unknown versions.
* Restrict to `chapter_ids` when provided.
* Create a normal translation activity/job through existing orchestration.
* Use the current glossary revision/hash.
* Save new translation versions.
* Do not overwrite old versions.
* Do not automatically activate new versions unless `activate=true`.
* Preserve existing active-version behavior by default.

Response:

```json
{
  "novel_id": "novel-id",
  "current_glossary_revision": 12,
  "stale_chapter_count": 7,
  "legacy_unknown_chapter_count": 3,
  "scheduled_chapter_count": 7,
  "activate_on_completion": false,
  "activity_id": "activity-id"
}
```

## Admin UI

Add admin UI affordances:

* stale glossary badge in chapter/version lists,
* freshness state in version detail,
* tooltip showing version glossary revision versus current revision,
* stale active translation count in novel translation overview,
* legacy/unknown count where applicable,
* retranslate stale action,
* option to include or exclude legacy/unknown versions,
* option to activate new versions automatically or leave them for review,
* post-retranslation fresh status after completion.

Do not add public reader warnings in this spec.

## Glossary Revision Verification

This spec should verify existing glossary revision behavior rather than redesign it.

Meaningful approved glossary changes should already increment the glossary revision, including:

* approved translation changed,
* approved term created,
* approved term deleted or deactivated,
* enforcement level changed,
* aliases used by prompt injection changed,
* term status changes into or out of approved/enforced state.

If a gap is found, patch the specific missing write path only. Do not introduce a second revision system.

## Migration and Backward Compatibility

* Existing translation versions remain readable.
* Existing active-version selection is unchanged.
* Existing public reader output is unchanged.
* Existing translation cache entries may remain on disk.
* Old cache entries without glossary identity are not reused for current glossary-aware translations.
* Legacy versions without glossary metadata are reported as `legacy_unknown`.
* Stale versions remain selectable and comparable in admin UI.
* No DB migration is required if the project already has reliable glossary revision state.
* Storage changes are additive fields on translation version payloads.

## Test Design

Create `backend/tests/test_glossary_revision_translation_invalidation.py`.

Core backend tests:

* `test_translation_version_stores_glossary_revision`
* `test_translation_version_stores_glossary_hash_when_available`
* `test_active_version_marked_stale_after_glossary_revision_increment`
* `test_historical_versions_compute_staleness_independently`
* `test_legacy_version_without_glossary_metadata_loads_as_legacy_unknown`
* `test_stale_detection_does_not_deactivate_active_version`
* `test_admin_version_response_includes_glossary_freshness`
* `test_admin_summary_counts_stale_active_versions`
* `test_retranslate_stale_creates_new_fresh_version`
* `test_retranslate_stale_does_not_overwrite_old_version`
* `test_retranslate_stale_does_not_activate_by_default`
* `test_retranslate_stale_can_activate_when_requested`

Cache regression tests:

* `test_cache_key_includes_glossary_revision`
* `test_cache_key_includes_glossary_hash_when_available`
* `test_legacy_cache_entry_not_reused_for_nonzero_glossary_revision`

Queued job tests:

* `test_queued_translation_records_scheduled_glossary_snapshot`
* `test_queued_translation_detects_glossary_change_before_start`
* `test_stale_queued_translation_cancelled_and_rescheduled_by_default`
* `test_running_translation_records_execution_glossary_snapshot`

Frontend tests, if admin UI is changed:

* stale badge renders,
* stale reason tooltip renders,
* stale count appears in novel summary,
* retranslate stale action calls API,
* include legacy/unknown option is respected,
* activate-on-completion option is respected.

No tests should call live translation providers.

## Acceptance Criteria

1. New translation versions store glossary revision metadata.
2. New translation versions store glossary hash when available.
3. Active and historical translation versions can be classified as `fresh`, `stale`, `legacy_unknown`, or `unknown`.
4. Glossary changes make older translations visibly stale without deactivating them.
5. Queued translation jobs detect when their scheduled glossary snapshot is stale before execution.
6. Stale queued jobs are cancelled/rescheduled or handled according to documented behavior.
7. Admin APIs expose glossary freshness fields additively.
8. Admin summaries expose stale and legacy/unknown counts.
9. Admins can retranslate stale chapters and produce new fresh versions.
10. Retranslation does not overwrite old versions.
11. Retranslation does not activate new versions by default unless requested.
12. Existing translation versions without glossary metadata remain loadable.
13. Existing glossary gate, prompt injection, cache identity, and active-version behavior remain intact.
14. Public reader behavior is unchanged.
15. Focused backend and admin UI tests pass.
