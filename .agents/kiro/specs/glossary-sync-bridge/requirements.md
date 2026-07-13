# Requirements: Glossary Sync Bridge

## Introduction

The repository contains two completely disconnected glossary systems that must work together but currently do not.

The **file-backed orchestration glossary** (`glossary.json`) is populated by three orchestration phases — `extract_glossary_terms`, `translate_glossary_terms`, `review_glossary_terms` — and stores entries with `source`, `target`, `status`, `notes`, `context_summary`, and `occurrence_count`. The review phase can mark entries as `approved` (with `review_reason = "auto_approved_rule"`) or leave them at `needs_manual_review`, and then writes everything back to `glossary.json`. It never touches the database.

The **DB-backed prompt injection system** (`NovelGlossaryEntry`, `GlossaryPromptInjectionService`) is what `TranslateStage` actually uses to build the glossary block injected into translation prompts. `_build_prompt_glossary_block` resolves an integer `platform_novel_id` from `context.metadata`, opens a DB session, queries `NovelGlossaryEntry` rows with `status="approved"`, and builds the ranked prompt block. If `platform_novel_id` is absent from context, the block is silently skipped. If the DB query fails, it also silently returns `None`. There is zero fallback to the file glossary.

The result: the entire file-backed extraction/review workflow produces approved terms that never reach the translation prompt. `TranslateStage` queries a DB table that is never populated from the file workflow. The two systems are fully disconnected. A novel can have a fully reviewed `glossary.json` with 50 approved terms and still receive zero glossary prompt injection at translation time.

This spec builds the sync bridge: a service that promotes reviewed/approved file-glossary entries into the DB `NovelGlossaryEntry` table, and ensures `TranslateStage` can always resolve `platform_novel_id` so the DB prompt injection path fires.

## Glossary

- **File glossary**: entries in `storage/novel_library/<novel>/glossary.json`, managed by `storage/glossary.py` and `services/orchestration/glossary.py`
- **DB glossary**: rows in `novel_glossary_entries` table, managed by `services/glossary_repository.py`
- **Sync**: the act of promoting approved file-glossary entries into DB glossary entries
- **`platform_novel_id`**: the integer DB primary key of the `novels` table row, distinct from the string `novel_id` used in file storage paths

## Requirements

### REQ-1: Glossary File-to-DB Sync Service

A new service must bridge reviewed file-glossary entries into the DB glossary table.

- REQ-1.1: A new module `backend/src/novelai/services/glossary_sync_service.py` must be created containing a `GlossarySyncService` class.
- REQ-1.2: `GlossarySyncService` must accept a `GlossaryRepository` and a `StorageService` instance.
- REQ-1.3: The service must expose a `sync_from_file(novel_id: str, *, actor_user_id: int | None = None, dry_run: bool = False) -> GlossarySyncResult` method.
- REQ-1.4: The method must load entries from `storage.load_glossary(novel_id)` (file source).
- REQ-1.5: The method must filter to entries where `status` is `"approved"` or `"needs_manual_review"`. Entries with `status = "ignored"` or `status = "pending"` without a translated target must be skipped.
- REQ-1.6: For each eligible entry, the method must resolve the integer `platform_novel_id` by querying `Novel.slug = novel_id` from the DB session (available via `GlossaryRepository.db`).
- REQ-1.7: For each eligible entry, the method must call `GlossaryRepository.create_glossary_entry` with the following field mapping:
  - `canonical_term` ← entry `source`
  - `term_type` ← `"extracted"` (provenance marker)
  - `approved_translation` ← entry `target` (when non-empty)
  - `status` ← `"approved"` when file entry `status = "approved"`; `"candidate"` when `"needs_manual_review"`
  - `confidence` ← entry `confidence` (float, when present)
  - `admin_notes` ← entry `notes` (when present)
  - `decision_source` ← `"file_glossary_sync"`
  - `rationale` ← `"Promoted from file glossary review"`
