# Tasks: Novel Onboarding State Machine

## Task List

- [ ] 1. Preflight Workflow Review
  - [ ] 1.1 Inspect admin crawler page flow that triggers preliminary crawl and full crawl activity.
  - [ ] 1.2 Inspect `OperationsService.preliminary_crawl_novel`.
  - [ ] 1.3 Inspect `OperationsService.scrape_novel` and activity crawl execution.
  - [ ] 1.4 Inspect `NovelOrchestrationService.scrape_metadata` and `scrape_chapters`.
  - [ ] 1.5 Inspect `bootstrap_glossary_if_needed` and glossary status fields.
  - [ ] 1.6 Inspect admin novel list/detail API response models.
  - [ ] 1.7 Inspect translation preflight path in `translate_novel` and orchestration translation code.
  - [ ] 1.8 Inspect existing activity/crawler/admin UI tests and fixtures.

- [ ] 2. Define Onboarding Status Constants
  - [ ] 2.1 Add a shared constant or enum for valid onboarding statuses. (REQ-1.2)
  - [ ] 2.2 Include `not_started`.
  - [ ] 2.3 Include `metadata_discovered`.
  - [ ] 2.4 Include `glossary_pending`.
  - [ ] 2.5 Include `chapters_pending`.
  - [ ] 2.6 Include `scraping_chapters`.
  - [ ] 2.7 Include `ready_for_translation`.
  - [ ] 2.8 Include `failed`.
  - [ ] 2.9 Include `cancelled`.

- [ ] 3. Add Metadata Storage Helpers
  - [ ] 3.1 Add `update_onboarding_status(...)` near novel metadata storage helpers. (REQ-1.4)
  - [ ] 3.2 Validate requested status against allowed statuses.
  - [ ] 3.3 Patch `onboarding_status` in `metadata.json`. (REQ-1.1)
  - [ ] 3.4 Patch `onboarding_updated_at`.
  - [ ] 3.5 Support optional `onboarding_error_code`.
  - [ ] 3.6 Support optional `onboarding_error_message`.
  - [ ] 3.7 Support `clear_error=True` for retry/resume start. (REQ-3.6)
  - [ ] 3.8 Save metadata through existing safe metadata write path.
  - [ ] 3.9 Refresh catalog projection if existing metadata updates normally do so.

- [ ] 4. Add Status Inference for Existing Novels
  - [ ] 4.1 Add `resolve_onboarding_status` or equivalent helper. (REQ-1.3, REQ-9.1)
  - [ ] 4.2 Return explicit status when valid.
  - [ ] 4.3 Infer `ready_for_translation` when existing raw chapters are available.
  - [ ] 4.4 Infer `chapters_pending` when metadata has chapters but raw chapters are missing.
  - [ ] 4.5 Infer `metadata_discovered` when metadata exists but no chapter list is present.
  - [ ] 4.6 Ensure invalid explicit statuses fall back safely and log a warning.

- [ ] 5. Integrate Preliminary Crawl Status
  - [ ] 5.1 After preliminary crawl saves metadata, set status to `metadata_discovered`. (REQ-2.1)
  - [ ] 5.2 After discovered chapters are available, set status to `chapters_pending`. (REQ-2.3)
  - [ ] 5.3 If glossary review is the most actionable blocker, expose `glossary_pending` or separate glossary status without losing chapter pending information. (REQ-2.2)
  - [ ] 5.4 Add `onboarding_status` to preliminary crawl response. (REQ-2.4, REQ-8.1)
  - [ ] 5.5 Add `body_scrape_required` to preliminary crawl response if not already present. (REQ-2.4)
  - [ ] 5.6 Ensure preliminary crawl failure does not set `ready_for_translation`. (REQ-2.5)

- [ ] 6. Integrate Full Chapter Scrape Status
  - [ ] 6.1 When full scrape starts, set `onboarding_status` to `scraping_chapters`. (REQ-3.1)
  - [ ] 6.2 Clear stale onboarding error fields on scrape start. (REQ-3.6)
  - [ ] 6.3 On successful scrape with usable raw chapters, set `ready_for_translation`. (REQ-3.2)
  - [ ] 6.4 For partial failures, follow existing translation support for partial chapter sets before setting ready. (REQ-3.3)
  - [ ] 6.5 On fatal scrape failure before usable raw chapters, set `failed`. (REQ-3.4)
  - [ ] 6.6 Record `onboarding_error_code`. (REQ-3.5)
  - [ ] 6.7 Record safe `onboarding_error_message`. (REQ-3.5)
  - [ ] 6.8 Avoid storing stack traces, raw chapter text, or secrets in onboarding error metadata.

