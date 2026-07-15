# Data Recovery Runbook

Procedures for storage backups, database snapshotting, and system recovery.

---

## Backup Generation

Backup archives are written to local disk. Only file storage domains (novels, metadata, translations, assets) are packaged by `BackupManager`.

### Scheduled Backups

Scheduled backups run via the asyncio-based scheduler loop when `BACKUP_ENABLED=true`. The schedule is controlled by:

- `BACKUP_SCHEDULE_CRON` (default `0 2 * * *` — daily at 02:00)
- `BACKUP_TIMEZONE` (default `UTC`)

Backups use a multi-process file lock (`InterProcessFileLock`) to prevent concurrent backup runs. The lock file lives at `<backups_dir>/.backup.lock`.

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

**Notice:** If `STORAGE_BACKEND=s3` is active with R2, local backup generation is disabled. Use R2 lifecycle rules, cross-region replication, or external bucket snapshot procedures for R2 backups.

---

## R2 Storage Recovery

When using Cloudflare R2 (`STORAGE_BACKEND=s3` with R2 endpoint), recovery differs from filesystem:

### R2 Backup Options

1. **R2 Lifecycle Rules**: Configure object versioning or transition rules in the Cloudflare dashboard.
2. **Cross-Region Replication**: Replicate to a backup bucket in another region.
3. **Manual Bucket Snapshot**: Use `aws s3 sync` or boto3 to copy objects to a backup prefix:
   ```bash
   aws s3 sync s3://dokushodo/ s3://dokushodo-backup/$(date +%Y-%m-%d)/ \
     --endpoint-url=https://<ACCOUNT_ID>.r2.cloudflarestorage.com
   ```

### R2 Restore Procedure

1. **Identify backup source**: Determine the backup prefix (e.g. `backups/2026-07-14/`)
2. **Copy objects back to production prefix**:
   ```bash
   aws s3 sync s3://dokushodo/backups/2026-07-14/ s3://dokushodo/ \
     --endpoint-url=https://<ACCOUNT_ID>.r2.cloudflarestorage.com
   ```
3. **Rebuild catalog projections**: `POST /api/admin/catalog/rebuild`
4. **Verify**: Run smoke checks, spot-check novel metadata and chapter content

Never restore into the production prefix without first verifying the backup contents against the expected artifact index (see `docs/storage-contract.md`).

---

## Database Snapshotting

To dump database-owned tables (glossary, users, reviews, audit logs), execute standard PostgreSQL utilities:

```bash
pg_dump -U novelai -d novelai -t glossaries -t users -t audit_logs > db_snapshot.sql
```

---

## System Restore Sequence

If a storage or database failure occurs, execute recovery in this sequence:

1. **Restore storage files:** Re-deploy the novel library storage folder (`storage/novel_library/`) from the latest backup zip.
2. **Restore Postgres tables:** Apply the database snapshot:
   ```bash
   psql -U novelai -d novelai -f db_snapshot.sql
   ```
3. **Rebuild derived catalog state:** Relational `Novel` and `Chapter` database rows are derived projections. Trigger a catalog sync to rebuild them:
   ```bash
   POST /api/admin/catalog/rebuild
   ```
   This reads all metadata files under `storage/novel_library/` and updates Postgres tables.

---

## Canonical Ownership

See [`docs/storage-contract.md`](../storage-contract.md) for the full canonical ownership matrix and restore rules.
