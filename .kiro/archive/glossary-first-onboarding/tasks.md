# Implementation Plan: Glossary-First Onboarding

## Overview

Implement the glossary readiness gate across four layers: DB schema, backend
services/orchestration, API, and frontend. Each phase builds on the previous
so that no orphaned code is introduced. All changes are additive — nothing is
removed.

---

## Tasks

- [x] 1. Add glossary columns to the Novel ORM model and Alembic migration
  - [x] 1.1 Extend `Novel` ORM model with `glossary_status` and `glossary_revision` columns
    - Add `GLOSSARY_STATUS_VALUES` frozenset constant and the two `mapped_column`
      declarations to `backend/src/novelai/db/models/novel.py`
    - Add `@validates("glossary_status")` decorator that raises `ValueError` for
      any value outside the frozenset
    - _Requirements: 1.1, 1.2, 1.3, 1.4_

  - [x]* 1.2 Write property test for glossary status validation (Property 1)
    - **Property 1: Glossary status validation rejects all invalid values**
    - Use `hypothesis.strategies.text()` filtered against the valid set; assert
      `ValueError` is raised; assert all three valid values are accepted
    - **Validates: Requirements 1.3, 1.4**

  - [x] 1.3 Create Alembic migration `add_glossary_status_fields`
    - `down_revision = "9f3b2c1d0e7a"` (after glossary tables migration)
    - `upgrade`: `op.add_column` for both columns with `server_default`; create
      `ix_novels_glossary_status` index
    - `downgrade`: drop index and both columns
    - _Requirements: 1.1, 1.2_

  - [x]* 1.4 Write migration smoke test
    - Apply migration on a SQLite in-memory test DB; assert both columns exist
      with correct types and defaults
    - _Requirements: 1.1, 1.2_

- [x] 2. Extend catalog projection with glossary fields
  - [x] 2.1 Add `glossary_status` and `glossary_revision` to `CATALOG_PROJECTION_FIELDS`
    - Edit `catalog_service.py` (or wherever `CATALOG_PROJECTION_FIELDS` lives)
      to include both new columns; verify `recompute_catalog_projection` reads
      them from the ORM row without additional storage queries
    - _Requirements: 1.5_

  - [x]* 2.2 Write property test for catalog projection glossary fields (Property 2)
    - **Property 2: Catalog projection always carries glossary fields**
    - Use Hypothesis to generate arbitrary `(glossary_status, glossary_revision)`
      pairs (from valid statuses × positive integers); assert both keys are
      present in the projection dict with matching values
    - **Validates: Requirements 1.5**

- [x] 3. Implement `GlossaryStatusService` and status-transition endpoint
  - [x] 3.1 Create `services/glossary_status_service.py`
    - Implement `GlossaryStatusService` class with `__init__(session)` and
      `transition_status(novel_id, *, target_status, actor_user_id)` method
    - `transition_status` must: load novel (raise `LookupError` if missing),
      capture old status, set new status, increment `glossary_revision` only
      when `target_status == "glossary_ready"`, write
      `NovelGlossaryDecisionEvent`, flush, return updated `Novel`
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.6_

  - [x]* 3.2 Write property test — glossary-ready increments revision (Property 8)
    - **Property 8: Glossary-ready transition always increments revision**
    - Use SQLite in-memory session; generate arbitrary starting `glossary_revision`
      N ≥ 0; assert revision is exactly N + 1 after transitioning to
      `glossary_ready`
    - **Validates: Requirements 4.2, 6.2**

  - [x]* 3.3 Write property test — glossary-skipped preserves revision (Property 9)
    - **Property 9: Glossary-skipped transition never changes revision**
    - Same fixture; assert `glossary_revision` equals N after transitioning to
      `glossary_skipped`
    - **Validates: Requirements 6.3**

  - [x]* 3.4 Write property test — every transition writes a decision event (Property 10)
    - **Property 10: Every successful status transition writes a decision event**
    - For each valid `target_status` value: assert a `NovelGlossaryDecisionEvent`
      row is persisted with correct actor ID, old/new status values, and a valid
      ISO 8601 timestamp
    - **Validates: Requirements 6.6**

  - [x] 3.5 Add `PATCH /novels/{novel_id}/glossary-status` endpoint to `admin_glossary.py`
    - Deserialize `GlossaryStatusTransitionRequest` (Pydantic `Literal` field);
      require `owner` role; delegate to `GlossaryStatusService.transition_status`;
      map `LookupError` → HTTP 404; return `GlossaryStatusTransitionResponse`
    - _Requirements: 6.1, 6.4, 6.5, 6.6_

  - [x]* 3.6 Write unit tests for status-transition endpoint
    - Test HTTP 403 for non-owner caller; HTTP 404 for missing novel; HTTP 422
      for invalid `target_status`; HTTP 200 with correct response body on success
    - _Requirements: 6.1, 6.4, 6.5_

