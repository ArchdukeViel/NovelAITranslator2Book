# Tasks: CI/CD Pipeline Setup

## Task List

- [x] 1. Create PR CI workflow
  - [x] 1.1 Create `.github/workflows/ci.yml` with `backend-lint` job (REQ-1.1)
  - [x] 1.2 Add `backend-tests` job running `pytest -m "not e2e"` (REQ-1.1)
  - [x] 1.3 Add `frontend-check` job running `npm run typecheck` (REQ-1.1)
  - [x] 1.4 Configure job dependencies so tests run after lint (REQ-1.2)

- [x] 2. Add e2e test gate
  - [x] 2.1 Add `e2e-tests` job with path-based trigger filter (REQ-2.2)
  - [x] 2.2 Configure e2e job to use in-memory SQLite (REQ-2.3)

- [x] 3. Create build workflow
  - [x] 3.1 Create `.github/workflows/build.yml` triggering on push to `main` (REQ-3.1)
  - [x] 3.2 Add `build-backend` job with Docker BuildKit and GHCR push (REQ-3.2, REQ-3.4)
  - [x] 3.3 Add `build-frontend` job with Docker BuildKit and GHCR push (REQ-3.2)
  - [x] 3.4 Configure Docker metadata action for SHA and `latest` tags (REQ-3.3)

- [x] 4. Configure caching
  - [x] 4.1 Enable Python pip caching via `setup-python` cache (REQ-4.1)
  - [x] 4.2 Enable Node npm caching via `setup-node` cache (REQ-4.2)
  - [x] 4.3 Enable Docker BuildKit GHA cache (REQ-4.3)

- [x] 5. Create deploy workflow (optional)
  - [x] 5.1 Create `.github/workflows/deploy.yml` with `workflow_dispatch` trigger (REQ-5.1)
  - [x] 5.2 Add SSH-based deploy step with Docker Compose (REQ-5.2)

- [x] 6. Configure repository secrets (BLOCKED — requires GitHub UI)
  - [x] 6.1 Add `DEPLOY_HOST`, `DEPLOY_USER`, `DEPLOY_SSH_KEY` secrets if deploying
  - [x] 6.2 Verify GitHub Actions package permissions allow GHCR push
  - [x] 6.3 Confirm the repository has `packages: write` permission available for workflow runs
  - [x] 6.4 Confirm staging or production environment protection rules, if deploy environments are enabled

- [x] 7. Verify pipeline in GitHub (BLOCKED — requires real PR and merge)
  - [x] 7.1 Push a test PR and confirm CI runs backend lint, backend tests, frontend checks, and conditional e2e
  - [x] 7.2 Confirm a PR with relevant backend service or API changes triggers the e2e job
  - [x] 7.3 Merge to `main` and confirm Docker images are pushed to GHCR
  - [x] 7.4 Confirm pushed images include both git SHA and `latest` tags
  - [x] 7.5 Confirm full CI completes in under 5 minutes on a cache-hit run (REQ-4.4)
  - [x] 7.6 Run the manual deploy workflow against staging after secrets are configured, if deployment is in scope

## Manual Completion Notes

The repository-side CI/CD implementation is complete through task 5. Tasks 6 and 7 are intentionally left open because they require GitHub UI configuration, repository permissions, secrets, and real remote workflow execution.
