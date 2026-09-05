---
title: Configuration
document_role: reference
authority: canonical
scope: configuration keys precedence validation secret classification and failure behavior
audience:
  - agents
  - developers
  - operators
update_triggers:
  - configuration key changes
  - precedence changes
  - secret classification changes
owned_concerns:
  - configuration-runtime-settings
---
# Configuration

This document owns configuration meaning, precedence, validation, and secret classification. It does not own architecture decisions, release procedures, runtime evidence, or secret values.

Current state: settings are loaded through the project configuration module, real environment files remain local and untracked, and examples expose only safe defaults or placeholders.

Related contracts: [`ARCHITECTURE.md`](ARCHITECTURE.md), [`DEPLOYMENT.md`](DEPLOYMENT.md), [`STORAGE.md`](STORAGE.md), and [`OPERATIONS.md`](OPERATIONS.md).

Maintenance: update this reference when a setting, bound, precedence rule, or failure behavior changes; record environment-specific verification in [`EVIDENCE.md`](EVIDENCE.md).

Configuration contract. Exact fields/defaults live in
`backend/src/novelai/config/settings.py`; examples live in `.env.example` and
`deploy/.env.example`. Do not duplicate every tuning default here.

## Loading

- Canonical environment selector: `ENV`; never introduce `APP_ENV`.
- Pydantic settings reads root `.env`; process environment overrides it.
- Compose reads `deploy/.env` and supports co-located native PostgreSQL 17 (`POSTGRES_*` settings) or an external `DATABASE_URL`.
- `MIGRATION_DATABASE_URL` optionally gives the one-shot Alembic service a
  separate elevated role; long-running processes continue using `DATABASE_URL`.
- Immutable remote releases combine the shared secret `.env` with a non-secret
  per-release `release.env` containing the full SHA and image digests.
- Real `.env*` files are untracked; only example templates are committed.
- Settings are read through `novelai.config.settings.settings`; no direct
  `os.environ` outside settings module.

## Environment counterpart policy

Every active `.env` assignment must be represented by the matching example
template, but the real value must not be copied into that template. Secret,
external, and operator values intentionally differ from examples; examples use
safe defaults or clearly marked placeholders. The 2026-08-22 audit found seven
files and synchronized the active/template key sets exactly for all three active
application pairs. The root and deployment templates also share one ordered
129-key contract; the frontend pair has four keys. The current counterparts are:

| Active file | Counterpart | Special handling |
|---|---|---|
| `.env` | `.env.example` | Local backend/runtime profile; real credentials stay local and redacted |
| `deploy/.env` | `deploy/.env.example` | Docker Compose development profile; `RUNTIME_HOST_DIR=../data/runtime` is local-only |
| `deploy/.env.production` | `deploy/.env.production.example` | Runtime file is not present locally; the production template remains the source for operator provisioning |
| `frontend/.env.local` | `frontend/.env.example` | Local Next.js overlay; same-origin/public API defaults plus local backend/reader URLs |
| root `.env.local` | No application counterpart | Runtime file is not present locally; do not create it for backend configuration |

### Value ownership

| Ownership | Variables | Source and rule |
|---|---|---|
| Locally generated or derived | `SESSION_SECRET_KEY`, `OWNER_BOOTSTRAP_SECRET`, `PROVIDER_CREDENTIAL_ENCRYPTION_KEY`, `DATABASE_BACKUP_ENCRYPTION_KEY` | Generate with a cryptographically secure local tool such as `secrets.token_hex`; store and rotate through the operator's secret store, never derive from a URL or password |
| Build/runtime generated | `VERSION`, local `RUNTIME_HOST_DIR`, local Compose `REDIS_URL`, `GOOGLE_OAUTH_REDIRECT_URI` | Git/CI, Compose defaults, or derivation from the confirmed public URL; the operator still reviews the result before deployment |
| External service values | `DATABASE_URL`, `MIGRATION_DATABASE_URL`, `DATABASE_BACKUP_URL`, `DATABASE_RESTORE_TARGET_URL`, `R2_GATEWAY_URL`, `R2_GATEWAY_CLIENT_ID`, `R2_GATEWAY_CLIENT_SECRET`, `R2_RECOVERY_GATEWAY_URL`, `R2_RECOVERY_CLIENT_ID`, `R2_RECOVERY_CLIENT_SECRET`, `PROVIDER_GEMINI_API_KEY`, `GOOGLE_OAUTH_CLIENT_ID`, `GOOGLE_OAUTH_CLIENT_SECRET`, `SMTP_*` | Issued by Supabase/PostgreSQL, the private Cloudflare Worker/Access boundary, Google AI/OAuth, or the selected SMTP provider; never fabricate or reuse across scopes |
| Operator decisions | `ENV`, `DEPLOY_MODE`, domains/origins/hosts, `R2_BACKUP_ENABLED`, backup/restore/maintenance flags, quotas, schedules, pool sizes, `PROVIDER_DEFAULT`, model, target language, and retention values including `BACKUP_SAFETY_GRACE_DAYS` | Chosen and approved for the target environment; safe defaults may be supplied by the examples, but production activation is an operator decision |

