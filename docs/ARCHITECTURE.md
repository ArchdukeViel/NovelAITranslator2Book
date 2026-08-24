# Architecture

Canonical project architecture. This file wins when project documents conflict.

## Ingestion & Pipeline Architecture

### Hybrid Crawl & Generation Contracts
- **Syosetu / Novel18 Official API Enrichment**: Official JSON API array responses (Header `allcount` + work objects) provide initial title, author, genre codes, keywords, episode count, content length, timestamps, and status flags (`end=0` completed, `isstop=1` suspended). HTML crawling remains authoritative for chapter URLs, TOC structure, synopsis, and body text.
- **Public age-gate handling**: Supported public age-confirmation interstitials are followed through the source's bounded cookie/redirect flow before parsing. Interstitial HTML is never treated as chapter text; unresolved or unsafe targets fail as structured source-fetch errors, and parsed prose is not classified as a gate merely because it mentions age restrictions.
- **Novel18 as a first-class novel**: `novel18_syosetu` keeps source-specific host, cookie, API, and adult taxonomy provenance, but uses the same crawl, storage, translation, glossary, publication, catalog, detail, availability, and reader lifecycle as every other novel. Adult/R18 classification does not suppress an explicitly published novel from the default catalog; `include_adult` controls optional taxonomy exposure and filtering only.
- **Kakuyomu Stable Chapter Identity**: Every chapter carries three identifiers: `chapter_id` (the stable logical key used everywhere downstream, e.g. `kakuyomu:<episode_id>`), `source_episode_id` (the source-native identifier exposed by adapters), and `sequence_number` (mutable display position). Selections like `"all"`, `"1-3;8"`, `"2"`, or the raw stable id all resolve through `resolve_chapter_selection` so Kakuyomu's percent-encoded ids and Syosetu numeric ids share one pipeline. `int(chapter["id"])` and `chapter_id.isdigit()` checks were removed from the request flow.
- **Optional Cross-Source Section Hierarchy**: Source metadata may associate an existing reading unit with an optional structural section without changing chapter identity. The normalized optional fields are `section_title` (source display text), `section_source_id` (the real Kakuyomu `Chapter.id`, or `null` for Syosetu/Novel18 where no stable source id is observed), `section_ordinal` (source-order occurrence), and `section_level` when Kakuyomu supplies it. Syosetu and Novel18 derive sections only from structural TOC headings and carry the active heading across pagination; episode-title text never creates a section. Kakuyomu prefers `__NEXT_DATA__/__APOLLO_STATE__/Work/tableOfContentsV2` and its ordered `episodeUnions`, with a bounded DOM fallback that fails closed on unenumerated lazy/UI-paginated indexes. A Syosetu-style root-body short work is marked `work_structure="direct_body"`; ordinary episode indexes remain `work_structure="episodes"` so a direct short, a one-episode serial, and a one-episode Kakuyomu work stay distinct.
- **Content-Addressed Raw Generations**: Crawl runs upload immutable chapter and asset objects to R2, then upload a small manifest at `novels/<novel_id>/generations/<generation_id>.json.gz`. PostgreSQL activates the verified manifest and exact chapter references in one optimistic-concurrency transaction. There is no R2 active-pointer object and no local content directory. A failed activation leaves the previous PostgreSQL generation reference unchanged.
- **Durable Long-Running Crawl Operations**: `POST /api/admin/{novel_id}/scrape` returns `202 Accepted` after creating a durable `scrape` activity. The activity worker performs metadata reconciliation and chapter acquisition under the normal heartbeat, lease, cancellation, staging, validation, compare-and-swap activation, and rollback contracts. `GET /api/admin/activity/{activity_id}` is the status source; `POST /api/admin/activity/{activity_id}/run` is the explicit operator-run path when a background worker is not enabled. Onboarding resume queues the same durable chapter activity instead of holding an HTTP request open. Network and provider timeouts bound individual calls; they do not bound the total activity lifetime.
- **Pre-Activation Validation**: `R2GenerationActivationService` validates the candidate manifest before PostgreSQL activation. Every chapter reference must use the requested novel's exact `novels/<novel_id>/chapters|translations|media/<chapter_id>/...json.gz` namespace, have a matching logical SHA-256 in R2 metadata, and resolve by exact HEAD; the manifest identity and expected active-generation value must also match. The service uploads the immutable generation manifest, locks the PostgreSQL novel row, updates the active generation and chapter references in one transaction, and fails closed on a missing object, checksum mismatch, unknown chapter, or stale writer. There is no R2 active pointer, local atomic rename, staged `metadata.json`, or filesystem recovery bypass. Uploaded objects that are not committed because validation or activation fails remain harmless and are handled by the reference-aware grace-period GC workflow.
- **Immutable Content-Addressed Artifacts**: Raw chapters, translations, media state, and assets are immutable R2 objects. Their keys are `novels/<novel_id>/chapters/<chapter_id>/<source_hash>.json.gz`, `translations/<chapter_id>/<translation_hash>.json.gz`, `media/<chapter_id>/<media_hash>.json.gz`, and `assets/<sha256>.<ext>`. PostgreSQL stores the exact active references; edits create new objects and change references. Carrying unchanged content into a generation reuses existing hashes instead of copying a directory tree.
- **Episode Order & Convergence**: `update_source_state` persists `ordered_episode_ids` matching the complete current index plus per-episode `source_availability` / `first_seen_at` / `last_seen_at` / `missing_since`. Episodes absent from the index become `missing_from_current_index` (raw + translated history retained). A subsequent crawl with the same order produces an empty `reordered_episode_ids` / `removed_episode_ids` delta. `create_crawl_plan` uses the persisted `ordered_episode_ids` as the previous order (never `episode_map` insertion order); `removed_episode_ids` emits only newly missing episodes; episodes already marked `missing_from_current_index` are not re-emitted as new removals; a second identical crawl yields an empty delta.
- **Cache Acceptance on Attempt Identity**: `CacheEntry` carries `attempt_number`, `translation_run_id`, `output_hash`, and `cache_key`. `CacheFlushStage` drops rejected chunks (`needs_retry` / `needs_review` / `qa_failed`) and writes **only the pending entry matching the exact QA-accepted attempt tuple** (`accepted_attempt_number`, `accepted_provider_key`, `accepted_provider_model`, `accepted_cache_key`, `accepted_output_hash`). Chunk status + cache-key dedup is no longer the acceptance rule; a cross-model retry (model A rejected, model B accepted) can never cache the rejected attempt's output under its own key.
- **HTTP Origin & Redirect Hardening**: `_origin` is `(scheme, hostname, effective_port)`; same scheme + same hostname but different effective port is cross-origin. The redirect loop strips Authorization / Proxy-Authorization / Cookie / Host / If-None-Match / If-Modified-Since / If-Match / If-Unmodified-Since / If-Range on cross-origin hops, drops `Referer`, and **only genuine domain/path-aware cookie containers (`httpx.Cookies`) survive a cross-origin hop** — plain `dict` cookies (which expose `.get()`) are hostless request cookies and never cross an origin boundary. `throttle.before_request` and `throttle.after_response` run for **every hop** (redirect, 304, 429, 4xx, 5xx, success) **before** `raise_for_status` can raise, so per-host adaptive penalties track the host that actually returned each status code; a redirected error is never charged to the original requested URL, and retried statuses account per attempt.
- **Translation Lineage & LLM QA**: Translated versions are hash-linked to raw source content hashes, prompt versions, QA policies, and glossary hashes/revisions. LLM QA policy (`advisory`, `blocking_retry`, `review`) enforces bounded retry attempts for below-threshold chunks without leaking unapproved outputs into cache. `TranslationRunManifest` records `raw_generation_id`, `prompt_template_version`, `qa_policy_fingerprint`, and finalized counts (`expected_count`, `completed_count`, `skipped_count`, `review_count`, `failed_count`) so the lineage evidence is observable end-to-end.

