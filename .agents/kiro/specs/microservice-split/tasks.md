# Tasks: Microservice Split

## Task List

- [x] 1. Extract shared `novelai-core` package
  - [x] 1.1 Create `backend/src/novelai_core/` with `pyproject.toml` (REQ-3.4)
  - [x] 1.2 Move DB models to `novelai_core/models/` (REQ-3.2)
  - [x] 1.3 Move shared Pydantic schemas to `novelai_core/schemas/` (REQ-3.1)
  - [x] 1.4 Move `StorageService` to `novelai_core/storage/` (REQ-3.3)
  - [x] 1.5 Move DB engine/session to `novelai_core/db/` (REQ-3.2)
  - [x] 1.6 Update imports in all existing files to use `novelai_core`

- [x] 2. Create service entry points
  - [x] 2.1 Create `backend/src/novelai/main_reader.py` with public-only routers (REQ-1.1)
  - [x] 2.2 Create `backend/src/novelai/main_admin.py` with admin-only routers (REQ-1.2)
  - [x] 2.3 Verify no endpoint is registered in both services (REQ-1.3)

- [x] 3. Update `main.py` monolith for backward compatibility
  - [x] 3.1 Add `DEPLOY_MODE` env var check (REQ-4.4, REQ-4.5)
  - [x] 3.2 Ensure monolith mode includes all routers as before

- [x] 4. Update deployment configuration
  - [x] 4.1 Add `reader` service to `deploy/compose.yml` (REQ-4.1)
  - [x] 4.2 Rename backend service to `admin` in `deploy/compose.yml` (REQ-4.2)
  - [x] 4.3 Create `deploy/reader.Dockerfile` (REQ-4.1)
  - [x] 4.4 Rename `deploy/backend.Dockerfile` to `deploy/admin.Dockerfile`
  - [x] 4.5 Update `deploy/Caddyfile` for dual-service routing (REQ-2.1)
  - [x] 4.6 Add health check directives to Caddyfile (REQ-2.2)
  - [x] 4.7 Add per-service rate limiting to Caddyfile (REQ-2.3)

- [x] 5. Update CI/CD
  - [x] 5.1 Update `.github/workflows/ci.yml` to build and test both services (REQ-5.1)
  - [x] 5.2 Update Docker image tagging for service names (REQ-5.2)

- [x] 6. Write tests
  - [x] 6.1 Test monolith mode serves all endpoints
  - [x] 6.2 Test split mode: reader serves only public endpoints
  - [x] 6.3 Test split mode: admin serves only admin endpoints
  - [x] 6.4 Test `DEPLOY_MODE` env var switching

- [x] 7. Verify, lint, and type-check
  - [x] 7.1 Run `pytest backend/tests/ --tb=short -q` and confirm all pass
  - [x] 7.2 Run `ruff check backend/src/` and fix issues
  - [x] 7.3 Run `pyright` and fix type errors
