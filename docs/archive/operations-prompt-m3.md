# Implementation Prompt - Milestone M3 (Deployment Readiness)

Copy-paste fenced block into new session. Filled from
`docs/operations/implementation-prompt-template.md`, M3 in `docs/roadmap.md`,
active specs, deployment files, and debt register.

---

```
You are working in the NovelAITranslator2Book repository on branch main.
Latest commit: 7e80ae1.

## 1. Read These Files First (in this order)

1. `AGENTS.md` - operating rules, architecture, deployment security, verification commands.
2. `docs/architecture/architecture.md` - canonical architecture, security boundaries, deployment direction.
3. `docs/roadmap.md` - milestones and M3 scope.
4. `docs/DEBT.md` - DEBT-026, DEBT-032, DEBT-039, DEBT-055, DEBT-061 completion criteria.
5. `docs/SPECS_COMPLETION.md` - active/archived spec inventory.
6. `docs/storage-contract.md` - storage ownership and restore rules.
7. `docs/operations/deployment.md` - current container and routing document. Treat stale statements as documentation bugs, not architecture authority.
8. `docs/operations/runbook.md` and `docs/operations/data-recovery.md` - operator procedures.
9. `docs/cicd-manual-setup.md` - CI/CD manual setup. Update stale M0 status if touched.
10. `.agents/kiro/specs/rate-limit-and-abuse-protection-baseline/design.md`, `requirements.md`, `tasks.md`.
11. `.agents/kiro/specs/deployment-production-hardening/design.md`, `requirements.md`, `tasks.md`.
12. `.agents/kiro/specs/cloud-storage-s3/design.md`, `requirements.md`, `tasks.md`.
13. `.github/workflows/ci.yml`, `.github/workflows/build.yml`, `.github/workflows/deploy.yml`.
14. `deploy/compose.yml`, `deploy/compose.dev.yml`, `deploy/Caddyfile`, Dockerfiles, `deploy/docker-compose-dev.ps1`.

## 2. Your Task

Implement **Milestone M3 - Deployment Readiness** from `docs/roadmap.md`.

### Scope (from roadmap.md)

- Set up Redis rate limiting and verify multi-instance behavior. (DEBT-039)
- Configure Caddy routes matching ordered admin/auth/public split backend targets.
- Setup ESLint configs and check within CI build. (DEBT-026, DEBT-032)
- Verify S3 storage backend with real integration checks. (DEBT-061)
- Implement production configuration validator and startup checks. (DEBT-055)
- Harden TLS, proxy, CORS, CSRF, cookies, and security headers. (DEBT-055)
- Add deploy smoke checks, rollback procedure, and migration gate. (DEBT-055)

### M3 Acceptance Evidence

Roadmap has no explicit acceptance-gate block. Use exact DEBT completion criteria plus these objective gates:

- Redis-backed limits reject bursts across two independent app instances using same Redis.
- Caddy routes admin/auth/novel traffic to admin backend, public API traffic to reader, health traffic to admin, catch-all to frontend; route order verified.
- `npm run lint` runs non-interactively and CI executes it.
- S3 integration proves configured endpoint/bucket/prefix write, read, list, delete behavior; no real credentials printed.
- Production startup fails closed for fatal configuration defects and passes with valid production config.
- Smoke check confirms migration one-shot service succeeds before API services, live/ready endpoints are healthy, public/admin route separation works, and rollback procedure is executable.

### Current State (inspect again before edits)

- `RedisRateLimiter` exists in `backend/src/novelai/infrastructure/http/rate_limiter.py`, selected by `WEB_RATE_LIMITER_BACKEND=redis`, but DEBT-039 says split multi-process behavior has no verification.
- Compose already starts `redis:7-alpine`, passes `REDIS_URL=redis://redis:6379/0`, and defaults `WEB_RATE_LIMITER_BACKEND` to `memory`. Production must use `redis`; memory is development-only / single-process only.
- `deploy/Caddyfile` has ordered handles for `/health/*`, `/api/admin/*`, `/api/auth/*`, and session-authenticated `/api/user/*` to `backend:8000`; `/api/public/*` to `reader:8001`; and the catch-all, including public `/novels/*` pages, to `frontend:3000`. Validate the contract against actual Compose service names and split app entrypoints.
- `frontend/package.json` defines `lint` as `next lint`, has ESLint packages, but no checked `eslint.config.mjs` is confirmed and `ci.yml` runs typecheck/tests but not lint.
- S3 backend and mocked tests exist. DEBT-061 requires real integration checks, production validation, and S3 backup/restore drill evidence. Use an explicitly configured non-production bucket/prefix or S3-compatible test target. Never test against production data.
- `deploy/compose.yml` runs Alembic through one-shot `migrate` before backend/reader. Preserve this gate. Do not run migrations inside long-running containers.
- `docs/operations/deployment.md` line 65 says APScheduler. This conflicts with architecture rules: M2c uses a lightweight asyncio loop, and APScheduler must not return. Fix stale docs if touched.
- `docs/cicd-manual-setup.md` says M0 build verification remains pending, but DEBT-002 and DEBT-003 are resolved. Fix it only if M3 changes that document.

