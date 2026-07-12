# Novel AI — Current Operational State

**Last updated:** 2026-07-12
**Source of truth:** `docs/architecture/architecture.md` (canonical architecture), `docs/DEBT.md` (canonical debt register)

---

## Architecture Overview

**Backend:** FastAPI + SQLAlchemy 2.0 + Alembic (PostgreSQL 16)
- Dual entry points for microservice-split readiness:
  - `novelai.main_admin:app` (port 8000) — owner/admin, session middleware, CSRF, all admin routers
  - `novelai.main_reader:app` (port 8001) — public reader, no session, no CSRF
  - `novelai.api.app:app` — monolith (default). `DEPLOY_MODE=split` runs both via multiprocessing
- CLI launcher: `novelaibook` (subcommands: `web`, `worker`, `doctor`, `create-user`, `adminweb`, `publicweb`)
- 9 router layer violations pending extraction to services (see DEBT-054)

**Frontend:** Next.js 15 App Router + TypeScript + Tailwind
- Route groups: `(admin)/admin/*` (owner UI), `(public)/*` (guest + authenticated user UI)
- API clients: `lib/api.ts` (admin), `lib/public-api.ts` (public) — only allowed direct-fetch files
- State: TanStack Query (server), Zustand (client)

**Storage:** Dual-layer
- Canonical: filesystem (`storage/novel_library/`) — metadata, chapters, translations, assets, exports
- Derived: PostgreSQL — catalog projection, users, jobs, settings, glossary
- S3 backend available (`STORAGE_BACKEND=s3`), not production-verified

**Queue/Worker:** In-process activity worker (`JOB_WORKER_ENABLED=true`) or standalone `novelaibook worker`. Redis/RQ available for distributed mode.

**Auth:** Single owner (bootstrapped via `OWNER_BOOTSTRAP_SECRET`). Public auth via Google OAuth + email/password creates `role="user"` sessions only. CSRF enforced on cookie-authenticated state-changing endpoints.

---

## Implemented Major Capabilities

| Capability | Status | Notes |
|------------|--------|-------|
| Novel onboarding (crawl metadata + chapters) | ✅ Implemented | Multi-source adapters (syosetu, kakuyomu, generic, novel18) |
| Chapter translation pipeline | ✅ Implemented | Chunked, parallel, glossary-aware, cache-backed, retry with scheduler |
| Glossary system (file + DB, sync bridge) | ✅ Implemented | Auto-extract, provider suggestions, review/approve, apply to chapters |
| Translation editing & versioning | ✅ Implemented | Manual edits create new versions, rollback, edit history |
| Admin dashboard & activity monitoring | ✅ Implemented | Queue, progress, scheduler state, provider health |
| Public catalog & reader | ✅ Implemented | Paginated catalog, novel detail, chapter reader, reading progress |
| Public user auth (Google OAuth + email/password) | ✅ Implemented | Session cookies, CSRF, password reset (noop/smtp) |
| User library, progress, history, reviews | ✅ Implemented | Authenticated user features |
| Export (EPUB, HTML, Markdown) | ✅ Implemented | Admin + public (when published) |
| Document import (EPUB, DOCX, TXT, HTML) | ✅ Implemented | Orchestrator + storage |
| Taxonomy (genres/tags) admin | ✅ Implemented | Admin CRUD, scraper assignments preserved |
| Translation cache (SHA-256 keyed, sharded) | ✅ Implemented | TTL, glossary invalidation |
| Scheduler (provider/model routing, rate limits) | ✅ Implemented | Admin-owned credentials, cooldown/exhaustion tracking |
| Traceability (pipeline events, chunk states, provider requests) | ✅ Implemented | Runtime JSON, not canonical |
| Environment config (pydantic-settings) | ✅ Implemented | Single source: `backend/src/novelai/config/settings.py` |

---

## Phase Completion Status

### Phase 0 — Foundation & CI/CD ✅ **Verified Complete**

| Item | Status | Evidence |
|------|--------|----------|
| CI pipeline (lint, typecheck, test) | ✅ Verified | `.github/workflows/ci.yml` runs ruff, pyright, pytest (non-e2e) |
| Dual-service Dockerfiles | ✅ Verified | `deploy/admin.Dockerfile`, `deploy/reader.Dockerfile`, `deploy/frontend.Dockerfile` |
| Build workflow fixed | ⚠️ Implemented but unverified | `build.yml` references new Dockerfiles; **not yet run on push to main** (DEBT-002) |
| Test fixes (Phase 0c) | ✅ Verified locally | `test_crawl_resilience_contracts.py` 18→0, `test_glossary_sync_bridge.py` 0, `test_frontend_api_contract.py` 0 |
| DB-dependent tests on CI | ❌ Blocked | Requires Postgres on GitHub Actions (DEBT-003) |

**Phase 0 verdict:** Core implementation complete. CI build verification and CI Postgres remain.

### Phase 1 — Glossary Consolidation & Translation Hardening ✅ **Verified Complete (with 1 new blocker)**