## Product Boundary

Novel AI is a single-owner Japanese-novel ingestion, translation, editing, and
public-reading system.

| Surface | Contract |
|---|---|
| Owner | Crawling, imports, translation, editing, providers, users, requests, takedowns, and operations. |
| Guest | Public catalog, novel detail, chapter list, and reader. |
| User | Google OAuth or email/password session; private library, progress, history, reviews, and requests. |
| Enabled | Unified provider credentials with user contribution pooling, and public rankings. |
| Deferred | Community features, billing, organizations, and multiple admins. |

Generated translated-novel downloads are outside scope. Do not add PDF, EPUB,
HTML, Markdown, manifests, freshness, or downloads without an approved spec.
Novel ingestion accepts source URLs only; local EPUB, PDF, text, image-folder,
and archive imports are not supported. Preserve historical generated files.

## Runtime Topology

- `novelai.api.app:app`: monolith.
- `novelai.main_admin:app`: owner/user control plane, port 8000.
- `novelai.main_reader:app`: public reader, port 8001.
- `novelaibook worker`: dedicated provider-backed crawl/translation worker;
  it claims durable database activities and is not exposed through Caddy.
- `DEPLOY_MODE=monolith|split` selects topology.
- Next.js serves admin and public pages on port 3000.
- PostgreSQL owns relational state and exact artifact references; R2 owns
  immutable novel content. Local disk is disposable runtime state only.