- [ ] 7. Add Resume Operation
  - [ ] 7.1 Decide whether resume is a new endpoint or an extension of existing crawl activity creation. (REQ-4.1)
  - [ ] 7.2 Allow resume from `metadata_discovered`. (REQ-4.1)
  - [ ] 7.3 Allow resume from `glossary_pending`. (REQ-4.1)
  - [ ] 7.4 Allow resume from `chapters_pending`. (REQ-4.1)
  - [ ] 7.5 Allow resume from `failed`. (REQ-4.1)
  - [ ] 7.6 Reuse existing metadata and discovered chapter list. (REQ-4.2)
  - [ ] 7.7 Do not rerun preliminary crawl unless explicitly requested. (REQ-4.3)
  - [ ] 7.8 Create or run normal crawl activity so crawl observability still applies. (REQ-4.4)
  - [ ] 7.9 Respect existing crawl concurrency locks and avoid conflicting duplicate scrapes. (REQ-4.5)
  - [ ] 7.10 Return `activity_id` and current onboarding status.

- [ ] 8. Add Cancel Operation
  - [ ] 8.1 Add backend operation to mark incomplete onboarding as `cancelled`. (REQ-5.1)
  - [ ] 8.2 Allow cancel from metadata-only states.
  - [ ] 8.3 Allow cancel from `failed`.
  - [ ] 8.4 Do not delete files by default. (REQ-5.2)
  - [ ] 8.5 Ensure cancelled novels are not ready for translation. (REQ-5.4)
  - [ ] 8.6 Ensure cancelled novels remain visible in admin if existing listing includes them. (REQ-5.5)
  - [ ] 8.7 Keep destructive cleanup delegated to existing delete/remove novel flow. (REQ-5.3)

- [ ] 9. Add Translation Readiness Gate
  - [ ] 9.1 Add onboarding readiness check to translation preflight. (REQ-6.1)
  - [ ] 9.2 Block `metadata_discovered`. (REQ-6.2)
  - [ ] 9.3 Block `glossary_pending` unless existing flow intentionally handles glossary separately. (REQ-6.2)
  - [ ] 9.4 Block `chapters_pending`. (REQ-6.2)
  - [ ] 9.5 Block `scraping_chapters`. (REQ-6.2)
  - [ ] 9.6 Block `failed`. (REQ-6.2)
  - [ ] 9.7 Block `cancelled`. (REQ-6.2)
  - [ ] 9.8 Preserve existing glossary gate behavior. (REQ-6.3, REQ-6.4)
  - [ ] 9.9 Use inferred readiness for existing novels without status. (REQ-6.5)

- [ ] 10. Expose Status in Admin API Responses
  - [ ] 10.1 Add `onboarding_status` to admin novel detail responses. (REQ-8.2)
  - [ ] 10.2 Add `onboarding_status` to admin novel list/library responses. (REQ-8.2)
  - [ ] 10.3 Add `onboarding_updated_at` where useful.
  - [ ] 10.4 Add `onboarding_error_code` and `onboarding_error_message` where useful for failed state.
  - [ ] 10.5 Update strict response models if needed. (REQ-8.5)
  - [ ] 10.6 Keep all response changes additive. (REQ-8.4)

- [ ] 11. Update Admin UI
  - [ ] 11.1 Add onboarding status badges to admin novel list/library. (REQ-7.1)
  - [ ] 11.2 Add resume scrape action for pending states. (REQ-7.2)
  - [ ] 11.3 Add retry action for failed onboarding. (REQ-7.4)
  - [ ] 11.4 Display safe onboarding error message for failed state. (REQ-7.3)
  - [ ] 11.5 Add cancel action for incomplete onboarding if product patterns allow it. (REQ-5, REQ-7)
  - [ ] 11.6 Make cancelled novels visually distinct. (REQ-7.5)
  - [ ] 11.7 Ensure ready novels are not visually regressed. (REQ-7.6)

- [ ] 12. Backward Compatibility Checks
  - [ ] 12.1 Confirm old `metadata.json` files without onboarding fields load successfully. (REQ-9.1)
  - [ ] 12.2 Confirm no DB migration is needed if metadata-only state is sufficient. (REQ-9.2)
  - [ ] 12.3 If adding a DB projection field, add migration and backfill plan. (REQ-9.3)
  - [ ] 12.4 Confirm existing crawler route paths still work. (REQ-9.4)
  - [ ] 12.5 Confirm existing translation route paths still work. (REQ-9.4)
  - [ ] 12.6 Confirm public reader exposure remains governed by publish and reader availability rules. (REQ-9.5)

