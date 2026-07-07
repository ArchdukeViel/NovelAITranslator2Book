# Requirements: Glossary Revision Translation Invalidation

## Introduction

The glossary system is already integrated into the translation pipeline: glossary candidates are bootstrapped during onboarding, glossary review gates translation, and approved terms are injected into prompts during `TranslateStage`. The deep research reports identify the next reliability gap: when glossary terms change after a chapter has already been translated, existing translation versions may no longer reflect the current approved terminology.

This spec makes glossary state part of translation version metadata and cache identity. It allows the backend and admin UI to identify stale translations, explain why they are stale, and retranslate affected chapters deterministically.

## Requirements

### REQ-1: Store Glossary Revision on Translation Versions

Every newly saved translation version must record the glossary state used to produce it.

- REQ-1.1: Translation version metadata must include `glossary_revision: int`.
- REQ-1.2: Translation version metadata must include `glossary_hash: str | null` when a hash is available from prompt injection or glossary snapshot logic.
- REQ-1.3: Translation version metadata must include `glossary_term_count: int | null` when available.
- REQ-1.4: Translation version metadata must include `glossary_stale: bool`, defaulting to `false` for newly created versions that use the current glossary.
- REQ-1.5: Existing translation versions without glossary metadata must remain loadable and should be treated as `glossary_revision=0` or `unknown` by compatibility helpers.
- REQ-1.6: The storage schema change must be additive and must not delete or rewrite existing version text.

### REQ-2: Include Glossary Revision in Translation Cache Keys

Translation cache identity must change when glossary state changes.

- REQ-2.1: Cache keys for translation outputs must include the active novel `glossary_revision`.
- REQ-2.2: If `glossary_hash` is available and stable, cache keys should include it as well or use it as a stronger replacement for revision.
- REQ-2.3: Cache keys must continue to include existing dimensions such as provider, model, source language, target language, prompt settings, and source text identity.
- REQ-2.4: A glossary update must not reuse a cached translation generated with an older glossary revision.
- REQ-2.5: Existing cache entries without glossary revision must be treated as legacy and must not be used when current glossary revision is non-zero.

### REQ-3: Detect Stale Translation Versions

The system must be able to determine whether a translated chapter version is stale relative to current glossary state.

- REQ-3.1: Add helper logic to compare a translation version's stored glossary revision/hash with the novel's current glossary revision/hash.
- REQ-3.2: A version is stale when its `glossary_revision` is lower than the current novel `glossary_revision`.
- REQ-3.3: If a current `glossary_hash` is available, a version is stale when its stored hash differs from the current hash.
- REQ-3.4: Versions with missing glossary metadata must be reported as `unknown` or stale according to a conservative compatibility policy.
- REQ-3.5: Stale detection must not change the active version automatically unless explicitly requested by an admin operation.

### REQ-4: Expose Glossary Freshness in Admin APIs

Admin-facing chapter/version APIs must expose glossary freshness information.

- REQ-4.1: Version list responses must include `glossary_revision`, `glossary_hash` if available, and `glossary_stale`.
- REQ-4.2: Chapter translation detail responses must expose whether the active version is stale.
- REQ-4.3: Novel/admin summary responses should expose an aggregate count of stale translated chapters when practical.
- REQ-4.4: Response changes must be additive.
- REQ-4.5: Strict response models must be updated if they would otherwise drop the new fields.

### REQ-5: Mark or Recompute Staleness After Glossary Changes

When glossary entries change, affected translations must become discoverably stale.

- REQ-5.1: When approved glossary terms are created, updated, deleted, or have enforcement/translation values changed, the novel's `glossary_revision` must increment according to existing glossary revision behavior.
- REQ-5.2: After glossary revision changes, stale translation detection must reflect the new revision without requiring manual JSON edits.
- REQ-5.3: The implementation may compute `glossary_stale` dynamically on read, persist stale flags in translation metadata, or both.
- REQ-5.4: If stale flags are persisted, the update must be best-effort and must not corrupt translation version files.
- REQ-5.5: Stale detection must apply to active and historical versions.

### REQ-6: Retranslate Stale Chapters

Admins must be able to retranslate stale chapters using current glossary state.

- REQ-6.1: Add or extend an admin operation to retranslate chapters whose active translation is glossary-stale.
- REQ-6.2: The operation must support a single chapter.
- REQ-6.3: The operation should support all stale chapters in a novel.
- REQ-6.4: Retranslation must use the current glossary revision/hash.
- REQ-6.5: Retranslation must save a new translation version rather than overwriting the old version.
- REQ-6.6: After successful retranslation, the new version must have `glossary_stale=false`.
- REQ-6.7: Existing translation locks and activity tracking must be reused.

### REQ-7: Preserve Active Version Semantics

Glossary staleness must not unexpectedly publish or unpublish content.

- REQ-7.1: Detecting that an active version is stale must not deactivate it automatically.
- REQ-7.2: Saving a fresh retranslation should follow existing active-version behavior.
- REQ-7.3: If existing behavior auto-activates new translation versions, preserve it unless a current setting says otherwise.
- REQ-7.4: If existing behavior does not auto-activate, the admin must be able to review and activate the fresh version through existing version controls.
- REQ-7.5: Public reader output must continue to use active-version selection unless a separate reader policy says otherwise.

### REQ-8: Admin UI Visibility

Admin UI must make stale glossary translations visible and actionable.

- REQ-8.1: Translation/chapter version UI must show a stale glossary badge when a version uses an older glossary revision/hash.
- REQ-8.2: Novel/admin summary UI should show stale translation count when available.
- REQ-8.3: Stale version UI must show current glossary revision and version glossary revision when available.
- REQ-8.4: UI must provide a retranslate action for stale active versions.
- REQ-8.5: UI must avoid showing stale warnings in the public reader unless a separate public reader glossary feature is implemented.

### REQ-9: Backward Compatibility

Existing translations and deployments must continue to work.

- REQ-9.1: Translation versions without glossary metadata must still load.
- REQ-9.2: Existing active version selection must still work.
- REQ-9.3: Existing glossary gate behavior must remain intact.
- REQ-9.4: Existing cache entries may remain on disk but must not be reused incorrectly for newer glossary revisions.
- REQ-9.5: No database migration is required unless existing glossary revision data is not accessible from current models.

### REQ-10: Tests

Focused tests must prove cache invalidation, stale detection, and retranslation behavior.

- REQ-10.1: Test new translation versions store `glossary_revision`.
- REQ-10.2: Test new translation versions store `glossary_hash` when available.
- REQ-10.3: Test cache keys differ after glossary revision changes.
- REQ-10.4: Test active version staleness is detected after glossary revision increments.
- REQ-10.5: Test historical versions report staleness independently.
- REQ-10.6: Test legacy versions without glossary metadata remain loadable.
- REQ-10.7: Test retranslate-stale creates a new version with current glossary metadata.
- REQ-10.8: Test stale detection does not deactivate active versions automatically.
- REQ-10.9: Test admin API responses include glossary freshness fields.
- REQ-10.10: Test UI badge/action behavior if frontend code is changed.

## Non-Goals

- This spec does not redesign glossary review workflows.
- This spec does not change glossary prompt injection rules except to record revision/hash metadata.
- This spec does not force automatic retranslation immediately after every glossary edit.
- This spec does not change public reader behavior.
- This spec does not delete old translation versions.
- This spec does not implement glossary-aware manual editor linting; that belongs to `glossary-aware-editor-qa`.

