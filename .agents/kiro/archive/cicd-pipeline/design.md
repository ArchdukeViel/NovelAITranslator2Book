# Design: CI/CD Pipeline Setup

## Overview

Create a modular GitHub Actions CI/CD pipeline. PR CI runs linting, type-checking, and unit tests. A conditional e2e job runs on relevant file changes. On merge to main, Docker images are built and pushed to a container registry.

## Architecture

### Affected Files

| File | Change type |
|---|---|
| `.github/workflows/ci.yml` | New — PR CI pipeline (lint, typecheck, unit tests, e2e) |
| `.github/workflows/build.yml` | New — Docker build and push on merge to main |
| `.github/workflows/deploy.yml` | New — manual deploy to staging (optional) |

### Files Not Touched

- All application source code — no changes
- Dockerfiles — referenced, not changed
- `pyproject.toml` — referenced, not changed

## Component Design

### 1. PR CI Workflow (`.github/workflows/ci.yml`)

```yaml
name: CI

on:
  pull_request:
    branches: [main, develop]
  push:
    branches: [main, develop]

jobs:
  backend-lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
          cache: "pip"
      - run: pip install -e ".[dev,db,worker]"
      - run: ruff check .
      - run: pyright

  backend-tests:
    runs-on: ubuntu-latest
    needs: backend-lint
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
          cache: "pip"
      - run: pip install -e ".[dev,db,worker]"
      - run: pytest --tb=short -q -m "not e2e"

  frontend-check:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: "20"
          cache: "npm"
          cache-dependency-path: frontend/package-lock.json
      - working-directory: frontend
        run: |
          npm ci
          npm run typecheck

  e2e-tests:
    runs-on: ubuntu-latest
    needs: backend-tests
    if: |
      contains(github.event.head_commit.modified, 'backend/src/novelai/services/') ||
      contains(github.event.head_commit.modified, 'backend/src/novelai/api/') ||
      contains(github.event.head_commit.modified, 'backend/tests/e2e/')
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
          cache: "pip"
      - run: pip install -e ".[dev,db,worker]"
      - run: pytest -m e2e --tb=short -q
```

### 2. Build Workflow (`.github/workflows/build.yml`)

```yaml
name: Build and Push

on:
  push:
    branches: [main]

jobs:
  build-backend:
    runs-on: ubuntu-latest
    permissions:
      contents: read
      packages: write
    steps:
      - uses: actions/checkout@v4
      - uses: docker/setup-buildx-action@v3
      - uses: docker/login-action@v3
        with:
          registry: ghcr.io
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}
      - id: meta
        uses: docker/metadata-action@v5
        with:
          images: ghcr.io/${{ github.repository }}/novelai-backend
          tags: |
            type=sha,prefix=
            type=raw,value=latest
      - uses: docker/build-push-action@v5
        with:
          context: .
          file: deploy/backend.Dockerfile
          push: true
          tags: ${{ steps.meta.outputs.tags }}
          labels: ${{ steps.meta.outputs.labels }}
          cache-from: type=gha
          cache-to: type=gha,mode=max

  build-frontend:
    runs-on: ubuntu-latest
    permissions:
      contents: read
      packages: write
    steps:
      - uses: actions/checkout@v4
      - uses: docker/setup-buildx-action@v3
      - uses: docker/login-action@v3
        with:
          registry: ghcr.io
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}
      - id: meta
        uses: docker/metadata-action@v5
        with:
          images: ghcr.io/${{ github.repository }}/novelai-frontend
          tags: |
            type=sha,prefix=
            type=raw,value=latest
      - uses: docker/build-push-action@v5
        with:
          context: ./frontend
          file: frontend/Dockerfile
          push: true
          tags: ${{ steps.meta.outputs.tags }}
          labels: ${{ steps.meta.outputs.labels }}
          cache-from: type=gha
          cache-to: type=gha,mode=max
```

### 3. Deploy Workflow (`.github/workflows/deploy.yml`)

```yaml
name: Deploy

on:
  workflow_dispatch:
    inputs:
      version:
        description: "Image tag to deploy"
        required: true
        default: "latest"
      environment:
        description: "Target environment"
        required: true
        type: choice
        options:
          - staging
          - production

jobs:
  deploy:
    runs-on: ubuntu-latest
    environment: ${{ github.event.inputs.environment }}
    steps:
      - name: Deploy via SSH
        uses: appleboy/ssh-action@v1
        with:
          host: ${{ secrets.DEPLOY_HOST }}
          username: ${{ secrets.DEPLOY_USER }}
          key: ${{ secrets.DEPLOY_SSH_KEY }}
          script: |
            cd /opt/novelai
            docker compose pull
            docker compose up -d --remove-orphans
```

### 4. Caching Strategy

| Dependency | Cache Mechanism | Key |
|---|---|---|
| Python (pip) | `setup-python` built-in cache | `requirements.lock` |
| Node (npm) | `setup-node` built-in cache | `package-lock.json` |
| Docker layers | BuildKit GHA cache backend | `type=gha` |

## Migration and Backward Compatibility

- No existing CI pipeline to migrate from — this is greenfield.
- The `ci.yml` already exists in the repo but may be minimal. The new workflow enhances it.
- Repository secrets must be configured for Docker registry login and deployment SSH.

## Acceptance Criteria

1. A PR to `main` triggers linting, type-checking, and unit tests; they pass.
2. A PR changing files in `backend/src/novelai/services/` triggers e2e tests.
3. A PR with lint errors causes the CI check to fail.
4. Push to `main` triggers Docker image build and push to GHCR with correct tags.
5. Full CI pipeline (lint + test + frontend check) completes in under 5 minutes.
6. Docker images are available at `ghcr.io/<repo>/novelai-backend:latest`.
