# Documentation Index

Documentation for Novel AI, organized around the current web-first direction.

Current mode is single-owner / controlled-admin with file-backed runtime storage, scheduler-enabled admin-owned provider/model routing, and baseline owner/admin security hardening. Public auth, public contribution credentials, database storage, batch mode, billing, organizations, and multi-admin teams are not implemented.

## Start Here

- [../readme.md](../readme.md): project overview, local run, production-style run, and verification commands
- [guides/GETTING_STARTED.md](guides/GETTING_STARTED.md): full setup guide, daily workflow, and troubleshooting

## Architecture

- [architecture/architecture.md](architecture/architecture.md): canonical architecture, current status, runtime flow, security posture, blocked phases, debt register, and roadmap

## Reference

- [reference/DATA_OUTPUT_STRUCTURE.md](reference/DATA_OUTPUT_STRUCTURE.md): runtime storage, chapter bundle, activity/jobs, scheduler state, requests, exports, and compatibility notes
- [reference/PYTHON_COMMANDS.md](reference/PYTHON_COMMANDS.md): backend launcher commands and useful Python API examples

## Current Direction

Novel AI is being shaped as a production-style web novel platform:

- Next.js owns public reader and admin UI.
- FastAPI serves `/api/*`.
- The worker process handles queued crawler and translation activity.
- The translation scheduler handles admin-owned provider/model routing and exposes model state through activity progress.
- `storage/novel_library` is the local durable data store.
- Public contribution credentials remain blocked until the architecture readiness gate says they are safe.
