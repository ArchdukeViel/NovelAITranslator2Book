# Data Recovery Runbook

Procedures for storage backups, database snapshotting, and system recovery.

---

## Backup Generation

Backup archives are written to local disk. Only file storage domains (novels, metadata, translations, assets) are packaged by `BackupManager`.

Manual backup trigger (admin endpoint, planned under DEBT-010):
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

Scheduled backups run based on `BACKUP_SCHEDULE_CRON` (planned under DEBT-010).
**Notice:** If `STORAGE_BACKEND=s3` is active, backup generation is disabled. S3 storage requires external bucket snapshot procedures.

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