- Redis provides distributed queueing, rate limiting, and coordination.
- Scheduler loops, long translation jobs, and restore verification need
  always-on compute; provider-backed activities run in the dedicated worker
  service so web processes do not consume their event loops for translation.
- Worker database hot paths use narrow projections: activity claims are atomic
  `UPDATE ... RETURNING` operations, heartbeats update only lease timestamps,
  and expired-lease recovery loads only the fields it needs. The background
  runner backs off from 5 to 30 seconds while the queue is empty. Routine
  catalog reconciliation defers the large novel metadata-history JSON and
  loads it only when an actual metadata change needs an audit append. The
  worker reuses the row returned by the atomic claim rather than immediately
  reloading it. A broader per-job metadata/glossary/raw-bundle cache remains a
  measured follow-up, not a current contract; no stale-cache behavior may be
  inferred from this boundary.

## Deployment Topologies

Two deployment modes, each with different topology and security properties.
The production topology is the target.

### Local Docker acceptance (``compose.yml``)

- Backend: split admin and reader containers on ports 8000 and 8001.
- Frontend: Next.js container on port 3000, proxied through Caddy.
- Database: external PostgreSQL; Compose does not provision the primary DB.
- Storage: Cloudflare R2 application bucket ``dokushodo``; only disposable
  runtime data is mounted locally at ``RUNTIME_DIR``.
- Redis: Compose service for split-mode rate limiting and coordination.
- Migrations: one-shot Compose ``migrate`` service must succeed before APIs.
- Purpose: production-like local acceptance and smoke testing.

### Tailscale-hosted production (WSL/Docker + split containers + managed PostgreSQL + R2)

