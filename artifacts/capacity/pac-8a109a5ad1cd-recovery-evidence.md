# Recovery verification evidence

Date: 2026-08-24 (local execution)

This record contains sanitized outcomes only. No credential, database URL,
object key, source URL, or provider payload is included.

## PostgreSQL backup and isolated restore

- The backend image was rebuilt successfully with the pinned PostgreSQL 18
  client tools.
- The disposable `restore-db` Compose service was healthy before the drill.
- The encrypted custom-format PostgreSQL backup was created successfully in
  the independent R2 database-backup target.
- The latest committed backup was downloaded, decrypted, checksum-checked,
  restored into the isolated `restore-db` target, and verified successfully.
- Restore verification reported 37 public tables and 0 invalid constraints;
  the Alembic metadata was present and matched the backup manifest.
- `DATABASE_BACKUP_URL` is now present exactly once in both real environment
  files, synchronized from the configured migration connection under the
  previously authorized local credential-copy rule. The second persisted
  backup/restore run succeeded without a process override.

Sanitized command result:

```text
backup_status=succeeded
backup_id_present=true
restore_status=succeeded
restore_backup_id_present=true
public_tables=37
invalid_constraints=0
alembic_head_present=true
persisted_backup_url=true
```

## Independent R2 object snapshot

- The latest committed snapshot manifest was read from the independent R2
  target.
- Every referenced backup object was read and verified against its recorded
  size and SHA-256 digest.

Sanitized command result:

```text
latest_present=true
snapshot_id_present=true
files_count=980
size_bytes=4022175
verified=true
```

These results establish local backup and restore evidence. They do not claim
hosted reader-load capacity, provider quota capacity, CDN/origin acceptance,
or production-scale telemetry.
