# Deployment

Canonical deployment topology, release, rollback, and GitHub-control contract. For runtime health probes, backup recovery, and incident runbooks, see [`OPERATIONS.md`](OPERATIONS.md).

## Topology

`deploy/compose.yml` is canonical:

| Service | Purpose |
|---|---|
| `caddy` | Private HTTP entry point, compression, security headers, ordered routing. |
| `frontend` | Next.js public/admin UI, port 3000. |
| `backend` | Admin/auth/user API, worker/scheduler, port 8000. |
| `reader` | Guest public API, port 8001. |
| `migrate` | One-shot Alembic migration profile before APIs. |
| `redis` | Shared limits, queue, coordination where enabled. |
| `restore-db` | Isolated disposable PostgreSQL 17 restore verifier (profile: `recovery`). |

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

### Tailscale staging access

Staging is reachable only on the private Tailscale network. The current host
address detected on 2026-08-14 is `100.93.40.30`; set both
`SITE_DOMAIN=100.93.40.30` and `PUBLIC_BIND_ADDRESS=100.93.40.30` in the
shared host environment, then browse to `http://100.93.40.30/`. The Caddy site
address is explicitly prefixed with `http://`, so the private IP remains plain
HTTP rather than enabling automatic HTTPS. This release publishes only port
80 and binds it to the configured Tailnet address; backend, reader, Redis, and
PostgreSQL have no host-published ports. Only `SITE_DOMAIN` is passed to Caddy;
never inject the shared `.env` into the proxy container because it contains
unrelated database and runtime secrets. TLS remains deferred until a trusted,
renewable Tailscale certificate path exists.

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
4. Start backend/reader/frontend with `docker compose up --wait`; require
   container health and `/health/ready` through Caddy before advancing the
   current-release symlink.
5. Run authenticated production smoke:
   - `deploy/scripts/deploy-smoke.ps1 -Production` requires `NOVELAI_SMOKE_SESSION_COOKIE`;
     validates recovery probes (object snapshot, DB backup, restore) all healthy.
   - `deploy/scripts/verify-runtime-role.py` inside backend image with runtime
     `DATABASE_URL`; transactional checks cover identity, DML, role reachability,
     schema scope, and denied admin DDL.
6. Verify liveness/readiness, public catalog, owner auth boundary, CSRF/OAuth,
   storage scope, and frontend.
7. Record release commit, immutable tags, UTC time, and sanitized evidence.

## Deploy Workflow

`.github/workflows/deploy.yml` performs manual deployments via
`workflow_dispatch` with two inputs:

- `version` — published immutable GHCR image tag `sha-<full commit SHA>`.
- `environment` — `staging` or `production`.

Hardening contract:

- **All environments are SHA-only.** The workflow derives the exact checkout ref in a
  validated Bash step (`Resolve deployment ref`) because GitHub Actions
  expressions have no `replace()` function; the free-form version input is
  validated **before** it is used as a checkout ref or an image tag. Production
  deployments require an immutable `sha-<40 lowercase hex>` tag; `latest` is
  rejected. The validated value is passed to the remote SSH script through
  environment variables, never through expression interpolation into the
  script body.
- **Restore password preflight (scanner-safe).** Compose references
  `DATABASE_RESTORE_PASSWORD` with plain interpolation (no required-variable
  error text, which GitGuardian can mistake for a hard-coded credential); the
  remote deploy script fails closed unless the shared `.env` on the host
  contains a non-empty `DATABASE_RESTORE_PASSWORD` required by the
  `restore-db` (recovery) profile.
- **Cryptographic Provenance Verification.** GitHub artifact attestations are
  unavailable for this user-owned private repository, so `build.yml` creates
  keyless Sigstore SLSA provenance in the GHCR OCI referrer graph with Cosign.
  Before remote deployment begins, the workflow resolves the exact OCI index
  digest for `novelai-admin`, `novelai-reader`, and `novelai-frontend` and runs
  `cosign verify-attestation` with the protected `build.yml` workflow identity
  and GitHub OIDC issuer. Deployment fails closed if provenance is missing or
  invalid.
- **Migration-head parity.** Before SSH, the workflow compares the checked-out
  migration head with the exact admin image digest and requires
  `c7a8b9d0e1f2`, the current release head. The role migration
  `c7d9e1f3a5b2` is an earlier migration in that chain, not the final head;
  a staging database at that earlier head is advanced by the one-shot
  migration profile before readiness is accepted.
- **Immutable Release Directory.** Deployment files under `deploy/` are copied
  to `/opt/novelai/releases/<VERSION>/` on the target host. `/opt/novelai/current`
  is updated as an atomic symlink to the release directory, guaranteeing remote Compose
  and Caddy configuration match the checked-out Git SHA.
- **Separate environment files.** Each release records non-secret `release.env`
  metadata containing the full Git SHA and all three image digest references;
  Compose receives it separately from the shared secret `.env`.
- **Migration and readiness gate.** The `migration` profile is run exactly once,
  then Compose starts with `--wait --wait-timeout 180`; `/health/ready` must pass
  through Caddy before `/opt/novelai/current` advances. Automatic image pruning
  is disabled so previous release evidence remains recoverable.
- **One deployment per environment at a time.** `concurrency` groups by target
  environment with `cancel-in-progress: false`; a newer deployment request
  waits rather than cancel a deployment that is mid-migration or starting
  containers.
