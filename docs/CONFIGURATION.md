# Configuration

Configuration contract. Exact fields/defaults live in
`backend/src/novelai/config/settings.py`; examples live in `.env.example` and
`deploy/.env.example`. Do not duplicate every tuning default here.

## Loading

- Canonical environment selector: `ENV`; never introduce `APP_ENV`.
- Pydantic settings reads root `.env`; process environment overrides it.
- Compose reads `deploy/.env` and requires external `DATABASE_URL`.
- `MIGRATION_DATABASE_URL` optionally gives the one-shot Alembic service a
  separate elevated role; long-running processes continue using `DATABASE_URL`.
- Real `.env*` files are untracked; only example templates are committed.
- Settings are read through `novelai.config.settings.settings`; no direct
  `os.environ` outside settings module.

## Minimum Local Configuration

```dotenv
ENV=development
DATABASE_URL=postgresql+psycopg://user:password@localhost:5432/novelai
SESSION_SECRET_KEY=<random>
OWNER_BOOTSTRAP_SECRET=<random>
PROVIDER_DEFAULT=gemini
AUTH_EMAIL_DELIVERY_MODE=noop
```

Generate secrets with `python -c "import secrets; print(secrets.token_hex(32))"`.

## Required Production Settings

| Area | Required contract |
|---|---|
| Runtime | `ENV=production`; `DEPLOY_MODE=monolith|split`. |
| Database | `DATABASE_URL` uses `postgresql+psycopg://`; TLS mode and connection budget reviewed. |
| Sessions | Strong `SESSION_SECRET_KEY`, `OWNER_BOOTSTRAP_SECRET`, HTTPS cookie behavior. |
| Public URL | HTTPS `PUBLIC_FRONTEND_URL`; exact OAuth redirect when OAuth enabled. |
| Origins | Explicit `WEB_CORS_ORIGINS`, `CSRF_TRUSTED_ORIGINS`, `ALLOWED_HOSTS`; no wildcard with credentials. |
| Provider | Gemini key/model configuration; production never uses dummy provider. |
| Credentials | `PROVIDER_CREDENTIAL_ENCRYPTION_KEY` before storing provider keys. |
| Storage | `STORAGE_BACKEND=filesystem|s3`; complete S3/R2 endpoint/bucket/credentials for `s3`. |
| Distributed runtime | Redis URL and Redis rate limiter for split/multi-instance mode. |

## Storage and Recovery Groups

Application S3/R2 uses `S3_*`. Independent object snapshots use `BACKUP_S3_*`
plus separate read-only `SNAPSHOT_SOURCE_S3_*` credentials. Application bucket,
backup bucket, and prefixes must not collapse into one unrestricted scope.

`BACKUP_ENABLED` controls object snapshots. `DATABASE_BACKUP_ENABLED` controls
encrypted PostgreSQL dumps and requires backup encryption key, independent DB
prefix, and PostgreSQL 17 client tools. `DATABASE_RESTORE_VERIFICATION_MAX_AGE_DAYS`
(default 32) sets max days since last successful restore before probe goes unhealthy.
Restore verification requires an explicit disposable target whose database name
contains `restore`.

Schedules use cron plus IANA timezone. Cross-instance jobs use configured lease
duration and renewal; do not tune lease below realistic job duration without tests.

## Runtime Groups

- `JOB_WORKER_ENABLED`: in-process activity worker.
- `WEB_RATE_LIMITER_BACKEND=memory|redis`: memory only for single instance.
- `REDIS_URL`: shared rate limiting and distributed queue where enabled.
- `TRANSLATION_*`: chunking, concurrency, attempts, scheduler/model policy.
- `PROVIDER_GEMINI_*`: key, default model, fallback models.
- `TRANSLATION_CACHE_*`: exact cache enablement, TTL, size.
- `MAINTENANCE_*`: schedule and dry-run controls.
- `HEALTH_*`: bounded probe timeout and disk thresholds.
- `OPERATOR_ALERT_*`: alert enable, email, failure threshold, cooldown, stale backup hours.
- `PRODUCTION_BASE_URL`: GitHub Actions secret (not a process env var) feeding the
  best-effort five-minute external HTTPS monitor. Set in GitHub secrets, never
  in `.env` files.
- `GITGUARDIAN_API_KEY`: GitHub Actions secret (not a process env var) supplying
  `.github/workflows/gitguardian.yaml`. Set in GitHub secrets, never in `.env` files.

Use source defaults unless measured behavior justifies change.

## Auth and Email

Google OAuth requires client ID, client secret, and exact redirect URI. One
deployment uses one configured redirect URI; provider client may allow several.
Public OAuth/password registration creates users only.

Email defaults to `AUTH_EMAIL_DELIVERY_MODE=noop`. SMTP requires host, port,
credentials, sender, TLS/SSL choice, tested domain, operator recipient where
alerts are enabled, and acceptance gates in `WORK.md`.

## Profiles

| Profile | Key choices |
|---|---|
| Local | `ENV=development`, memory limiter allowed, worker optional, noop email. |
| Preview | HTTPS session, exact domains/OAuth, development-only R2; worker/scheduler/backups/SMTP disabled on sleeping free host. |
| Production | `ENV=production`, always-on backend, Redis, private R2 scopes, backups, monitoring, tested alerts. |

## Request Body Limits

App bounds every API request body, validates JSON mutation content types, and
emits route-specific 413/415 responses. Caddy outer guard
(`request_body { max_size 34MiB }`) emits 413 before routing.

| Setting | Group | Max | Accepts |
|---|---|---|---|
| `WEB_MAX_AUTH_BODY_BYTES` | Auth (login, register) | 64 KiB | `application/json`, `application/*+json` |
| `WEB_MAX_JSON_BODY_BYTES` | General JSON API | 1 MiB | `application/json`, `application/*+json` |
| `ANALYTICS_INGEST_MAX_BODY_BYTES` | Analytics events | 32 KiB (configurable) | `application/json` |
| `WEB_MAX_DOCUMENT_BODY_BYTES` | Reserved doc upload | 32 MiB | – (no route) |

App enforcement authoritative for direct Uvicorn access.

## Security

Never print, hash, paste, or commit secret values, DB URLs, provider keys, SMTP
passwords, storage credentials, or encryption keys. Presence checks report only
`present=true|false`. Rotate compromised secrets immediately. Session-secret
rotation logs out users; credential-encryption rotation requires re-encryption.

## Validation

- Production startup runs fail-closed configuration validation.
- Apply migrations from `backend`: `alembic -c alembic.ini upgrade head`.
- Verify OAuth URI exactly, TLS DB connection, explicit origins/hosts, Redis
  sharing, R2 scope separation, and restore target isolation.
- When adding a setting, update `settings.py`, example env files, deployment
  wiring, focused tests, and this file only when operator understanding changes.
