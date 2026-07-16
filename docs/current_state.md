# Current Operational State

This is a high-level operational snapshot of the local repository.
For the detailed milestones and active tasks, see the roadmap: [`docs/roadmap.md`](roadmap.md).
For the technical debt register and launch blockers, see the register: [`docs/DEBT.md`](DEBT.md).

---

## Launch Status

- **Launch readiness:** Not ready. Seven new Kiro specs (admin audit viewer, deployment hardening, frontend error states, launch checklist, public reader accessibility, public reader performance, terms/DMCA takedown) are planned but not implemented.
- **V1 launch blockers:** 4 (DEBT-001 health probes, DEBT-002 CI build verification, DEBT-003 CI Postgres, DEBT-006 admin glossary circular import).

---

## Core Infrastructure Config

- **Backend:** FastAPI monolith (default) with split deployment options under `DEPLOY_MODE=split`.
- **Frontend:** Next.js 15 App Router.
- **Storage:** Storage backend files are canonical for novel metadata, chapters, translations, assets, and exports. PostgreSQL database holds derived projections (catalog, novels, chapters) and canonical domain rows (users, auth, glossary, requests, audits).
- **Worker:** Background activity worker defaults to in-process (`JOB_WORKER_ENABLED=true`). Async queue support via Redis/RQ exists.
- **Settings:** Configured via `pydantic-settings` in `backend/src/novelai/config/settings.py`. Canonical environment variable is `ENV` (not `APP_ENV`).

---

## Technical Debt and Blockers Summary

- **V1 Launch Blockers:** Health probes (DEBT-001), CI build checks (DEBT-002), CI Postgres setup (DEBT-003), and admin glossary circular imports (DEBT-006).
- **Technical Debt Register:** Consolidated active registry is in [`docs/DEBT.md`](DEBT.md). 33 active entries.

---

## Validation Status

- **Backend Lint:** Ruff passes clean on backend files.
- **Backend Typecheck:** Pyright type checking passes with 0 errors.
- **Backend Unit Tests:** Core unit tests pass locally.
- **Frontend Typecheck:** Next.js type check passes.
- **Frontend Build:** Production build finishes clean.
- **Docker builds:** Local admin, reader, and frontend Dockerfiles build successfully.
- **CI:** Database-dependent tests blocked (DEBT-003). Image build verification pending (DEBT-002).

---

## Known Gaps (Not Launch-Ready)

- Health endpoints are static; no real DB/storage/worker probes.
- No scheduled backups; no retention cleanup.
- No audit log writer or owner-only audit viewer.
- No takedown workflow; no HTTP 451 enforcement.
- No measured performance or accessibility gate.
- No launch readiness evidence or go/no-go decision.
- No production config validator; no deploy smoke checks.

## Implemented Features (Phase 2 Live Library Summary)

Status legend:
- Implemented — code shipped; contract + tests in place.
- Locally validated — passing on local dev backend and frontend test runs.
- CI validated — passing on GitHub Actions workflow.
- Production verified — passing against an authenticated, owner-provisioned read-only call against the production environment.

- **Live Admin Library Summary** (`GET /api/admin/library/summary`): derives per-novel counts from a single recursive R2 listing pass. Counts: total, scraped, translated, failed, pending. 30s TTL, explicit `refresh=true` bypass. Catalog-identity-aware cache (DB slugs vs storage union). [Implemented / Locally validated / CI validated / Production verified: pending]
- **Single-flight concurrency** via per-generation `_BuildGeneration` object, condition variable, and generation counter: exactly one storage listing per overlapping generation. Forced refresh joins active same-identity build. Generation-outcome lifetime is held via direct reference to the generation object so a later completion cannot destroy an earlier waiter's outcome. [Implemented / Locally validated / CI validated / Production verified: pending]
- **Invalidation epoch** (`self._invalidation_epoch`): monotonic counter incremented on every `invalidate_cache()`. Each generation captures its `start_epoch`. If the epoch advances during a build, the result is **not** published to cache; the generation is marked `invalidated=True`, all attached waiters are notified and re-enter the acquisition loop iteratively (not recursively) so exactly one starts a post-invalidation build. Repeated invalidation never silently publishes stale data. [Implemented / Locally validated / Production verified: pending]
- **Crawl failure history semantics**: the newest activity with `status` in (`completed`, `failed`) is authoritative — its `failures` list (including an empty list) overrides older activities. Cancelled, pending, queued, and running activities are skipped. Malformed/missing failure payload returns empty set (no resurrection). Stored chapter IDs are excluded from failed. Pending = `max(total - scraped - failed, 0)`. [Implemented / Locally validated / Production verified: pending]
- **Immutable cached state** (`tuple[NovelSummaryCounts, ...]`); outward responses are fresh dicts/lists — caller mutation cannot corrupt cache. [Implemented / Locally validated]
- **Catalog-identity-aware caching**: cache key includes sorted unique DB slugs; identity change forces rebuild. [Implemented / Locally validated]
- **Frontend join**: `summary.data.items` merged into novel rows via `Map(novel_id → item)`. Rows recompute when `summary.data` or `summary.isLoading` changes. [Implemented / Locally validated]
- **Settled background-refetch failure detection**: detects a failed background refetch after it settles (via `summary.isRefetchError`, with `status === "error" && data !== undefined && fetchStatus === "idle"` as a TanStack v5-compatible equivalent). One amber banner + Retry; previous values remain visible; distinct from initial-load and explicit-refresh failure states. [Implemented / Locally validated / Production verified: pending]
- **Three distinct error states**: initial failure (destructive banner + Retry), settled background failure (amber banner preserving values + Retry), explicit-refresh failure (`refreshSummary.error` banner + Retry). No duplicate banners; "Retry retry" typo removed. [Implemented / Locally validated]
- **Route uniqueness**: exactly one `GET /api/admin/library/summary` registration in monolith; no aliases under `/novels` or `/api/novels`. All OpenAPI operation IDs unique. [Implemented / Locally validated]
- **Invalidation**: immediate after full-crawl deletion and metadata replacement; best-effort after chapter/translation/glossary/activation saves. Consolidated `best_effort_invalidate(context=)` helper. `scrape_metadata` now uses `best_effort_invalidate(context="scrape_metadata")` (no manual try/except remains in that function). [Implemented / Locally validated]
- **Tests**: 50 library-summary tests (covering the four new race / failure-semantics contracts: successive-generation waiter retention, invalidation-epoch stale-build rejection, concurrent failed-generation propagation with 8+ threads, crawl-failure newest-authority, plus real Path/Windows-prefix normalization spies); 57 storage tests stay green; 609 frontend tests across 52 files (7 admin-library regression tests now); Ruff, Pyright, TypeScript typecheck, ESLint, and the router-layer architecture guard are clean locally. [Implemented / Locally validated / CI validated: pending—GitHub Actions evidence: unavailable / no associated run.]
- **Production verification**: `Authenticated production read-only verification against the intended configured environment remains operator-pending.` The exact read-only command template with secret placeholders is preserved for the operator step. [Production verified: pending]
