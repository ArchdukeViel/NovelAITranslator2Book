# Deployment

Canonical deployment topology, release, rollback, and GitHub-control contract. For runtime health probes, backup recovery, and incident runbooks, see [`OPERATIONS.md`](OPERATIONS.md).

## Topology

`deploy/compose.yml` is canonical:

| Service | Purpose |
|---|---|
| `caddy` | Internal HTTP proxy behind the browser-facing HTTPS entry point, compression, security headers, ordered routing. |
| `frontend` | Next.js public/admin UI, port 3000. |
| `backend` | Admin/auth/user API and scheduler, port 8000; no normal provider worker. |
| `reader` | Guest public API, port 8001. |
| `worker` | Dedicated database-backed crawl/translation worker; no host port. |
| `migrate` | One-shot Alembic migration profile before APIs. |
| `redis` | Shared limits, queue, coordination where enabled. |
| `restore-db` | Isolated disposable PostgreSQL 18 restore verifier (profile: `recovery`). |

PostgreSQL is external; Compose does not provision primary DB. Never run
migrations inside long-running backend containers.
Use `MIGRATION_DATABASE_URL` for a dedicated schema-owner/migrator role and
`DATABASE_URL` for the least-privilege long-running application role.
Migration `c7d9e1f3a5b2` maintains `novelai_app`, a stable NOLOGIN privilege
role with explicit application DML and RLS policies. Migration
`b6c8d0e2f4a6` extends that contract to the later `activity_records` and
contributor tables while revoking Supabase Data API roles. Provision the
separate `novelai_runtime` LOGIN member with
`backend/sql/provision_novelai_runtime.sql`; rotate that member password
without changing schema ownership or grants.

Compose mounts only disposable runtime state at `/app/data/runtime`. For local
Windows development, set `RUNTIME_HOST_DIR=../storage/runtime` in `deploy/.env`;
production must use a separately provisioned writable host directory such as
`/opt/novelai/shared/data/runtime`. The mount is never a novel-content source.

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
reader entry points and requires shared Redis for distributed behavior. In the
canonical Compose topology, both web services keep `JOB_WORKER_ENABLED=false`
and the `worker` service runs `novelaibook worker` against the shared database.

### Tailscale staging access

Staging is reachable only on the private Tailscale network. Set `SITE_DOMAIN` to
the host's stable Tailscale DNS name (not a changing Tailnet IP), keep
`PUBLIC_BIND_ADDRESS=127.0.0.1`, and configure Tailscale Serve on the Windows
host to terminate HTTPS and forward the private hostname to the WSL loopback
listener on `127.0.0.1:8080`. Browse only to `https://<tailscale-hostname>/`.
The checked-in Caddyfile is the internal HTTP hop; it must not be exposed
directly to the Tailnet. Set `PUBLIC_FRONTEND_URL`, `WEB_CORS_ORIGINS`,
`CSRF_TRUSTED_ORIGINS`, and `ALLOWED_HOSTS` to the HTTPS hostname and keep
`SESSION_COOKIE_SECURE=true`. Backend, reader, Redis, and PostgreSQL have no
host-published ports. Only `SITE_DOMAIN` is passed to Caddy; backend and reader
healthchecks send the same configured host header. Never inject the shared
`.env` into the proxy container because it contains unrelated database and
runtime secrets.

## Profiles

### Local

Only zero-cost profile expected to run worker, scheduler, maintenance, backups,
restore verification, and SMTP acceptance reliably.

### Local and Tailscale staging

Use the same Docker Compose services for local acceptance and private staging.
Local checks use the host's loopback entry point; staging uses the WSL/Docker host
through Tailscale and exposes only Caddy. Run the one-shot migration and the
container health/readiness checks before browser acceptance. This path keeps the
frontend, admin API, reader API, Redis, and their configuration together.

### Production

Tailscale-hosted WSL/Docker Compose frontend and split backend, Supabase/managed
PostgreSQL, R2 application and independent backup buckets, managed Redis, tested
SMTP, and external monitoring. Must satisfy `WORK.md` operator gates.

## Production Validation

Startup fails closed for fatal production defects. Validate:

- strong non-default session and owner bootstrap secrets;
- HTTPS public URL and OAuth callback;
- explicit CORS, CSRF origins, and allowed hosts;
- Redis backend/URL for multi-instance deployment;
- R2-only application bucket `dokushodo`, exact `R2_*` credentials, and no
  local content volume;
- independent `dokushodo-backup` bucket and split least-privilege source/read
  and backup/write credentials;
- TLS DB connection and reviewed per-process connection budget;
- backup encryption, SMTP/recipient when alerts enabled;
- worker/scheduler settings consistent with topology.
- the `worker` service is running the same admin image revision as `backend`,
  has no published port, and claims the `activity_records` queue after the
  migration has succeeded;

Validator output remains redacted.

## Release