- **Frontend**: pinned Node.js 26.7.x Next.js container behind Caddy on the
  WSL/Docker host, with explicit
  ``WEB_CORS_ORIGINS``, ``CSRF_TRUSTED_ORIGINS``, ``ALLOWED_HOSTS``, CSP,
  and HSTS. Operators reach the private site through Tailscale.
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
  - `DB_POOL_PROCESS_COUNT` explicitly counts long-lived backend, reader,
    worker, and replica pool owners; `DB_CONNECTION_RESERVE` accounts for
    migration, readiness, and operator access.
  - In direct/session mode, startup fails closed unless
    `DB_POOL_PROCESS_COUNT * (DB_POOL_SIZE + DB_MAX_OVERFLOW) +
    DB_CONNECTION_RESERVE` fits within `DB_CONNECTION_BUDGET`. This source
    guard does not replace verification against the managed pooler. Transaction
    mode uses `NullPool` and still requires measured pooler concurrency review.
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
    restore procedure; encrypted database dumps and incremental R2 snapshots.
    ``R2IncrementalBackupTarget.apply_retention()`` keeps manifests and shared
    objects reference-aware, while ``InterProcessFileLock`` protects scheduled
    backup and retention runs. The local runtime contains only the lock and
    other disposable state; it is never a backup archive.
  - **R2 transfer boundary**: ``R2Storage.put_immutable()`` handles
    content-addressed JSON writes, while ``R2Storage.save_stream()`` uses
    bounded multipart transfer, provider SHA-256 checksums, and committed
    length verification for larger binary artifacts.
- **Scheduled maintenance**: PostgreSQL-side cron for internal cleanup
  (``private.cleanup_expired_scheduler_states()``); application-side
  scheduler loop checks ``scheduled_cron_log`` for pending backup and
  maintenance work.
- **Image immutability**: containers built by SHA-pinned Docker images,
  not mutable tags.
- **Windows runtime-file-lock resilience**: `os.replace` (atomic rename) on Windows
  can transiently fail with `WinError 5` (`Access is denied`) when the
  destination is briefly held open (antivirus scan, reader handle, directory
  watcher). The shared runtime-only filesystem primitive
  `novelai.utils.filesystem.replace_with_retry` wraps the replace in a bounded
  retry loop (defaults to 8 attempts, requires
  `attempts >= 1`, retries only `PermissionError`, uses bounded increasing backoff
  of 0.02 s × retry number). Persistent `PermissionError` is re-raised after the
  bounded retry budget. Failed atomic replacements do not delete the committed destination,
  and callers clean temporary files so the old target remains intact on failure.
  A permanently held handle fails gracefully with target preservation.

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
- Production translation uses the one discovered Gemini model
  `gemini-3.5-flash-lite` (`models/gemini-3.5-flash-lite` in discovery
  responses). There is no model or provider fallback: rate limits, temporary
  failures, quota exhaustion, and 5xx responses wait, retry, or defer on that
  same model; permanent configuration, credential, model, or request errors
  fail closed.
- All Gemini work shares hard request accounting: 15 requests/minute,
  250,000 tokens/minute, and 500 requests/day. Body, metadata, chapter-title,
  glossary discovery/translation, optional LLM QA, validation, cache
  reconciliation, and retries are mapped by purpose and persisted through the
  Gemini quota state and sanitized provider-request usage records.

## Storage and Database Ownership

- PostgreSQL owns novel identity, public/source URLs, publication state,
  chapter identity/order, active generation, exact R2 artifact references,
  users, sessions, identities, glossary, requests, reviews, credentials,
  audit, jobs, and usage.
- R2 bucket `dokushodo` owns only immutable novel artifacts. The exact active
  layout is documented in [`STORAGE.md`](STORAGE.md); there are no folder
  metadata files, active-pointer objects, mutable overlays, or runtime data in
  the bucket.
- R2 bucket `dokushodo-backup` owns incremental object manifests and encrypted
  database recovery material. Backup credentials are independent from
  application credentials.
- Redis/Valkey owns transient queues, locks, leases, rate limits, and quota
  reservations. The local runtime directory owns only disposable caches,
  checkpoints, logs, and worker scratch data. On the host this boundary is
  `data/runtime/`; Compose maps it to the container's `/app/data/runtime`.
