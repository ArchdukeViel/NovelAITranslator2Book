# design.md

# Design: Deployment Production Hardening

## Overview

`deployment-production-hardening` defines the production deployment guardrails needed before public launch.

The project now has public reader features, admin operations, background workers, storage, exports, backups, notifications, analytics, rate limits, and takedown handling. Production deployment must be hardened so environment configuration, secrets, network boundaries, storage, database migrations, worker processes, TLS/proxy headers, observability, backups, and rollback behavior are safe and predictable.

This spec does not choose a specific hosting provider. It defines the checks and implementation hooks required for any production environment.

## Goals

* Define production environment configuration requirements.
* Validate required secrets and environment variables at startup.
* Harden CORS, cookies, auth, CSRF, and security headers.
* Support trusted reverse proxy/TLS behavior.
* Ensure database migrations are safe in production.
* Ensure workers, queues, schedulers, and maintenance jobs run predictably.
* Ensure object storage/public storage paths are correctly configured.
* Ensure backup, restore, and retention configuration is production-ready.
* Ensure logging, health checks, metrics, and alerts are enabled.
* Add deploy checklist and rollback procedure.
* Add tests and startup checks for production misconfiguration.

## Non-goals

* No specific cloud provider migration.
* No Kubernetes-only design.
* No full infrastructure-as-code implementation unless already used.
* No paid monitoring vendor requirement.
* No complete zero-downtime deployment system if current stack cannot support it.
* No new business features.
* No rewriting CI/CD from scratch.
* No legal/compliance certification.

## Production readiness principles

Production deployment should follow these rules:

```text id="4g8hzt"
fail fast on dangerous misconfiguration
never use development secrets in production
never expose admin or private storage publicly
serve public content only through approved public paths
protect auth cookies and sessions
run migrations intentionally
run workers separately from web process when required
make health/readiness checks accurate
log safely without secrets
support rollback
document operator steps
```

## Environment modes

Define explicit app environment modes:

```text id="xcrj8v"
development
test
staging
production
```

Recommended variable:

```text id="x4y6y6"
ENV=production
```

Rules:

```text id="ogjz5i"
production disables debug mode
production requires strong secrets
production requires explicit public site URL (PUBLIC_FRONTEND_URL)
production requires secure cookie settings (SESSION_SECRET_KEY)
production requires trusted proxy configuration if behind proxy
production must not use in-memory-only critical stores unless explicitly single-node
```

## Required production configuration

Recommended production config groups:

```text id="d0x0u2"
app identity
public URLs
database
queue/Redis
object storage
auth/session
CORS/CSRF
rate limits
email/notification delivery
backups
health/metrics
logging
scheduler/worker settings
export settings
analytics/privacy settings
```

Required variables should be validated at startup.

Example required production variables:

```text id="uzaynd"
APP_ENV=production
PUBLIC_SITE_URL=https://example.com
DATABASE_URL=...
SECRET_KEY=...
SESSION_SECRET=...
CORS_ALLOWED_ORIGINS=https://example.com
TRUSTED_PROXY_CIDRS=...
OBJECT_STORAGE_BUCKET=...
OBJECT_STORAGE_PUBLIC_BASE_URL=...
BACKUP_ENABLED=true
RATE_LIMIT_ENABLED=true
```

Adjust names to project conventions.

## Startup configuration validation

Add a production config validator.

Recommended component:

```text id="3swpqh"
ProductionConfigValidator
```

Validation categories:

```text id="x8eh1y"
missing required secrets
weak/default secrets
debug mode enabled
insecure cookies
wildcard CORS
unsafe trusted proxy config
missing public URL
misconfigured storage
missing database/queue URL
backup disabled or incomplete
rate limit disabled
admin setup missing
```

Severity:

```text id="g4tx5f"
fatal
warning
info
```

Production should fail startup on fatal issues.

## Secrets hardening

Secrets must not be checked into source, logs, or public config.

Required secret categories:

```text id="3c9ixr"
application secret key
session secret
JWT/signing secret if used
database password
Redis/queue password
object storage credentials
email provider credentials
LLM/provider API keys
backup encryption key if used
analytics salt/hash secret
rate-limit hash salt
OAuth/client secrets if used
```

Rules:

```text id="7i33sv"
no default secrets in production
no placeholder secrets in production
no secrets in frontend bundle
no secrets in logs
no secrets in generated docs/artifacts
support secret rotation procedure
```

## TLS and reverse proxy

The app should assume TLS is terminated either by the app or a trusted proxy.

Rules:

```text id="vn5mqc"
production public URLs use https
secure cookies enabled
HTTP-to-HTTPS redirect at proxy or app
trusted forwarded headers only from configured proxies
correct client IP resolution for rate limits/logs
host header validation where supported
```

Recommended variables:

```text id="yad6d7"
PUBLIC_SITE_URL=https://example.com
TRUSTED_PROXY_CIDRS=...
TRUST_X_FORWARDED_FOR=true
TRUST_X_FORWARDED_PROTO=true
ALLOWED_HOSTS=example.com
```

## CORS and CSRF

Production CORS must be restrictive.

Rules:

```text id="c0sufo"
no wildcard CORS with credentials
allowed origins explicit
admin APIs only accessible from approved origins
CSRF protection enabled for cookie-auth write actions where applicable
preflight behavior tested
```

Recommended:

```text id="eeoyk4"
CORS_ALLOWED_ORIGINS=https://example.com
CSRF_ENABLED=true
CSRF_TRUSTED_ORIGINS=https://example.com
```

## Cookie and session security

Rules:

```text id="o955wn"
Secure cookies in production
HttpOnly session cookies
SameSite=Lax or Strict according to auth flow
reasonable session expiration
session revocation works
disabled users cannot keep using old sessions
```

