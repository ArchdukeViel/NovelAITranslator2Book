# Operations

Solo-owner runbook for health, maintenance, backup, recovery, incidents, and reader budgets. For topology, environment setup, and release procedures, see [`DEPLOYMENT.md`](DEPLOYMENT.md). Never record secret values in evidence.

## Managed test database verification

`MANAGED_DATABASE_TEST_URL` is reserved for the disposable Supabase project
named `testdatabase=dokushodo`. It may use the Supabase session pooler, but it
must never point at the active application database. The strict hosted
verification workflow does not apply migrations automatically; this preserves
stale-schema detection.

When the candidate schema must be created or refreshed, run the manual
confirmation-gated `managed-services-verification.yml` workflow with
`migrate_test_database=true` and `confirm_test_database=true`. It calls
`.github/workflows/managed-services-test-migrate.yml`, which runs Alembic once
with the privileged `MIGRATION_DATABASE_URL` variable and does not start an
application or worker. After it succeeds, run the same verification workflow
again with migration disabled for the observed database and R2 checks, then
leave `MANAGED_SERVICE_TESTS_ENABLED=false`.
Record only the workflow URL, commit, UTC timestamp, pass/skip/fail counts,
and sanitized schema evidence; never record the URL or its credentials.

## Managed non-production recovery verification

`managed-services-recovery-verification.yml` is a manual, confirmation-gated
development workflow for the disposable `testdatabase=dokushodo` project and
the dedicated test R2 target. It creates a temporary backup-capable database
role for the run, generates the database-backup encryption key in the runner,
uses the existing `DatabaseBackupService`, and restores into an ephemeral local
PostgreSQL service. The run uses a unique R2 prefix and removes the temporary
role and test objects before recording sanitized evidence.

Run it only with `confirm_test_recovery=true`. The workflow refuses the
canonical production bucket names and refuses a non-local restore target. Its
success proves one current isolated backup/restore path and representative
schema/public-isolation checks; it does not prove recurring production backup
freshness, operator alert delivery, or production recovery readiness. Keep the
worker/full queue paused and leave `MANAGED_SERVICE_TESTS_ENABLED=false`.

## Health

| Endpoint | Expected behavior |
|---|---|
| `GET /health/live` | Process-only, unauthenticated, always 200; no dependency calls. |
| `GET /health/ready` | Redacted, short-TTL cached/single-flight DB/lightweight-storage/worker/disk probes; 503 when the cached result is unhealthy. |
| `GET /api/admin/health` | Owner-only detailed but redacted probe status and latency. |

States: `healthy`, `degraded`, `unhealthy`. Investigate stale worker heartbeat,
DB connectivity, storage reachability/capacity, and disk before restart. Public
readiness does not perform a mutating storage probe or R2 usage enumeration;
`/api/admin/health` remains the fresh owner diagnostic for those checks.
Public health output never includes paths, hosts, credentials, or traces.

### Database connection capacity

Treat `DB_CONNECTION_BUDGET` as a deployment-wide limit, not only a single
web-process setting. Account for every backend, reader, worker, migration, and
operator process using `DB_POOL_SIZE + DB_MAX_OVERFLOW`, then reserve capacity
for readiness and emergency access. Verify the resulting aggregate against the
managed pooler before changing `DB_CONNECTION_MODE` or scaling a service.
Set `DB_POOL_PROCESS_COUNT` to the number of long-lived pool owners and
`DB_CONNECTION_RESERVE` to the migration/readiness/operator reserve. Direct and
session startup now fails closed when
`DB_POOL_PROCESS_COUNT * (DB_POOL_SIZE + DB_MAX_OVERFLOW) +
DB_CONNECTION_RESERVE` exceeds `DB_CONNECTION_BUDGET`. The current split
Compose example therefore requires `32` for three processes with pools of
`5 + 5` and a reserve of `2`; change the count and budget together when
scaling or changing topology. Transaction mode still requires direct pooler
concurrency verification because `NullPool` removes the fixed SQLAlchemy pool
ceiling rather than proving a managed-pooler limit.

When a recognized SQLAlchemy pool/server-capacity failure occurs, the API
returns `503 DATABASE_CAPACITY_EXHAUSTED` with sanitized retryable details.
Unrelated database errors remain internal failures. A capacity response is a
signal to reduce admission or correct the pooler budget; do not hide it by
raising pool timeouts or enabling unbounded overflow. Record the affected
service, UTC window, status counts, and sanitized pooler evidence without
recording connection URLs, credentials, cookies, or raw traces.

