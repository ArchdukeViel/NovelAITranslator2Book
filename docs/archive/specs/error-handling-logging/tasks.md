# Tasks: Enhanced Error Handling and Logging

## Task List

- [ ] 1. Define error infrastructure
  - [ ] 1.1 Create `backend/src/novelai/api/errors.py` with `ErrorCategory`, `ErrorResponse`, `StructuredHTTPException` (REQ-1.1, REQ-2.1)
  - [ ] 1.2 Implement `CATEGORY_TO_STATUS` mapping (REQ-2.3)
  - [ ] 1.3 Define error code hierarchy constants (REQ-1.2)

- [ ] 2. Register exception handler
  - [ ] 2.1 Add `structured_exception_handler` in `main.py` (REQ-1.5)
  - [ ] 2.2 Review and update existing `HTTPException` usages to include `error_code` (REQ-1.3)

- [ ] 3. Add pipeline structured logging
  - [ ] 3.1 Create `backend/src/novelai/services/pipeline/context.py` with `PipelineContext` class (REQ-3.1)
  - [ ] 3.2 Create `get_pipeline_logger` helper with contextual fields (REQ-3.4)
  - [ ] 3.3 Add `stage_enter` / `stage_exit` / `stage_error` methods (REQ-3.2, REQ-3.5)

- [ ] 4. Integrate logging into pipeline stages
  - [ ] 4.1 Update each stage in `services/pipeline/stages/` to use `PipelineContext` (REQ-3.2)
  - [ ] 4.2 Log stage entry/exit with duration (REQ-3.3)

- [ ] 5. Add JSON log formatter
  - [ ] 5.1 Create `JsonFormatter` in `logging_config.py` (REQ-4.1)
  - [ ] 5.2 Support `LOG_FORMAT=json` environment variable (REQ-4.2)

- [ ] 6. Add error metrics endpoint
  - [ ] 6.1 Implement error counters (`by_category`, `by_stage`) in `errors.py` (REQ-4.3)
  - [ ] 6.2 Implement `GET /api/admin/health/errors` endpoint (REQ-4.4)

- [ ] 7. Write tests
  - [ ] 7.1 Test `StructuredHTTPException` -> `ErrorResponse` serialization
  - [ ] 7.2 Test `PipelineContext` stage lifecycle logging
  - [ ] 7.3 Test `JsonFormatter` output is valid JSON
  - [ ] 7.4 Test `/health/errors` endpoint

- [ ] 8. Verify, lint, and type-check
  - [ ] 8.1 Run `pytest backend/tests/ --tb=short -q` and confirm all pass
  - [ ] 8.2 Run `ruff check backend/src/novelai/api/errors.py backend/src/novelai/services/pipeline/` and fix issues
  - [ ] 8.3 Run `pyright` and fix type errors