- Chapter state is stored as one service-managed JSON record per stable chapter
  identity under `chapter-state/<novel-id>/`; checkpoint filenames use the same
  encoded physical chapter stem. Current checkpoints include temporary raw,
  translated, and state copies to support application-level recovery. They are
  private disposable recovery material, not a canonical content source; exact
  PostgreSQL references and immutable R2 objects remain authoritative. Larger
  catalogs will need checkpoint retention/compaction and a reference-based or
  R2-backed payload strategy to avoid unnecessary duplicate content and local
  filesystem metadata pressure.
- PostgreSQL owns users, sessions, identities, glossary, requests, reviews,
  credentials, audit, jobs, and catalog projections.
- The `chapters` table carries stable-identity columns
  (`logical_chapter_id`, `source_episode_id`, `sequence_number`) for
  Kakuyomu-style percent-encoded ids and Syosetu numeric ids.
- Section metadata remains on the existing storage metadata chapter index; it
  does not require a `sections` SQL table, new R2 body objects, or a chapter
  identity change. Reconciliation treats the current source TOC as
  authoritative for present grouping, so section rename, move, order changes,
  flat/grouped transitions, and Kakuyomu Chapter-title updates converge by
  existing episode identity. Section metadata is display context: it refreshes
  the catalog projection and optional metadata-title translations, but does
  not invalidate raw body hashes, body translations, glossary identity, or
  chapter selection/cache keys.
- **Canonical DB identity invariant**: `UNIQUE(novel_id, logical_chapter_id)` with
  `logical_chapter_id` `NOT NULL` (String(512)). The ORM and migration agree
  exactly: migration `c7a8b9d0e1f2` adds the three columns, backfills existing
  rows (first row per `(novel_id, chapter_number)` inherits the numeric id;
  duplicates and `NULL`s get deterministic `legacy-<id>` values), then
  enforces `NOT NULL` and a unique index; downgrade drops columns and indexes.
  The ORM model (`Chapter.logical_chapter_id`) is `Mapped[str]` (non-nullable),
  and the migration enforces `UNIQUE(novel_id, logical_chapter_id)`. The
  `CatalogService` resolves chapter rows by `novel_id + logical_chapter_id`,
  never by title; reorder updates `sequence_number` in place without creating
  new rows; same-title chapters remain distinct rows.
- SQL chapter counts are projections of PostgreSQL-owned references; public
  readers do not enumerate R2 to rebuild a response.
- `Novel.public_reader_unavailable_policy` is an optional projection of the
  per-novel availability policy from canonical metadata. Migration
  `e5f7a9c1d3b2` persists it so projection-first public chapter reads retain
  policy behavior without a request-time metadata fallback or object-storage
  enumeration.
- R2 directories are virtual prefixes; no host-filesystem assumptions and no
  local content fallback.
- Preserve immutable scraped artifacts and historical generated references.
- The configured runtime directory is private, disposable, and never served
  directly.
- APIs never expose raw paths, internal keys, secrets, or full credentials.

See [`STORAGE.md`](STORAGE.md).

## API Contracts

Canonical names:

```text
source_key source_novel_id source_url novel_id chapter_id paragraph_id chunk_id
bundle_id provider_key provider_model activity_id job_id request_id credential_id
requesting_user_id credential_owner_user_id prompt_version prompt_template_version
glossary_hash canonical_glossary_hash qa_policy_version qa_policy_fingerprint
raw_generation_id logical_chapter_id stable_chapter_id source_episode_id
sequence_number ordered_episode_ids removed_episode_ids unavailable_chapter_ids
translation_run_id attempt_number output_hash cache_key

```

Contracts are forward-only. Update all callers together; no aliases, mirrored
fields, fallback readers, compatibility routes, or import shims.

- `/api/admin/*`: owner operations.
- `/api/auth/*`: owner and public authentication.
- `/api/user/*`: session-authenticated user data through admin process.
- `/api/public/*`: guest-safe reader and rankings through reader process.
- `/api/user/contributions`: authenticated user contribution views over the
  unified provider credential registry through the admin process; identity is
  session-derived and unsafe methods are CSRF-protected.
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
- **Worker process** (``admin.Dockerfile``) claims database-backed crawl and
  translation activities through ``novelaibook worker``. It has no public port
  and does not run an in-process web worker.
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

