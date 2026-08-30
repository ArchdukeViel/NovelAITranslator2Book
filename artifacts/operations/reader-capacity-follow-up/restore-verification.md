# Isolated Restore Verification Record

Spec ID: reader-capacity-and-recovery-follow-up
Task: T-009
Observed UTC: 2026-08-29 (latest hosted run)

## Result

The original 2026-08-25 record was blocked because no operator-authorized
isolated hosted target had been supplied. Confirmation-gated test-only runs on
2026-08-28 and 2026-08-29 now prove the managed PostgreSQL/R2 backup and
isolated-restore path for the disposable test project and dedicated
non-production R2 targets. They do not establish production recovery
readiness.

## Evidence boundary

- The earlier review found that the workflow referenced the missing
  `backend/tests/integration/test_r2_snapshot_integration.py`. The source-level
  repair now invokes the existing
  `backend/tests/integration/test_r2_backup_integration.py` and the new
  `backend/tests/integration/test_r2_restore_integration.py`; its R2 variable
  names match the tests, and the managed PostgreSQL assertion tracks the
  current migration head. The repaired recovery workflow was subsequently
  executed at the candidate revision; its current result is recorded below.
- The earlier baseline did not name a disposable hosted database or isolated
  R2 target. The later authorized run used only the disposable managed test
  project, an ephemeral local restore database, and the dedicated
  non-production R2 target; no production target was opened or overwritten.
- The local verification commands passed:
  - `tools/pytest.ps1 backend/tests/test_database_backup_crypto.py backend/tests/test_r2_backup.py backend/tests/test_backup_service.py -q` — exit code 0, 15 passed.
  - `tools/pytest.ps1 backend/tests/test_backup_service.py backend/tests/test_database_backup_crypto.py backend/tests/test_health_service.py backend/tests/test_operator_alert_service.py backend/tests/test_scheduler_service.py -q` — exit code 0, 44 passed.

## Current non-production recovery checkpoint - 2026-08-28

The earlier confirmation-gated run
[`33182847311`](https://github.com/ArchdukeViel/NovelAITranslator2Book/actions/runs/33182847311)
passed backup creation, manifest/checksum verification, backup freshness,
isolated restore, Alembic-head verification, representative queries, public
isolation, R2 cleanup, temporary-role cleanup, and overall cleanup. The
sanitized artifact records 37 public tables, 37 RLS tables, zero invalid
constraints, and `production_mutation=none`.

The temporary confirmation variable was removed after the run and the
permanent managed-service test flag remains `false`. This is one current
non-production recovery proof; recurring production freshness, alert delivery,
production smoke, reader capacity, hosted telemetry, and production recovery
readiness remain open.

Production database, canonical R2 content, and public production routes remain
untouched.

## Latest non-production recovery checkpoint - 2026-08-29 UTC

The explicitly authorized test-only recovery workflow
[`33270802038`](https://github.com/ArchdukeViel/NovelAITranslator2Book/actions/runs/33270802038)
completed successfully in 1m51s at merged `main` commit
`01f106ade3700405f3f4a998a1c708ed7113505b`. Its sanitized artifact is
`managed-database-recovery-evidence-33270802038`.

The artifact reports successful backup creation, healthy freshness,
manifest/checksum verification, isolated restore, representative queries,
Alembic-head verification, public isolation, R2 cleanup, temporary-role
cleanup, and overall cleanup. It records 37 public tables, 37 RLS tables, zero
invalid constraints, and `production_mutation=none`. Independent Supabase MCP
SQL found zero fixture novel rows and zero fixture chapter rows. Cloudflare MCP
read-only listings found zero objects under `novels/123/` in `test-dokushodo`
and zero `recovery-` objects in `test-dokushodo-backup`.

This is current non-production restore evidence and changes the recovery
disposition to `partial`, not `complete`: recurring schedule/retention
evidence, stale/failure alert transition and delivery, production smoke, and
production recovery readiness remain open. No production database, canonical
R2 content, public route, secret, or repository variable was changed.
