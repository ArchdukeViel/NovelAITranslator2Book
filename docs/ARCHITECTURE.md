# Architecture

Canonical project architecture. This file wins when project documents conflict.

## Ingestion & Pipeline Architecture

### Hybrid Crawl & Generation Contracts
- **Syosetu / Novel18 Official API Enrichment**: Official JSON API array responses (Header `allcount` + work objects) provide initial title, author, genre codes, keywords, episode count, content length, timestamps, and status flags (`end=0` completed, `isstop=1` suspended). HTML crawling remains authoritative for chapter URLs, TOC structure, synopsis, and body text.
- **Public age-gate handling**: Supported public age-confirmation interstitials are followed through the source's bounded cookie/redirect flow before parsing. Interstitial HTML is never treated as chapter text; unresolved or unsafe targets fail as structured source-fetch errors, and parsed prose is not classified as a gate merely because it mentions age restrictions.
- **Novel18 as a first-class novel**: `novel18_syosetu` keeps source-specific host, cookie, API, and adult taxonomy provenance, but uses the same crawl, storage, translation, glossary, publication, catalog, detail, availability, and reader lifecycle as every other novel. Adult/R18 classification does not suppress an explicitly published novel from the default catalog; `include_adult` controls optional taxonomy exposure and filtering only.
- **Kakuyomu Stable Chapter Identity**: Every chapter carries three identifiers: `chapter_id` (the stable logical key used everywhere downstream, e.g. `kakuyomu:<episode_id>`), `source_episode_id` (the source-native identifier exposed by adapters), and `sequence_number` (mutable display position). Selections like `"all"`, `"1-3;8"`, `"2"`, or the raw stable id all resolve through `resolve_chapter_selection` so Kakuyomu's percent-encoded ids and Syosetu numeric ids share one pipeline. `int(chapter["id"])` and `chapter_id.isdigit()` checks were removed from the request flow.
- **Optional Cross-Source Section Hierarchy**: Source metadata may associate an existing reading unit with an optional structural section without changing chapter identity. The normalized optional fields are `section_title` (source display text), `section_source_id` (the real Kakuyomu `Chapter.id`, or `null` for Syosetu/Novel18 where no stable source id is observed), `section_ordinal` (source-order occurrence), and `section_level` when Kakuyomu supplies it. Syosetu and Novel18 derive sections only from structural TOC headings and carry the active heading across pagination; episode-title text never creates a section. Kakuyomu prefers `__NEXT_DATA__/__APOLLO_STATE__/Work/tableOfContentsV2` and its ordered `episodeUnions`, with a bounded DOM fallback that fails closed on unenumerated lazy/UI-paginated indexes. A Syosetu-style root-body short work is marked `work_structure="direct_body"`; ordinary episode indexes remain `work_structure="episodes"` so a direct short, a one-episode serial, and a one-episode Kakuyomu work stay distinct.
- **Staged Raw Generations**: Crawl runs write to staged generation directories (`generations/<gen_id>/`) with manifest-last atomic pointer activation (`active_generation.json`). Full crawls never call destructive deletion on active data. Generation activation uses a cross-process compare-and-swap on `active_generation.json`: the filesystem backend wraps the read-compare-write in an `InterProcessFileLock`; the S3 backend uses a conditional `PUT` with `If-Match`/`If-None-Match` so concurrent activations cannot silently overwrite each other (loser receives `GenerationConflictError`).
- **Pre-Activation Validation**: `commit_generation` runs `validate_generation_activation` before swapping the pointer. Checks cover manifest status, metadata identity, chapter-index presence, every-index-entry-resolved (bundle or explicit unavailable/refresh-failed-retained record), image-asset resolution inside the stage, manifest hash reconciliation, and physical stem / chapter-id consistency. Index entry ids are normalized to logical ids (integer ids become strings) before reconciliation, and reconciliation is against physical bundles, not index entries alone; `source_state.json` must exist and manifest hashes must be non-empty and match staged bytes exactly. Every current-index chapter ends with exactly one canonical disposition: `fetched_new`, `fetched_replaced`, `reused_planner`, `carried_unselected`, `unchanged_selected`, `refresh_failed_retained`, or `unavailable`. Aggregate counts (`saved_chapters`, `reused_chapters`, `failed_chapters`, `carried_unselected_count`, `unchanged_selected_count`, `refresh_failed_retained_count`, `unavailable_count`, `failed_refresh_count`, `removed_count`) are derived from the disposition map and must reconcile with the physical staged state. The disposition map itself is mandatory on the normal commit path; missing or empty `chapter_dispositions` fails closed. There is no normal bypass flag. Removed episode IDs come from `crawl_plan.removed_episode_ids`; `commit_generation` persists the canonical removal set and derives `removed_count` from that set. Activation validation reconciles the count before pointer activation. No separate normal-path removal acknowledgment key is required. Failures roll the stage back and keep the prior active pointer. Explicit operator recovery uses `commit_generation_recovery(reason=..., evidence=...)` for recovery paths.
- **Immutable Raw Generations + Translation Overlays**: A committed raw generation's `chapters/*.json` and `assets/images/**` are byte-immutable. All translation writes (machine translation, manual edit, rollback activation, edit history) land in `novels/<novel_id>/translations/<encoded_chapter_stem>.json` plus an `active/` pointer. Mutable OCR/re-embedding state lands in a novel-root media overlay (`media/<encoded-chapter-stem>.json`, schema `media_overlay_v1`) composed over the bundle at read time. Readers compose the raw bundle with the per-chapter overlay at read time so machine translation never rewrites raw bytes; while a generation is active, raw bundle writes are refused outright (persist, imports, checkpoint raw restores, rollback bundle-pop) instead of being silently rewritten. Carrying a chapter forward from generation A to generation B uses `seed_generation_from_active` which copies both the bundle and image assets.
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
  always-on compute; the backend runs in the always-on Docker services.

## Deployment Topologies

Two deployment modes, each with different topology and security properties.
The production topology is the target.

### Local Docker acceptance (``compose.yml``)

- Backend: split admin and reader containers on ports 8000 and 8001.
- Frontend: Next.js container on port 3000, proxied through Caddy.
- Database: external PostgreSQL; Compose does not provision the primary DB.
- Storage: local filesystem at ``NOVEL_LIBRARY_DIR`` or configured S3/R2.
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
- **Windows file-lock resilience**: `os.replace` (atomic rename) on Windows
  can transiently fail with `WinError 5` (`Access is denied`) when the
  destination is briefly held open (antivirus scan, reader handle, directory
  watcher). The shared filesystem primitive `novelai.utils.filesystem.replace_with_retry`
  wraps the replace in a bounded retry loop (defaults to 8 attempts, requires
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

- Storage owns canonical novel metadata, raw chapters, translated versions,
  edit history, and assets.
- Storage also owns the immutable raw generation tree
  (`generations/<gen-id>/`), the per-chapter translation overlay
  (`translations/<encoded-chapter-stem>.json`), and the novel-root media
  overlay (`media/<encoded-chapter-stem>.json`, schema `media_overlay_v1`);
  raw bundles are byte-immutable once a generation is active and
  translation/media writes never touch them.
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