- REQ-1.8: If a `NovelGlossaryEntry` with the same `(novel_id, canonical_term)` already exists (unique constraint), the method must **upsert**: update `approved_translation`, `admin_notes`, `confidence`, and (only if the existing status is `"candidate"`) `status` from the file entry. It must not downgrade an `"approved"` DB entry to `"candidate"`.
- REQ-1.9: When `dry_run=True`, the method must return a `GlossarySyncResult` describing what would be created/updated without writing to the DB.
- REQ-1.10: `GlossarySyncResult` must contain: `novel_id`, `dry_run`, `created` (int), `updated` (int), `skipped` (int), `errors` (list of `{term, error}` dicts), `synced_terms` (list of canonical terms that were created or updated).

### REQ-2: Sync Triggered After File Glossary Review

The sync must be triggered automatically after `review_glossary_terms` completes.

- REQ-2.1: `review_glossary_terms` in `services/orchestration/glossary.py` must call `GlossarySyncService.sync_from_file` after saving the reviewed glossary back to `glossary.json`.
- REQ-2.2: The sync call must be best-effort: if it raises, the exception must be caught, logged at `WARNING` level, and `review_glossary_terms` must still return its normal result.
- REQ-2.3: The sync result must be included in the return dict of `review_glossary_terms` under the key `"db_sync"` (a dict with `created`, `updated`, `skipped`, `errors` counts).
- REQ-2.4: When a DB session is not available (e.g. no `platform_novel_id` resolvable), the sync must be silently skipped and `"db_sync"` must contain `{"skipped": true, "reason": "novel_not_in_db"}`.

### REQ-3: Sync Admin Endpoint

The owner must be able to trigger a manual sync and see its result.

- REQ-3.1: A new endpoint `POST /novels/{novel_id}/glossary/sync-to-db` must be added to `api/routers/admin_glossary.py`. It must be owner-only.
- REQ-3.2: The request body must accept `dry_run: bool = False`.
- REQ-3.3: The response must return the `GlossarySyncResult` fields: `novel_id`, `dry_run`, `created`, `updated`, `skipped`, `errors`, `synced_terms`.
- REQ-3.4: The endpoint must return HTTP 404 when the novel does not exist in storage.
- REQ-3.5: The endpoint must return HTTP 422 with a clear message when the novel does not have a DB row (cannot resolve `platform_novel_id`), because the caller needs to know this is a data state issue.

### REQ-4: `platform_novel_id` Resolution in `TranslateStage`

`TranslateStage` must always attempt to resolve `platform_novel_id` from context rather than silently skipping glossary injection.

- REQ-4.1: In `TranslateStage.run()`, before the translate loop begins, if `context.metadata` does not contain a valid `platform_novel_id` (a positive integer), the stage must attempt to resolve it by querying `db.query(Novel).filter_by(slug=context.novel_id).one_or_none()`.
- REQ-4.2: When the DB query resolves a `Novel` row, the stage must store `novel.id` into `context.metadata["platform_novel_id"]` so `_build_prompt_glossary_block` can use it.
- REQ-4.3: When the DB query fails or returns `None`, the stage must log a `DEBUG` message (not `WARNING`) and continue without glossary injection — same behavior as today, but now with an explicit resolution attempt.
- REQ-4.4: The DB query in REQ-4.1 must use the same `session_scope` pattern already used in `_build_prompt_glossary_block`.
- REQ-4.5: This resolution must happen at most once per `run()` call, not once per chunk.

### REQ-5: Glossary Sync Coverage in Admin Glossary Status

The admin glossary status surface must reflect whether the file glossary and DB glossary are in sync.

