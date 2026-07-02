# Requirements: Glossary Apply Safety and Reversibility

## Introduction

The glossary system has a preview endpoint (`POST /novels/{novel_id}/glossary/apply/preview`) that classifies replacement candidates as `safe`, `needs_review`, or `blocked`, but the actual apply step — writing new translated chapter versions with the replacements committed — does not exist. The storage layer already supports multi-version chapter bundles, per-version `glossary_revision` tracking, and a rollback primitive (`activate_translated_chapter_version`), but none of these are reachable from the admin API through a glossary apply path.

The result is a glossary system that can analyze but never commit, with no rollback UI, no per-chapter diff record, no max-delta safety guard, and no enforcement of `owner_locked` or `replacement_policy` constraints at write time. This spec builds the missing apply engine, exposes the existing rollback primitive, and enforces the safety constraints that preview already classifies but apply currently ignores.

## Requirements

### REQ-1: Glossary Apply Endpoint

The system must expose a committed apply endpoint that writes new translated chapter versions with glossary replacements applied.

- REQ-1.1: A new endpoint `POST /novels/{novel_id}/glossary/apply/commit` must be added to `api/routers/admin_glossary.py`. It must be owner-only.
- REQ-1.2: The request body must accept: `entry_ids` (list of glossary entry IDs to apply, optional), `include_all_approved` (boolean), `chapter_numbers` (optional list), `chapter_start` / `chapter_end` (optional int range), `max_chapters` (optional int), `dry_run` (boolean, default false), and `max_delta_fraction` (float 0.0–1.0, default 0.15).
- REQ-1.3: When `dry_run=true`, the endpoint must compute and return the per-chapter diff summary without writing any storage artifact. This must produce an identical result to the existing preview endpoint for the `safe` entries and additionally include the `delta_fraction` per chapter.
- REQ-1.4: When `dry_run=false`, the endpoint must apply replacements to all chapters classified as `safe` in the preview phase. Chapters classified as `needs_review` must be skipped unless the request explicitly includes `force_needs_review=true`. Chapters classified as `blocked` must never be written regardless of flags.
- REQ-1.5: The endpoint response must include: per-chapter results with `chapter_id`, `status` (`applied` / `skipped` / `blocked` / `failed`), `replacements_made` (int), `delta_fraction` (float), `new_version_id`, `previous_version_id`; a summary with total counts; and `glossary_revision` that was active at apply time.

### REQ-2: Apply Engine Safety Constraints

The apply engine must enforce safety constraints that currently exist only as preview classifications.

- REQ-2.1: Before writing any chapter, the engine must compute `delta_fraction = changed_character_count / original_character_count`. If `delta_fraction` exceeds `max_delta_fraction`, the chapter must be marked `blocked` and not written.
- REQ-2.2: Terms with `replacement_policy = "protected"` or `owner_locked = True` in the glossary entry must be applied without modification (they cannot be downgraded to advisory). The engine must enforce, not merely preview, that locked terms are substituted exactly.
- REQ-2.3: Terms classified as `blocked` by `GlossaryApplyPreviewService` (e.g. overlapping with structural markers, inside code spans, ambiguous anchors) must not be written to any chapter.
- REQ-2.4: If any individual chapter write fails (I/O error, corrupt bundle, etc.), that chapter must be marked `failed` in the response and the engine must continue processing remaining chapters. A partial batch must not leave the novel in an undetectable mixed-revision state.
- REQ-2.5: The engine must accept an optional `batch_id` string. If provided, it must be stored in each new version's metadata so the entire apply run can be correlated later.

### REQ-3: Per-Chapter Versioning on Apply

Each chapter that receives a glossary apply must produce a new version in the chapter bundle with full traceability metadata.

- REQ-3.1: Each applied chapter must call `save_translated_chapter` (or `save_edited_translation`) with `version_kind = ChapterVersionKind.GLOSSARY_APPLY` (this enum value must be added if absent).
- REQ-3.2: The new version must carry: `glossary_revision` (the current revision at apply time), `glossary_injected_term_count` (count of distinct terms applied), `base_version_id` (the version that was active before apply), and `batch_id` when supplied.
- REQ-3.3: An `edit_history` entry must be written for each applied chapter with `action = "glossary_apply"`, the `previous_version_id`, and the `batch_id` when supplied.
- REQ-3.4: The `active_translation_version_id` must be updated to the new version on successful write.

### REQ-4: Rollback API Endpoint

The storage-layer rollback primitive must be exposed through the admin API.