- [x] 4. Checkpoint — Ensure all tests pass, ask the user if questions arise.

- [x] 5. Add `skip_glossary_gate` to `TranslateRequest` and wire through call chain
  - [x] 5.1 Add `skip_glossary_gate: bool = False` field to `TranslateRequest` in
    `api/routers/operations.py`
    - _Requirements: 3.4_

  - [x]* 5.2 Write unit test for `TranslateRequest` deserialization
    - Assert that a request body without `skip_glossary_gate` deserializes with
      `False` as the default; assert `True` round-trips correctly
    - _Requirements: 3.4_

  - [x] 5.3 Thread `skip_glossary_gate` through the translate call chain
    - Pass the flag from the router into `OperationsService.translate_novel`,
      then into `orchestrator.translate_chapters`, then into
      `_preflight_translation` — add `skip_glossary_gate: bool = False` at
      each level as a keyword argument
    - _Requirements: 3.2_

- [x] 6. Implement the translation guard in `_preflight_translation`
  - [x] 6.1 Add glossary gate check to `_preflight_translation` in
    `orchestration/translation.py`
    - After existing checks: if `skip_glossary_gate` is `False` and
      `novel.glossary_status == "glossary_pending"`, call
      `_count_pending_glossary_entries` and append a `PreflightIssue` with
      code `"glossary_gate_pending"` and `details` dict; if `skip_glossary_gate`
      is `True`, log the override in the activity log
    - Add private helper `_count_pending_glossary_entries(novel_id)` that
      queries the glossary entries table
    - _Requirements: 3.1, 3.2, 3.3, 3.5_

  - [x]* 6.2 Write property test — guard blocks pending novels (Property 6)
    - **Property 6: Translation guard blocks pending novels**
    - Mock `session_scope` and `Novel` query; for any `skip_glossary_gate=False`
      and `glossary_status="glossary_pending"`, assert the returned issues list
      contains exactly one item with `code="glossary_gate_pending"` and the
      required `details` keys
    - **Validates: Requirements 3.1, 3.5**

  - [x]* 6.3 Write property test — guard respects skip flag and non-pending statuses (Property 7)
    - **Property 7: Translation guard respects skip flag and non-pending statuses**
    - Generate all combinations of `skip_glossary_gate=True` and valid statuses,
      plus `skip_glossary_gate=False` with `glossary_ready`/`glossary_skipped`;
      assert no `glossary_gate_pending` issue is appended in any case
    - **Validates: Requirements 3.2, 3.3**

- [x] 7. Add `_increment_glossary_revision` to `GlossaryRepository` and hook
    approved-entry operations
  - [x] 7.1 Add `_increment_glossary_revision(novel_id)` private helper to
    `services/glossary_repository.py`
    - Load novel by PK; raise `LookupError` if not found; increment
      `glossary_revision` by 1; call `self.db.flush()` — all within the
      caller's existing transaction
    - _Requirements: 8.1, 8.2, 8.3, 8.5_

  - [x] 7.2 Call `_increment_glossary_revision` in `change_glossary_entry_status`
    - Call the helper when the new status is `"approved"`
    - Call the helper when the previous status was `"approved"` and the new
      status is `"deprecated"` or `"rejected"`
    - _Requirements: 8.1, 8.3_

  - [x] 7.3 Call `_increment_glossary_revision` in `update_glossary_entry`
    - Call the helper only when the entry's current status is `"approved"`;
      skip the call for `"candidate"` or `"recommended"` entries
    - _Requirements: 8.2, 8.4_

  - [x]* 7.4 Write property test — approved entry changes increment revision (Property 13)
    - **Property 13: Approved entry changes increment glossary_revision**
    - Use SQLite in-memory session; generate arbitrary starting revision N;
      for each of the three approved-change operations, assert `glossary_revision`
      equals N + 1 within the same transaction
    - **Validates: Requirements 8.1, 8.2, 8.3**

  - [x]* 7.5 Write property test — non-approved entry changes do not increment (Property 14)
    - **Property 14: Non-approved entry changes do not increment glossary_revision**
    - Generate entries with `"candidate"` or `"recommended"` status; update
      fields without transitioning to `"approved"`; assert `glossary_revision`
      is unchanged
    - **Validates: Requirements 8.4**

