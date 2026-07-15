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

1. `/health/*` -> `backend:8000` (Health probe endpoints — liveness, readiness, admin)
2. `/api/admin/*` -> `backend:8000` (Admin management endpoints)
3. `/api/auth/*` -> `backend:8000` (Registration and authentication)
4. `/api/novels/*` -> `backend:8000` (Admin novel settings and imports)
5. `/novels/*` -> `backend:8000` (Novel assets and source actions)
6. `/api/public/*` -> `reader:8001` (Unauthenticated public reader endpoints)
7. Catch-all -> `frontend:3000` (Next.js server-side files)

Caddy terminates TLS, adds baseline security headers (`Strict-Transport-Security`, `X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy`), and enables compression. HSTS is only emitted when `SITE_DOMAIN` is set to a public HTTPS domain; localhost dev deployments remain usable without HSTS preloading.

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

The backend container runs an optional in-process activity worker when `JOB_WORKER_ENABLED=true`. Scheduled backup and maintenance tasks are managed by a lightweight asyncio loop when `BACKUP_ENABLED=true` or `MAINTENANCE_ENABLED=true`. The scheduler starts and stops with the application lifespan.

- **Backups** (`BACKUP_SCHEDULE_CRON`, default `0 2 * * *`): Creates local tar.gz backups of novel storage. Retention policy preserves the newest `BACKUP_MIN_SUCCESSFUL_TO_KEEP` (default 3) successful backups and deletes backups older than `BACKUP_MAX_AGE_DAYS` (default 30) beyond `BACKUP_RETENTION_COUNT` (default 5). Uses `InterProcessFileLock` to prevent concurrent backup runs.
- **Maintenance** (`MAINTENANCE_SCHEDULE_CRON`, default `0 3 * * *`): Cleans expired fetch cache entries, old pipeline events, terminal activity records, expired scheduler runtime states, and applies backup retention. Supports `MAINTENANCE_DRY_RUN=true` for staging verification. Uses allowlisted cleanup roots with path safety checks.

---

## Production Configuration Validation

When `ENV=production`, the backend and reader services run `assert_production_config()` at startup. Fatal configuration defects cause the process to exit before serving traffic. The validator checks:

- `ENV` is `production`
- `SESSION_SECRET_KEY` is strong and non-default (admin only)
- `OWNER_BOOTSTRAP_SECRET` is set and non-weak (admin only)
- `PUBLIC_FRONTEND_URL` is set and uses HTTPS (admin only)
- `WEB_CORS_ORIGINS` does not use `*` with credentials
- `WEB_RATE_LIMITER_BACKEND` is `redis` with `REDIS_URL` set (admin only)
- `STORAGE_BACKEND` is `filesystem` or `s3`; `S3_BUCKET` set when `s3`
- `S3_ACCESS_KEY_ID` and `S3_SECRET_ACCESS_KEY` set when `S3_ENDPOINT` is set (e.g. R2)
- `ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS`, `BACKUP_ENABLED` warnings

The reader service (`SERVICE_ROLE=reader`) skips session, owner, public URL, and rate-limiter checks since it has no auth or session middleware.

Validator output is redacted — no secrets, DB URLs, paths, or credentials are logged.

---

## Storage Backend: Cloudflare R2

Cloudflare R2 is an S3-compatible object storage service. The existing `S3Backend` works with R2 via the `endpoint_url` parameter. No code changes are needed — only configuration.

### R2 Configuration

Set the following in `.env` or `deploy/.env`:

```
STORAGE_BACKEND=s3
S3_BUCKET=<bucket-name>
S3_REGION=auto
S3_ENDPOINT=https://<ACCOUNT_ID>.r2.cloudflarestorage.com
S3_ACCESS_KEY_ID=<access-key-id>
S3_SECRET_ACCESS_KEY=<secret-access-key>
```

Create an R2 API token in the Cloudflare dashboard:
1. Go to **R2 > Manage R2 API Tokens > Create Account API Token**
2. Set permissions to **Object Read & Write**
3. Scope to the specific bucket
4. Copy the Access Key ID and Secret Access Key

### R2 vs Filesystem

| Aspect | Filesystem | R2 |
|---|---|---|
| Setup | None | Create bucket + API token |
| Scaling | Single server | Multi-region, CDN-backed |
| Cost | Disk only | Storage + operations |
| Backup | Tar.gz to local disk | Bucket lifecycle rules, cross-region replication |
| Backup note | `BACKUP_ENABLED=true` creates local tar.gz | Disable local backup; use R2 lifecycle rules or external snapshot |
| Latency | Local disk | Network round-trip (mitigated by CDN caching) |

### R2 Bucket Configuration

