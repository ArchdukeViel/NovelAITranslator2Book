# Current Operational State

This is a high-level operational snapshot of the local repository.
For the detailed milestones and active tasks, see the roadmap: [`docs/roadmap.md`](roadmap.md).
For the technical debt register and launch blockers, see the register: [`docs/DEBT.md`](DEBT.md).

---

## Core Infrastructure Config

- **Backend:** FastAPI monolith (default) with split deployment options under `DEPLOY_MODE=split`.
- **Frontend:** Next.js 15 App Router.
- **Storage:** Storage backend files are canonical for novel metadata, chapters, translations, assets, and exports. PostgreSQL database holds derived projections (catalog, novels, chapters) and canonical domain rows (users, auth, glossary, requests, audits).
- **Worker:** Background activity worker defaults to in-process (`JOB_WORKER_ENABLED=true`). Async queue support via Redis/RQ exists.
- **Settings:** Configured via `pydantic-settings` in `backend/src/novelai/config/settings.py`.

---

## Technical Debt and Blockers Summary

- **V1 Launch Blockers:** Health probes (DEBT-001), CI build checks (DEBT-002), CI Postgres setup (DEBT-003), and admin glossary circular imports (DEBT-006).
- **Technical Debt Register:** Consolidated active registry is in [`docs/DEBT.md`](DEBT.md). Duplicated records have been cleaned.

---

## Validation Status

- **Backend Lint:** Ruff passes clean on backend files.
- **Backend Typecheck:** Pyright type checking passes with 0 errors.
- **Backend Unit Tests:** Core unit tests pass locally. Database-backed tests fail on remote Actions due to missing Postgres service (DEBT-003).
- **Frontend Typecheck:** Next.js type check passes.
- **Frontend Build:** Production build finishes clean.
- **Docker builds:** Local admin, reader, and frontend Dockerfiles build successfully.