- **Post-deploy acceptance gate.** After `docker compose up`, production
  deploys run `deploy/scripts/deploy-smoke.ps1 -Production` against
  `PRODUCTION_BASE_URL` (validates live/ready, routing, catalog, frontend,
  legal/SEO, and owner recovery health). The deployment is reported **failed**
  unless the smoke gate passes (fail-closed). Required repository variable:
  `PRODUCTION_BASE_URL`; required production-environment secret:
  `NOVELAI_SMOKE_SESSION_COOKIE`. Staging deploys do not run the remote smoke gate
  because no staging base URL variable is configured.

## Rollback

- Inspect the previous release's `release.env` and require image/current-schema
  compatibility before switching traffic. The exact two-env-file restart form is:
  `docker compose --env-file /opt/novelai/shared/.env --env-file
  /opt/novelai/releases/<VERSION>/release.env -f
  /opt/novelai/releases/<VERSION>/compose.yml up -d --pull never --wait`.
- Redeploy the previous immutable image/version only after that compatibility
  check. The old `sha-071f6829f572b431f9583ff0988560cd795c9b56` image is retained
  as an identifiable **schema-incompatible rollback candidate** and must not be
  executed against the current schema. Use a forward fix when compatibility is
  not proven.
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
- The monitor job is gated on repository variable `PRODUCTION_MONITOR_ENABLED`
  (`'true'` to enable). Set it only once a real production domain exists, so
  scheduled runs do not allocate runners while monitoring is disabled.
- Checks use a 10-second per-URL timeout (`-TimeoutSeconds 10`). Runs are
  serialized with `cancel-in-progress: false`: an in-progress run is never
  canceled, so a slow degraded-incident run still reaches its failure result.
- Checks: live, ready, public catalog, frontend, robots.txt, sitemap.xml,
  privacy/terms/legal routes. No session cookie — public surface only.
- Failure produces a failed workflow run visible in repo. Real operator
  notification (alert delivery, escalation, dashboard) requires hosted acceptance.

## GitHub Controls

Owner-operated settings should match tracked workflow expectations:

- Protect `main`: PR required, conversations resolved, required status checks
  (`docker-build`, `e2e-tests`, `Analyze (actions)`,
  `Analyze (javascript-typescript)`, `Analyze (python)`, `GitGuardian scan`,
  and `dependency-review`), no force push/deletion, owner-only bypass. The
  replacement `Analyze (...)` jobs use Zizmor, locked Ruff security rules, and
  Node/ESLint/TypeScript checks. `dependency-review` uses read-only Trivy
  lockfile and misconfiguration scanning because GitHub Dependency Review and
  CodeQL are unavailable without GitHub Code Security on this private repo.
  No approving-review requirement: this is a single-operator repository and GitHub
  forbids PR authors from approving their own pull request, so a review gate would
  block every merge. Re-enable review requirements if a second write-access
  reviewer is added.
- Keep default `GITHUB_TOKEN` read-only; grant write only per job.
- Python CI dependencies are installed from `uv.lock` via `uv sync --locked --extra ...` and executed via `uv run --locked <cmd>`. `--locked` fails CI if `uv.lock` is stale relative to `pyproject.toml`.
- Node major version is pinned to 22 in `frontend/.nvmrc`, `package.json` (`>=22 <23`), and production `frontend.Dockerfile`.
- Container image provenance is generated by `build.yml` via keyless Cosign/Sigstore SLSA attestations for default-branch GHCR publications. The deploy workflow verifies the exact digest, certificate identity, and GitHub OIDC issuer with `cosign verify-attestation`; GitHub artifact-attestation APIs are not used because this is a user-owned private repository.
- Pin third-party actions to immutable SHAs.
- Enable dependency graph, Dependabot security updates, secret scanning, push
  protection, and validity checks. If GitHub Code Security is later enabled,
  add CodeQL only through a separate protected change; it is not assumed by
  this private-repository release.
- Keep deployment secrets in GitHub environments/provider secret stores, never files.
- Run `.github/workflows/gitguardian.yaml` (ggshield v1.52.2 pinned) on push and
  same-repository PR; `GITGUARDIAN_API_KEY` repo secret, read-only token, no
  `pull_request_target`. Fork PRs are skipped — secrets are not exposed to
  untrusted fork code. Fork owners should enable GitGuardian's native public-repo
  scanning on their own fork or configure their own API key.
- Verify actual required-check names against current `.github/workflows/`; docs
  do not override workflows.

Required deployment configuration:

- Repository variables:
  - `PRODUCTION_BASE_URL`
  - `PRODUCTION_MONITOR_ENABLED`
- Production-environment secrets:
  - `DEPLOY_HOST`
  - `DEPLOY_USER`
  - `DEPLOY_SSH_KEY`
  - `NOVELAI_SMOKE_SESSION_COOKIE`
- Managed-service verification variables and credentials use the scopes
  documented by `managed-services-verification.yml`.

## Provider Boundaries

- Vercel hosts frontend only; same-origin `/api` rewrite targets backend URL.
- Register exact HTTPS Google callback for each deployed environment.
- R2 application and backup scopes remain private and separate.
- Supabase remains PostgreSQL behind SQLAlchemy/Alembic; dashboard changes do
  not replace repository migrations.

## Staging Host Limits and Scaling

This release is a single WSL/Docker host, not HA. Frontend and reader processes
are stateless and can be replicated later while Supabase and S3 remain external.
Redis and Caddy remain single-host components. Backend replicas must respect the
database connection budget and the worker/scheduler lease model; do not scale
backend replicas without reviewing `DB_CONNECTION_BUDGET`, Redis coordination,
and scheduler lease ownership.

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