Optional external/operator values may remain absent. SMTP settings and the
production migration URL remain unset where no approved source value exists.
Gateway URLs and Access identities are supplied only through ignored runtime
environment files or an approved secret store. Example templates and frontend
environment files remain secret-free, and `R2_BACKUP_ENABLED` remains false
until recovery is explicitly authorized and tested.

List-valued `NoDecode` settings use comma-separated values, not JSON-array
syntax. For example, use `ALLOWED_HOSTS=localhost,127.0.0.1` and leave an
empty list as a blank assignment; the same rule applies to
`WEB_CORS_ORIGINS`, `CSRF_TRUSTED_ORIGINS`, and `TRUSTED_PROXY_CIDRS`.

## Python Interpreter

The canonical interpreter is the project virtualenv at `.venv\Scripts\python.exe`
(Python ≥ 3.14). Always invoke backend tooling through the wrappers in `tools/`
(`tools/pytest.ps1`, `tools/pyright.ps1`, `tools/ruff.ps1`); they resolve the
venv explicitly so a PATH-precedence mistake cannot poison results. Bare
`python` / `pytest` / `ruff` / `pyright` invocations outside the wrappers
fall through to the system interpreter. To rebuild the venv after schema or
dependency changes, follow the entry in [`OPERATIONS.md`](OPERATIONS.md).

## Dependency and Runtime Pins

The root `pyproject.toml` and `uv.lock` are authoritative for Python
dependencies. `requirements.lock` and `requirements-dev.lock` are generated
deployment and CI artifacts and must be regenerated with
`deploy/update-lockfiles.ps1`; never edit either generated lock manually.
Frontend and Worker dependencies are independently locked by their respective
`package-lock.json` files. Local, CI, and Docker JavaScript runtime is pinned
to Node.js 26.8.1, and Python CI/runtime images are pinned to Python 3.14.7.

At the current candidate, TypeScript 6.0.3 and ESLint 9.39.5 remain explicit
compatibility holds because the installed TypeScript-ESLint and import/React
plugin peer ranges do not admit their current major releases. They are not
reported as latest until those peer constraints are resolved with a focused
migration. The R2 Worker safety script is `npm run deploy:dry-run`; it always
targets the non-production `test` environment and must not default to a
production binding.

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
| Storage | R2-only: `R2_BUCKET=dokushodo`, private HTTPS `R2_GATEWAY_URL`, application Access identity, fixed `R2_BACKUP_BUCKET=dokushodo-backup`, and separate recovery gateway identity; no filesystem content backend. |
| Distributed runtime | Redis URL and Redis rate limiter for split/multi-instance mode. |

## Cloudflare HTTPS Staging

The single-host staging release uses `ENV=staging`, `DB_CONNECTION_MODE=session`,
and `DB_SSL_MODE=require` with Supabase session-pooler URLs on port 5432. Set
`PUBLIC_FRONTEND_URL`, `WEB_CORS_ORIGINS`, `CSRF_TRUSTED_ORIGINS`, and
`ALLOWED_HOSTS` to the same approved Cloudflare HTTPS origin. Set `SITE_DOMAIN`
to that hostname, keep `PUBLIC_BIND_ADDRESS=127.0.0.1`, and set
`SESSION_COOKIE_SECURE=true`. Cloudflare Tunnel terminates HTTPS for the
browser and forwards to the loopback-only internal Caddy listener. Staging and
production always force secure session cookies, even when an old environment
file contains an explicit false override.

## Current development HTTPS origin

The temporary Windows/Docker development profile uses
`https://dev.dokushodo.online` for `PUBLIC_FRONTEND_URL`,
`WEB_CORS_ORIGINS`, `CSRF_TRUSTED_ORIGINS`, `ALLOWED_HOSTS`, and `SITE_DOMAIN`.
Cloudflare terminates the public HTTPS connection through the remotely managed
`dokushodo-dev` Tunnel and forwards the request to the internal Caddy service
over `http://caddy:80`; Caddy remains the only host-published application
entry point. The connector token is a local Compose secret at
`deploy/.cloudflared/dokushodo-dev.token`, which is ignored and must never be
added to tracked or example configuration.

