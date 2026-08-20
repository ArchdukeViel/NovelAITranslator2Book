# Configuration

Configuration contract. Exact fields/defaults live in
`backend/src/novelai/config/settings.py`; examples live in `.env.example` and
`deploy/.env.example`. Do not duplicate every tuning default here.

## Loading

- Canonical environment selector: `ENV`; never introduce `APP_ENV`.
- Pydantic settings reads root `.env`; process environment overrides it.
- Compose reads `deploy/.env` and requires external `DATABASE_URL`.
- `MIGRATION_DATABASE_URL` optionally gives the one-shot Alembic service a
  separate elevated role; long-running processes continue using `DATABASE_URL`.
- Immutable remote releases combine the shared secret `.env` with a non-secret
  per-release `release.env` containing the full SHA and image digests.
- Real `.env*` files are untracked; only example templates are committed.
- Settings are read through `novelai.config.settings.settings`; no direct
  `os.environ` outside settings module.

## Python Interpreter

The canonical interpreter is the project virtualenv at `.venv\Scripts\python.exe`
(Python ≥ 3.14). Always invoke backend tooling through the wrappers in `tools/`
(`tools/pytest.ps1`, `tools/pyright.ps1`, `tools/ruff.ps1`); they resolve the
venv explicitly so a PATH-precedence mistake cannot poison results. Bare
`python` / `pytest` / `ruff` / `pyright` invocations outside the wrappers
fall through to the system interpreter. To rebuild the venv after schema or
dependency changes, follow the entry in [`OPERATIONS.md`](OPERATIONS.md).

## Minimum Local Configuration

```dotenv
ENV=development
DATABASE_URL=postgresql+psycopg://user:password@localhost:5432/novelai
SESSION_SECRET_KEY=<random>
OWNER_BOOTSTRAP_SECRET=<random>
PROVIDER_DEFAULT=gemini
AUTH_EMAIL_DELIVERY_MODE=noop
```

Generate secrets with `python -c "import secrets; print(secrets.token_hex(32))"`.

## Required Production Settings

| Area | Required contract |
|---|---|
| Runtime | `ENV=production`; `DEPLOY_MODE=monolith|split`. |
| Database | `DATABASE_URL` uses `postgresql+psycopg://`; TLS mode and deployment-wide connection budget are reviewed across backend, reader, worker, migrations, and operator reserve. |
| Sessions | Strong `SESSION_SECRET_KEY`, `OWNER_BOOTSTRAP_SECRET`, HTTPS cookie behavior. |
| Public URL | HTTPS `PUBLIC_FRONTEND_URL`; exact OAuth redirect when OAuth enabled. |
| Origins | Explicit `WEB_CORS_ORIGINS`, `CSRF_TRUSTED_ORIGINS`, `ALLOWED_HOSTS`; no wildcard with credentials. |
| Provider | Gemini key/model configuration; production never uses dummy provider. |
| Credentials | `PROVIDER_CREDENTIAL_ENCRYPTION_KEY` before storing provider keys. |
| Storage | `STORAGE_BACKEND=filesystem|s3`; complete S3/R2 endpoint/bucket/credentials for `s3`. |
| Distributed runtime | Redis URL and Redis rate limiter for split/multi-instance mode. |

## Private HTTPS Staging

The single-host staging release uses `ENV=staging`, `DB_CONNECTION_MODE=session`,
and `DB_SSL_MODE=require` with Supabase session-pooler URLs on port 5432. Set
`PUBLIC_FRONTEND_URL`, `WEB_CORS_ORIGINS`, `CSRF_TRUSTED_ORIGINS`, and
`ALLOWED_HOSTS` to the same `https://<tailscale-hostname>` origin. Set
`SITE_DOMAIN` to that hostname, keep `PUBLIC_BIND_ADDRESS=127.0.0.1`, and set
`SESSION_COOKIE_SECURE=true`. Tailscale Serve terminates HTTPS for the browser
and forwards to the loopback-only internal Caddy listener. Staging and
production always force secure session cookies, even when an old environment
file contains an explicit false override.

## Storage and Recovery Groups

Application S3/R2 uses `S3_*`. Independent object snapshots use `BACKUP_S3_*`
plus separate read-only `SNAPSHOT_SOURCE_S3_*` credentials. Application bucket,
backup bucket, and prefixes must not collapse into one unrestricted scope.

