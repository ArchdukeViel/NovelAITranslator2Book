# Deployment

Canonical deployment topology, release, rollback, and GitHub-control contract. For runtime health probes, backup recovery, and incident runbooks, see [`OPERATIONS.md`](OPERATIONS.md).

## Topology

`deploy/compose.yml` is canonical:

| Service | Purpose |
|---|---|
| `caddy` | TLS, compression, security headers, ordered routing. |
| `frontend` | Next.js public/admin UI, port 3000. |
| `backend` | Admin/auth/user API, worker/scheduler, port 8000. |
| `reader` | Guest public API, port 8001. |
| `migrate` | One-shot Alembic migration before APIs. |
| `redis` | Shared limits, queue, coordination where enabled. |
| `restore-db` | Isolated disposable PostgreSQL 17 restore verifier. |

PostgreSQL is external; Compose does not provision primary DB. Never run
migrations inside long-running backend containers.
Use `MIGRATION_DATABASE_URL` for a dedicated schema-owner/migrator role and
`DATABASE_URL` for the least-privilege long-running application role.
Migration `c7d9e1f3a5b2` maintains `novelai_app`, a stable NOLOGIN privilege
role with explicit application DML and RLS policies. Provision the separate
`novelai_runtime` LOGIN member with `backend/sql/provision_novelai_runtime.sql`;
rotate that member password without changing schema ownership or grants.

## Routing

```text
/health/*      -> backend:8000
/api/admin/*   -> backend:8000
/api/auth/*    -> backend:8000
/api/user/*    -> backend:8000
/api/public/*  -> reader:8001
everything else -> frontend:3000
```

`DEPLOY_MODE=monolith` serves all routers in one process. `split` uses admin and
reader entry points and requires shared Redis for distributed behavior.

## Profiles

### Local

Only zero-cost profile expected to run worker, scheduler, maintenance, backups,
restore verification, and SMTP acceptance reliably.

### Disposable preview

Vercel Services frontend plus Vercel FastAPI Function in monolith mode, Supabase
Free, and development-only R2 scope. Disable continuous worker/scheduler,
maintenance, backup/restore, SMTP, and alerts. Sleep and ephemeral filesystem
make preview non-production.

### Production

Vercel frontend, always-on container backend, Supabase/managed PostgreSQL, R2
application and independent backup buckets, managed Redis, tested SMTP, and
external monitoring. Must satisfy `WORK.md` operator gates.

## Production Validation

Startup fails closed for fatal production defects. Validate:

- strong non-default session and owner bootstrap secrets;
- HTTPS public URL and OAuth callback;
- explicit CORS, CSRF origins, and allowed hosts;
- Redis backend/URL for multi-instance deployment;
- supported storage backend and complete S3/R2 credential sets;
- independent backup bucket/prefix and split least-privilege credentials;
- TLS DB connection and reviewed per-process connection budget;
- backup encryption, SMTP/recipient when alerts enabled;
- worker/scheduler settings consistent with topology.

Validator output remains redacted.

## Release

1. Run lint, type checks, focused tests, frontend build, GitGuardian scan, and router guard.
2. Build immutable images tagged by commit SHA.
3. Run one-shot migration against target DB.
4. Start backend/reader/frontend; require migration success before APIs.
5. Run authenticated production smoke:
   - `deploy/scripts/deploy-smoke.ps1 -Production` requires `NOVELAI_SMOKE_SESSION_COOKIE`;
     validates recovery probes (object snapshot, DB backup, restore) all healthy.
   - `deploy/scripts/verify-runtime-role.py` inside backend image with runtime
     `DATABASE_URL`; transactional checks cover identity, DML, role reachability,
     schema scope, and denied admin DDL.
6. Verify liveness/readiness, public catalog, owner auth boundary, CSRF/OAuth,
   storage scope, and frontend.
7. Record release commit, immutable tags, UTC time, and sanitized evidence.

## Rollback

- Redeploy previous immutable image/version.
- Prefer forward-fix for migrations. Take DB snapshot and test any downgrade on
  isolated staging before production.
