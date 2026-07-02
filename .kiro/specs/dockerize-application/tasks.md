# Tasks: Dockerize Application

## Task List

- [x] 1. Update backend Dockerfile
  - [x] 1.1 Create/update `deploy/backend.Dockerfile` with multi-stage build (REQ-1.1, REQ-1.2)
  - [x] 1.2 Install system dependencies: build-essential, libffi-dev (REQ-1.1)
  - [x] 1.3 Install Python dependencies from `requirements.lock` (REQ-1.1)
  - [x] 1.4 Install `novelai` package in editable mode (REQ-1.1)
  - [x] 1.5 Set correct ENTRYPOINT (REQ-1.1)

- [x] 2. Update frontend Dockerfile
  - [x] 2.1 Create/update `deploy/frontend.Dockerfile` with multi-stage build (REQ-2.1, REQ-2.2)
  - [x] 2.2 Configure `NEXT_PUBLIC_API_URL` build argument (REQ-2.3)
  - [x] 2.3 Use Next.js standalone output for smaller runtime image (REQ-2.1)

- [x] 3. Update Docker Compose
  - [x] 3.1 Update `deploy/compose.yml` with `db`, `backend`, `frontend`, `caddy` services (REQ-3.1)
  - [x] 3.2 Define shared network and named volumes (REQ-3.2, REQ-3.3)
  - [x] 3.3 Add healthchecks for `db` and `backend` (REQ-3.4)
  - [x] 3.4 Configure environment variables via `.env` file (REQ-3.5)

- [x] 4. Create development overrides
  - [x] 4.1 Create `deploy/compose.dev.yml` with hot-reload volumes (REQ-4.1)
  - [x] 4.2 Ensure production compose has no source bind-mounts (REQ-4.2)

- [x] 5. Update `.dockerignore`
  - [x] 5.1 Add entries for `.venv/`, `__pycache__/`, `node_modules/`, `storage/`, etc. (REQ-1.4)

- [x] 6. Update documentation
  - [x] 6.1 Update `deploy/.env.example` with all required variables (REQ-5.2)
  - [ ] 6.2 Add "Quick Start with Docker" section to `readme.md` (REQ-5.1)

- [ ] 7. Verify
  - [ ] 7.1 Run `docker compose -f deploy/compose.yml up -d` and check `docker compose ps` (all healthy)
  - [ ] 7.2 Run `docker compose exec backend novelai create-user` and verify
  - [ ] 7.3 Confirm backend image under 500 MB (REQ-1.3)
  - [ ] 7.4 Test hot-reload with dev override (REQ-4.1)