### Spec Contract

#### Rate limits

- Use Redis for multi-instance production. Fail closed if configured Redis limiter cannot reach Redis; do not silently fall back to memory.
- Keep rate-limit keys privacy-safe. Do not retain/log raw IPs, session IDs, emails, tokens, or limiter keys.
- Trusted forwarded headers apply only from configured proxies. Ignore spoofed `X-Forwarded-*` from untrusted clients.
- Return controlled `429` with safe body and `Retry-After` where available. Add request-size limits only for active high-risk request paths; do not block reader streaming or uploads without a concrete contract.
- Existing limiter interface may be enough. Do not rewrite to a broad middleware/policy framework unless actual endpoint requirements prove it necessary.

#### Caddy and split deployment

- Caddy routing order is security-sensitive: `/api/admin/*`, `/api/auth/*`, and `/api/user/*` go to the session-enabled backend on 8000; `/api/public/*` goes to the sessionless reader on 8001; `/health/*` goes to the backend; all remaining traffic, including frontend `/novels/*` pages, goes to the frontend on 3000.
- Match Caddy upstream hostnames to actual Compose service names. Current service is named `backend`, even though its image/entrypoint is admin service. Do not break a working compose network by speculative renaming.
- TLS terminates at Caddy. Preserve compression and safe headers. Add HSTS only for HTTPS production domain; never make localhost development unusable.
- Caddy must not expose `storage/novel_library` as static files.

#### Production hardening

- Validate `ENV=production`; reject default/weak `SESSION_SECRET_KEY`; require `OWNER_BOOTSTRAP_SECRET`, `PUBLIC_FRONTEND_URL`, `DATABASE_URL`, explicit production `WEB_CORS_ORIGINS`, and production-safe cookie/proxy/rate-limit/storage/backup settings.
- Use canonical names: `ENV`, `PUBLIC_FRONTEND_URL`, `SESSION_SECRET_KEY`, `WEB_CORS_ORIGINS`, `S3_BUCKET`, `WEB_RATE_LIMITER_BACKEND`. Do not introduce `APP_ENV` or spec aliases such as `PUBLIC_SITE_URL`.
- Fail startup on fatal defects. Redact validator output; no secret, DB URL, raw host path, bucket credential, or full config dump.
- Harden allowed hosts/trusted proxies, HTTPS/proxy awareness, CORS, CSRF, secure `HttpOnly` SameSite cookies, and headers. Do not bypass CSRF to pass tests.
- Keep `/health/live` process-only; `/health/ready` public-safe; `/api/admin/health` owner-only and redacted.

#### S3 validation

- Keep storage differences behind `StorageBackend`; do not add raw S3 calls to routers/services.
- Exercise save/load/exists/list/delete against real isolated test prefix. Clean only objects under generated test prefix after test. Do not delete bucket root or unrelated objects.
- Validate endpoint, region, bucket, prefix, credentials, and public/private exposure configuration without exposing values.
- Verify backup/restore only against isolated test target and restore directory. Do not restore into production DB/storage.

### Implementation Checklist

Use full task checklists by path. Apply smallest changes meeting M3 scope. Do not build optional dashboard, CAPTCHA, WAF, provider-specific infrastructure, or Kubernetes support.

- [ ] 1. Preflight Compose/Caddy, split entrypoints, settings, auth cookies/CSRF/CORS, rate limiter wiring, S3 factory, health endpoints, migration service, CI scripts, and docs.
- [ ] 2. Add production config validator plus startup hook and focused tests. Distinguish fatal/warning/info. Ensure fatal production config fails before serving traffic.
- [ ] 3. Make production Compose default/require Redis limiter safely; add Redis multi-instance integration test using two independent limiter/app instances.
- [ ] 4. Add trusted-proxy/allowed-host/CORS/cookie/security-header hardening with focused regression tests. Preserve development behavior only where explicitly allowed.
- [ ] 5. Verify/fix Caddy route order and Compose dependencies. Add deploy smoke script/check with migration gate, readiness, public/admin route boundary, and Caddy config validation.
- [ ] 6. Add frontend flat ESLint config if missing; update `package.json` lint script if `next lint` is incompatible with installed Next version; run lint in CI after `npm ci`. Do not add legacy interactive configuration.
- [ ] 7. Add S3 real integration runner/documented procedure using isolated non-production endpoint/bucket/prefix; validate S3 config in production validator; run backup/restore drill only in isolated target.
- [ ] 8. Document deploy procedure, migration gate, smoke checks, rollback steps, secret rotation, proxy/CORS rules, Redis requirement, S3 verification, and operational evidence.
- [ ] 9. Resolve DEBT-026, DEBT-032, DEBT-039, DEBT-055, DEBT-061 only after exact evidence exists. Do not claim remote deployment, live S3, registry, or rollback verification without running it.

