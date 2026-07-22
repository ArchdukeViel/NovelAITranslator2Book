# Tasks: Enhanced Error Handling and Logging

## Task List

- [x] 1. Define error infrastructure
  - [x] 1.1 Create `backend/src/novelai/api/errors.py` with `ErrorCategory`, `ErrorResponse`, `StructuredHTTPException` (REQ-1.1, REQ-2.1)
  - [x] 1.2 Implement `CATEGORY_TO_STATUS` mapping (REQ-2.3)
  - [x] 1.3 Define error code hierarchy constants (REQ-1.2)

- [x] 2. Register exception handler
  - [x] 2.1 Add `structured_exception_handler` in `main.py` (REQ-1.5)
  - [x] 2.2 Review and update existing `HTTPException` usages to include `error_code` (REQ-1.3)

- [x] 3. Add pipeline structured logging
  - [x] 3.1 Create `backend/src/novelai/services/pipeline/context.py` with `PipelineContext` class (REQ-3.1)
  - [x] 3.2 Create `get_pipeline_logger` helper with contextual fields (REQ-3.4)
  - [x] 3.3 Add `stage_enter` / `stage_exit` / `stage_error` methods (REQ-3.2, REQ-3.5)

- [x] 4. Integrate logging into pipeline stages
  - [x] 4.1 Update each stage in `services/pipeline/stages/` to use `PipelineContext` (REQ-3.2)
  - [x] 4.2 Log stage entry/exit with duration (REQ-3.3)

- [x] 5. Add JSON log formatter
  - [x] 5.1 Create `JsonFormatter` in `logging_config.py` (REQ-4.1)
  - [x] 5.2 Support `LOG_FORMAT=json` environment variable (REQ-4.2)

- [x] 6. Add error metrics endpoint
  - [x] 6.1 Implement error counters (`by_category`, `by_stage`) in `errors.py` (REQ-4.3)
  - [x] 6.2 Implement `GET /api/admin/health/errors` endpoint (REQ-4.4)

- [x] 7. Write tests
  - [x] 7.1 Test `StructuredHTTPException` -> `ErrorResponse` serialization
  - [x] 7.2 Test `PipelineContext` stage lifecycle logging
  - [x] 7.3 Test `JsonFormatter` output is valid JSON
  - [x] 7.4 Test `/health/errors` endpoint

- [x] 8. Verify, lint, and type-check
  - [x] 8.1 Run `pytest backend/tests/ --tb=short -q` and confirm all pass
  - [x] 8.2 Run `ruff check backend/src/novelai/api/errors.py backend/src/novelai/services/pipeline/` and fix issues
  - [x] 8.3 Run `pyright` and fix type errors
