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

- **Live Admin Library Summary** (`GET /api/admin/library/summary`): derives per-novel counts from a single recursive R2 listing pass. Counts: total, scraped, translated, failed, pending. 30s TTL, explicit `refresh=true` bypass. Catalog-identity-aware cache (DB slugs vs storage union).
- **Single-flight concurrency** via condition variable + generation counter: exactly one storage listing per overlapping generation. Forced refresh joins active build.
- **Immutable cached state** (`tuple[NovelSummaryCounts, ...]`); outward responses are fresh dicts/lists — caller mutation cannot corrupt cache.
- **Catalog-identity-aware caching**: cache key includes sorted unique DB slugs; identity change forces rebuild.
- **Frontend join**: `summary.data.items` merged into novel rows via `Map(novel_id → item)`. Rows recompute when `summary.data` or `summary.isLoading` changes.
- **Three distinct error states**: initial failure (destructive banner + Retry), background failure (amber banner preserving values + Retry), explicit-refresh failure (`refreshSummary.error` banner + Retry). No duplicate banners; "Retry retry" typo removed.
- **Route uniqueness**: exactly one `GET /api/admin/library/summary` registration in monolith; no aliases under `/novels` or `/api/novels`.
- **Invalidation**: immediate after full-crawl deletion and metadata replacement; best-effort after chapter/translation/glossary/activation saves. Consolidated `best_effort_invalidate(context=)` helper.
- **Tests**: 35 library-summary tests (14 new deterministic concurrency, POSIX path, public logical-id); 57 storage tests; 2 previously-fixed web API tests green; 608 frontend tests (6 new regression).