This development origin is not the production apex or `www` topology. Keep
the worker/full queue stopped and use an explicit Compose service target when
restarting the tunnel; external development HTTP success does not establish
production capacity, recovery, monitoring, or launch acceptance.
The reader-capacity follow-up uses this Cloudflare origin as its selected
`cloudflare_tunnel` SLO topology; no private-peer network setting is required.

## Storage and Recovery Groups

Application R2 uses the private `R2_GATEWAY_*` boundary and the fixed bucket
`dokushodo`. Independent object snapshots use the separate
`R2_RECOVERY_GATEWAY_*` boundary and fixed bucket `dokushodo-backup`.
Application and recovery identities must not collapse into one unrestricted
scope. Application keys begin directly with `novels/`; there is no key-prefix
setting.

Required R2 settings:

| Setting | Meaning |
|---|---|
| `R2_BUCKET` | Application bucket; production must be `dokushodo`. |
| `R2_GATEWAY_URL` | Private versioned Worker HTTPS endpoint for application R2 operations. |
| `R2_GATEWAY_CLIENT_ID` / `R2_GATEWAY_CLIENT_SECRET` | Application Cloudflare Access service identity. |
| `R2_BACKUP_BUCKET` | Independent recovery bucket; production must be `dokushodo-backup`. |
| `R2_RECOVERY_GATEWAY_URL` | Private versioned Worker HTTPS endpoint for recovery operations. |
| `R2_RECOVERY_CLIENT_ID` / `R2_RECOVERY_CLIENT_SECRET` | Separate recovery Cloudflare Access service identity. |
| `R2_BACKUP_PREFIX` | Fixed snapshot namespace under the recovery bucket. |
| `RUNTIME_DIR` | Disposable local cache/checkpoint/log/scratch root. It is not a content library. |
| `RUNTIME_HOST_DIR` | Compose-only host directory mounted to `RUNTIME_DIR`; use `../data/runtime` for local Windows Compose and a provisioned writable path such as `/opt/novelai/shared/data/runtime` in production. It must contain only disposable runtime state. |

`R2_*` credentials are never returned by diagnostics. Rotate application,
source-read, and backup-write tokens independently and verify access scopes
against an isolated bucket before a production cutover.

### Isolated R2 integration tests

The opt-in R2 Worker integration suite uses `TEST_R2_GATEWAY_URL`, the exact
`TEST_R2_BUCKET=test-dokushodo` and `TEST_R2_BACKUP_BUCKET=test-dokushodo-backup`
classes, and dedicated application/recovery Access identities. Generated
objects use a unique prefix and must be removed and confirmed absent by a
final paginated sweep.

The backup and restore integrations are separate gates. They use the exact test
bucket classes with `TEST_R2_RECOVERY_CLIENT_ID` and
`TEST_R2_RECOVERY_CLIENT_SECRET`; the recovery identity may read the app class
only for a verified restore flow and writes only to the backup or isolated
restore namespace. Do not reuse production identities for that test. Keep all
test values in ignored local environment files or an approved secret store; the
committed examples contain placeholders only.

The managed database recovery workflow assigns each run a unique
`database/recovery-<run_id>` prefix. The `database/` namespace is required by
the R2 gateway for database-backup writes, reads, listing, and cleanup; a
root-level `recovery-` prefix is rejected before R2 is called.

`BACKUP_ENABLED` controls object snapshots. `BACKUP_RETENTION_COUNT`,
`BACKUP_MIN_SUCCESSFUL_TO_KEEP`, and `BACKUP_MAX_AGE_DAYS` bound committed
snapshot retention; `BACKUP_SAFETY_GRACE_DAYS` protects unreferenced shared R2
objects from premature collection. `DATABASE_BACKUP_ENABLED` controls encrypted
PostgreSQL dumps and requires a dedicated `DATABASE_BACKUP_URL` role that can
dump RLS-protected application tables, a backup encryption key, an independent
DB prefix, and PostgreSQL 18 client tools. Do not reuse the runtime
`DATABASE_URL`; it is intentionally not allowed to bypass RLS.
`DATABASE_RESTORE_VERIFICATION_MAX_AGE_DAYS`
(default 32) sets max days since last successful restore before probe goes unhealthy.
Restore verification requires an explicit disposable target whose database name
contains `restore`.

Schedules use cron plus IANA timezone. Cross-instance jobs use configured lease
duration and renewal; do not tune lease below realistic job duration without tests.

## Runtime Groups

