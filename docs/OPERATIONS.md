# Operations

Solo-owner runbook for health, maintenance, backup, recovery, incidents, and reader budgets. For topology, environment setup, and release procedures, see [`DEPLOYMENT.md`](DEPLOYMENT.md). Never record secret values in evidence.

## Health

| Endpoint | Expected behavior |
|---|---|
| `GET /health/live` | Process-only, unauthenticated, always 200; no dependency calls. |
| `GET /health/ready` | Bounded DB/storage/worker/disk probes; 503 when any probe is unhealthy. |
| `GET /api/admin/health` | Owner-only detailed but redacted probe status and latency. |

States: `healthy`, `degraded`, `unhealthy`. Investigate stale worker heartbeat,
DB connectivity, storage writes/capacity, and disk before restart. Public health
output never includes paths, hosts, credentials, or traces.

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

### Database

- `DATABASE_BACKUP_ENABLED=true` creates PostgreSQL 17 custom-format dumps of
  application-owned schema.
- Dumps are streamed through AES-256-GCM encryption and committed independently.
- No plaintext dump remains after successful or failed handling.
- Restore verification uses a disposable PostgreSQL 17 database whose name
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
tooling (Python ≥ 3.13). To rebuild after schema changes, dependency
upgrades, or accidental deletions:

```powershell
py -3.13 -m venv .venv
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
