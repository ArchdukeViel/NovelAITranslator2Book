# Architecture

Canonical project architecture. This file wins when project documents conflict.

## Product Boundary

Novel AI is a single-owner Japanese-novel ingestion, translation, editing, and
public-reading system.

| Surface | Contract |
|---|---|
| Owner | Crawling, imports, translation, editing, providers, users, requests, takedowns, and operations. |
| Guest | Public catalog, novel detail, chapter list, and reader. |
| User | Google OAuth or email/password session; private library, progress, history, reviews, and requests. |
| Deferred | Contribution credentials, community features, rankings, billing, organizations, and multiple admins. |

Generated translated-novel downloads are outside scope. Do not add PDF, EPUB,
HTML, Markdown, manifests, freshness, or downloads without an approved spec.
EPUB/PDF source-document input and recovery backups remain supported. Preserve
historical generated files.

## Runtime Topology

- `novelai.api.app:app`: monolith.
- `novelai.main_admin:app`: owner/user control plane, port 8000.
- `novelai.main_reader:app`: public reader, port 8001.
- `DEPLOY_MODE=monolith|split` selects topology.
- Next.js serves admin and public pages on port 3000.
- PostgreSQL owns relational state; filesystem or S3/R2 owns chapter content.
- Redis provides distributed queueing, rate limiting, and coordination.
- Scheduler loops, long translation jobs, and restore verification need
  always-on compute; backend is not a Vercel Functions workload.

## Deployment Topologies

Three distinct deployment modes, each with different topology and security
properties. The architecture supports all three; the production topology is
the target.

### Local Docker acceptance (``compose.yml``)

- Backend: split admin and reader containers on ports 8000 and 8001.
- Frontend: Next.js container on port 3000, proxied through Caddy.
- Database: external PostgreSQL; Compose does not provision the primary DB.
- Storage: local filesystem at ``NOVEL_LIBRARY_DIR`` or configured S3/R2.
- Redis: Compose service for split-mode rate limiting and coordination.
- Migrations: one-shot Compose ``migrate`` service must succeed before APIs.
- Purpose: production-like local acceptance and smoke testing.

### Preview (disposable — Vercel Services + Supabase + R2)

- Frontend: Vercel Next.js service.
- Backend: Vercel FastAPI Function in monolith mode, routed through the same
  deployment URL. It scales to zero and has the plan's request-duration limit.
- Database: Supabase PostgreSQL (shared pool).
- Storage: R2 application bucket scoped to a non-root preview prefix.
- Ephemeral local cache: ``NOVEL_LIBRARY_DIR=/tmp/novelai-preview``; no durable
  data may rely on Vercel's read-only deployment filesystem or temporary disk.
- Redis: optional (in-memory rate limiter otherwise).
- Migrations: an operator or CI one-shot runs ``alembic upgrade head`` before
  deploying a revision that requires new schema.
- Backend uses SQLAlchemy/Alembic directly; Supabase Data API roles are not an
  application persistence path and remain denied on backend-internal tables.
- Workers, scheduler, maintenance, backups, and SMTP remain disabled. Acceptable
  for bounded feature previews; not for long translations or production.
- Vercel host validation uses ``ALLOWED_HOSTS=*.vercel.app`` because internal
  service hostnames differ from the public alias. List-typed settings use the
  application's comma-separated environment format, not JSON array text.

### Production (optimal — Vercel + split containers + managed PostgreSQL + R2)

- **Frontend**: Vercel with an immutable release, explicit
  ``WEB_CORS_ORIGINS``, ``CSRF_TRUSTED_ORIGINS``, ``ALLOWED_HOSTS``, CSP,
  and HSTS.
- **Backend**: always-on split deployment:
  - **Admin process** (``admin.Dockerfile``, port 8000) — owner/user
    control plane, session-authenticated endpoints, CSRF-protected
    mutations, scheduled jobs, health probes.
  - **Reader process** (``reader.Dockerfile``, port 8001) — public reader
    API, guest-safe GETs, no admin session, no mutations.
  - A separate one-shot migration job runs ``alembic upgrade head`` before
    either long-running API process starts.