- [~] 8. Checkpoint — Ensure all tests pass, ask the user if questions arise.

- [x] 9. Implement the glossary bootstrap hook in the onboarding orchestrator
  - [x] 9.1 Add `bootstrap_glossary_if_needed` async helper to
    `orchestration/crawler.py`
    - Implement the five-step logic: load novel, skip if `glossary_ready`, call
      `extract_glossary_terms`, persist candidates via `GlossaryRepository` and
      set status to `glossary_pending` if ≥ 1 candidate returned, log warning
      if 0 candidates, catch all exceptions and log at appropriate level without
      re-raising
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5_

  - [x] 9.2 Call `bootstrap_glossary_if_needed` from `scrape_metadata`
    - Invoke the helper after `safely_refresh_catalog_projection_after_storage_write`
      in `crawler.py`, passing the existing scoped session
    - Return `bootstrap_candidate_count` in the `scrape_metadata` result dict
    - _Requirements: 2.1, 2.5_

  - [x]* 9.3 Write property test — bootstrap exception isolation (Property 3)
    - **Property 3: Bootstrap exception isolation**
    - For any exception type raised by `extract_glossary_terms`, assert
      `scrape_metadata` returns successfully, `glossary_status` is unchanged,
      and no exception propagates
    - **Validates: Requirements 2.4**

  - [x]* 9.4 Write property test — bootstrap invocation gate (Property 4)
    - **Property 4: Bootstrap invocation gate**
    - For `glossary_pending` and `glossary_skipped` novels: assert bootstrap is
      called; for `glossary_ready` novels: assert bootstrap is not called
    - **Validates: Requirements 2.1, 2.5**

  - [x]* 9.5 Write property test — bootstrap produces pending status (Property 5)
    - **Property 5: Bootstrap produces pending status**
    - For any non-empty candidate list returned by the mock extractor, assert
      `glossary_status` is `"glossary_pending"` and candidates are queryable
      via `GlossaryRepository.list_glossary_entries_for_novel`
    - **Validates: Requirements 2.2**

- [x] 10. Wire glossary audit metadata through `TranslateStage`
  - [x] 10.1 Populate `glossary_revision` in translation context metadata at job start
    - In `orchestration/translation.py`, at the start of `translate_chapters`,
      read `novels.glossary_revision` from the DB and set
      `context.metadata["glossary_revision"]` before the chunk loop
    - Count `PromptGlossaryBlock.included_terms` after
      `GlossaryPromptInjectionService.build_for_chapter` and set
      `context.metadata["glossary_injected_term_count"]`
    - _Requirements: 7.5_

  - [x] 10.2 Write audit keys in `_save_chunk_output` inside `TranslateStage`
    - Add `"glossary_revision"` and `"glossary_injected_term_count"` to the
      output record dict, defaulting to `0` if the keys are absent from
      `context.metadata`
    - _Requirements: 7.1, 7.2, 7.3_

  - [x]* 10.3 Write property test — TranslateStage audit metadata matches DB state (Property 12)
    - **Property 12: TranslateStage audit metadata matches DB state at job start**
    - Mock `StorageService` and `GlossaryPromptInjectionService`; generate
      arbitrary (revision R, term count N); assert every saved chunk record
      contains `glossary_revision == R` and `glossary_injected_term_count` equal
      to the mocked `len(included_terms)`
    - **Validates: Requirements 7.1, 7.2, 7.3, 7.5**

- [x] 11. Enrich novel detail API response with glossary fields
  - [x] 11.1 Add `glossary_status`, `glossary_revision`, and `glossary_pending_count`
    to the admin novel detail API endpoint in `api/routers/admin_novels.py`
    - Compute `glossary_pending_count` by counting `novel_glossary_entries` rows
      with status `"candidate"` or `"recommended"` for the novel
    - Update the Pydantic response model with the three new fields
    - _Requirements: 5.5_

  - [x]* 11.2 Write property test — novel detail API always returns glossary fields (Property 11)
    - **Property 11: Novel detail API always returns glossary fields**
    - Use SQLite in-memory session + FastAPI `TestClient`; generate arbitrary
      `(glossary_status, glossary_revision, pending_count)` combos; assert
      response JSON contains all three fields with values consistent with DB state
    - **Validates: Requirements 5.5**

