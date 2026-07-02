# Tasks: Glossary Auto-Population

## Task List

- [x] 1. Create `SuggestionExtractor`
  - [x] 1.1 Create `backend/src/novelai/services/glossary/suggestion_extractor.py` (REQ-1)
  - [x] 1.2 Implement frequency-based extraction (n-gram counting) (REQ-1.2)
  - [x] 1.3 Implement LLM-based extraction for proper nouns (REQ-1.2)
  - [x] 1.4 Add configurable `min_frequency` threshold (REQ-1.2)
  - [x] 1.5 Exclude terms already in novel glossary (REQ-1.4)
  - [x] 1.6 Handle extraction failure gracefully (WARNING log, proceed) (REQ-1.3)

- [x] 2. Create `GlossarySuggestionService`
  - [x] 2.1 Create `backend/src/novelai/services/glossary/suggestion_service.py` (REQ-2)
  - [x] 2.2 Define `GlossarySuggestion` Pydantic model (REQ-2.2)
  - [x] 2.3 Implement file-backed storage (`glossary_suggestions.json`) (REQ-2.1)
  - [x] 2.4 Implement `add_suggestions` with merge/dedup logic (REQ-5.1, REQ-5.2, REQ-5.3)
  - [x] 2.5 Implement `list_suggestions` with status/source filtering (REQ-3.1)
  - [x] 2.6 Implement `accept` / `reject` (REQ-3.2, REQ-3.3)
  - [x] 2.7 Implement `accept_all` / `reject_all` (REQ-3.4, REQ-3.5)

- [x] 3. Trigger extraction after translation
  - [x] 3.1 Update `post_process.py` to call `SuggestionExtractor.extract()` after chapter save (REQ-1.1)
  - [x] 3.2 Store extracted suggestions via `GlossarySuggestionService` (REQ-1.1)

- [x] 4. Add owner review API endpoints
  - [x] 4.1 Add `GET /api/admin/novels/{novel_id}/glossary/suggestions` (REQ-3.1)
  - [x] 4.2 Add `POST .../suggestions/{id}/accept` with optional `modified_translation` (REQ-3.2)
  - [x] 4.3 Add `POST .../suggestions/{id}/reject` with optional `reason` (REQ-3.3)
  - [x] 4.4 Add `POST .../suggestions/accept-all` (REQ-3.4)
  - [x] 4.5 Add `POST .../suggestions/reject-all` (REQ-3.5)

- [x] 5. Wire acceptance into glossary
  - [x] 5.3 On accept: call `GlossaryService.add_term()` (REQ-4.1)
  - [x] 5.4 On accept: call `TranslationCacheService.invalidate()` if available (REQ-4.2)

- [x] 6. Write tests
  - [x] 6.1 Test `SuggestionExtractor` frequency-based extraction returns expected n-grams
  - [x] 6.2 Test `GlossarySuggestionService` add/list/accept/reject flow
  - [x] 6.3 Test deduplication: same term merged, not duplicated
  - [x] 6.4 Test rejected terms are not re-suggested
  - [x] 6.5 Test review API endpoints with various filter combinations
  - [x] 6.6 Test best-effort behavior when extraction fails

- [x] 7. Verify, lint, and type-check
  - [x] 7.1 Run `pytest backend/tests/ --tb=short -q` and confirm all pass
  - [x] 7.2 Run `ruff check backend/src/novelai/services/glossary/` and fix issues
  - [x] 7.3 Run `pyright` and fix type errors