- **Database**: managed PostgreSQL (Supabase / RDS / Cloud SQL) with:
  - TLS required, connection pool with transaction-level budgeting.
  - Dedicated direct-database role (not ``anon``/``authenticated``) used by
    backend SQLAlchemy connections. It owns application tables or has the
    audited privileges required to operate while RLS denies Data API roles.
  - ``anon`` and ``authenticated`` roles exist only if Data API is
    enabled; their privileges are explicitly revoked on backend-internal
    tables and sequences.
- **Storage**: two separate R2 buckets with least-privilege credentials:
  - **App bucket**: chapter content, novel assets, catalog projections.
  - **Backup bucket**: encrypted dumps and snapshots. Backup-target
    credentials write only there; separate snapshot-source credentials read
    only the application bucket.
- **Redis**: managed (Upstash / ElastiCache / managed Redis) for
  distributed rate limiting and the job queue in split mode.
- **Networking**: explicit HTTPS termination at the selected edge/proxy,
  explicit CORS origins, CSRF token validation on cookie-authenticated
  mutations, explicit allowed hosts, ``X-Forwarded-Proto`` enforcement.
- **Observability**: health endpoints (``/health/live``, ``/health/ready``,
  ``/api/admin/health``), structured logging, runtime error monitoring.
- **Email**: SMTP delivery configured through ``AUTH_EMAIL_DELIVERY_MODE``
  and canonical SMTP settings.
- **Backup and restore**: independently restorable copies with verified
  restore procedure; encrypted database dumps and R2 snapshots. Retention
  uses ``BackupManager.apply_retention()`` and ``InterProcessFileLock``.
- **Scheduled maintenance**: PostgreSQL-side cron for internal cleanup
  (``private.cleanup_expired_scheduler_states()``); application-side
  scheduler loop checks ``scheduled_cron_log`` for pending backup and
  maintenance work.
- **Image immutability**: containers built by SHA-pinned Docker images,
  not mutable tags.

## Backend Boundaries

```text
api -> services/orchestration -> domain -> storage/db/providers/sources
translation -> prompts -> providers
frontend -> approved frontend API clients -> backend
```

- Routers stay thin; use cases belong in services.
- Routers never directly import `novelai.db.models`,
  `novelai.storage.service`, or `novelai.sources`. Construction stays in
  `api/routers/dependencies.py`.
- Source parsing belongs in `sources/`; outbound HTTP, SSRF protection,
  throttling, retries, and fetch cache belong in `infrastructure/http/`.
- Provider integration belongs in `providers/`; prompt assembly in `prompts/`.
- Persistence stays behind `storage/` and `db/`.
- Scheduler/provider policy stays in backend service/job layers, never React.
- Components call backend only through `frontend/lib/api.ts` or
  `frontend/lib/public-api.ts`.

## Translation Flow

```text
chapter storage -> paragraph IDs -> chunks/bundles -> prompt + glossary
-> scheduler/provider -> structured or safe text output -> deterministic QA
-> post-process -> versioned translated chapter
```

- Preserve `novel_id`, `chapter_id`, `paragraph_id`, and `chunk_id` throughout.
- Fan-out uses bounded `asyncio.Semaphore` and
  `asyncio.gather(..., return_exceptions=True)` so one failure does not erase
  successful chapters.
- QA checks empty/source-identical output, suspicious length, placeholders,
  refusals/errors, and mapping integrity before save.
- Durable scheduler state records cooldown, exhaustion, heartbeat, and next eligibility.
- Provider chain is Gemini only: `gemini-3.1-flash-lite`, then
  `gemma-4-31b-it` through Gemini API.

## Storage and Database Ownership

- Storage owns canonical novel metadata, raw chapters, translated versions,
  edit history, and assets.
- PostgreSQL owns users, sessions, identities, glossary, requests, reviews,
  credentials, audit, jobs, and catalog projections.
- SQL chapter counts are projections; canonical counts come from storage.
- S3/R2 directories are virtual prefixes; no host-filesystem assumptions.
- Preserve raw scraped chapters and historical generated files.
- `storage/novel_library` is private and never served directly.
- APIs never expose raw paths, internal keys, secrets, or full credentials.

See [`STORAGE.md`](STORAGE.md).