- [~] 12. Checkpoint — Ensure all tests pass, ask the user if questions arise.

- [x] 13. Build `ReadinessBadge` frontend component
  - [x] 13.1 Create `frontend/src/components/admin/ReadinessBadge.tsx`
    - Accept props `{ glossaryStatus, glossaryRevision, glossaryPendingCount, novelId }`
    - Render amber-500 badge with pending count + review link for
      `glossary_pending`; green-500 badge with revision number for
      `glossary_ready`; gray-400 badge for `glossary_skipped`
    - Use Next.js `<Link>` for the review navigation (SPA, no full reload)
    - _Requirements: 5.1, 5.2, 5.3, 5.4_

  - [x]* 13.2 Write snapshot/example tests for `ReadinessBadge`
    - Render each of the three statuses with React Testing Library; assert
      correct colour class and text content for each variant
    - _Requirements: 5.1, 5.2, 5.3_

  - [x] 13.3 Mount `ReadinessBadge` on the admin novel detail page
    - Pass `glossaryStatus`, `glossaryRevision`, `glossaryPendingCount`, and
      `novelId` from the existing novel detail API response to the component
    - _Requirements: 5.1, 5.5_

- [x] 14. Build `GlossaryOnboardingActions` frontend widget
  - [x] 14.1 Create `frontend/src/components/admin/GlossaryOnboardingActions.tsx`
    - Accept props `{ novelId, bootstrapCandidateCount }`
    - When `bootstrapCandidateCount > 0`: render three buttons — "Review
      glossary before translating" (SPA link), "Approve all & set ready"
      (calls `PATCH glossary-status` with `glossary_ready` then
      `POST batch-approve`), "Skip for now" (calls `PATCH glossary-status`
      with `glossary_skipped`)
    - When `bootstrapCandidateCount == 0`: render only "Skip for now" button
      plus the no-terms-detected notice
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5_

  - [x]* 14.2 Write example tests for `GlossaryOnboardingActions`
    - Assert three buttons are rendered when `bootstrapCandidateCount > 0`; assert
      only one button and the notice when `bootstrapCandidateCount == 0`
    - _Requirements: 4.1, 4.5_

  - [x] 14.3 Mount `GlossaryOnboardingActions` in the novel-add flow
    - Display the widget after preliminary crawl completes, reading
      `bootstrap_candidate_count` from the API response
    - _Requirements: 4.1_

  - [x]* 14.4 Write API client test for `skip_glossary_gate` field
    - Assert that the frontend API client includes `skip_glossary_gate` in the
      translate request body and that it defaults to `false` when omitted
    - _Requirements: 3.4_

- [x] 15. Final checkpoint — Ensure all tests pass, ask the user if questions arise.

---

## Notes

- Tasks marked with `*` are optional and can be skipped for a faster MVP.
- Each task references specific requirements for traceability.
- Checkpoints at tasks 4, 8, and 12 ensure incremental validation.
- Property tests use **Hypothesis** (`pip install hypothesis`); each test is
  annotated with `Feature: glossary-first-onboarding, Property N: <title>`.
- Unit tests use `unittest.mock` or SQLite in-memory sessions; no real DB or
  LLM calls are made.
- The bootstrap step (task 9) is non-fatal by design — exceptions are swallowed
  so the onboarding pipeline is never blocked by LLM unavailability.
- The `skip_glossary_gate` flag (task 5) must be threaded through three call
  levels before the guard in task 6 can consume it.

---

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1", "1.3"] },
    { "id": 1, "tasks": ["1.2", "1.4", "2.1", "3.1"] },
    { "id": 2, "tasks": ["2.2", "3.2", "3.3", "3.4", "7.1"] },
    { "id": 3, "tasks": ["3.5", "5.1", "7.2", "7.3"] },
    { "id": 4, "tasks": ["3.6", "5.2", "5.3", "7.4", "7.5"] },
    { "id": 5, "tasks": ["6.1", "9.1"] },
    { "id": 6, "tasks": ["6.2", "6.3", "9.2", "10.1"] },
    { "id": 7, "tasks": ["9.3", "9.4", "9.5", "10.2"] },
    { "id": 8, "tasks": ["10.3", "11.1"] },
    { "id": 9, "tasks": ["11.2", "13.1"] },
    { "id": 10, "tasks": ["13.2", "13.3", "14.1"] },
    { "id": 11, "tasks": ["14.2", "14.3"] },
    { "id": 12, "tasks": ["14.4"] }
  ]
}
```