Readiness defaults to a five-second cache (`HEALTH_CACHE_TTL_SECONDS`). The
first request after expiry performs one bounded probe run and concurrent
requests join it. Inspect
`novelai_readiness_cache_hits_total`,
`novelai_readiness_cache_misses_total`,
`novelai_readiness_cache_entries`, and
`novelai_readiness_cache_age_seconds` in the owning backend metrics. A
healthy cache result is not proof that storage remains healthy after its
timestamp; investigate repeated refresh failures rather than disabling the
cache or increasing probe timeouts blindly.

## Worker, Scheduler, and Maintenance

- Check owner worker/scheduler status and `SchedulerRuntimeState` heartbeat,
  last result, cooldown/exhaustion, and next eligible run.
- Scheduled jobs use cron/timezone evaluation and renewable PostgreSQL leases.
- Local disk is runtime-only; it is never used for canonical novel content or
  retention. Redis/Valkey owns distributed leases and coordination.
- Generation activation verifies immutable R2 objects and changes the active
  PostgreSQL reference with optimistic concurrency. There is no R2 pointer
  object, filesystem compare-and-swap, or local-generation fallback.
- Explicit operator recovery from a failed generation activation uses
  `commit_generation_recovery(reason=..., evidence=...)` — both arguments are
  required non-empty strings that are logged for audit. This bypasses the
  strict validation gate and must only be invoked after isolated verification.
- Maintenance cleans allowlisted cache/events/activity/runtime-state roots and
  applies backup retention. Use dry-run before changed cleanup policy.
- Never reintroduce APScheduler.

### Long-running scrape and resume

`POST /api/admin/{novel_id}/scrape` is an enqueue operation and returns
`202 Accepted` with an `activity_id`; it does not wait for metadata or chapter
fetching to finish. The durable `scrape` activity runs metadata reconciliation
and chapter acquisition in one worker lease, renewing its heartbeat and
preserving the standard staged-generation validation, activation, and rollback
behavior. Resume of an interrupted onboarding flow queues a durable chapter
activity using the same contract.

Poll `GET /api/admin/activity/{activity_id}` for the redacted status record.
With a worker disabled, an owner can execute one queued record through
`POST /api/admin/activity/{activity_id}/run`; with the worker enabled, the
background runner claims it. A request/network timeout applies to each
individual outbound operation, while the activity lease and heartbeat govern
the total crawl duration.

### Long-running translation

`POST /api/admin/{novel_id}/translate` returns `202 Accepted` with
`activity_id` and `status=pending`; it never waits for provider calls or
translation artifact commits. Supply an `Idempotency-Key` when a client may
retry the enqueue request. Without one, the server derives a stable key from
the non-secret operation parameters. Poll
`GET /api/admin/activity/{activity_id}` and use the existing activity run,
cancel, retry, and lease status controls.

The Compose `worker` service is the normal execution owner. Keep
`JOB_WORKER_ENABLED=false` explicitly on both web services so the admin/reader
processes do not duplicate provider work; do not rely on a shared environment
file to provide that override. Before a repair or image recreation, verify the
effective flag in `backend`, `reader`, and `worker`, and verify that only the
dedicated worker owns the `novelaibook worker` process. The activity queue is
backed by the `activity_records` table; claims are row-locked, expired leases
are recovered, and bounded history/metadata limits prevent queue state from
growing without control. Monitor `novelai_activity_queue_age_seconds`,
`novelai_activity_queue_operation_total_ms`, and the activity status gauges.
The worker heartbeat renews from an independent daemon thread, so synchronous
provider or orchestration work cannot starve lease renewal; the focused worker
test covers this failure mode. After a code rebuild, verify the running worker
image before relying on the correction for multi-worker recovery.

The worker protects managed-database egress on the translation hot path. Claims
use one atomic returning update, the `run-next` path reuses that returned row,
heartbeats write only lease timestamps, and empty-queue polling backs off from
5 to 30 seconds. Routine catalog reconciliation defers the large novel
metadata-history JSON. A broader per-job metadata/glossary/raw-bundle cache was
not selected because the live audit did not establish a safe repetition or
invalidation baseline. If Supabase egress rises unexpectedly, stop the worker
before investigating:

```powershell
docker compose -f deploy/compose.yml stop --timeout 5 worker
docker compose -f deploy/compose.yml ps worker
```

Then inspect Supabase **Reports → Database / Pooler Egress** and compare the
time window with sanitized application query/operation metrics. `pg_stat_*`
views can identify query volume and rows but do not provide an exact billing
byte attribution; do not claim a precise worker share without provider-side
egress evidence. Do not restart the worker until the query-shape fix is built,
validated, and the operator has reviewed the remaining queue state.

When a worker is interrupted, repair chapter state through the activity and
storage services or the documented activity retry controls. Do not hand-edit or
delete `data/runtime/chapter-state` or checkpoint JSON files. A stale lease
should be allowed to expire and be recovered by the queue; a terminal QA or
provider failure should remain visible for review rather than being relabeled
as translated.

Provider overload should surface as queue age, bounded retry delay, or a
truthful paused/failed activity—not as an unbounded web request. Owner Gemini
uses global RPM/TPM/RPD and in-flight limits. Contributor credentials use the
same dimensions per credential and remain isolated from owner-only jobs.
Provider timing counters include admission wait, execution, retries, quota
reservation, and usage-ledger write time; they intentionally contain no
prompt or credential data.

The translation cache's JSON entries are indexed by a SQLite WAL sidecar.
Only initialization/backfill may scan the cache directory. Invalidation,
statistics, and eviction operate on indexed metadata. If the sidecar is
corrupt, stop the worker, preserve the JSON entries, and rebuild it during a
maintenance window rather than deleting cache data blindly.

Owner maintenance status:

```text
GET /api/admin/maintenance/status
Admin UI: /admin/maintenance
```

| Field/state | Meaning |
|---|---|
| `never_run` | Registered task has no durable completed attempt. This is not success. |
| `running` | Task recorded a start and has not recorded completion. Check heartbeat/lease when stale. |
| `idle` / `succeeded` | Latest recorded attempt completed successfully. |
| `failed` | Latest attempt failed. UI exposes generic redacted guidance only. |
| `disabled` | Maintenance scheduling is disabled; no next eligibility is advertised. |
| `next_eligible_at` | Next cron occurrence in UTC from configured cron/timezone and durable completion state. |

Every allowlisted task records best-effort start/success/failure transitions in
`SchedulerRuntimeState`. Observability-write failure is logged safely and does
not turn successful cleanup into failed cleanup. DB state is durable truth;
absence remains explicit and no local runtime cache may manufacture success.

Manual novel cache invalidation:

```text
POST /api/admin/novels/{novel_id}/cache/invalidate
```

## Backups

### Object storage

- `BACKUP_ENABLED=true` enables scheduled snapshots.
- R2 production snapshots use independent `dokushodo-backup` target
  credentials.
- Application CRUD, snapshot-source read, and backup-target write credentials
  remain separate and least privilege.
- Snapshot success requires a manifest-last commit plus byte-length, checksum,
  and referenced-object verification. Incremental manifests copy only new
  content-addressed objects and reference prior verified snapshots.
- Retention is implemented by `R2IncrementalBackupTarget` and preserves the
  configured newest/minimum successful manifests. It deletes a shared object
  only when no retained manifest references it and its
  `BACKUP_SAFETY_GRACE_DAYS` period has elapsed. Lifecycle rules/locks are
  safeguards, not copies.

Manual trigger:

```text
POST /api/admin/backups
```

### R2-only cutover and migration

The hard cutover is an operator-gated data operation, not a startup migration.
Before any destructive action:

1. Pause crawl, import, translation, worker, and maintenance writers.
2. Record the three PostgreSQL novel IDs, slugs, source URLs, publication
   states, chapter counts, active generations, and exact current references.
3. Inventory `dokushodo` and `dokushodo-backup` with fully paginated listings,
   checksums, byte totals, and sanitized manifests.
4. Verify an independent backup and an isolated restore before reset.
5. Require an explicit confirmation naming both buckets and the migration ID.

The reset tool may delete only the named buckets after the confirmation gate;
it must verify zero objects, keep both buckets, repopulate immutable objects,
upload manifests, commit PostgreSQL references, and verify all three previous
public URLs. It must refuse legacy prefixes, guessed buckets, incomplete
identity evidence, or a live writer. A dry-run is the default. Production
object counts and repopulation are not claimed until sanitized live evidence is
recorded in the conformance ledger.