- [ ] 13. Add Backend Tests
  - [ ] 13.1 Create or update tests for preliminary crawl status. (REQ-10.1)
  - [ ] 13.2 Test glossary bootstrap coexists with onboarding status. (REQ-10.2)
  - [ ] 13.3 Test full scrape start sets `scraping_chapters`. (REQ-10.3)
  - [ ] 13.4 Test full scrape completion sets `ready_for_translation`. (REQ-10.4)
  - [ ] 13.5 Test fatal scrape failure sets `failed` and safe error metadata. (REQ-10.5)
  - [ ] 13.6 Test resume from pending or failed state. (REQ-10.6)
  - [ ] 13.7 Test cancel sets `cancelled`. (REQ-10.7)
  - [ ] 13.8 Test translation preflight blocks non-ready states. (REQ-10.8)
  - [ ] 13.9 Test existing metadata without onboarding fields infers compatible status. (REQ-10.9)
  - [ ] 13.10 Test admin responses include onboarding status. (REQ-10.10)

- [ ] 14. Add Frontend/Admin Tests If Existing Test Setup Supports It
  - [ ] 14.1 Test status badge rendering for pending state.
  - [ ] 14.2 Test failed onboarding displays error and retry action.
  - [ ] 14.3 Test resume action calls the chosen backend flow.
  - [ ] 14.4 Test cancelled state is visually distinct.

- [ ] 15. Run Verification
  - [ ] 15.1 Run focused backend onboarding tests.
  - [ ] 15.2 Run existing crawl/activity tests.
  - [ ] 15.3 Run existing translation preflight tests.
  - [ ] 15.4 Run admin frontend tests if touched.
  - [ ] 15.5 Run `ruff check` on changed backend files and tests.
  - [ ] 15.6 Run the configured backend type checker if present.
  - [ ] 15.7 Fix test, lint, and type failures caused by this work.

- [ ] 16. Final Acceptance Review
  - [ ] 16.1 Verify preliminary crawl records explicit onboarding state.
  - [ ] 16.2 Verify full scrape start/completion/failure updates onboarding state.
  - [ ] 16.3 Verify admin can resume pending or failed onboarding.
  - [ ] 16.4 Verify admin can cancel incomplete onboarding non-destructively.
  - [ ] 16.5 Verify translation is blocked for non-ready onboarding states.
  - [ ] 16.6 Verify existing novels without onboarding fields remain compatible.
  - [ ] 16.7 Verify admin list/detail responses expose onboarding status additively.
  - [ ] 16.8 Verify existing glossary gate remains intact.
  - [ ] 16.9 Verify focused tests pass.

## Requirement Coverage Matrix

| Requirement | Covered By Tasks |
|---|---|
| REQ-1 Explicit Onboarding State | 2, 3, 4, 10, 13, 16 |
| REQ-2 Preliminary Crawl State | 5, 13, 16 |
| REQ-3 Full Chapter Scrape State | 6, 13, 16 |
| REQ-4 Resume Onboarding | 7, 11, 13, 14, 16 |
| REQ-5 Cancel or Remove Incomplete Onboarding | 8, 11, 13, 14, 16 |
| REQ-6 Translation Readiness Gate | 9, 13, 16 |
| REQ-7 Admin UI Visibility | 10, 11, 14, 16 |
| REQ-8 API Response Shape | 5, 7, 8, 10, 13, 16 |
| REQ-9 Backward Compatibility | 4, 12, 13, 16 |
| REQ-10 Tests | 13, 14, 15 |

## Definition of Done

- [ ] `metadata.json` stores additive onboarding status fields.
- [ ] Existing novels infer compatible onboarding status.
- [ ] Preliminary crawl marks metadata/body-scrape pending state.
- [ ] Full chapter scrape marks running, ready, or failed state.
- [ ] Failed state stores safe error metadata.
- [ ] Resume flow reuses existing crawl activity path.
- [ ] Cancel flow is non-destructive.
- [ ] Translation preflight blocks non-ready novels.
- [ ] Admin responses and UI expose onboarding status.
- [ ] Existing glossary gate and public reader behavior remain intact.
- [ ] Focused backend and UI tests pass.