- REQ-5.1: `GET /novels/{novel_id}/glossary/sync-status` (new endpoint, owner-only) must return:
  - `file_approved_count`: count of `status="approved"` entries in `glossary.json`
  - `db_approved_count`: count of `status="approved"` DB entries for this novel
  - `in_sync`: `True` when `file_approved_count == db_approved_count` and `db_approved_count > 0`
  - `last_sync_at`: timestamp of the last successful sync (tracked per-novel in a module-level dict, not persisted)
  - `recommendation`: `"sync_required"` when `file_approved_count > db_approved_count`, `"healthy"` when `in_sync`, `"empty"` when both are zero
- REQ-5.2: The endpoint must be read-only.
- REQ-5.3: `last_sync_at` must default to `null` when no sync has been run in the current process.

### REQ-6: Cache Invalidation on Sync

When terms are synced from the file glossary to the DB, the glossary revision must be bumped.

- REQ-6.1: `GlossarySyncService.sync_from_file` must call `GlossaryRepository._increment_glossary_revision(platform_novel_id)` after any successful create or update (when `dry_run=False` and at least one entry was created or updated).
- REQ-6.2: The revision increment must be called once per sync run, not once per entry, to avoid excessive revision bumps.
- REQ-6.3: `TranslateStage`'s existing `glossary_hash` cache key computation must remain unchanged — it already invalidates on approved-term set change because it reads from the DB and hashes the rendered block.

### REQ-7: Tests

- REQ-7.1: A new test file `backend/tests/test_glossary_sync_bridge.py` must be created.
- REQ-7.2: `test_sync_creates_new_entries` — file glossary with 3 approved entries, DB empty → 3 entries created in DB.
- REQ-7.3: `test_sync_upserts_existing_entry` — one DB entry already exists for a term; sync updates `approved_translation` without duplicating.
- REQ-7.4: `test_sync_does_not_downgrade_approved_to_candidate` — DB entry is `"approved"`, file entry is `"needs_manual_review"` for same term → DB status remains `"approved"`.
- REQ-7.5: `test_sync_skips_ignored_entries` — file glossary has one `"ignored"` entry → not created in DB.
- REQ-7.6: `test_sync_dry_run_no_writes` — `dry_run=True` → no DB writes, result `created > 0`.
- REQ-7.7: `test_sync_increments_glossary_revision_once` — 3 entries synced → `_increment_glossary_revision` called exactly once.
- REQ-7.8: `test_review_triggers_sync` — mock `GlossarySyncService.sync_from_file`, call `review_glossary_terms`, assert sync was called.
- REQ-7.9: `test_review_succeeds_even_if_sync_raises` — `sync_from_file` raises → `review_glossary_terms` still returns a success result.
- REQ-7.10: `test_translate_stage_resolves_platform_novel_id` — context has `novel_id` but no `platform_novel_id`; mock DB query returns a novel row; assert `context.metadata["platform_novel_id"]` is set before translate loop.
- REQ-7.11: `test_translate_stage_no_glossary_injection_when_novel_not_in_db` — DB query returns `None`; assert `_build_prompt_glossary_block` returns `None` and no exception raised.
- REQ-7.12: `test_sync_status_endpoint_healthy` — DB and file counts match → `in_sync=True`, `recommendation="healthy"`.
- REQ-7.13: `test_sync_status_endpoint_sync_required` — file has 5 approved, DB has 3 → `recommendation="sync_required"`.

## Non-Goals

- This spec does not change how glossary entries are extracted, translated in isolation, or reviewed in the file workflow. Those phases are owned by `prompt-translation-hardening` and `glossary-first-onboarding`.
- This spec does not change `GlossaryPromptInjectionService` prompt rendering logic (owned by `prompt-translation-hardening`).
- This spec does not add glossary-apply-to-chapters (owned by `glossary-apply-safety`).
- This spec does not add bidirectional sync (DB → file). The file glossary is the source of truth for extraction; the DB glossary is the source of truth for prompt injection.
- This spec does not add a real-time sync watcher. Sync is triggered by explicit orchestration events or manual admin action.