### Garbage collection

GC is mark-and-sweep over exact PostgreSQL references plus protected rollback,
backup, and in-progress migration manifests. It lists R2 only in the GC job,
archives or verifies backup presence before deletion, applies the configured
grace period (seven days initially), and emits a dry-run report. Active,
current, protected, referenced, or grace-period objects are never deleted.

### Backup Bucket Object Lock & Operator Retention Debt Procedure

The Cloudflare R2 backup bucket `dokushodo-backup` operates with bucket-level Object Lock / retention policies. When automatic retention cleanup (`apply_retention()`) attempts to delete snapshots whose retention period has not expired, Cloudflare R2 rejects `DeleteObject` with `ObjectLockedByBucketPolicy: The object is locked by the bucket policy.`

- **Operator Retention Debt**: Old snapshots (e.g. historical snapshots created before data-resets) remain immutable in `dokushodo-backup` until their lock period expires.
- **Runbook Rule**:
  1. Do not treat `ObjectLockedByBucketPolicy` errors as application backup failures; new snapshots and manifests are committed successfully.
  2. Maintain `BACKUP_MIN_SUCCESSFUL_TO_KEEP` policy in application logic.
  3. Once bucket retention locks expire, run standard retention prune via maintenance tasks or manual admin API call.
  4. Never attempt force-deletion of locked objects; Cloudflare R2 bucket policy enforces compliance.

### Database

- `DATABASE_BACKUP_ENABLED=true` creates PostgreSQL 18 custom-format dumps of
  application-owned schema.
- Dumps are streamed through AES-256-GCM encryption and committed independently.
- No plaintext dump remains after successful or failed handling.
- Restore verification uses a disposable PostgreSQL 18 database whose name
  contains `restore`; never point it at production.

## Restore Procedure

1. Select a committed backup and verify manifest/checksums.
2. Restore storage into an isolated prefix; inspect counts and representative content.
3. Restore encrypted PostgreSQL dump into a clean isolated database.
4. Verify Alembic head, tables, constraints, row counts, and representative queries.
5. Restore production storage first, then PostgreSQL.
6. Rebuild catalog projections with `POST /api/admin/catalog/rebuild`.
7. Run deployment smoke checks and spot-check public/private boundaries.
8. Record UTC time, candidate version, operator, commands, and sanitized results.

Never restore directly into production before isolated verification. Historical
generated files are preservation-only data and must not be deleted automatically.

## Incident and Rollback

Rollback triggers include private/taken-down content exposure, owner bypass,
secret exposure, corrupt migration/data, uncontrolled queue growth, broad
storage failure, severe reader errors, or failed recovery without safe mitigation.

1. Pause worker and scheduler.
2. Disable public reader or affected feature when possible.
3. Purge affected CDN/application cache.
4. Preserve logs and current data; do not destroy evidence.
5. Redeploy previous immutable image/version.
6. Prefer forward-fix for DB migrations. Snapshot first; downgrade only after
   isolated testing and explicit data-loss acceptance.
7. Re-run health, auth, reader, takedown, storage, and smoke checks.

## Secret Rotation

- Session secret rotation invalidates all sessions.
- Provider credential encryption-key rotation requires re-encryption before old-key removal.
- Rotate R2 application, snapshot-read, and backup-write tokens independently.
- Owner bootstrap secret seeds only fresh owner state; never expose it.
- Keep SMTP disabled (`noop`) until delivery readiness in `WORK.md` passes.

## SMTP Activation Gate

`AUTH_EMAIL_DELIVERY_MODE=noop` is the safe default. Before switching to `smtp`:

While `noop` is active, public password signup is intentionally a deferred
email-delivery path: account creation and session login can be tested, but
verification and password-reset messages are not sent. Do not treat an
unverified account or a generated but undelivered token as SMTP evidence.

1. Verify sending domain ownership plus SPF, DKIM, and DMARC.
2. Store SMTP credentials only in provider secret storage.
3. Test verification/reset delivery, bounce handling, timeout, and rate limits.
4. Confirm application and provider logs omit tokens, credentials, message body,
   private recipient data, host internals, and traces.
5. Trigger one real stale/failure operator alert and verify cooldown behavior.
6. Revert to `noop`, confirm authentication remains usable, then document rollback.
7. Record candidate commit, UTC time, operator, provider environment, exact safe
   action, sanitized result, and blocker/waiver status.

