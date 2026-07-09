# Requirements: CI/CD Pipeline Setup

## Introduction

The repository has no automated build, test, or deployment pipeline. Developers must manually run linting, tests, and type checks before merging. There is no automated Docker image building, no staging deployment, and no gate to prevent merging broken code. This leads to inconsistencies across environments and manual release overhead.

This spec adds a GitHub Actions CI/CD pipeline that runs linting, type-checking, unit tests, and e2e tests on every pull request, and builds Docker images on merge to main.

## Requirements

### REQ-1: Pull Request CI

Every pull request must trigger automated checks.

- REQ-1.1: On every PR to `main` or `develop`, the workflow must:
  - Install Python backend dependencies
  - Run `ruff check .` for linting (backend)
  - Run `pyright` for type checking (backend)
  - Run `pytest --tb=short -q -m "not e2e"` for unit tests (backend)
  - Install Node frontend dependencies
  - Run `npm run typecheck` (frontend)
  - Run `npm run lint` (frontend, if configured)
- REQ-1.2: The workflow must fail if any step fails. Only green checks should allow merging.
- REQ-1.3: The workflow file must be at `.github/workflows/ci.yml`.

### REQ-2: E2E Test Gate

End-to-end tests must run on PRs that touch pipeline or service code.

- REQ-2.1: A separate job `e2e-tests` must run `pytest -m e2e --tb=short -q` using the e2e test suite.
- REQ-2.2: The e2e job must only run when files in `backend/src/novelai/services/`, `backend/src/novelai/api/`, or `backend/tests/e2e/` are changed (path-based triggers for efficiency).
- REQ-2.3: The e2e job must use the same in-memory SQLite and `tmp_path` approach as local runs.

### REQ-3: Build on Merge

On merge to `main`, Docker images must be built and tagged.

- REQ-3.1: A `build` workflow (separate file or job) must trigger on push to `main`.
- REQ-3.2: Build Docker images for the backend and frontend using the project's existing `Dockerfile`s.
- REQ-3.3: Images must be tagged with the git short SHA and `latest`.
- REQ-3.4: Images must be pushed to a container registry (GitHub Container Registry or Docker Hub) configured via repository secrets.

### REQ-4: Caching and Performance

CI must use caching to keep run times low.

- REQ-4.1: Python dependencies must be cached using `actions/setup-python` cache or `actions/cache` with `requirements.lock` as the key.
- REQ-4.2: Node dependencies must be cached using `actions/setup-node` cache with `package-lock.json` as the key.
- REQ-4.3: Docker build layers must be cached using Docker BuildKit cache.
- REQ-4.4: The full CI pipeline (excluding e2e) must complete within 5 minutes on a cache hit.

### REQ-5: Deployment (Stretch)

Optional staging deployment from `main`.

- REQ-5.1: A `deploy` job (optional, manually triggered via `workflow_dispatch`) must deploy the Docker images to a staging server via SSH or Docker Compose pull.
- REQ-5.2: The deploy job must accept a version tag input and a target environment input (`staging` / `production`).

## Non-Goals

- This spec does not add Kubernetes deployment or Helm charts.
- This spec does not add pre-commit hooks (those are developer-local).
- This spec does not add automated version bumping or release notes generation.
- This spec does not change the existing `ci.yml` if one exists (enhances it).