- `JOB_WORKER_ENABLED`: legacy/in-process activity runner switch. Production
  Compose keeps this `false` for both web services; the dedicated `worker`
  service runs `novelaibook worker` against the database queue. The canonical
  Compose file explicitly overrides this value on `backend` and `reader`, even
  if a shared `deploy/.env` contains a monolith-era value. Do not rely on
  environment inheritance when auditing the executor topology.
- `DB_CONNECTION_MODE=direct|session|transaction`: selects the application-side
  SQLAlchemy pool behavior. `transaction` uses transaction-pooler-safe
  `NullPool`; `direct` and `session` use the configured SQLAlchemy pool. The
  actual Supabase endpoint is selected by `DATABASE_URL`, not this setting.
  The current runtime uses a Supabase Session Pooler endpoint on port `5432`
  while retaining `DB_CONNECTION_MODE=direct` for its application pool
  behavior; keep those two concepts distinct during egress investigations.
- `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB`: credentials for co-located PostgreSQL 17 in `deploy/compose.yml`.
- `POSTGRES_BIND_ADDRESS`: host interface binding for PostgreSQL port (defaults to `127.0.0.1` for secure desktop GUI SSH tunneling).
- `POSTGRES_PORT`: host port mapping for PostgreSQL (defaults to `5432`).
- `DB_POOL_SIZE` and `DB_MAX_OVERFLOW`: bound each direct/session process pool. Defaults are tuned to `DB_POOL_SIZE=5` and `DB_MAX_OVERFLOW=5` (10 max connections per process). Across the three split Compose processes (`backend`, `reader`, `worker`), this consumes 30 connections plus 2 reserved (`DB_CONNECTION_RESERVE=2`), fitting cleanly within `DB_CONNECTION_BUDGET=32`. For dedicated PostgreSQL 17 deployments, pool size can be scaled up proportionately with budget.
- `DB_POOL_PROCESS_COUNT`: count every long-lived process or replica that can
  own one of those pools. The current split Compose topology defaults to three
  (backend, reader, and worker); update it whenever replicas or topology
  change.
- `DB_CONNECTION_RESERVE`: reserve connections for one-shot migration,
  readiness, and emergency operator access outside the long-lived pool
  ceiling.
- `DB_CONNECTION_BUDGET`: deployment-wide database pool ceiling (e.g. `32` for managed cloud poolers, or up to `100` for native PostgreSQL 17). Startup checks that
  `DB_POOL_PROCESS_COUNT * (DB_POOL_SIZE + DB_MAX_OVERFLOW) + DB_CONNECTION_RESERVE <= DB_CONNECTION_BUDGET`.
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
  `GEMINI_CONCURRENCY_LIMIT`: owner-key request/minute, token/minute,
  request/day, and in-flight bounds.
- `CONTRIBUTOR_RPM_LIMIT`, `CONTRIBUTOR_TPM_LIMIT`, `CONTRIBUTOR_RPD_LIMIT`,
  and `CONTRIBUTOR_CONCURRENCY_LIMIT`: local per-contributor credential
  admission bounds.
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
  `.github/workflows/secret-scan.yml`. Set in GitHub secrets, never in `.env` files.

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
non-personalized, JSON-safe catalog pages, novel summaries, chapter
reader responses (when `version_id is None`), and warm search query results. User identity, progress, history, cookies, and raw translation chunks are never stored in this cache.

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
R2 reachability, worker, and disk. Full storage write/read/delete and R2
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
alerts are enabled, and acceptance gates in `STATUS.md`. With `noop`, signup and
session testing remain available, but verification and password-reset emails
are not delivered and the account remains unverified until delivery is
configured and the verification flow is completed.

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

## Unified Provider Credentials and Public Rankings

Owner-managed credentials and user contributions share the encrypted
`provider_credentials` registry. The old contributor-only table is not part of
the current schema. Startup never imports `PROVIDER_GEMINI_API_KEY`; an owner
must explicitly invoke the protected environment-import operation, which
validates the key before owner-scoped translation may use it:

| Setting | Purpose | Default |
|---|---|---:|
| `CONTRIBUTOR_CREDENTIALS_ENABLED` | Enable user contribution intake and contributor-pool jobs | `true` |
| `CONTRIBUTOR_CONSENT_VERSION` | Consent text/version required on every replacement | `2026-08-19` |
| `CONTRIBUTOR_MAX_ACTIVE_PER_USER` | Maximum credentials per user in v1 | `1` |
| `CONTRIBUTOR_RPM_LIMIT` | Per-credential requests per minute | `15` |
| `CONTRIBUTOR_TPM_LIMIT` | Per-credential tokens per minute | `250000` |
| `CONTRIBUTOR_RPD_LIMIT` | Per-credential requests per day | `500` |
| `CONTRIBUTOR_CONCURRENCY_LIMIT` | Per-credential in-flight provider calls | `2` |
| `CONTRIBUTOR_USAGE_RETENTION_DAYS` | Contributor ledger retention window | `365` |