SMTP construction tests and noop notifications are not delivery evidence.

## Reader Budgets

| Surface | Budget |
|---|---:|
| Catalog API | p95 <= 500 ms; <= 250 KiB |
| Novel API | p95 <= 300 ms; <= 100 KiB |
| Chapter API | p95 <= 750 ms; <= 1 MiB |
| Public route first-load JS | <= 250 KiB |
| Catalog page size | default 24; maximum 100 |
| Public annotations | maximum 50 |

Guest-safe catalog/reader GETs may use short shared caching. Auth, account,
admin, intake, errors, unavailable shells, owner previews, and HTTP 451 do not.
Use real-network/browser acceptance before launch; local budgets are not hosted evidence.

## Routine Checks

- Daily: health, queue, worker/scheduler heartbeat, errors, storage capacity.
- After deploy: migrations, liveness/readiness, public route, auth boundary, frontend.
- After takedown: reader 451, sitemap exclusion, cache/CDN propagation.
- After backup: committed manifest, checksum, retention, alert status.
- Periodically: isolated object and DB restore; secret/credential scope review.

## Recovering the Project Venv

The project venv at `.venv/` is the canonical interpreter for all backend
tooling (Python ≥ 3.14). To rebuild after schema changes, dependency
upgrades, or accidental deletions:

```powershell
py -3.14 -m venv .venv
& .venv\Scripts\python.exe -m pip install --upgrade pip
& uv sync --extra dev --extra db --extra auth --extra s3 --extra worker --extra gemini --extra test
```

Then verify tooling resolves the venv (not a PATH shadow):

```powershell
& tools/pytest.ps1 -q backend/tests/test_chapter_identity_codec.py
& tools/ruff.ps1 check backend/src backend/tests
& tools/pyright.ps1
```

Each `tools/*.ps1` wrapper refuses to run when `.venv\Scripts\python.exe`
is missing. The readme at `tools/README.md` lists the canonical extras.

Current unresolved operator gates live in [`WORK.md`](WORK.md).

## Unified Provider Credential Operations

For an enabled credential deployment, the owner and user paths operate on the
same `provider_credentials` table. Verify:

1. Confirm `PROVIDER_CREDENTIAL_ENCRYPTION_KEY` is present and not the owner
   bootstrap or session secret.
2. Confirm the current `CONTRIBUTOR_CONSENT_VERSION` is the version shown by
   the frontend and record any consent copy change.
3. Confirm per-credential RPM/TPM/RPD limits and the quota-state directory are
   writable only by the backend runtime.
4. Import the configured owner key only through the owner-only
   `POST /api/admin/providers/credentials/import-environment` operation. It
   explicitly validates `PROVIDER_GEMINI_API_KEY`, stores it encrypted, marks
   it owner-job eligible, and never makes it contributor-pool eligible. A
   failed validation is persisted as `invalid`; do not queue owner bulk work
   until the key validates. At the current 2026-08-22 checkpoint the imported
   owner row is `active`/`valid` and owner-job eligible; this does not make it
   contributor-pool eligible.
5. Confirm at least one user contribution is `active` with
   `validation_status=valid` and `contributor_pool_eligible=true` before
   queueing contributor-backed translation. A zero-key pool is an intentional
   preflight stop; never substitute an owner row or environment key.
6. Verify the active Gemini project limits in Google AI Studio. The local
   RPM/TPM/RPD values are defensive ceilings, not proof of independent quota
   per API key; TPD is model-dependent and is not configured separately here.
7. Apply Alembic migrations with the elevated migration role before starting
   the long-running services; the runtime role must have the required DML but
   should not be granted broad schema-DDL privileges.
8. Verify the user route returns masked metadata only, unsafe methods reject
   missing CSRF, validation attempts are rate-limited per user, and a user
   cannot read or mutate another user's credential.

Owners may pause or revoke a credential for emergency abuse remediation. A
revoked credential cannot be resumed by a user. Permanent user deletion removes
the encrypted credential row but preserves sanitized usage-ledger history for
accounting and incident review. Do not delete ledger rows as part of ordinary
credential removal.

Rotation requires a maintenance window: pause contributor work, re-encrypt
stored credentials, verify fingerprints and validation state, switch the
configured key, resume only after a masked read and validation check, and
record the operator/evidence in `HISTORY.md`. If re-encryption cannot complete,
keep the old key available and fail closed rather than accepting new keys.

