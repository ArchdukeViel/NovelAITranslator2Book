# Operations

Solo-owner runbook for health, maintenance, backup, recovery, incidents, and reader budgets. For topology, environment setup, and release procedures, see [`DEPLOYMENT.md`](DEPLOYMENT.md). Never record secret values in evidence.

## Health

| Endpoint | Expected behavior |
|---|---|
| `GET /health/live` | Process-only, unauthenticated, always 200; no dependency calls. |
| `GET /health/ready` | Redacted, short-TTL cached/single-flight DB/lightweight-storage/worker/disk probes; 503 when the cached result is unhealthy. |
| `GET /api/admin/health` | Owner-only detailed but redacted probe status and latency. |

States: `healthy`, `degraded`, `unhealthy`. Investigate stale worker heartbeat,
DB connectivity, storage reachability/capacity, and disk before restart. Public
readiness does not perform a mutating storage probe or S3 usage enumeration;
`/api/admin/health` remains the fresh owner diagnostic for those checks.
Public health output never includes paths, hosts, credentials, or traces.

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
- Local filesystem writes/retention also use `InterProcessFileLock` where needed.
- Generation pointer activation uses `compare_and_swap_active_pointer`: the
  filesystem backend wraps the read-compare-write in an `InterProcessFileLock`;
  the S3 backend uses a conditional `PUT` with `If-Match`/`If-None-Match`.
  Concurrent activations cannot silently overwrite each other; the loser
  receives `GenerationConflictError` and must roll its stage back.
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
absence remains explicit and no filesystem cache may manufacture success.

Manual novel cache invalidation:

```text
POST /api/admin/novels/{novel_id}/cache/invalidate
```

## Backups

### Object storage

- `BACKUP_ENABLED=true` enables scheduled snapshots.
- R2/S3 production snapshots require independent target bucket and credentials.
- Application CRUD, snapshot-source read, and backup-target write credentials
  remain separate and least privilege.
- Snapshot success requires manifest-last commit plus byte-length and SHA-256 verification.
- Retention preserves newest successful backup and
  `BACKUP_MIN_SUCCESSFUL_TO_KEEP`; lifecycle/locks are safeguards, not copies.

Manual trigger:

```text
POST /api/admin/backups
```

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
& uv sync --extra documents --extra dev --extra db --extra auth --extra s3 --extra worker --extra gemini --extra test
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

## Contributor Credential Operations

For an enabled contributor deployment, verify:

1. Confirm `PROVIDER_CREDENTIAL_ENCRYPTION_KEY` is present and not the owner
   bootstrap or session secret.
2. Confirm the current `CONTRIBUTOR_CONSENT_VERSION` is the version shown by
   the frontend and record any consent copy change.
3. Confirm per-credential RPM/TPM/RPD limits and the quota-state directory are
   writable only by the backend runtime.
4. Apply Alembic migrations with the elevated migration role before starting
   the long-running services; the runtime role must have the required DML but
   should not be granted broad schema-DDL privileges.
5. Verify the user route returns masked metadata only, unsafe methods reject
   missing CSRF, and a user cannot read or mutate another user's credential.

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
