# Requirements: Microservice Split

## Introduction

The application currently runs as a single FastAPI service that serves both the owner/admin orchestration endpoints and the public reader endpoints. These two workloads have different scalability, security, and availability requirements. The public reader needs to serve many unauthenticated users with low latency and high availability, while the owner orchestration service handles authenticated, long-running operations like scraping and translation.

This spec proposes separating the public reader service from the owner orchestration service into two independently deployable microservices. They share a database but are otherwise independent, enabling independent scaling, deployment, and failure isolation.

## Requirements

### REQ-1: Service Decomposition

The monolith must be split into two services with clear boundaries.

- REQ-1.1: **Public Reader Service** — serves all public endpoints (`GET /api/public/catalog`, `GET /api/public/novels/{slug}`, `GET /api/public/novels/{slug}/chapters/{chapter_id}`). No authentication required. Read-only.
- REQ-1.2: **Owner Admin Service** — serves all owner/admin endpoints (`POST /api/admin/*`). Requires authentication. Read-write.
- REQ-1.3: Shared endpoints must not exist. Every endpoint must belong exclusively to one service.
- REQ-1.4: Both services must share the same database (read-replica for public service, primary for owner service) to avoid data synchronization complexity.
- REQ-1.5: The public service must have its own FastAPI application instance, its own port, and its own Docker container.

### REQ-2: API Gateway / Reverse Proxy

A reverse proxy must route requests to the correct service.

- REQ-2.1: The existing Caddyfile must be updated to route `/api/public/*` to the public reader service and all other `/api/*` paths to the owner admin service.
- REQ-2.2: The reverse proxy must add a grace period for service startup (health check before routing).
- REQ-2.3: The reverse proxy must support rate limiting per service (higher limits for public, lower for admin to prevent brute force).

### REQ-3: Shared Code

Shared code must be extracted into a common library to avoid duplication.

- REQ-3.1: Shared models, schemas, and utilities must live in `backend/src/novelai/common/` or be packaged as a separate installable library.
- REQ-3.2: DB models and Alembic migrations must be shared (both services use the same database schema).
- REQ-3.3: Storage layer (`StorageService`) must be shared — both services need to read/write to the same filesystem.
- REQ-3.4: A shared `novelai-core` Python package must be created and installed by both services.

### REQ-4: Deployment Configuration

The Docker Compose configuration must be updated.

- REQ-4.1: Add `reader` service to `deploy/compose.yml` with its own Dockerfile (`deploy/reader.Dockerfile`) and port (e.g. 8001).
- REQ-4.2: Rename the existing backend service to `admin` in `deploy/compose.yml`.
- REQ-4.3: Both services must share the same `.env` file for database credentials and storage paths.
- REQ-4.4: A `DEPLOY_MODE` environment variable (values: `monolith`, `split`) must control whether the application starts as one service or two.
- REQ-4.5: The default `DEPLOY_MODE=monolith` must preserve the current single-service behavior for backward compatibility.

### REQ-5: CI/CD Updates

The CI pipeline must handle the split.

- REQ-5.1: `.github/workflows/ci.yml` must build and test both services independently.
- REQ-5.2: Docker images must be tagged with service name: `novelai-admin:latest`, `novelai-reader:latest`.
- REQ-5.3: The CI must run the full test suite for both services and fail if either fails.

### REQ-6: Shared State Considerations

- REQ-6.1: The public reader must use a read-only database user (if the database supports it) to enforce the read-only contract.
- REQ-6.2: Both services must use the same filesystem storage for `storage/novel_library/`. The public service only reads; the admin service reads and writes.
- REQ-6.3: Session/cookie validation must remain in the admin service only. The public service does not need auth middleware.

## Non-Goals

- This spec does not split the database into separate instances (shared DB for now).
- This spec does not add a message queue or event bus between services.
- This spec does not change the existing API contract or response shapes.
- This spec does not add Kubernetes or container orchestration beyond Docker Compose.
- This spec does not change the frontend deployment or architecture.