## Ranking and Anonymous Viewer Retention

`/api/public/rankings` is based on published novel-detail events retained by
`ANALYTICS_RETENTION_DAYS`. Daily, Weekly, and Monthly mean 24 hours, 7 days,
and 30 days from query time. Chapter views are excluded. When analytics is
disabled or the retained set is empty, the API and UI expose an unavailable or
no-data state; operators must not seed placeholder rows or describe it as All
Time.

Successful non-empty ranking responses use a bounded process-local TTL/LRU
cache. The default TTL is 60 seconds and the default bound is 64 entries; the
cache is an optimization only and is not shared between reader workers or
replicas. Cache keys include the period, public-projection schema/update
version, and limit, so publication or projection updates select a new key.
Disabled analytics, no-data, and unavailable responses are never cached.
Inspect `novelai_public_ranking_cache_hits_total`,
`novelai_public_ranking_cache_misses_total`, and
`novelai_public_ranking_cache_entries` in `/metrics`. If the deployment scales
to multiple readers, measure duplicate origin work before moving this contract
to a shared Redis cache.

Migration `c8d2e4f6a1b3` adds the two composite analytics indexes used by the
ranking predicate and authenticated/anonymous viewer identities. Verify the
migration head and run a representative PostgreSQL `EXPLAIN (ANALYZE,
BUFFERS)` before treating ranking latency as production-capacity evidence.

### Public projection cache and analytics writer

Catalog base pages, DB-backed summaries, and chapter metadata use a bounded
30-second/256-entry process-local projection cache. Publication/reconciliation
and approved takedown review invalidate it; versioned keys also prevent normal
projection updates from reusing an older payload. Monitor
`novelai_public_projection_cache_hits_total`,
`novelai_public_projection_cache_misses_total`,
`novelai_public_projection_cache_entries`, and
`novelai_public_projection_cache_invalidations_total`. The reader process
does not expose the admin metrics route by default, so collect these metrics
from the owning operator process or add an approved reader telemetry path
before using them for capacity claims.

Public analytics writes use a bounded asynchronous queue (default 1,000). A
request response with `recorded` means queue admission, not durable commit;
`dropped` reports queue-full or unavailable admission. Monitor
`novelai_analytics_writer_accepted_total`,
`novelai_analytics_writer_dropped_total`,
`novelai_analytics_writer_processed_total`,
`novelai_analytics_writer_failures_total`, and
`novelai_analytics_writer_queue_depth`. Sustained drops require capacity
investigation; do not make the queue unbounded. The writer stores only
sanitized fields and never stores raw IP addresses.

Guest detail views may set the signed `novelai_viewer` first-party cookie. The
server stores only a digest of the opaque token, never the raw token or an IP
address. Clear the cookie or disable analytics when investigating identity
collection; do not export raw cookie values into logs or incident evidence.

The contributor usage ledger is pruned by the `contributor_usage_cleanup`
maintenance task according to `CONTRIBUTOR_USAGE_RETENTION_DAYS`. Permanent
credential deletion preserves rows until that retention task removes them;
dry-run the task before changing the policy.

## Reader capacity and recovery follow-up checkpoint — 2026-08-25

The current operational evidence package is blocked, with local validation
complete. The 1k reader report has a complete required matrix but no approved
fixture/target or controlled cold-cache evidence; all cells are therefore
unavailable and `reader_slo_status=blocked`. Layer attribution and hosted
telemetry are explicitly unavailable. Recovery control tests do not prove
current backup freshness, alert delivery, or an isolated hosted restore; the
workflow audit also identifies a missing integration-test path.

Keep the worker and original full queue stopped/paused. Do not run 10k/100k,
provider-volume, or full-queue traffic and do not make a production-capacity,
billing, or quota claim. Before any retry, an owner must supply the approved
opaque fixture and targets, establish a disposable cold-cache control, enable
fixed-label layer telemetry, repair or disposition the workflow path, and
authorize isolated recovery targets. The sanitized handoff and validation
records are under `artifacts/operations/reader-capacity-follow-up/`.

## Reader capacity and recovery runtime recheck — 2026-08-27

The local runtime baseline was re-established after Docker Desktop recovery.
Backend, reader, Caddy, frontend, Redis, and the isolated `restore-db` service
were healthy; the dedicated worker remained absent. Through local Caddy,
`/health/live` and `/health/ready` both returned HTTP 200 with empty bodies.
This closes the previously observed local Docker/Caddy outage only; it is not
private second-peer, hosted, or production availability evidence.