- **Rollback blocking gate**: Prior image must pass production smoke against
  *current* schema before routing traffic. Smoke validates catalog (200) and
  owner recovery health (all recovery probes healthy). A 500 from catalog or
  unhealthy recovery probe **blocks rollback** — investigate schema/image
  incompatibility and apply forward-fix or verified downgrade migration.
- Restore storage before DB, rebuild catalog, then run smoke checks.
- Full incident procedure lives in [`OPERATIONS.md`](OPERATIONS.md).

## External Monitoring

- GitHub Actions workflow `.github/workflows/production-monitor.yml` requests a
  run every 5 minutes against `PRODUCTION_BASE_URL` via
  `deploy-smoke.ps1 -ExternalMonitor`; GitHub schedule delivery is best-effort.
- Checks: live, ready, public catalog, frontend, robots.txt, sitemap.xml,
  privacy/terms/legal routes. No session cookie — public surface only.
- Failure produces a failed workflow run visible in repo. Real operator
  notification (alert delivery, escalation, dashboard) requires hosted acceptance.

## GitHub Controls

Owner-operated settings should match tracked workflow expectations:

- Protect `main`: PR required, conversations resolved, required CI, CodeQL, and
  GitGuardian checks, no force push/deletion, owner-only bypass. No approving-
  review requirement: this is a single-operator repository and GitHub forbids
  PR authors from approving their own pull request, so a review gate would
  block every merge. Re-enable review requirements if a second write-access
  reviewer is added.
- Keep default `GITHUB_TOKEN` read-only; grant write only per job.
- Pin third-party actions to immutable SHAs.
- CI installs Python dependencies from `uv.lock` via
  `uv sync --frozen --extra documents --extra gemini --extra dev --extra test
  --extra s3 --extra auth` (Dependabot keeps the lock fresh; `--frozen` fails
  CI if the lock drifts from `pyproject.toml`), and Node comes from
  `frontend/.nvmrc` (Node 22, matching the production image).
- GHCR publications attach signed SLSA build-provenance attestations
  (`actions/attest`); verify with `gh attestation verify`.
- Enable dependency graph, Dependabot security updates, CodeQL, secret scanning,
  push protection, and validity checks.
- Keep deployment secrets in GitHub environments/provider secret stores, never files.
- Run `.github/workflows/gitguardian.yaml` (ggshield v1.52.2 pinned) on push and
  same-repository PR; `GITGUARDIAN_API_KEY` repo secret, read-only token, no
  `pull_request_target`. Fork PRs are skipped — secrets are not exposed to
  untrusted fork code. Fork owners should enable GitGuardian's native public-repo
  scanning on their own fork or configure their own API key.
- Verify actual required-check names against current `.github/workflows/`; docs
  do not override workflows.

Required deployment secret categories: target host/user/key where SSH deploy is
used, DB URL, session/bootstrap/credential-encryption secrets, explicit origins,
public URL, provider credentials, and managed-service verification credentials.

## Provider Boundaries

- Vercel hosts frontend only; same-origin `/api` rewrite targets backend URL.
- Register exact HTTPS Google callback for each deployed environment.
- R2 application and backup scopes remain private and separate.
- Supabase remains PostgreSQL behind SQLAlchemy/Alembic; dashboard changes do
  not replace repository migrations.

## Acceptance

No deployment is launch-ready until hosted auth/security, monitoring/alerts,
recovery, accessibility, performance, SEO, legal propagation, and rollback gates
in [`WORK.md`](WORK.md) pass without unwaived blockers.

## Current Release Decision

Current decision is **NO-GO**. Repository checks prove local behavior, not hosted
operation. Production approval still requires:

| Area | Required hosted evidence |
|---|---|
| Identity/security | Real domains, OAuth callback, cookies, CORS/CSRF, hosts, disabled-user behavior. |
| Storage/recovery | Isolated current-head PostgreSQL restore and object snapshot restore. |
| Monitoring | External checks, real redacted alert delivery, escalation ownership. |
| Browser/network | Accessibility, real-network performance, SEO validators, legal propagation. |
| Rollback | Pause worker/scheduler, purge cache, disable reader, redeploy immutable prior version, smoke. |
| Ownership | Named launch, rollback, and monitoring operators. |

Provider configuration must be verified against tracked topology. Account or
payment blocks remain blocks; screenshots or free previews are not production
reliability evidence.