## API Contracts

Canonical names:

```text
source_key source_novel_id source_url novel_id chapter_id paragraph_id chunk_id
bundle_id provider_key provider_model activity_id job_id request_id credential_id
requesting_user_id credential_owner_user_id prompt_version glossary_hash
```

Contracts are forward-only. Update all callers together; no aliases, mirrored
fields, fallback readers, compatibility routes, or import shims.

- `/api/admin/*`: owner operations.
- `/api/auth/*`: owner and public authentication.
- `/api/user/*`: session-authenticated user data through admin process.
- `/api/public/*`: guest-safe reader through reader process.
- `/health/*`: liveness/readiness through admin process.
- `/novels/*`: frontend pages, not backend aliases.

### Request Body Boundaries

| Route group | Max body | Content-Type |
|---|---|---|
| Auth (login, register) | 64 KiB | `application/json`, `application/*+json` |
| General JSON API | 1 MiB | `application/json`, `application/*+json` |
| Analytics ingest | 32 KiB (default) | `application/json` |

ASGI middleware bounds every API request body and emits route-class `413`/`415`
responses. Caddy rejects bodies
above 34 MiB before routing; direct Uvicorn remains protected by app limits.

## Identity and Security

Roles are `guest`, `user`, and exactly one `owner`.

- Owner bootstrap is backend-only; public auth creates `role="user"` only.
- Public login never calls owner bootstrap `/api/auth/login`.
- Identity comes from session, never client-supplied `user_id`.
- Cookie-authenticated mutations require CSRF protection.
- Disabled users cannot log in or continue sessions.
- Never log or return keys, cookies, auth headers, encryption keys, database
  URLs, bootstrap secrets, private paths, or raw traces.
- `SESSION_SECRET_KEY` fails closed when default in production.
- Credential encryption key is required before storing provider keys.
- Production CORS and hosts are explicit; no wildcard with credentials.
- Source fetching is SSRF-safe.
- Models receive only public/non-sensitive text, never account data, secrets,
  private logs, or backups.
- Takedowns use exact decoded paths, safe HTTP 451, `no-store`, sitemap
  exclusion, and no complainant/private details.

Contribution credentials stay unavailable until encrypted storage, consent,
validation, revocation, usage limits/ledger, provider isolation, audit, abuse
controls, and owner approval exist.

## Operational Contracts

- `/health/live`: process-only, unauthenticated, always 200, no dependencies.
- `/health/ready`: bounded DB/storage/worker/disk probes; 503 when unhealthy.
- `/api/admin/health`: owner-only detailed but redacted diagnostics.
- Probe states: `healthy`, `degraded`, `unhealthy`.
- Scheduled backup, maintenance, and database dumps use renewable PostgreSQL
  leases plus local file locks where needed.
- Each registered maintenance task writes start/success/failure transitions to
  `SchedulerRuntimeState`; `GET /api/admin/maintenance/status` projects schedule,
  safe result, and next eligibility for owner UI. Missing state means `never_run`.
- R2 CRUD, snapshot reads, and backup writes use separate credentials.
- Backups are independently restorable copies, not lifecycle rules.

## Reader Contracts

- Genre: `{slug,name_ja,name_en}`; tag: `{name,name_ja}`.
- Shared accessible loading, empty, error, unavailable, not-found, unauthorized,
  forbidden, and partial-error states.
- One page `main`, skip link, visible focus, reduced-motion support.
- Canonical metadata and escaped structured data; robots/sitemap exclude 404/451.
- Guest-safe GETs may use short shared caching; auth/admin/errors/451 and owner
  previews use `no-store`.
- Public glossary annotations cap at 50 and report truncation.
- Missing covers use generated bookplates. Chapter and library content remains
  usable without optional cover assets or duplicate landmarks.

## Forbidden Work

- No contribution/community/ranking features before moderation and security gates.
- No fake APIs or frontend-only security controls.
- No raw SQL outside Alembic and explicit `backend/sql/` policy files.
- No APScheduler.
- No generated translated-novel downloads.
- No billing, organizations, multi-admin teams, or broad package flattening
  without architecture change.

Current unfinished work lives only in [`WORK.md`](WORK.md).
