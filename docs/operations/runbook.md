# Operations Runbook

Operational checklists for monitoring service health, worker status, and log parameters.

---

## Health Check Observability

Current health endpoints are static and do not perform real dependency probes:

- `GET /health` or `GET /api/health`: Returns `{"status": "ok"}`.
- `GET /api/admin/health`: Returns static admin health.
- `GET /api/public/health`: Returns static public health.

Real liveness/readiness probes (database, storage, worker) are planned under Milestone 2a (DEBT-001). Once implemented, the following endpoints will be available:

- `GET /health/live` or `GET /api/health/live`: Liveness check. Returns `200 OK` if the FastAPI process executes handlers.
- `GET /health/ready` or `GET /api/health/ready`: Readiness check. Returns `200 OK` if all database and storage connectivity checks succeed. Returns `503 Service Unavailable` on connection failure.

Planned diagnostics payload format (no credentials or tracebacks exposed):

```json
{
  "status": "healthy",
  "checked_at": "2026-07-12T21:00:00Z",
  "checks": {
    "database": {
      "status": "healthy",
      "latency_ms": 1.2
    },
    "storage": {
      "status": "healthy",
      "latency_ms": 4.5
    },
    "worker": {
      "status": "healthy",
      "last_tick_seconds_ago": 15
    }
  }
}
```

---

## Worker Heartbeat Monitoring

To verify the in-process worker activity:

1. Query `GET /api/admin/worker` (restricted to owner role).
2. Check `last_tick_at` timestamp.
3. If `last_tick_at` is older than `WORKER_HEARTBEAT_MAX_AGE_SECONDS`, mark the node degraded.

---

## Manual Invalidation actions

If translation cache needs clearing for a specific novel ID, run the invalidation task:

```bash
# REST API call (authenticated as owner)
POST /api/admin/novels/{novel_id}/cache/invalidate
```
This drops matching files under `storage/novel_library/cache/` to force new provider requests.

---

## Backup and Recovery

Scheduled and manual backup endpoints are planned under Milestone 2c (DEBT-010). Once implemented:

- `POST /api/admin/backups`: Owner-only manual backup trigger.
- Scheduled backups run based on `BACKUP_SCHEDULE_CRON`.

See [`docs/operations/data-recovery.md`](data-recovery.md) for restore procedures.