`BACKUP_ENABLED` controls object snapshots. `DATABASE_BACKUP_ENABLED` controls
encrypted PostgreSQL dumps and requires backup encryption key, independent DB
prefix, and PostgreSQL 18 client tools. `DATABASE_RESTORE_VERIFICATION_MAX_AGE_DAYS`
(default 32) sets max days since last successful restore before probe goes unhealthy.
Restore verification requires an explicit disposable target whose database name
contains `restore`.

Schedules use cron plus IANA timezone. Cross-instance jobs use configured lease
duration and renewal; do not tune lease below realistic job duration without tests.

## Runtime Groups

- `JOB_WORKER_ENABLED`: legacy/in-process activity runner switch. Production
  Compose keeps this `false` for web services; the dedicated `worker` service
  runs `novelaibook worker` against the database queue.
- `DB_CONNECTION_MODE=direct|session|transaction`: selects the PostgreSQL
  connection topology. `transaction` uses transaction-pooler-safe
  `NullPool`; `direct` and `session` use the configured SQLAlchemy pool.
- `DB_POOL_SIZE`, `DB_MAX_OVERFLOW`, `DB_POOL_TIMEOUT_SECONDS`, and
  `DB_CONNECTION_BUDGET`: bound per-process pool behavior and declare the
  deployment-wide connection budget. Review
  `processes * (DB_POOL_SIZE + DB_MAX_OVERFLOW)` across backend, reader,
  worker, migration, and operator processes, while reserving capacity for
  readiness and emergency access. The Phase 6 local burst showed that a
  nominal per-process setting is not production pooler evidence; verify the
  aggregate budget against the target pooler before launch. The current
  production validator checks the two web pools; worker, migration, and
  operator-process capacity still requires explicit deployment review.
- `WEB_RATE_LIMITER_BACKEND=memory|redis`: memory only for single instance.
- `REDIS_URL`: shared rate limiting and distributed queue where enabled.
- `TRUSTED_PROXY_CIDRS`: exact reverse-proxy CIDRs allowed to supply
  `X-Forwarded-For`; leave empty when clients connect directly. Do not trust
  forwarded headers from arbitrary public clients.
- `TRANSLATION_*`: chunking, concurrency, attempts, scheduler/model policy,
  provider deadline, and bounded retry backoff.
- `ACTIVITY_HISTORY_MAX_ENTRIES`, `ACTIVITY_METADATA_MAX_BYTES`, and
  `ACTIVITY_RETRY_HISTORY_MAX_ENTRIES`: durable queue history and metadata
  bounds. The queue is database-backed in production; the legacy JSON file is
  imported only as a compatibility path.
- `PROVIDER_GEMINI_*`: key, default model, fallback models.
- `GEMINI_RPM_LIMIT`, `GEMINI_TPM_LIMIT`, `GEMINI_RPD_LIMIT`, and
  `GEMINI_CONCURRENCY_LIMIT`: owner-key request/token/day and in-flight bounds.
- `CONTRIBUTOR_RPM_LIMIT`, `CONTRIBUTOR_TPM_LIMIT`, `CONTRIBUTOR_RPD_LIMIT`,
  and `CONTRIBUTOR_CONCURRENCY_LIMIT`: per-contributor credential bounds.
- `PROVIDER_RESERVATION_TTL_SECONDS`: expiry for abandoned provider admission
  reservations so crashed workers do not hold concurrency forever.
- `TRANSLATION_CACHE_*`: exact cache enablement, TTL, size.
- `PUBLIC_RANKING_CACHE_*`: successful ranking cache enablement, TTL, and
  bounded process-local entry count.
- `PUBLIC_PROJECTION_CACHE_*`: safe catalog/summary/chapter-projection cache
  enablement, TTL, and bounded process-local entry count.
- `MAINTENANCE_*`: schedule and dry-run controls.
- `HEALTH_*`: bounded probe timeout, readiness TTL, and disk thresholds.
- `ANALYTICS_ASYNC_QUEUE_SIZE`: bounded process-local analytics writer
  capacity and explicit drop-on-full backpressure.
- `OPERATOR_ALERT_*`: alert enable, email, failure threshold, cooldown, stale backup hours.
- `PRODUCTION_BASE_URL`: GitHub Actions secret (not a process env var) feeding the
  best-effort five-minute external HTTPS monitor. Set in GitHub secrets, never
  in `.env` files.
- `GITGUARDIAN_API_KEY`: GitHub Actions secret (not a process env var) supplying
  `.github/workflows/gitguardian.yaml`. Set in GitHub secrets, never in `.env` files.

Use source defaults unless measured behavior justifies change.

### Public ranking cache