### Unified provider credential contract

Provider credentials are enabled behind `CONTRIBUTOR_CREDENTIALS_ENABLED` and
stored once in `provider_credentials`. The same table holds owner-managed
credentials and user contributions; there is no separate contributor
credential table. V1 permits one Gemini contribution per authenticated user.
Each row carries its authenticated owner, source, `owner_job_eligible`, and
`contributor_pool_eligible` flags so privilege and pool participation are
independent decisions.

Every submitted key is encrypted at rest with
`PROVIDER_CREDENTIAL_ENCRYPTION_KEY`; responses expose only the credential id,
provider/model, last four characters, fingerprint, source, eligibility,
status, consent version, validation state, timestamps, and failure count. Raw
keys, prompts, authorization headers, and provider responses are never stored
in the usage ledger, logs, or API responses. The configured
`PROVIDER_GEMINI_API_KEY` is not imported at startup; an owner must explicitly
invoke the owner-only import/validation operation, which creates an owner-job
credential and never makes it contributor-pool eligible.

User registration requires the current `CONTRIBUTOR_CONSENT_VERSION`.
Validation uses the explicit submitted key without hydrating owner preferences.
A successful validation activates a user contribution immediately; a failed
validation persists an invalid state and the key cannot enter the contributor
pool. Users may replace, pause, resume, and permanently delete their own
contribution. Owners may pause, resume, revoke, or share/unshare pool
eligibility for emergency and abuse-remediation control. Revoked credentials
cannot be resumed by users.

Contributor translation selects only active, valid Gemini rows with
`contributor_pool_eligible=true` and uses per-credential RPM, TPM, RPD, and
in-flight concurrency reservations. Pool selection is deterministic and
row-locked for the short lease transaction so concurrent workers do not
repeatedly select the same credential. Owner-only jobs select only
`owner_job_eligible` rows and never consume contributor-pool credentials. The
single `contributor_usage_ledger` records both modes using credential owner,
requesting-user, provider/model, request/job/activity ids, contribution mode,
sanitized status, token accounting, estimated cost, timing fields, and
timestamps. `credential_owner_user_id` and `requesting_user_id` remain
distinct.

Credential validation is rate-limited per authenticated user, provider feedback
is bounded and redacted against the submitted key, and a validation result is
discarded if the credential was replaced while the provider request was in
flight. Production quota controllers enforce configured per-credential
concurrency through shared Redis state. Provider-request audit identity is
passed per call rather than stored in shared pipeline metadata, so parallel
chunks cannot cross-associate credential ownership or ids.

The configured RPM/TPM/RPD and in-flight values are local admission guards.
They do not establish independent upstream capacity per API key: Gemini limits
vary by model and usage tier and are generally applied at the provider project
level. Production-volume work requires an operator check of the active project
limits in Google AI Studio; the worker fails closed when no active validated
contributor credential is available.

### Durable translation activity contract

`POST /api/admin/{novel_id}/translate` is an enqueue operation and returns
`202 Accepted` with `activity_id` and `status=pending`. The optional
`Idempotency-Key` is stored only as a bounded opaque request key; when omitted,
the service derives a stable hash from non-secret operation parameters. The
database-backed `activity_records` table owns status, leases, heartbeats,
retry count, provider/model, and sanitized progress metadata. Claims use row
locking and `skip_locked` where supported, expired leases are recovered, and
history/list queries are bounded. The legacy JSON queue is imported once for
compatibility but is not the production control plane.

The worker passes the activity id as both `job_id` and `activity_id` to the
translation pipeline. Provider calls are globally bounded per owner key or
contributor credential, have a deadline and bounded exponential retry delay,
and write sanitized provider timing/usage records. The worker is the normal
execution owner; direct operator execution remains an explicit single-activity
recovery path.

