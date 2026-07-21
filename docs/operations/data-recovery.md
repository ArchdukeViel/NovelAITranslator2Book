# Data Recovery Runbook

Procedures for storage backups, database snapshotting, and system recovery.

## Acceptance Status (updated 2026-07-22)

- Application-driven R2 snapshot creation, manifest-last commit, checksum verification, isolated restore, and least-privilege credential boundaries are verified live.
- Encrypted logical PostgreSQL backup and one clean PostgreSQL 17 restore are verified live.
- Two consecutive scheduler-created R2 snapshots are verified live. Each
  committed 16 objects and 381,808 source bytes, and a post-run restore read
  matched every recorded SHA-256 checksum.
- A scheduler-created encrypted logical database backup is committed in the
  independent R2 bucket and was automatically restored into a newly created
  PostgreSQL 17 target. Verification matched Alembic head `8b7f3d1a2c4e`, found
  30 public tables, and found zero invalid constraints.
- The hosted Supabase project subsequently migrated to repository head
  `9c2e4a6b8d0f` on 2026-07-22. That current schema verification is separate
  from—and does not retroactively change—the historical restore evidence at
  `8b7f3d1a2c4e` above.
- Alert cooldown and secret redaction now have direct regression coverage, and
  the opt-in hosted PostgreSQL/R2 suite passes with isolated artifacts cleaned.
  Pending operational evidence is limited to real stale/failure SMTP delivery
  and a successful hosted managed-services GitHub workflow.
- Provider lifecycle rules and retention locks are safeguards; independently restorable snapshots and database dumps remain the recovery sources of truth.

---

## Backup Generation

Filesystem deployments write local archives. S3/R2 deployments snapshot canonical `novels/` objects into an independent S3-compatible bucket.

### Scheduled Backups

Scheduled backups run through cron/timezone evaluation and a PostgreSQL-backed renewable lease when `BACKUP_ENABLED=true`. The schedule is controlled by:

- `BACKUP_SCHEDULE_CRON` (default `0 2 * * *` — daily at 02:00)
- `BACKUP_TIMEZONE` (default `UTC`)

Backups retain `InterProcessFileLock` for same-host filesystem safety. The database lease prevents duplicate work across hosts and expires automatically after a crashed process stops renewing it.

### Retention Policy

After each successful backup, retention is automatically applied:

- `BACKUP_RETENTION_COUNT` (default 5): Maximum backups to keep by count.
- `BACKUP_MIN_SUCCESSFUL_TO_KEEP` (default 3): Minimum successful backups always preserved regardless of age. The newest successful backup is never deleted.
- `BACKUP_MAX_AGE_DAYS` (default 30): Backups older than this are eligible for deletion when beyond the retention count.

Failed or offsite states do not erase local successful artifacts.

### Manual Backup

Manual backup trigger (admin endpoint):
```bash
POST /api/admin/backups
```
This queues a background backup activity. Response format:
```json
{
  "status": "queued",
  "activity_id": "maintenance_backup_0f8e9c"
}
```

**Notice:** With `STORAGE_BACKEND=s3`, a scheduled run succeeds only after the independent snapshot manifest is committed and every copied object has passed byte-length and SHA-256 verification. Lifecycle and bucket-lock rules remain safeguards rather than backup copies.

---

## R2 Storage Recovery

When using Cloudflare R2 (`STORAGE_BACKEND=s3` with R2 endpoint), recovery differs from filesystem:

### R2 Backup Requirements

1. **Independent destination**: Configure `BACKUP_S3_BUCKET` separately from `S3_BUCKET`, using target-scoped credentials.
2. **Least privilege**: Application CRUD, snapshot-source read, and backup-target read/write use different credentials. Verify exact bucket scopes in the Cloudflare dashboard because the connector cannot inspect token policies.
3. **Commit marker**: A snapshot is successful only when `<BACKUP_S3_PREFIX>/<snapshot-id>/manifest.json` exists and parses. Prefixes without a manifest are incomplete.
3. **Artifact verification**: The scheduler conditionally copies each inventoried source ETag, downloads the target bytes, and records SHA-256 checksums in the manifest.
4. **Retention safeguards**: Lifecycle rules may clean old snapshots, and bucket locks may protect the immutable backup prefix. Configure lifecycle deletion after the lock retention period.
5. **Manual fallback**: If the application scheduler is unavailable, use `aws s3 sync` or boto3 with separate source and target credentials:
   ```bash
   aws s3 sync s3://<production-bucket>/ s3://<backup-bucket>/<snapshot-id>/ \
     --endpoint-url=https://<ACCOUNT_ID>.r2.cloudflarestorage.com
   ```

### R2 Restore Procedure

1. **Identify backup source**: Select a verified snapshot from the independent backup location.
2. **Stage and inspect**: Restore into an isolated staging prefix first; compare the artifact index, counts, and representative checksums.
3. **Copy objects back to production prefix** only after verification:
   ```bash
   aws s3 sync s3://<backup-bucket>/<snapshot-id>/ s3://<production-bucket>/ \
     --endpoint-url=https://<ACCOUNT_ID>.r2.cloudflarestorage.com
   ```
4. **Rebuild catalog projections**: `POST /api/admin/catalog/rebuild`
5. **Verify**: Run smoke checks, spot-check novel metadata and chapter content, and record the drill result.

Never restore into the production prefix without first verifying the backup contents against the expected artifact index (see `docs/storage-contract.md`).

---

## Database Snapshotting

Free-plan Supabase recovery uses nightly logical exports independent of Supabase-managed backups. The admin runtime includes PostgreSQL 17 client utilities. Enable `DATABASE_BACKUP_ENABLED` to create encrypted, manifest-committed custom-format dumps under `database/` in the independent backup bucket.

For the monthly drill, provision a disposable PostgreSQL 17 database with `restore` in its database name, set `DATABASE_RESTORE_TARGET_URL`, and enable `DATABASE_RESTORE_VERIFICATION_ENABLED`. Never point the target at the source project. Success requires the manifest checksum, Alembic head, public tables, and constraint validation checks to pass.

The canonical Compose deployment includes `restore-db`, an isolated PostgreSQL 17 target named `novelai_restore_verify`. Set `DATABASE_RESTORE_PASSWORD` and use the matching internal `DATABASE_RESTORE_TARGET_URL`; production application traffic must never use this database.

For an emergency manual export, use PostgreSQL 17 tools and encrypt the result before durable storage:

```bash
pg_dump --format=custom --no-owner --no-privileges --schema=public "$DATABASE_URL" > db_snapshot.custom
```

---

## System Restore Sequence

If a storage or database failure occurs, execute recovery in this sequence:

1. **Restore storage files:** Re-deploy the novel library storage folder (`storage/novel_library/`) from the latest backup zip.
2. **Restore Postgres:** Decrypt the selected committed database artifact, restore it into a clean PostgreSQL 17 database with `pg_restore --no-owner --no-privileges`, then verify Alembic head, row counts, constraints, and representative queries before cutover.
3. **Rebuild derived catalog state:** Relational `Novel` and `Chapter` database rows are derived projections. Trigger a catalog sync to rebuild them:
   ```bash
   POST /api/admin/catalog/rebuild
   ```
   This reads all metadata files under `storage/novel_library/` and updates Postgres tables.

---

## Canonical Ownership

See [`docs/storage-contract.md`](../storage-contract.md) for the full canonical ownership matrix and restore rules.