1. Run lint, type checks, focused tests, frontend build, GitGuardian scan, and router guard.
2. Build immutable images tagged by commit SHA.
3. Run one-shot migration against target DB.
4. Start backend/reader/frontend with `docker compose up --wait`; require
   container health and `/health/ready` through Caddy before advancing the
   current-release symlink.
5. Verify the worker claims one queued activity and renews its lease without a
   second worker claiming the same record.
6. Run authenticated production smoke:
   - `deploy/scripts/deploy-smoke.ps1 -Production` requires `NOVELAI_SMOKE_SESSION_COOKIE`;
     validates recovery probes (object snapshot, DB backup, restore) all healthy.
   - `deploy/scripts/verify-runtime-role.py` inside backend image with runtime
     `DATABASE_URL`; transactional checks cover identity, DML, role reachability,
     schema scope, and denied admin DDL.
7. Verify liveness/readiness, public catalog, owner auth boundary, CSRF/OAuth,
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
  `d7e4f9a1c2b3`, the current release head. The role migration
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
- **Local Compose fallback.** The base Compose file uses local-only image names
  for development builds. Release deployment still requires the workflow to
  override all three names with immutable GHCR digests in `release.env`.
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
- Local, CI, and Docker Node is pinned to 26.7.x in `frontend/.nvmrc`, `frontend/package.json`, the CI setup, and production `frontend.Dockerfile`.
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

- Caddy is the only host-published entry point; it routes the frontend and API
  services while backend, reader, Redis, and PostgreSQL remain private.
- Register exact HTTPS Google callback for each deployed environment.
- R2 application and backup scopes remain private and separate. The application
  uses exact PostgreSQL-referenced keys; only inventory, backup, migration, and
  GC jobs list R2 prefixes.
- Supabase remains PostgreSQL behind SQLAlchemy/Alembic; dashboard changes do
  not replace repository migrations.

## Staging Host Limits and Scaling

This release is a single WSL/Docker host, not HA. Frontend and reader processes
are stateless and can be replicated later while Supabase and R2 remain external.
Redis and Caddy remain single-host components. Backend replicas must respect the
database connection budget and the worker/scheduler lease model; do not scale
backend replicas without reviewing `DB_CONNECTION_BUDGET`, Redis coordination,
and scheduler lease ownership.

## Staging Deployment Evidence

The following sanitized record captures the first successful private staging
cutover for PR #88 before the HTTPS session-cookie hardening in this review. It
is historical evidence for this WSL/Docker host, not the current staging access
contract, and does not change the production `NO-GO` decision above.

- **UTC deployment window:** `2026-08-15 13:46:20Z` through `2026-08-15 13:47:50Z`
  (Deploy run `31888063044`).
- **Source:** `main` at full SHA
  `5856df87eff3a0f957e5310834b6fb30182ffa8f`; the staging loopback proxy
  adjustment was delivered by PR #105 in the PR #88 deployment series.
- **Published images:** Build and Push run `31887840108`; provenance was
  verified before SSH deployment.
  - admin: `sha256:565949d850c191d124e771930c9b1ed4d8a3730c67ee82c41fcac2453dadb407`
  - reader: `sha256:258bf087d3fbb113111d69b5dd6cdf5538c9886f2140e4982e27cfc34ad4ff66`
  - frontend: `sha256:3d1738c750a12e5b9dd811d5cb14dc26cad5f09f05d1a58044772673d5482207`
- **Database:** The container-run migration completed successfully; Supabase
  read-only verification reported Alembic head `c7a8b9d0e1f2`, with
  `novelai_app` present as `NOLOGIN` and `novelai_runtime` present as the
  application `LOGIN` role.
- **Private URL:** `http://100.93.40.30/` through Tailscale. Windows forwards
  Tailnet port 80 to WSL loopback port 8080; only Caddy is host-published.
  Backend, reader, Redis, and PostgreSQL have no host-published ports.
- **Routing evidence:** Through the Tailnet address, `/`, `/health/live`,
  `/health/ready`, `/api/auth/me`, and `/api/public/catalog?page_size=1`
  returned `200`; `/api/admin/health` returned the expected unauthenticated
  `401`.
- **Restart evidence:** Backend and Caddy were restarted independently; both
  returned to `healthy`, and `/health/ready` returned `200` afterward.
- **Previous release:** `PREVIOUS_RELEASE` was empty at the successful cutover
  because earlier failed attempts never advanced `/opt/novelai/current`. The
  old `sha-071f6829f572b431f9583ff0988560cd795c9b56` image remains an
  identifiable schema-incompatible rollback candidate and was not executed.
- **Limitations:** This is one WSL/Docker host, not HA; the laptop, Docker
  Desktop, Ubuntu/WSL, network, and Tailscale must remain available. Access is
  private HTTP only; TLS, production hosted monitoring, recovery acceptance,
  and the full end-user flow remain outstanding. This documentation-only
  follow-up is not redeployed.

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