### Public ranking contract

`GET /api/public/rankings?period=daily|weekly|monthly&limit=...` ranks published
novels by distinct novel-detail viewers from `public_novel.view` events only:
24 hours, 7 days, or 30 days. Authenticated user ids and signed opaque
first-party anonymous viewer-token digests are counted separately; IP addresses
are never stored. Chapter events do not contribute. When analytics is disabled
or there is no retained data, the API returns `available=false` with a truthful
reason. There is no All Time period because the retention-backed event table
cannot provide that claim.

Ranking aggregation joins the published `Novel` projection, uses composite
event-time/novel/viewer indexes, and loads taxonomy with bounded database
queries rather than per-result storage-backed summaries. Successful non-empty
responses use a short process-local TTL/LRU cache keyed by period, public
projection schema/update version, and limit. Disabled, empty, and unavailable
responses remain explicit and uncached; cache metrics are exposed through
`/metrics`. A shared cache or durable rollup requires measured multi-reader
load evidence and an explicit invalidation contract.

Safe public catalog pages, novel summaries, and chapter metadata also use a
bounded process-local `PublicProjectionCache`. Catalog keys include the
published projection timestamp; novel-summary and chapter-context keys include
the current novel timestamp. Catalog publication/reconciliation and approved
takedown review invalidate the projection cache. Search text, identity,
progress, history, cookies, and chapter text are never cached. This cache is
an origin optimization and does not restore request-time object-storage
enumeration.

Public detail, chapter, and approved frontend analytics events cross a bounded
asynchronous writer. Metadata is sanitized before queue admission; the queue
contains only canonical event fields and no raw IP, prompt, authorization
header, or unsanitized payload. Queue-full events are dropped and counted,
worker failures are suppressed and counted, and each worker event uses its own
database transaction. Writer shutdown drains briefly during app lifespan
shutdown. The signed anonymous viewer digest and retention policy remain
unchanged.

## Operational Contracts

- `/health/live`: process-only, unauthenticated, always 200, no dependencies.
- `/health/ready`: redacted, cached/single-flight DB/lightweight-storage/
  worker/disk probes; 503 when the cached result is unhealthy.
- Recognized SQLAlchemy pool/server-capacity failures return a sanitized
  retryable `503 DATABASE_CAPACITY_EXHAUSTED`; unrelated database errors remain
  internal failures. This response classification does not replace
  deployment-wide pooler-budget verification.
- `/api/admin/health`: owner-only detailed but redacted diagnostics.
- Probe states: `healthy`, `degraded`, `unhealthy`.
- Public readiness does not run full storage write/read/delete or R2 usage
  scans. Those remain owner-only or scheduled diagnostics so reverse-proxy
  health checks do not amplify object-storage latency.
- Scheduled backup, maintenance, and database dumps use renewable PostgreSQL
  leases plus Redis/Valkey coordination where needed.
- Each registered maintenance task writes start/success/failure transitions to
  `SchedulerRuntimeState`; `GET /api/admin/maintenance/status` projects schedule,
  safe result, and next eligibility for owner UI. Missing state means `never_run`.
- R2 CRUD, snapshot reads, and backup writes use separate least-privilege
  credentials. R2 listing is limited to inventory, backup, migration, and GC
  workflows; normal readers use exact references.
- Backups are independently restorable copies, not lifecycle rules.
- HTTP origin is `(scheme, hostname, effective_port)`; default ports are
  80 for http and 443 for https, so different effective ports are
  cross-origin. Multi-hop redirects strip Authorization / Proxy-Authorization /
  Cookie / Host / If-* / If-Range headers and Referer on cross-origin hops;
  dict-style cookies (which lack domain context) only apply to the first
  hop, real cookie jars keep domain semantics across hops. `throttle.before_request`
  / `throttle.after_response` runs for every hop and attributes to the host
  that returned the status code.
