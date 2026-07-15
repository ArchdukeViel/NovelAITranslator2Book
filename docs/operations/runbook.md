# Operations Runbook

Operational checklists for monitoring service health, worker status, and log parameters.

---

## Health Check Observability

Health endpoints perform real dependency probes (M2a, DEBT-001 resolved):

- `GET /health/live`: Liveness check. Returns `200 OK` with `{"status": "ok", "service": "novelai", "timestamp": "..."}`. No DB/storage/worker calls. Use for container liveness probes.
- `GET /health/ready`: Readiness check. Returns `200 OK` if all probes are healthy or degraded. Returns `503 Service Unavailable` if any probe is unhealthy. Probes: database (`SELECT 1`), storage (temp file write+delete), worker (runner status), disk space.
- `GET /api/admin/health`: Owner-only detailed diagnostics. Returns probe status, latency (ms), safe message, and checked timestamp per probe. Still redacted — no raw exceptions, stack traces, credentials, or paths.

Public-safe readiness response format (no credentials or tracebacks exposed):

```json
{
  "status": "healthy",
  "service": "novelai",
  "timestamp": "2026-07-14T12:00:00Z",
  "checks": {
    "database": {"status": "healthy"},
    "storage": {"status": "healthy"},
    "worker": {"status": "healthy"},
    "disk": {"status": "healthy"}
  }
}
```

Admin health response format (owner-only, includes latency and messages):

```json
{
  "status": "healthy",
  "service": "novelai",
  "timestamp": "2026-07-14T12:00:00Z",
  "checks": {
    "database": {"status": "healthy", "message": "Database responsive", "latency_ms": 1, "checked_at": "..."},
    "storage": {"status": "healthy", "message": "Storage responsive", "latency_ms": 4, "checked_at": "..."},
    "worker": {"status": "degraded", "message": "Worker not running", "latency_ms": 0, "checked_at": "..."},
    "disk": {"status": "healthy", "message": "Disk space sufficient", "free_percent": 75, "latency_ms": 0, "checked_at": "..."}
  }
}
```

Probe states: `healthy`, `degraded`, `unhealthy`. Disk probe reports `degraded` below `HEALTH_DISK_WARNING_FREE_PERCENT` (default 15%) and `unhealthy` below `HEALTH_DISK_CRITICAL_FREE_PERCENT` (default 5%).

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

---

## Redis Rate Limiter (M3)

Production uses `WEB_RATE_LIMITER_BACKEND=redis` for multi-instance safety. Two independent app processes sharing the same Redis see the same rate-limit counters — a burst on one instance blocks the same client on the other.

If Redis is unreachable, the rate limiter **fails closed** — requests raise `RuntimeError` rather than silently falling back to memory. Ensure Redis healthcheck passes before app services start (enforced via `depends_on: redis: condition: service_healthy` in compose.yml).

### Verification

```python
# From inside any backend container:
from novelai.infrastructure.http.rate_limiter import RedisRateLimiter
limiter = RedisRateLimiter(limits={"test": 3}, window_seconds=60)
print(limiter.hit("client1", "test"))  # True
print(limiter.hit("client1", "test"))  # True
print(limiter.hit("client1", "test"))  # True
print(limiter.hit("client1", "test"))  # False (blocked)
```

---

## Security Headers (M3)

Production responses include:
- `X-Content-Type-Options: nosniff`
- `Referrer-Policy: strict-origin-when-cross-origin`
- `X-Frame-Options: DENY`
- `Strict-Transport-Security` (HSTS, only when `HSTS_MAX_AGE_SECONDS > 0`)

Trusted proxy forwarded headers (`X-Forwarded-For`) are honored only when `TRUSTED_PROXY_CIDRS` includes the proxy's CIDR. Spoofed forwarded headers from untrusted clients are ignored.

---

## Secret Rotation

See [`docs/operations/deployment.md`](deployment.md#secret-rotation) for full secret rotation procedures including `SESSION_SECRET_KEY`, R2 API tokens, and `OWNER_BOOTSTRAP_SECRET`.
