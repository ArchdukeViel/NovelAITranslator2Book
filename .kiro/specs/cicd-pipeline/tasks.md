# Tasks: CI/CD Pipeline Setup

## Task List

- [ ] 1. Create PR CI workflow
  - [ ] 1.1 Create `.github/workflows/ci.yml` with `backend-lint` job (REQ-1.1)
  - [ ] 1.2 Add `backend-tests` job running `pytest -m "not e2e"` (REQ-1.1)
  - [ ] 1.3 Add `frontend-check` job running `npm run typecheck` (REQ-1.1)
  - [ ] 1.4 Configure job dependencies so tests run after lint (REQ-1.2)

- [ ] 2. Add e2e test gate
  - [ ] 2.1 Add `e2e-tests` job with path-based trigger filter (REQ-2.2)
  - [ ] 2.2 Configure e2e job to use in-memory SQLite (REQ-2.3)

- [ ] 3. Create build workflow
  - [ ] 3.1 Create `.github/workflows/build.yml` triggering on push to `main` (REQ-3.1)
  - [ ] 3.2 Add `build-backend` job with Docker BuildKit and GHCR push (REQ-3.2, REQ-3.4)
  - [ ] 3.3 Add `build-frontend` job with Docker BuildKit and GHCR push (REQ-3.2)
  - [ ] 3.4 Configure Docker metadata action for SHA and `latest` tags (REQ-3.3)

- [ ] 4. Configure caching
  - [ ] 4.1 Enable Python pip caching via `setup-python` cache (REQ-4.1)
  - [ ] 4.2 Enable Node npm caching via `setup-node` cache (REQ-4.2)
  - [ ] 4.3 Enable Docker BuildKit GHA cache (REQ-4.3)

- [ ] 5. Create deploy workflow (optional)
  - [ ] 5.1 Create `.github/workflows/deploy.yml` with `workflow_dispatch` trigger (REQ-5.1)
  - [ ] 5.2 Add SSH-based deploy step with Docker Compose (REQ-5.2)

- [ ] 6. Configure repository secrets
  - [ ] 6.1 Add `DEPLOY_HOST`, `DEPLOY_USER`, `DEPLOY_SSH_KEY` secrets if deploying
  - [ ] 6.2 Verify GHCR token permissions

- [ ] 7. Verify
  - [ ] 7.1 Push a test PR and confirm CI runs all jobs
  - [ ] 7.2 Merge to `main` and confirm Docker images are pushed to GHCR
  - [ ] 7.3 Confirm full CI completes in under 5 minutes (REQ-4.4)