- Cache acceptance is locked to the QA-accepted attempt: `CacheEntry` carries
  `attempt_number`, `translation_run_id`, `output_hash`, and `cache_key`;
  `CacheFlushStage` drops pending entries for rejected chunks
  (`needs_retry`, `needs_review`, `qa_failed`) and dedupes by key. Provider /
  model / prompt / glossary hash changes produce different cache keys.
- Translation runs produce a `TranslationRunManifest` linking
  `translation_run_id` to `raw_generation_id`, the canonical glossary hash,
  the effective `prompt_template_version`, the `qa_policy_fingerprint`,
  finalized counts (`expected_count`, `completed_count`, `skipped_count`,
  `review_count`, `failed_count`) and the in-source-order `chapter_ids`.
- Long-running scrape and resume operations are activity records, not request
  lifetimes. The activity lease is renewed by an independent worker heartbeat
  thread so synchronous orchestration cannot starve lease renewal, and durable
  status is polled through the activity API. A failed activity must
  leave the previous active generation visible; a staged generation is only
  reader-visible after complete-snapshot validation and pointer activation.
- Translation activities use the database queue rather than full-file JSON
  rewrites. `ACTIVITY_HISTORY_MAX_ENTRIES`, metadata-size, and retry-history
  limits bound durable state; queue metrics expose pending age and claim,
  heartbeat, list, and update timings.
- Gemini admission reserves requests-per-minute, tokens-per-minute,
  requests-per-day, and global in-flight capacity. `TRANSLATION_PROVIDER_DEADLINE_SECONDS`
  and bounded retry backoff limit provider work. Provider runtime metrics and
  the sanitized usage ledger record wait, execution, retry, quota-reservation,
  and usage-write duration without prompts, keys, authorization headers, or
  response secrets.
- Translation cache entries are disposable runtime data and are never used as
  canonical content. Durable translation lineage and active artifact
  references remain in PostgreSQL and R2.

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

- No community features before their separate moderation and security gate.
- No fake APIs or frontend-only security controls.
- No raw SQL outside Alembic and explicit `backend/sql/` policy files.
- No APScheduler.
- No generated translated-novel downloads.
- No billing, organizations, multi-admin teams, or broad package flattening
  without architecture change.

Current unfinished work lives only in [`WORK.md`](WORK.md).

## Pipeline async execution and capacity checkpoint - 2026-08-24

Translation persistence now crosses an explicit bounded
`TranslationPersistencePort`. The port owns per-operation storage/session
work, rejects live ORM/session values at the boundary, returns detached plain
data, records bounded queue-wait/duration observations, and batches coalescible
progress writes. Terminal lineage and active-reference writes remain critical
and ordered. The persistence expansion profile is disabled by default and is
reversible through `TRANSLATION_PERSISTENCE_EXPANSION_ENABLED=false`.

Runtime telemetry is a bounded fixed-label observation buffer with explicit
event-loop/process-resource availability states. It must never contain prompt,
response, source-text, credential, authorization-header, or arbitrary
exception data. Process CPU/memory and event-loop gauges are supporting
application evidence, not hosted billing or egress attribution.

Contributor admission applies one conservative shared project quota controller
and one per-credential controller. Distinct keys do not multiply project quota
without verified independent domains. Contributor selection remains separate
from owner-job selection, and translation-provider RPS remains separate from
public reader HTTP RPS. A credential reservation has a bounded reconciliation
or expiry outcome and sanitized ledger attribution.

The fixture-only capacity harness and checkpoint footprint measurement are
local evidence. The isolated R2 operation benchmark, source canary, and 1k,
10k, and 100k reader stages remain unavailable or operator-deferred until
their endpoint, traffic model, stop thresholds, rollback owner, and hosted
telemetry gates are supplied.