| Item | Status | Evidence |
|------|--------|----------|
| Glossary routers split (5 files) | ✅ Verified | `admin_glossary.py`, `admin_glossary_candidates.py`, `admin_glossary_apply.py`, `admin_glossary_provider.py`, `admin_glossary_suggestions.py` |
| Glossary sync bridge (file ↔ DB) | ✅ Verified | `GlossarySyncService.sync_from_file()`, API endpoints |
| Glossary prompt injection (DB-approved) | ✅ Verified | `GlossaryPromptInjectionService.build_for_chapter()` |
| Glossary apply engine (preview/commit/rollback) | ✅ Verified | `GlossaryApplyService`, `GlossaryApplyPreviewService` |
| Provider suggestions (LLM-assisted) | ✅ Verified | `GlossaryProviderSuggestionService` |
| Translation pipeline hardening | ✅ Verified | Chunk retry, QA integration, scheduler observability |
| **Circular import in glossary routers** | ❌ **New blocker** | `admin_glossary.py` ↔ `admin_glossary_provider.py` (DEBT-006) |

**Phase 1 verdict:** Feature work complete. Circular import (DEBT-006) must be fixed before merge.

---

## Known Limitations

1. **No health probes** — `/api/health` returns static `{"status":"ok"}` (DEBT-001)
2. **No scheduled backups** — `BackupManager` exists but not wired (DEBT-010)
3. **In-process worker only** — No separate worker container in Compose (DEBT-060)
4. **S3 storage untested in production** (DEBT-061)
5. **Caddy TLS automation untested with real domain** (DEBT-062)
6. **Redis rate limiter unverified multi-instance** (DEBT-039)
7. **No metrics/dashboard** (DEBT-040)
8. **Legacy aliases (`slug`, `provider`, `model`, `id`, `source`) still in codebase** (DEBT-021)
9. **Windows file locking causes test flakiness** (DEBT-035)
10. **Public glossary annotations feature-flagged off** (DEBT-037)

---

## Active Technical Debt Summary

**Total active entries:** 72 (see `docs/DEBT.md` for full register)

| Priority | Count | Key Items |
|----------|-------|-----------|
| Blocker | 3 | Health probes (DEBT-001), CI build verify (DEBT-002), CI Postgres (DEBT-003) |
| Critical | 2 | Circular import (DEBT-006), Router layer violations ×9 (DEBT-054) |
| High | 12 | Service extractions, source pipeline fixes, storage safety, rate limiter |
| Medium | 28 | Backups, worker health, S3, Caddy, metrics, SEO, maintenance cron, etc. |
| Low | 27 | Analytics, notifications, PDF export, package flattening, docs polish |

**V1 Launch Blockers:** DEBT-001, DEBT-002, DEBT-003

---

## Testing & Deployment Status

| Area | Status |
|------|--------|
| Backend lint (ruff) | ✅ 0 errors |
| Backend typecheck (pyright) | ✅ 0 errors, 0 warnings |
| Backend tests (unit, non-DB) | ✅ ~2200 tests pass locally |
| Backend tests (DB-dependent) | ⚠️ Pass locally, fail on CI (no Postgres) |
| E2E tests | ⚠️ 3 flaky (pipeline events) |
| Frontend typecheck | ✅ Passes |
| Frontend build | ✅ Passes |
| Frontend lint | ❌ Not configured (DEBT-026) |
| Docker build (local) | ✅ All 3 images build |
| Docker build (CI) | ⚠️ Not verified on push to main |
| Deploy workflow | ⚠️ Manual `workflow_dispatch` only (DEBT-032) |

---

## Next Recommended Milestone

**Priority order:**

1. **Fix DEBT-006** (circular import) — blocks any glossary admin work
2. **Fix DEBT-002/003** (CI build verify + Postgres on CI) — unblocks CI confidence
3. **Fix DEBT-001** (health probes) — required for production deployment
4. **Extract 9 router services** (DEBT-054) — CI guard will fail otherwise
5. **Wire scheduled backups** (DEBT-010) — data integrity prerequisite
6. **Verify S3 + Caddy TLS** (DEBT-061, DEBT-062) — production readiness

---

## Key Documentation Links

| Document | Purpose |
|----------|---------|
| `docs/architecture/architecture.md` | Canonical system architecture (implemented vs planned) |
| `docs/DEBT.md` | Canonical debt register (all 72 entries) |
| `docs/SPECS_COMPLETION.md` | Spec/phase completion index with evidence |
| `docs/storage-contract.md` | File/JSON storage contract |
| `docs/reference/data-output-structure.md` | Low-level runtime data reference |
| `docs/glossary/glossary-system.md` | Glossary lifecycle & integration |
| `docs/jp-en-prompt-quality-policy.md` | JP-EN translation quality contract |
| `docs/environment.md` | Environment variable reference |
| `docs/cicd-manual-setup.md` | CI/CD manual steps |
| `docs/guides/GETTING_STARTED.md` | Onboarding guide |
| `docs/reference/python-commands.md` | Backend CLI & Python API reference |