- REQ-4.1: A new endpoint `POST /novels/{novel_id}/chapters/{chapter_id}/versions/{version_id}/activate` must be added to the admin chapter management router. It must be owner-only.
- REQ-4.2: The endpoint must call `storage.activate_translated_chapter_version(novel_id, chapter_id, version_id)`.
- REQ-4.3: The response must include: `chapter_id`, `activated_version_id`, `previous_version_id`, `activated_at`.
- REQ-4.4: If the `version_id` does not exist in the chapter bundle, the endpoint must return HTTP 404.
- REQ-4.5: A convenience endpoint `POST /novels/{novel_id}/glossary/apply/rollback` must be added that accepts a `batch_id` and rolls back all chapters whose current active version has that `batch_id` in metadata. This is a bulk rollback for an entire apply run.
- REQ-4.6: The bulk rollback endpoint response must list each chapter with `chapter_id`, `rolled_back_from_version_id`, `rolled_back_to_version_id`, `status` (`success` / `failed` / `skipped_not_found`).

### REQ-5: Apply Preview Includes Delta Fraction

The existing preview endpoint must be extended to include `delta_fraction` per chapter.

- REQ-5.1: `GlossaryApplyPreviewService.preview()` result must include `delta_fraction: float` per chapter entry.
- REQ-5.2: The `GlossaryApplyPreviewResponse` schema must expose `delta_fraction` in the per-chapter results.
- REQ-5.3: Chapters where `delta_fraction` would exceed the default `max_delta_fraction` (0.15) must be pre-classified as `blocked` in the preview result, with reason `"delta_fraction_exceeded"`.

### REQ-6: Glossary Apply Orchestration Function

The orchestration layer must expose a `apply_glossary_to_chapters` function following the established orchestration pattern.

- REQ-6.1: A new function `apply_glossary_to_chapters` must be added to `services/orchestration/glossary.py`.
- REQ-6.2: The function must accept: `novel_id`, `entry_ids`, `include_all_approved`, chapter range parameters, `dry_run`, `max_delta_fraction`, `force_needs_review`, `batch_id`.
- REQ-6.3: The function must delegate classification to `GlossaryApplyPreviewService` and then write chapter versions using storage functions.
- REQ-6.4: `NovelOrchestrationService` must bind `apply_glossary_to_chapters` onto the service class following the same pattern as existing orchestration bindings.

### REQ-7: `ChapterVersionKind.GLOSSARY_APPLY` Enum Value

- REQ-7.1: `ChapterVersionKind` (in `core/chapter_state.py` or equivalent) must include a `GLOSSARY_APPLY` value.
- REQ-7.2: `storage/translations.py` must normalize and accept `"glossary_apply"` as a valid `kind` string in `_normalize_version_kind`.
- REQ-7.3: The admin chapter version list response must return `"glossary_apply"` as the `version_kind` for these versions.

### REQ-8: Tests

- REQ-8.1: A new test file `tests/test_glossary_apply_engine.py` must cover the apply engine logic.
- REQ-8.2: Tests must cover: apply with all-safe chapters, apply with mixed safe/needs_review/blocked (needs_review skipped by default, skipped chapters not written), blocked chapters never written regardless of flags, delta_fraction guard (chapter blocked when over threshold), partial failure (one chapter fails, others succeed), dry_run returns summary without writing.
- REQ-8.3: Tests must cover rollback: single chapter rollback via version activate endpoint, bulk rollback by `batch_id`, rollback returns 404 for unknown version_id.
- REQ-8.4: Tests must cover the extended preview: `delta_fraction` present in response, chapters over threshold pre-classified as `blocked`.
- REQ-8.5: Tests must assert that each committed chapter version carries `glossary_revision`, `base_version_id`, `batch_id`, and `version_kind = "glossary_apply"`.
- REQ-8.6: Overlapping-term tests: two glossary terms where source of term A is a substring of source of term B — assert the longer match wins and no double-replacement occurs.
- REQ-8.7: Protected-span tests: a chapter with a `[P p001]` marker — assert the marker text is never altered by a replacement, regardless of glossary terms that match the marker string.

## Non-Goals

- This spec does not change how glossary entries are extracted, translated, or reviewed.
- This spec does not change the glossary prompt injection path (prompt-translation-hardening spec owns that).
- This spec does not add a re-translation trigger for affected chapters (that is a future automated retranslation feature).
- This spec does not add glossary file versioning/history (the file is the projection of the DB entries; DB provides the audit trail).
- This spec does not change the public reader API.
