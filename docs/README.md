# Documentation Index

Documentation for Novel AI, organized around the current web-first direction.

## Start Here

- [../readme.md](../readme.md): project overview, local run, production-style run, and verification commands
- [guides/GETTING_STARTED.md](guides/GETTING_STARTED.md): full setup guide, daily workflow, and troubleshooting

## Architecture

- [architecture/architecture.md](architecture/architecture.md): backend/frontend architecture, runtime flow, deployment layout, and future roadmap

## Reference

- [reference/DATA_OUTPUT_STRUCTURE.md](reference/DATA_OUTPUT_STRUCTURE.md): runtime storage, chapter bundle, jobs, requests, exports, and compatibility notes
- [reference/PYTHON_COMMANDS.md](reference/PYTHON_COMMANDS.md): backend launcher commands and useful Python API examples

## Current Direction

Novel AI is being shaped as a production-style web novel platform:

- Next.js owns public reader and admin UI.
- FastAPI serves `/api/*`.
- The worker process handles queued crawler and translation jobs.
- `storage/novel_library` is the local durable data store.
- Documentation now follows the web platform direction only.