`PUBLIC_RANKING_CACHE_ENABLED` defaults to `true`. The default
`PUBLIC_RANKING_CACHE_TTL_SECONDS` is `60` and may be set from `1` through
`300`; `PUBLIC_RANKING_CACHE_MAX_ENTRIES` defaults to `64` and may be set from
`1` through `1024`. Each backend/reader process owns its bounded TTL/LRU cache;
the settings do not create a shared Redis cache.

Only successful, non-empty ranking responses are cached. Disabled analytics,
no retained events, and unavailable responses are never cached. Keys include
the ranking period, public-projection schema/update version, and requested
limit, so publication or projection updates naturally select a new entry.
The cache is an origin optimization, not a popularity source or a data
durability mechanism. Monitor `novelai_public_ranking_cache_hits_total`,
`novelai_public_ranking_cache_misses_total`, and
`novelai_public_ranking_cache_entries`; measure cross-worker duplication before
introducing a shared cache.

### Public projection cache

`PUBLIC_PROJECTION_CACHE_ENABLED` defaults to `true`.
`PUBLIC_PROJECTION_CACHE_TTL_SECONDS` defaults to `30` and accepts
`1..300`; `PUBLIC_PROJECTION_CACHE_MAX_ENTRIES` defaults to `256` and
accepts `1..2048`. Each process owns a bounded TTL/LRU cache for
non-personalized, JSON-safe catalog pages, novel summaries, and chapter
metadata. Search query text, user identity, progress, history, cookies, and
raw chapter text are never stored in this cache.

Catalog keys include the current published projection timestamp. Novel-summary
and chapter-context keys include the current novel timestamp. Publish,
unpublish/reconciliation, and approved takedown review invalidate the
projection cache. The cache is an optimization only; a miss recomputes from
the database projection and does not restore request-time object-storage
enumeration. Monitor
`novelai_public_projection_cache_hits_total`,
`novelai_public_projection_cache_misses_total`,
`novelai_public_projection_cache_entries`, and
`novelai_public_projection_cache_invalidations_total` from the owning
operator metrics process.

### Readiness cache and analytics writer

`HEALTH_CACHE_TTL_SECONDS` defaults to `5` seconds and accepts `0..300`;
`0` disables result reuse while retaining one in-flight refresh. Public
`/health/ready` is process-safe and redacted: it checks database, lightweight
storage reachability, worker, and disk. Full storage write/read/delete and S3
usage diagnostics are owner-only or scheduled checks. `/health/live` remains
process-only and does not use the cache.

`ANALYTICS_ASYNC_QUEUE_SIZE` defaults to `1000` and accepts `1..10000`.
Public analytics events are sanitized before admission to a bounded
process-local worker queue. `recorded` means accepted by the queue;
`dropped` means the queue was full or unavailable. Queue drops and worker
failures are observable through
`novelai_analytics_writer_accepted_total`,
`novelai_analytics_writer_dropped_total`,
`novelai_analytics_writer_processed_total`,
`novelai_analytics_writer_failures_total`, and
`novelai_analytics_writer_queue_depth`. The queue never stores raw IP
addresses, prompts, authorization headers, or unsanitized metadata.

### Frontend server prefetch

- `READER_API_URL`: internal reader-service URL used only by Next.js server-side
  public catalog and ranking prefetch. The split Compose default is
  `http://reader:8001`; it is not exposed to the browser.
- `BACKEND_API_URL`: backend/admin URL retained for backend-facing rewrites and
  other existing server-side use; it does not serve public reader routes in
  split mode.
- `BACKEND_API_HOST`: `Host` header used for internal server-side public reads.
  It must match the configured `ALLOWED_HOSTS`/`SITE_DOMAIN` contract.

Keep these values aligned with the internal service topology. A wrong boundary
can make server prefetch return a truthful fallback while silently restoring a
browser request waterfall.

## Auth and Email

Google OAuth requires client ID, client secret, and exact redirect URI. One
deployment uses one configured redirect URI; provider client may allow several.
Public OAuth/password registration creates users only.

Email defaults to `AUTH_EMAIL_DELIVERY_MODE=noop`. SMTP requires host, port,
credentials, sender, TLS/SSL choice, tested domain, operator recipient where
alerts are enabled, and acceptance gates in `WORK.md`.

## Profiles

| Profile | Key choices |
|---|---|
| Local | `ENV=development`, memory limiter allowed, worker optional, noop email. |
| Preview | HTTPS session, exact domains/OAuth, development-only R2; worker/scheduler/backups/SMTP disabled on sleeping free host. |
| Production | `ENV=production`, always-on backend, Redis, private R2 scopes, backups, monitoring, tested alerts. |