## 3. Constraints

- Do not modify completed work unless regression proven.
- Routers remain thin. No direct `db.models`, `storage.service`, or `sources` imports in routers outside `dependencies.py`.
- Use `require_role("owner")` for owner-only APIs. No multi-admin roles.
- Do not read or print `.env`, `deploy/.env`, or production secrets.
- Do not log/return secrets, raw IPs, tokens, DB URLs, storage credentials, signed URLs, raw paths, stack traces, or complete credential values.
- No new dependency if stdlib/existing package works. If dependency changes, regenerate lockfiles only with `deploy/update-lockfiles.ps1`.
- No raw SQL outside Alembic/database-policy scripts.
- No APScheduler. Existing lightweight asyncio scheduler remains canonical.
- Do not change direct public/client fetch usage; frontend API access stays in `frontend/lib/api.ts` or `frontend/lib/public-api.ts`.
- Do not commit/push/amend/force checkout unless explicitly authorized.

## 4. Preflight (before coding)

1. Confirm docs/spec conflicts: spec uses legacy setting examples; project canonical settings win. Deployment doc APScheduler statement is stale; architecture wins.
2. Map Caddy patterns to actual routes in both admin and reader app entrypoints. Check Caddy syntax with `caddy validate` inside image/container if available.
3. Trace rate limiter call sites. Confirm two independent app processes share same Redis counter and window.
4. Check `next lint` compatibility with installed Next 15. Do not assume it works because script exists.
5. Inspect S3 integration test tooling and find safe isolated target. If no credentials/endpoint are available, implement test harness and document manual gate; do not mark DEBT-061 resolved.
6. Inspect current production config/startup lifecycle and existing security middleware before adding validator/middleware.
7. List expected files and smallest diff. State all external prerequisites and unverified assumptions.

## 5. Implementation Order

1. Add/update canonical settings and production validator tests.
2. Wire validator into startup; add proxy/host/CORS/cookie/security headers.
3. Fix Redis limiter production wiring and cross-instance tests.
4. Fix Caddy/Compose routing and migration/readiness dependencies; add smoke checks.
5. Add ESLint flat config/script and CI lint step.
6. Add S3 integration harness/config validation and isolated backup/restore drill procedure.
7. Update deployment/runbook/data-recovery/CI docs, DEBT evidence, and roadmap after checks pass.

## 6. Verification (run before declaring done)

| Command | Purpose |
|---|---|
| `python -m ruff check .` | Backend lint |
| `python -m pyright` | Backend typecheck |
| `python -m pytest backend/tests/test_rate_limiter.py --tb=short -q` | Limiter unit tests |
| `python -m pytest backend/tests/test_storage_backends.py --tb=short -q` | S3/filesystem backend behavior |
| `python -m pytest backend/tests/test_<production_config>.py --tb=short -q` | Validator/security tests added by this work |
| `python -m pytest backend/tests/test_<rate_limit_redis>.py --tb=short -q` | Cross-instance Redis test added by this work |
| `rg -n "^from novelai\.(db\.models|storage\.service|sources\.)" backend/src/novelai/api/routers/ --glob "!dependencies.py"` | Router guard; no output |
| `git diff --check` | Diff integrity |
| `cd frontend; npm run lint` | Frontend non-interactive lint |
| `cd frontend; npm run typecheck` | Frontend typecheck |
| `cd frontend; npm run test` | Frontend tests |
| `docker compose -f deploy/compose.yml config` | Compose validation |
| `docker compose -f deploy/compose.yml up -d` | Local stack smoke, only with safe local config |
| `docker compose -f deploy/compose.yml ps` | Migration/API health status |

For actual S3/deployment verification, record exact command, isolated target, and result. Never expose secret-bearing command output.

## 7. Final Report

Report:
1. Files changed and behavior delivered by scope item.
2. Docs/spec conflicts found and authority applied.
3. Commands run and exact outcomes.
4. External validation completed: Redis two-instance, Caddy/Compose smoke, real S3, backup/restore drill, rollback.
5. Debt resolved with evidence; remaining unverified external prerequisites.
6. Deviations/new debt.

Do not mark debt complete without implementation and validation evidence.
```

---

## M3 Notes

- Existing rate limiter and S3 backend reduce code needed. Main work is production wiring and real integration proof.
- `cloud-storage-s3` implementation tasks are complete, but DEBT-061 requires real integration and production validation.
- `deploy/compose.yml` calls service `backend`; Caddy must target actual service names, not idealized labels.
- Add only verified deployment steps. Remote environment checks cannot be claimed from local static review.