If cross-site auth is required, document why `SameSite=None` is needed and require Secure.

## Security headers

Recommended headers:

```text id="pbb3et"
Strict-Transport-Security
X-Content-Type-Options: nosniff
X-Frame-Options or CSP frame-ancestors
Referrer-Policy
Permissions-Policy
Content-Security-Policy
```

CSP can start in report-only mode if the frontend has inline scripts that need cleanup.

Recommended minimum:

```text id="8tvcyg"
X-Content-Type-Options: nosniff
Referrer-Policy: strict-origin-when-cross-origin
X-Frame-Options: DENY
```

## Database migrations

Production migration behavior must be explicit.

Rules:

```text id="ibr9vb"
migrations run before app version serves traffic
migration failures stop deployment
destructive migrations require backup/approval
schema version visible in health/admin status
rollback plan documented
long migrations reviewed before production
```

Migration process options:

```text id="ng6iz8"
manual migration command before deploy
CI/CD migration step
release job
app startup migration disabled in production unless explicitly safe
```

Recommended:

```text id="daxidf"
do not run automatic destructive migrations from every web process
```

## Workers, queues, and schedulers

Production must define process roles:

```text id="mkbl5q"
web
worker
scheduler
maintenance
backup
```

Rules:

```text id="mvecj6"
web process should not run duplicate schedulers unless designed
workers have concurrency limits
queue connection configured
scheduler locks enabled
maintenance cron enabled intentionally
backup scheduler enabled intentionally
health checks detect stale workers
```

Recommended variables:

```text id="t3xrrj"
WORKER_CONCURRENCY=...
SCHEDULER_ENABLED=true
MAINTENANCE_ENABLED=true
BACKUP_ENABLED=true
```

## Storage hardening

Storage must separate private and public objects.

Rules:

```text id="muc11b"
private source files are not publicly readable
private translations/drafts are not publicly readable
public reader projections are in public-safe location
public export artifacts are served only through authorized/safe paths
signed URLs are short-lived if used
storage bucket names and paths are not leaked unnecessarily
takedown invalidates public storage/projection access
```

Recommended storage checks:

```text id="4avlxz"
object storage credentials valid
public base URL configured
bucket permissions match policy
backup storage separate from public storage
temporary storage cleanup enabled
```

## Public reader deployment safety

Production public reader requires:

```text id="b5ozxa"
public path/auth contract enforced
public reader availability checks enabled
graceful degradation configured
SEO/sitemap configured
rate limits enabled
takedown enforcement enabled
public cache respects publication/takedown state
```

## Backup and restore readiness

Production must not launch without backup policy.

Required:

```text id="q43gu9"
scheduled backups enabled or explicit documented exception
backup target configured
backup retention configured
backup status visible
restore drill procedure documented
restore verification runnable
backup failure visible in health/admin status
```

## Observability

Production observability should include:

```text id="o8ujr8"
structured logs
request IDs
health/readiness endpoints
metrics summary
worker/scheduler status
backup status
maintenance status
rate-limit/abuse logs
frontend error logs if available
```

Logs must avoid:

```text id="dnokvh"
secrets
tokens
passwords
raw prompts
raw source text
raw translated text
private legal details
signed URLs
```

## Health checks

Deployment should use:

```text id="wu2sun"
/health/live
/health/ready
/admin/health
```

Production readiness should check:

```text id="618gyl"
database reachable
migrations current
queue reachable
storage reachable
critical config valid
workers/schedulers if required
backup freshness warning if configured
```

Liveness must remain lightweight.

## Release and rollback

Deployment must document:

```text id="lstxcv"
how to deploy
how to run migrations
how to verify health
how to pause workers/schedulers
how to rollback app version
how to restore database/storage if migration corrupts data
how to invalidate public caches
how to disable public features with kill switches
```

Recommended kill switches:

```text id="c4v375"
PUBLIC_READER_ENABLED
PUBLIC_GLOSSARY_ANNOTATIONS_ENABLED
ANALYTICS_ENABLED
EXPORT_ENABLED
SCHEDULER_ENABLED
MAINTENANCE_ENABLED
TAKEDOWN_INTAKE_ENABLED
```

Use actual project variable names.

## CI/CD deployment gates

Recommended production gates:

```text id="jk8xah"
tests pass
lint/type checks pass
migration dry-run or validation passes
production config validation passes
backup status checked
security smoke checks pass
build artifact created once and promoted
```

## Production smoke tests

After deployment, verify:

```text id="8j7s39"
public homepage/reader loads
public chapter loads
login works
admin health page works
queue worker can process a small job
storage read/write works
export generation works if enabled
backup status is healthy
sitemap/robots available
rate limit returns 429 when exceeded in controlled test
takedown tombstone works in test fixture if safe
```

## Documentation

Required operator docs:

```text id="xx6vg9"
production environment variables
deployment steps
migration steps
worker/scheduler process roles
backup/restore procedure
health check URLs
rollback procedure
secret rotation procedure
public cache invalidation procedure
```

## Testing strategy

Tests should cover:

```text id="1sg7v7"
production config validation
weak/default secret rejection
wildcard CORS rejection with credentials
insecure cookie rejection
trusted proxy config behavior
security headers
health/readiness responses
migration status check
storage config validation
worker/scheduler config validation
backup config validation
public cache safety settings
```

## Rollout plan

1. Inventory production environment variables.
2. Add config validator.
3. Add security header middleware/config.
4. Harden CORS, cookies, proxy behavior.
5. Validate storage/public path config.
6. Validate database migration process.
7. Validate worker/scheduler process model.
8. Validate backups and restore drills.
9. Add smoke tests and deployment checklist.
10. Add rollback and kill-switch documentation.
11. Run staging deployment with production-like config.
12. Promote to production only after hardening checks pass.
