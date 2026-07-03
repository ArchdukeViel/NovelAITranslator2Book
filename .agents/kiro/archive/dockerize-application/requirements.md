# Requirements: Dockerize Application

## Introduction

The application has no container setup. Developers must manually install Python and Node environments, configure dependencies, and manage service processes locally. This makes onboarding difficult, leads to environment inconsistencies, and complicates deployment. While Dockerfiles exist in `deploy/`, they may be incomplete or not tested end-to-end.

This spec ensures the application is fully containerized with working Dockerfiles for the backend and frontend, a Docker Compose configuration for the full stack (backend, frontend, database, reverse proxy), and documented setup instructions.

## Requirements

### REQ-1: Backend Dockerfile

The backend must build and run correctly in a container.

- REQ-1.1: Create or update `deploy/backend.Dockerfile` to:
  - Use `python:3.12-slim` as the base image.
  - Install system dependencies (build-essential, libffi-dev for compiled packages).
  - Copy `requirements.lock` and run `pip install`.
  - Install the `novelai` package in editable mode (`pip install -e .`).
  - Copy application source code.
  - Expose port 8000.
  - Set `ENTRYPOINT ["novelai", "web", "--host", "0.0.0.0", "--port", "8000"]`.
- REQ-1.2: The Dockerfile must use multi-stage builds: a `builder` stage for dependency installation and a `runtime` stage with only runtime dependencies.
- REQ-1.3: The image must be under 500 MB uncompressed.
- REQ-1.4: A `.dockerignore` must exclude `.venv/`, `__pycache__/`, `.git/`, `node_modules/`, `frontend/`, `storage/`, and `.hypothesis/`.

### REQ-2: Frontend Dockerfile

The frontend must build and serve correctly in a container.

- REQ-2.1: Create or update `deploy/frontend.Dockerfile` to:
  - Use `node:20-alpine` as the base image.
  - Copy `package.json` and `package-lock.json`, run `npm ci`.
  - Copy source code and run `npm run build`.
  - Use `node:20-alpine` for the runtime stage.
  - Expose port 3000.
  - Set `CMD ["npm", "start"]` or use Next.js standalone output.
- REQ-2.2: The Dockerfile must use multi-stage builds (build stage + runtime stage).
- REQ-2.3: The frontend must be configured to proxy `/api` requests to the backend via the `NEXT_PUBLIC_API_URL` build argument.

### REQ-3: Docker Compose Configuration

A single `docker compose up` must start the full stack.

- REQ-3.1: Update `deploy/compose.yml` to include:
  - `backend` service — builds from `deploy/backend.Dockerfile`, port 8000, mounts `storage/` as a volume, reads `.env`.
  - `frontend` service — builds from `deploy/frontend.Dockerfile`, port 3000, depends on `backend`.
  - `db` service — PostgreSQL 16, port 5432, volume for persistent data, healthcheck.
  - `caddy` service — Caddy 2 reverse proxy, port 80/443, routes to backend and frontend.
- REQ-3.2: All services must share a Docker network (`novelai-net`).
- REQ-3.3: The Compose file must define named volumes: `storage_data`, `db_data`.
- REQ-3.4: Service healthchecks must be defined for `backend` (HTTP `GET /api/public/catalog`) and `db` (pg_isready).
- REQ-3.5: The Compose file must respect the `.env` file in the `deploy/` directory.

### REQ-4: Development vs Production Modes

- REQ-4.1: A `deploy/compose.dev.yml` override must add hot-reload volumes for local development (mount backend source code, set `--reload` flag).
- REQ-4.2: The production Compose file must not bind-mount source code (only named volumes).
- REQ-4.3: Environment variable `COMPOSE_PROFILES` must allow starting only the database and backend for development (`--profile dev`).

### REQ-5: Documentation and Onboarding

- REQ-5.1: The `readme.md` must include a "Quick Start with Docker" section:
  - Prerequisites: Docker and Docker Compose installed.
  - Command: `cp deploy/.env.example .env && docker compose -f deploy/compose.yml up -d`.
  - How to access: frontend at `http://localhost:3000`, API at `http://localhost:8000/docs`.
  - How to create the first owner user: `docker compose exec backend novelai create-user admin admin@example.com`.
- REQ-5.2: The `.env.example` in `deploy/` must include all required environment variables with comments.

## Non-Goals

- This spec does not add Kubernetes manifests or Helm charts.
- This spec does not add a CI/CD pipeline for Docker builds (covered in `cicd-pipeline` spec).
- This spec does not add a cloud-specific deployment configuration (Terraform, etc.).
- This spec does not change the application code to support containerization (only Docker config).
