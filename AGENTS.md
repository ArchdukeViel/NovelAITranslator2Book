# AGENTS.md

Agent-neutral onboarding for any AI coding assistant (Hermes, Codex, Cline,
Cursor, etc.) working in this repository.

## Source of Truth

`docs/architecture/architecture.md` is the highest project-level design
authority. This file is a short operational pointer, NOT a replacement. When
this file and the architecture doc disagree, the architecture doc wins. Report
the conflict instead of guessing.

Read before any change:
- `docs/architecture/architecture.md` §4 (backend boundaries & dependency rules)
- `docs/architecture/architecture.md` §14 (current debt register)
- `docs/architecture/architecture.md` §16 (non-negotiable engineering rules)

## What This Project Is

Novel AI is a single-owner / controlled-admin web platform for crawling
Japanese web-novel sources, queueing translation jobs, editing translated
chapters, exporting books, and serving a public reader UI.

- Backend: FastAPI under `/api` (`backend/src/novelai`, import package `novelai`)
- Frontend: Next.js 15 / React 19 / TypeScript (`frontend/`)
- Storage: file-backed runtime data under `storage/` (private, gitignored)
- Worker: background crawler/translation activity process

## Architectural Boundaries (do not cross)

Dependency flow: `api -> services -> domain -> storage/providers/sources/export`.
Frontend calls the backend ONLY through `frontend/lib/api.ts`.

Before editing, identify which boundary owns the change:
- Routers stay thin; use-case logic lives in `services/` and `services/orchestration/`.
- Source parsing lives only in `sources/*`; HTTP/throttle/SSRF/cache in `infrastructure/http/*`.
- Prompt construction only in `prompts/*`; provider API details only in `providers/*`.
- Persistence only behind `storage/*`; scheduler policy in the translation/service/job layer, never in providers or React.
- Forbidden: storage->api, providers->storage, sources->services, translation stages touching FastAPI objects, React implementing scheduler/QA/provider policy.

Preserve canonical field names (`novel_id`, `chapter_id`, `paragraph_id`,
`chunk_id`, `bundle_id`, `provider_key`, `provider_model`, `activity_id`,
`job_id`, `request_id`). Legacy aliases (`id`, `source`, `provider`, `model`,
`slug`) are tolerated debt — do not introduce new ones.

## Blocked Phases (deliberate, NOT missing work)

Do NOT implement these unless the readiness gate in architecture.md §13 is
explicitly moved to Ready:
- Public contribution credentials and encrypted credential storage
- Batch mode, billing, organizations, multi-admin teams

The following are now implemented:
- Public user authentication / registered users (Google OAuth ready, schema supports it)
- `owner_admin` role model and object-level authorization
- Database migration (Supabase PostgreSQL 16)

Do not fake users with localStorage IDs, request-provided user names, unsigned
cookies, or frontend-only flags.

## Security Rules (hard contract)

- Never expose raw provider API keys, auth headers, cookies, or tracebacks in
  logs, error envelopes, provider request records, or API responses.
- Never serve `storage/novel_library` (or any runtime storage) as static files.
- Never accept or return raw filesystem paths across the API boundary.

## Build, Test, Verify

Python >= 3.13 is required (a local `python` may be 3.11 — check first).
Docs use PowerShell; adapt to your shell (git-bash / bash / CI Ubuntu).

Backend (from repo root):
```
pip install -e ".[documents,openai,gemini,dev]"
pytest --tb=short -q      # testpaths = backend/tests
pyright                   # type check (CI enforces pytest + pyright)
ruff check .              # lint (local only; not in CI)
```

Frontend (from `frontend/`):
```
npm install
npm run typecheck         # tsc --noEmit
npm run build
```

Run targets:
```
novelaibook web --reload  # backend, http://127.0.0.1:8000/api
novelaibook worker        # background worker
npm run dev               # frontend, http://127.0.0.1:3000/admin
```

CI (`.github/workflows/ci.yml`) runs pytest + pyright on Python 3.13 only.
Frontend typecheck/build and ruff are NOT in CI — run them locally before
claiming a change is verified.

## Context Hygiene

- Treat `docs/architecture/architecture.md` as authority; do not create
  competing roadmap/architecture docs that fragment the source of truth.
- Do not reintroduce `project_tree.txt` or other tree/scratch exports into the
  repo or `docs/`.
- Verify claims by reading code and running tests; state what you checked and
  what you could not verify.