## Request Body Limits

App bounds every API request body, validates JSON mutation content types, and
emits route-specific 413/415 responses. Caddy outer guard
(`request_body { max_size 34MiB }`) emits 413 before routing.

| Setting | Group | Max | Accepts |
|---|---|---|---|
| `WEB_MAX_AUTH_BODY_BYTES` | Auth (login, register) | 64 KiB | `application/json`, `application/*+json` |
| `WEB_MAX_JSON_BODY_BYTES` | General JSON API | 1 MiB | `application/json`, `application/*+json` |
| `ANALYTICS_INGEST_MAX_BODY_BYTES` | Analytics events | 32 KiB (configurable) | `application/json` |
| `WEB_MAX_DOCUMENT_BODY_BYTES` | Reserved doc upload | 32 MiB | – (no route) |

App enforcement authoritative for direct Uvicorn access.

## Security

Never print, hash, paste, or commit secret values, DB URLs, provider keys, SMTP
passwords, storage credentials, or encryption keys. Presence checks report only
`present=true|false`. Rotate compromised secrets immediately. Session-secret
rotation logs out users; credential-encryption rotation requires re-encryption.

## Validation

- Production startup runs fail-closed configuration validation.
- Apply migrations from repository root: `alembic -c alembic.ini upgrade head`.
- Verify OAuth URI exactly, TLS DB connection, explicit origins/hosts, Redis
  sharing, R2 scope separation, and restore target isolation.
- When adding a setting, update `settings.py`, example env files, deployment
  wiring, focused tests, and this file only when operator understanding changes.

## Contributor Credentials and Public Rankings

Contributor credentials are enabled. Startup and storage fail closed when the
encryption key or required deployment controls are missing:

| Setting | Purpose | Default |
|---|---|---:|
| `CONTRIBUTOR_CREDENTIALS_ENABLED` | Enable user-owned Gemini credential intake and contributor jobs | `true` |
| `CONTRIBUTOR_CONSENT_VERSION` | Consent text/version required on every replacement | `2026-08-19` |
| `CONTRIBUTOR_MAX_ACTIVE_PER_USER` | Maximum credentials per user in v1 | `1` |
| `CONTRIBUTOR_RPM_LIMIT` | Per-credential requests per minute | `15` |
| `CONTRIBUTOR_TPM_LIMIT` | Per-credential tokens per minute | `250000` |
| `CONTRIBUTOR_RPD_LIMIT` | Per-credential requests per day | `500` |
| `CONTRIBUTOR_CONCURRENCY_LIMIT` | Per-credential in-flight provider calls | `2` |
| `CONTRIBUTOR_USAGE_RETENTION_DAYS` | Contributor ledger retention window | `365` |

`PROVIDER_CREDENTIAL_ENCRYPTION_KEY` is required before a credential can be
stored. It is also the encryption boundary for owner-managed provider keys,
but contributor rows remain isolated by domain, owner, provider, and explicit
contribution mode. Rotate the key by decrypting and re-encrypting all stored
credentials in a controlled maintenance window, verify fingerprints before
removing the old key, and treat an unavailable old key as a fail-closed
incident. Never put a raw key in `.env` examples, logs, diagnostics, or API
responses.

Public rankings use `GET /api/public/rankings` with `period=daily|weekly|monthly`
and a bounded `limit`. Analytics retention is the truth boundary; there is no
All Time setting. Anonymous ranking identity uses a signed first-party opaque
cookie and stores only its digest, never an IP address.

### Translation worker and cache bounds

Long translation requests return an activity id immediately. In Compose, web
services keep `JOB_WORKER_ENABLED=false`; the `worker` service runs
`novelaibook worker` and claims the database-backed `activity_records` queue.
`ACTIVITY_HISTORY_MAX_ENTRIES` bounds list/history reads,
`ACTIVITY_METADATA_MAX_BYTES` bounds one progress envelope, and
`ACTIVITY_RETRY_HISTORY_MAX_ENTRIES` bounds retained retry snapshots.

The file-backed translation cache maintains a SQLite WAL metadata index at
`translation_cache_index.sqlite3`. A one-time backfill may scan existing JSON
entries; subsequent get, invalidate, statistics, and eviction operations use
indexed rows. Do not delete the sidecar while the cache is live; rebuild it
only through a controlled cache maintenance window.