The `dokushodo` bucket has the following settings configured via Cloudflare API:

**CORS Policy:**
- Allows `GET`, `HEAD` from `https://localhost:3000` and `https://*.dokushodo.com`
- Exposes `Content-Length`, `Content-Type`, `ETag` headers
- Preflight cache: 1 hour

**Lifecycle Rules:**
| Rule | Prefix | Action | Age |
|---|---|---|---|
| Abort multipart uploads | (all) | Abort | 7 days |
| Expire integration test objects | `_integration_test` | Delete | 1 day |
| Expire healthcheck artifacts | `.healthcheck/` | Delete | 1 day |
| Transition cache to InfrequentAccess | `cache/` | Transition | 30 days |
| Delete cache objects | `cache/` | Delete | 90 days |

**Object Lock Rules:**
- `novels/` prefix: 30-day retention (prevents accidental deletion of canonical novel content within 30 days of upload)

**Storage Limit Monitoring:**
- `S3_STORAGE_LIMIT_GB=9.5` (default, under R2 free tier 10 GB)
- Admin health endpoint reports `storage_usage` probe with `used_bytes`, `limit_bytes`, `free_bytes`, `used_percent`
- Warning (degraded) at 90%, Critical (unhealthy) at 95%

---

## Deploy Smoke Checks

After `docker compose -f deploy/compose.yml up -d`, run the smoke script:

```powershell
.\deploy\scripts\deploy-smoke.ps1
```

The script checks:
1. Migration gate — `migrate` container exited 0
2. Admin liveness — `/health/live` returns 200
3. Admin readiness — `/health/ready` returns 200 (or 503 if DB unavailable)
4. Reader liveness — `/health/live` returns 200
5. Route boundary — `/api/public/catalog` returns 200 via reader
6. Admin health auth — `/api/admin/health` returns 401 without auth
7. Frontend responds on port 3000

---

## Rollback Procedure

### App Rollback (Redeploy Previous Image)

```powershell
# List available image tags in GHCR
docker images --format "{{.Repository}}:{{.Tag}}" | Where-Object { $_ -match "novel-ai" }

# Redeploy previous version via deploy workflow (manual dispatch)
# Go to: Actions > Deploy > Run workflow > version: <previous-tag>

# Or via SSH directly:
ssh deploy@host "cd /opt/novelai && docker compose up -d --no-deps backend reader"
```

### Database Migration Rollback

**Prefer forward-fix** unless data loss is acceptable. Alembic downgrade is destructive.

```powershell
# Check current migration head
docker compose run --rm migrate alembic current

# Downgrade one migration (CAUTION: may lose data)
docker compose run --rm migrate alembic downgrade -1

# Downgrade to specific revision
docker compose run --rm migrate alembic downgrade <revision>
```

Safety rules:
- Never downgrade a migration that has been deployed for more than 24 hours
- Always take a database snapshot before downgrade (`pg_dump`)
- Test downgrade on staging first

### Storage Rollback (R2)

R2 objects are immutable — overwritten versions are replaced. To restore from a backup prefix:

1. Identify the backup prefix (e.g. `backups/2026-07-14/`)
2. Use R2 or boto3 to copy objects back to the production prefix
3. Rebuild catalog projections: `POST /api/admin/catalog/rebuild`

### Full Disaster Recovery

1. **Storage first**: Restore R2 objects from backup prefix to production prefix
2. **Database second**: Restore PostgreSQL from `pg_dump` snapshot
3. **App third**: Redeploy known-good image tag
4. **Catalog fourth**: Trigger `POST /api/admin/catalog/rebuild` to rebuild SQL projections
5. **Verify**: Run smoke checks, verify health endpoints, spot-check novel content

---

## Secret Rotation

### SESSION_SECRET_KEY

Rotating the session secret invalidates all active sessions. Users must re-authenticate.

```powershell
# Generate new secret
python -c "import secrets; print(secrets.token_hex(32))"

# Update .env and deploy/.env, then restart
docker compose -f deploy/compose.yml up -d backend reader
```

### R2 API Token

1. Create new R2 API token in Cloudflare dashboard
2. Update `S3_ACCESS_KEY_ID` and `S3_SECRET_ACCESS_KEY` in `.env` / `deploy/.env`
3. Revoke old token in Cloudflare dashboard
4. Restart services: `docker compose -f deploy/compose.yml up -d backend reader`

### OWNER_BOOTSTRAP_SECRET

Only used for initial owner bootstrap. After the owner account exists, rotating this secret has no effect on existing accounts. To re-bootstrap in a fresh database:
1. Set new `OWNER_BOOTSTRAP_SECRET`
2. Start with empty database
3. Use the new secret at `/api/auth/bootstrap`