The current campaign is `camp-20260827T130658Z`. The selected reader gate is
`private_network`, but the queue and other-writer states remain unobservable,
no approved fixture/target binding was supplied, and no controlled cold-cache
reset exists. The bounded 1k invocation therefore produced explicit
unavailable cells, `reader_slo_status=blocked`, `path_profile_status=blocked`,
`telemetry_status=unavailable`, and
`production_capacity_claim=not_established`. Keep the worker/full queue
stopped/paused and preserve the remaining release-configuration, cross-source,
provider/bulk, hosted pool/cache/analytics, CDN propagation, credential
rotation, and dedicated-host gates in `docs/WORK.md`.

## Reader capacity and recovery runtime recheck - 2026-08-28

The current local split Compose runtime remained healthy for the bounded
recheck: backend, reader, Caddy, frontend, Redis, and restore-db were healthy,
while the dedicated worker was absent. Local Caddy returned HTTP 200 with
empty bodies for `/health/live` and `/health/ready`. This is local runtime
evidence only and does not establish hosted, private second-peer, or
production availability.

The current campaign is `camp-20260828T042235Z`. Its bounded stage report is
`reader-stage-1000/reader-stage-1000-20260828T042533Z.json`, with 60 required
route/cache cells, 30 quantified blockers, and no live samples. The selected
`private_network` gate remains blocked because the approved fixture/target,
queue/writer observation, and controlled cold-cache method are unavailable.
The 38 pre-remediation and stage-1000 telemetry records are joinable but
explicitly unavailable. Recovery freshness, alert delivery, hosted restore,
and provider/R2 telemetry remain unobserved; `production_capacity_claim` is
`not_established`.

## Pipeline async execution and capacity runbook checkpoint - 2026-08-24

The local audit completed the bounded persistence boundary, fixed-label runtime
telemetry, contributor-pool admission/accounting, fixture-only reader harness,
checkpoint footprint measurement, and modeled cost-envelope work. Evidence is
under `artifacts/capacity/`. Local tests do not authorize a live workload.

Before any live action, confirm the worker is intentionally running, the
original queues are not being used as a benchmark, the migration head and
readiness state are healthy, and an operator has recorded the traffic model,
SLO/error budget, provider/R2/egress ceilings, stop thresholds, telemetry
window, and rollback owner. Do not activate a contributor key or substitute an
owner key for the contributor pool. Keep `translation_provider_rps` and
`reader_http_rps` in separate reports.

Rollback order is: stop new load; stop worker admission; allow critical
terminal writes to settle within the bounded shutdown deadline; disable the
expansion gate; verify queue/lease state through application APIs; and record
the result. Do not edit queue rows, runtime JSON, checkpoint files, R2 objects,
or canonical content by hand. The current audit did not resume the worker or
the original queues.

The isolated R2 benchmark is unavailable when `TEST_R2_ENDPOINT` is absent.
The source canary and reader stages are operator/hosted gates; missing hosted
telemetry is an unavailable result, never a pass.

## Cloudflare development tunnel operation - 2026-08-28

The temporary external development origin is
`https://dev.dokushodo.online`. Cloudflare manages the `dokushodo-dev`
tunnel configuration and its single development DNS route; the production
apex and `www` records are not part of this operation. The tunnel forwards to
the existing internal Caddy service at `http://caddy:80` on `novelai-net`.

The connector token is stored only in the ignored local file
`deploy/.cloudflared/dokushodo-dev.token` and is mounted as a Compose secret.
Do not print, commit, copy, or place it in an environment example. If the
token is exposed, rotate it through the Cloudflare control plane before
restarting the connector.

Use the explicit service target below for a restart; a bare Compose `up`
also includes the worker service, which must remain stopped while the reader
capacity and recovery gates are blocked:

```powershell
docker compose --env-file deploy/.env -f deploy/compose.yml up -d --no-build cloudflared
docker compose --env-file deploy/.env -f deploy/compose.yml stop --timeout 0 worker
```

Verify the connector with `docker compose ... ps -a` and the Cloudflare MCP
tunnel/DNS read path, then verify the real development URL. A healthy tunnel
and HTTP smoke result do not authorize provider work, the original full
queue, recovery writes, or a production launch.
