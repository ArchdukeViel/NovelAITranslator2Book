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
6. `/health/*` -> `backend:8000` (Health probe endpoints — liveness, readiness, admin)
7. Catch-all -> `frontend:3000` (Next.js server-side files)

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

Health endpoints perform real dependency probes (M2a, DEBT-001 resolved):

- `GET /health/live`: Process-only liveness check. Unauthenticated, fast, no DB/storage/worker calls. Returns `200` with `{"status": "ok", "service": "novelai", "timestamp": "..."}`.
- `GET /health/ready`: Public-safe readiness check. Probes database (`SELECT 1`), storage (write+delete temp file in `.healthcheck/`), worker (`activity_runner.status()`), and disk space. Returns `200` if healthy/degraded, `503` if any probe is unhealthy. Never exposes credentials, paths, hostnames, or stack traces.
- `GET /api/admin/health`: Owner-only detailed diagnostics (`require_role("owner")`). Returns probe status, latency, safe messages, and checked timestamp. Still redacted — no raw exceptions, stack traces, or secrets.

Probe states: `healthy`, `degraded`, `unhealthy`. Each probe is bounded by `HEALTH_PROBE_TIMEOUT_MS` (default 1000ms) and the total request by `HEALTH_TOTAL_TIMEOUT_MS` (default 3000ms). A failed probe does not stop unrelated probes.

---

## Worker and Maintenance

The backend container runs an optional in-process activity worker when `JOB_WORKER_ENABLED=true`. Scheduled backup and maintenance tasks are managed by APScheduler (`AsyncIOScheduler`) when `BACKUP_ENABLED=true` or `MAINTENANCE_ENABLED=true`. The scheduler starts and stops with the application lifespan.

- **Backups** (`BACKUP_SCHEDULE_CRON`, default `0 2 * * *`): Creates local tar.gz backups of novel storage. Retention policy preserves the newest `BACKUP_MIN_SUCCESSFUL_TO_KEEP` (default 3) successful backups and deletes backups older than `BACKUP_MAX_AGE_DAYS` (default 30) beyond `BACKUP_RETENTION_COUNT` (default 5). Uses `InterProcessFileLock` to prevent concurrent backup runs.
- **Maintenance** (`MAINTENANCE_SCHEDULE_CRON`, default `0 3 * * *`): Cleans expired fetch cache entries, old pipeline events, terminal activity records, expired scheduler runtime states, and applies backup retention. Supports `MAINTENANCE_DRY_RUN=true` for staging verification. Uses allowlisted cleanup roots with path safety checks.
