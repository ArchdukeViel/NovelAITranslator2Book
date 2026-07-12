# Deployment Architecture

This document defines the container layout, reverse proxy routing, and server execution parameters.

---

## Container Topology

Docker Compose launches the following services as defined in `deploy/compose.yml`:

- `caddy`: Outer reverse proxy mapping ingress traffic. Handles TLS termination.
- `frontend`: Next.js Node app serving user-facing reader and admin dashboard (port 3000).
- `backend`: FastAPI monolith admin service handling auth, scraping, editing, and scheduler loops (port 8000).
- `reader`: FastAPI public-reader instance handling catalog browsing and chapter reading (port 8001).
- `migrate`: Short-lived job that runs database migrations before API services boot.

PostgreSQL is **not** provisioned by Compose. An external database instance must be provided via `DATABASE_URL`.

---

## Reverse Proxy Routing

Caddy routes ingress traffic to backend containers using the following ordered rules:

1. `/api/admin/*` -> `backend:8000` (Admin management endpoints)
2. `/api/auth/*` -> `backend:8000` (Registration and authentication)
3. `/api/novels/*` -> `backend:8000` (Admin novel settings and imports)
4. `/novels/*` -> `backend:8000` (Novel assets and source actions)
5. `/api/public/*` -> `reader:8001` (Unauthenticated public reader endpoints)
6. Catch-all -> `frontend:3000` (Next.js server-side files)

---

## Multi-Process split mode

The environment variable `DEPLOY_MODE` controls API service registration:

- `DEPLOY_MODE=monolith` (default): All routers run in a single process.
- `DEPLOY_MODE=split`: Exposes administrative routes on port 8000 and guest reader routes on port 8001.

---

## Database Dependency in Compose

The Docker Compose configuration does not provision a PostgreSQL service. An external database instance must be provided via the `DATABASE_URL` setting.
If running DB-backed actions, configure `DATABASE_URL` in the `.env` template before launching containers.

---

## Health and Readiness

Current health endpoints are static:

- `GET /health` and `GET /api/health` return `{"status": "ok"}`.
- `GET /api/admin/health` and `GET /api/public/health` return static responses.

Real liveness/readiness probes (database, storage, worker) are planned under Milestone 2a (DEBT-001).

---

## Worker and Maintenance

The backend container runs an optional in-process activity worker when `JOB_WORKER_ENABLED=true`. There is no dedicated worker, scheduler, or backup container in the current Compose topology. Scheduled backup creation, retention cleanup, and maintenance tasks are planned under Milestone 2c (DEBT-010, DEBT-025).