These values are local safety ceilings, not a claim that each key
has an independent Gemini quota. Google limits vary by model and usage tier,
are generally applied per project, and must be checked in [Google AI
Studio](https://ai.google.dev/gemini-api/docs/rate-limits). The repository has
no separate TPD setting because TPD is model-dependent; an operator must not
derive one from `CONTRIBUTOR_RPD_LIMIT` or `CONTRIBUTOR_TPM_LIMIT`.

Credential replacement/validation is additionally limited to three attempts
per authenticated user per minute by the browser/API security limiter. This
protects the provider validation endpoint from repeated paid or quota-consuming
checks; it is separate from the per-credential Gemini request budgets.

`PROVIDER_CREDENTIAL_ENCRYPTION_KEY` is required before any credential can be
stored. It encrypts both owner and user rows; source, authenticated owner,
owner-job eligibility, contributor-pool eligibility, consent, and validation
state provide the isolation boundary. Rotate the key by decrypting and
re-encrypting all rows in a controlled maintenance window, verify fingerprints
before removing the old key, and treat an unavailable old key as a fail-closed
incident. Never put a raw key in `.env` examples, logs, diagnostics, or API
responses. Apply the unified-registry migration before enabling the routes.

Public rankings use `GET /api/public/rankings` with `period=daily|weekly|monthly`
and a bounded `limit`. Analytics retention is the truth boundary; there is no
All Time setting. Anonymous ranking identity uses a signed first-party opaque
cookie and stores only its digest, never an IP address.

### Translation worker and cache bounds

Long translation requests return an activity id immediately. In Compose, both
web services explicitly set `JOB_WORKER_ENABLED=false`; the `worker` service
runs `novelaibook worker` and claims the database-backed `activity_records`
queue. Verify the effective container environment after changing Compose or
runtime environment files; a second web-process runner can create duplicate
provider work and competing leases.
`ACTIVITY_HISTORY_MAX_ENTRIES` bounds list/history reads,
`ACTIVITY_METADATA_MAX_BYTES` bounds one progress envelope, and
`ACTIVITY_RETRY_HISTORY_MAX_ENTRIES` bounds retained retry snapshots.

The local runtime translation cache maintains a SQLite WAL metadata index at
`translation_cache_index.sqlite3`. A one-time backfill may scan existing JSON
entries; subsequent get, invalidate, statistics, and eviction operations use
indexed rows. This cache is disposable and is never a canonical content
source or an R2 artifact. Do not delete the sidecar while the cache is live;
rebuild it only through a controlled cache maintenance window.

## Pipeline capacity settings checkpoint - 2026-08-24

The async persistence and runtime-telemetry controls are configured in
`settings.py`, all environment examples, and Compose wiring:

| Setting | Default | Bound or rollback |
|---|---:|---|
| `TRANSLATION_PERSISTENCE_EXPANSION_ENABLED` | `false` | `false` is the rollback profile: one persistence worker and no queue |
| `TRANSLATION_PERSISTENCE_WORKERS` | `2` | `1..8`, used only when expansion is enabled |
| `TRANSLATION_PERSISTENCE_QUEUE_SIZE` | `8` | `0..64`; `0` is the rollback value |
| `TRANSLATION_PERSISTENCE_OBSERVATION_LIMIT` | `256` | `32..4096` bounded observations |
| `TRANSLATION_PERSISTENCE_SHUTDOWN_TIMEOUT_SECONDS` | `30` | `1..300` seconds |
| `RUNTIME_TELEMETRY_SAMPLE_INTERVAL_SECONDS` | `0.25` | `0.05..60` seconds |
| `RUNTIME_TELEMETRY_MAX_OBSERVATIONS` | `256` | `32..4096` bounded observations |
| `RUNTIME_EVENT_LOOP_LAG_THRESHOLD_MS` | `1000` | `1..60000` ms; stop threshold, not an auto-restart |

`TRANSLATION_CONCURRENCY` is validated to `1..256`; chapter concurrency and
provider/DB budgets remain separate. Production startup rejects an aggregate
DB pool arithmetic violation. A sanitized local read used
`3 * (5 + 5) + 2 = 32`; this is a configuration arithmetic check, not hosted
capacity evidence. No secret-bearing `.env` value was changed by this audit.
