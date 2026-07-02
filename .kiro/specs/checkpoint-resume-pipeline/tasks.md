# Tasks: Checkpoint and Resume Pipeline

## Task List

- [x] 1. Add DB state tracking
  - [x] 1.1 Add `translation_state` and `translation_error` columns to `Chapter` model (REQ-1.2, REQ-1.3)
  - [x] 1.2 Generate and run Alembic migration (REQ-1.2)
  - [x] 1.3 Define `TranslationState` enum (REQ-1.1)

- [ ] 2. Create `CheckpointManager`
  - [ ] 2.1 Create `backend/src/novelai/services/pipeline/checkpoint.py` (REQ-2)
  - [ ] 2.2 Define `Checkpoint` Pydantic model (REQ-2.2)
  - [ ] 2.3 Implement `load` with staleness and corruption handling (REQ-5.2)
  - [ ] 2.4 Implement `save` with atomic write (REQ-2.4)
  - [ ] 2.5 Implement `delete` (REQ-2)

- [ ] 3. Refactor `TranslationService` for resume
  - [ ] 3.1 Update state before/after each pipeline stage in `_translate_chapter` (REQ-1.4)
  - [ ] 3.2 Implement resume logic: skip COMPLETE, reset FAILED, resume from checkpoint (REQ-3.1)
  - [ ] 3.3 Write checkpoint after each segment and stage transition (REQ-2.3)
  - [ ] 3.4 Handle corrupt checkpoint gracefully (log WARNING, restart) (REQ-3.3)
  - [ ] 3.5 Handle checkpoint write failure gracefully (log WARNING, continue) (REQ-5.1)

- [x] 4. Add concurrency guard
  - [x] 4.1 Check for in-progress chapters before starting translation (REQ-5.3)
  - [x] 4.2 Return HTTP 409 if translation already in progress (REQ-5.3)

- [ ] 5. Add `force` parameter
  - [ ] 5.1 Accept `?force=true` query parameter on translate endpoint (REQ-3.4)
  - [ ] 5.2 Reset all chapters to PENDING when force is true (REQ-3.4)

- [x] 6. Add translation status endpoint
  - [x] 6.1 Add `GET /api/admin/novels/{id}/translate-status` (REQ-4.1)
  - [x] 6.2 Return per-chapter state and segment counts (REQ-4.1)
  - [x] 6.3 Include `translation_state` in existing novel detail endpoint (REQ-1.5)

- [ ] 7. Write tests
  - [ ] 7.1 Test checkpoint is written after stage completion
  - [ ] 7.2 Test resume from checkpoint skips completed stages
  - [ ] 7.3 Test COMPLETE chapters are skipped on re-run
  - [ ] 7.4 Test FAILED chapters are retried from scratch
  - [ ] 7.5 Test `?force=true` restarts all chapters
  - [x] 7.6 Test concurrent translation returns 409
  - [ ] 7.7 Test corrupt checkpoint is handled (restart chapter)
  - [ ] 7.8 Test stale checkpoint is invalidated
  - [x] 7.9 Test `translate-status` endpoint returns correct counts

- [x] 8. Verify, lint, and type-check
  - [x] 8.1 Run `pytest backend/tests/ --tb=short -q` and confirm all pass
  - [x] 8.2 Run `ruff check backend/src/novelai/services/pipeline/` and fix issues
  - [x] 8.3 Run `pyright` and fix type errors
