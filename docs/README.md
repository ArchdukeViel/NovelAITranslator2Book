# Documentation Index

Documentation for Novel AI, organized around the current web-first direction.

Current mode is single-owner / controlled-admin with Supabase PostgreSQL 16 for metadata, file-backed chapter content, scheduler-enabled admin-owned provider/model routing, and baseline owner/admin security hardening. Public auth and database storage are implemented. Public contribution credentials, batch mode, billing, organizations, and multi-admin teams are not implemented.

## Start Here

- [../readme.md](../readme.md): project overview, local run, production-style run, and verification commands
- [guides/GETTING_STARTED.md](guides/GETTING_STARTED.md): full setup guide, daily workflow, and troubleshooting

## Architecture

- [architecture/architecture.md](architecture/architecture.md): canonical architecture, current status, runtime flow, security posture, blocked phases, debt register, and roadmap
- [architecture/public-auth-contract.md](architecture/public-auth-contract.md): public auth and user data contract design (Google OAuth, `/api/user/*` contracts, implementation phases)

## Roadmap

- [roadmap/public-platform-expansion.md](roadmap/public-platform-expansion.md): historical multi-phase platform expansion plan (phases 1–6 complete, retained for context)

## Reference

- [reference/DATA_OUTPUT_STRUCTURE.md](reference/DATA_OUTPUT_STRUCTURE.md): runtime storage, chapter bundle, activity/jobs, scheduler state, requests, exports, and compatibility notes
- [reference/PYTHON_COMMANDS.md](reference/PYTHON_COMMANDS.md): backend launcher commands and useful Python API examples

## Current Direction

Novel AI is a production-style web novel platform:

- Next.js owns public reader and admin UI.
- FastAPI serves `/api/*`.
- The worker process handles queued crawler and translation activity.
- The translation scheduler handles admin-owned provider/model routing and exposes model state through activity progress.
- `storage/novel_library` is the local durable data store for chapter content; PostgreSQL 16 is the system of record for metadata, users, and jobs.
- Google OAuth provides public user login; public users can save library, track progress, view history, rate/review, and request novels/chapters.
- CSRF enforcement and basic rate limits protect cookie-authenticated mutations.
- Production session secret fails closed when left at default value.
- Public contribution credentials remain blocked until the architecture readiness gate says they are safe.
