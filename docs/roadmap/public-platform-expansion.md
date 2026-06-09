# Public Platform Expansion Implementation Plan

> **For Hermes:** This is a multi-phase platform-evolution plan derived from
> `novelai_wtr_lab_single_owner_platform_notes.txt`. Phases 1–2 are broken into
> bite-sized tasks ready for `subagent-driven-development`. Phases 3–10 are
> structured outlines — each must get its own detailed task-level plan when its
> prerequisites land (decisions in later phases depend on earlier phase output).

**Goal:** Evolve Novel AI from a single-owner, file-backed local translation
tool into a WTR-LAB-like public reading + machine-translation platform, using a
single-owner admin model (guest / user / owner), backed by PostgreSQL, Redis/RQ
workers, and backend-enforced authorization.

**Architecture:** Keep the existing FastAPI (`backend/src/novelai`) + Next.js
(`frontend/`) split and the chapter-based file/object storage for heavy content.
Introduce PostgreSQL (via SQLAlchemy + Alembic) as the system of record for
metadata and user-facing state. Move crawl/translation work onto Redis + RQ
background workers. Add guest/user/owner auth enforced in the backend, never the
frontend.

**Tech Stack:** Python 3.13, FastAPI, SQLAlchemy 2.x, Alembic, PostgreSQL 16,
Redis + RQ, Next.js 15 / React 19, Docker Compose, Caddy/Cloudflare for
HTTPS/DNS, S3-compatible object storage (R2/B2/MinIO) at public scale.

---

## CRITICAL: Conflict With Canonical Architecture (resolve before any code)

`docs/architecture/architecture.md` is the repo's declared source of truth. It
**currently forbids** most of what these notes propose:

- §3 Non-Goals & §12 Readiness Gate ("Not Ready") explicitly block: public user
  authentication, `owner_admin` roles, object-level authorization, database
  migration, batch mode, multi-tenant.
- §8 declares storage **file-backed**, not database-backed.

The notes themselves (§10) say the correct order is: audit → **update
architecture.md** → then build the database foundation. This plan honors that.
**No schema, auth, or worker code is written until architecture.md is formally
updated to authorize the new platform direction (Phase 1).** Skipping this means
every later phase silently violates the project's own highest authority.

**Scope distinction:** The notes' "public users" (read, save to library, track
progress, rate, request) are a *lighter* model than architecture.md's blocked
"public contribution credentials" (users donating Gemini/OpenAI API keys). This
plan implements the lighter read/user model and keeps credential-contribution
explicitly out of scope (still blocked).

---

## Phase Overview

| Phase | Theme | Output type | Status |
|---|---|---|---|
| 1 | Architecture expansion + arch.md update | Docs/decisions | ✅ Complete |
| 2 | Database foundation (SQLAlchemy + Alembic + Postgres) | Code (detailed) | ✅ Complete (Supabase) |
| 3 | Background workers (Redis + RQ) | Code (outline) | ✅ Complete |
| 4 | Auth: guest / user / owner | Code (outline) | ✅ Complete |
| 5 | Public reader features | Code (outline) | Phase 2 + 4 |
| 6 | User library / progress / ratings / requests | Code (outline) | Phase 4 + 5 |
| 7 | Owner dashboard hardening | Code (outline) | Phase 3 + 4 |
| 8 | Hosting / deployment | Infra (outline) | Phase 2–4 stable |
| 9 | Monitoring / backups / rate limiting | Infra (outline) | Phase 8 |
| 10 | Search / recommendation upgrades | Code (outline) | Phase 5 stable |

**Hard sequencing rule (from notes §5):** architecture → DB → migrations →
workers → auth → public read → user features → owner dashboard → hosting →
monitoring → search. Do **not** add Google login, deploy publicly, or let users
trigger paid translation jobs before the owner boundary is backend-enforced.

---

## Phase 1 — Architecture Expansion & architecture.md Update

**Objective:** Formally re-authorize the project direction so later phases are
legal under the source-of-truth doc. Planning + doc edits only; no app code.

### Task 1.1: Add a "Public Platform Mode" section to architecture.md

**Files:**
- Modify: `docs/architecture/architecture.md` (§0 status block + new section)

**Steps:**
1. Update the §0 "Current mode" block: change `not database-backed` /
   `not multi-tenant` framing to describe a planned, gated transition to
   `single-owner public platform (guest/user/owner), Postgres-backed metadata,
   file/object-backed content`.
2. Add a new top-level section "Public Platform Mode (Planned)" capturing the
   guest/user/owner boundary, the Postgres-as-system-of-record decision, and the
   Redis/RQ worker decision.
3. Explicitly state that **public contribution credentials remain blocked** —
   this expansion does NOT unblock §12.
4. Cross-reference this plan file.

**Verification:** `architecture.md` no longer self-contradicts the planned DB +
auth work; §12 contribution-credential gate is untouched and still "Not Ready".

### Task 1.2: Record the permission matrix in architecture.md

**Files:**
- Modify: `docs/architecture/architecture.md` (new "Permission Matrix" subsection)

**Step:** Paste the guest/user/owner capability matrix (see end of this plan) so
the backend authorization rules have a documented source.

### Task 1.3: Update AGENTS.md blocked-phases note

**Files:**
- Modify: `AGENTS.md` (Blocked Phases section)

**Step:** Clarify that DB + guest/user/owner auth are now *planned and
authorized* (pointing at this plan), while contribution credentials, batch mode,
billing, and multi-admin teams remain blocked.

**Commit (end of Phase 1):**
```bash
git add docs/architecture/architecture.md AGENTS.md
git commit -m "docs: authorize single-owner public platform direction"
```

---

## Phase 2 — Database Foundation (SQLAlchemy + Alembic + PostgreSQL)

**Objective:** Stand up Postgres as the metadata system of record with the core
tables from notes §6, migrations, and a clean storage boundary — without
breaking existing file-backed chapter storage. TDD throughout.

**Architecture rule:** All DB access lives behind `backend/src/novelai/db/` and
is consumed by `services/*`. Routers never touch the session directly. Heavy
content (raw/translated chapter text, covers, logs, exports) stays in
file/object storage; Postgres stores paths/keys/checksums + metadata.

### Task 2.1: Add dependencies and a `documents`-style `db` extra

**Files:**
- Modify: `pyproject.toml` (add `db` optional-dependency group)

**Step:** Add a `db` extra with `sqlalchemy>=2.0`, `alembic>=1.13`,
`psycopg[binary]>=3.2`. Do NOT add to base deps (keep file-only dev installable).

**Verify:** `pip install -e ".[db]"` resolves; `python -c "import sqlalchemy, alembic"`.

### Task 2.2: Add Postgres + Redis to local Docker Compose

**Files:**
- Modify: `deploy/compose.yml` (add `postgres` and `redis` services + volumes)
- Modify: `.env.example` (add `DATABASE_URL`, `REDIS_URL`)

**Step:** Add `postgres:16` and `redis:7` services with named volumes and
healthchecks. Wire `DATABASE_URL=postgresql+psycopg://...` and `REDIS_URL`.

**Verify:** `docker compose -f deploy/compose.yml up -d postgres redis` →
`docker compose exec postgres pg_isready` returns accepting connections.

### Task 2.3: Create the DB engine/session module (TDD)

**Files:**
- Create: `backend/src/novelai/db/__init__.py`
- Create: `backend/src/novelai/db/engine.py`
- Test: `backend/tests/test_db_engine.py`

**Step 1 — failing test:** assert `get_sessionmaker(url)` returns a sessionmaker
and a context-managed session yields a working `SELECT 1`.
**Step 2:** run `pytest backend/tests/test_db_engine.py -v` → FAIL.
**Step 3:** implement `engine.py` (engine factory, `session_scope()` contextmanager,
settings-driven URL from `config/settings.py`).
**Step 4:** run test → PASS (use SQLite in-memory for the unit test; Postgres in
integration).
**Step 5:** commit.

### Task 2.4: Declarative base + first model `Novel` (TDD)

**Files:**
- Create: `backend/src/novelai/db/base.py` (DeclarativeBase, naming convention)
- Create: `backend/src/novelai/db/models/novel.py`
- Test: `backend/tests/test_db_models_novel.py`

**Step:** Model fields per notes §6 `novels` (id, slug, title, original_title,
author, source_site, source_url, language, status, synopsis, cover_storage_key,
created_at, updated_at). TDD: test create + slug-unique constraint against
in-memory SQLite. Commit.

### Task 2.5: Add `Chapter` model (TDD)

**Files:**
- Create: `backend/src/novelai/db/models/chapter.py`
- Test: `backend/tests/test_db_models_chapter.py`

**Step:** Fields per notes §6 `chapters` (novel_id FK, chapter_number, title,
source_url, raw_storage_key, translated_storage_key, raw_status,
translation_status, word_count, timestamps). Test FK + cascade. Commit.

### Task 2.6: Add job/usage models (TDD)

**Files:**
- Create: `backend/src/novelai/db/models/jobs.py` (`CrawlJob`, `TranslationJob`, `ProviderRequest`)
- Test: `backend/tests/test_db_models_jobs.py`

**Step:** Fields per notes §6. Map existing file-backed job/provider-record
concepts onto these tables; do not delete file-backed code yet (parallel-run).
Commit.

### Task 2.7: Add user-facing models (TDD)

**Files:**
- Create: `backend/src/novelai/db/models/users.py` (`User`, `ReadingProgress`, `LibraryItem`, `Review`, `Request`)
- Create: `backend/src/novelai/db/models/system.py` (`AuditLog`, `SystemSetting`)
- Test: `backend/tests/test_db_models_user_system.py`

**Step:** Fields per notes §6. `User.role` enum = {guest, user, owner}. Commit.

### Task 2.8: Initialize Alembic + autogenerate first migration

**Files:**
- Create: `backend/alembic.ini`, `backend/alembic/env.py`, `backend/alembic/versions/0001_initial.py`

**Steps:**
1. `alembic init backend/alembic`; point `env.py` at `db.base.Base.metadata` and
   `DATABASE_URL`.
2. `alembic revision --autogenerate -m "initial schema"`.
3. Review the generated migration by hand (autogen is not trusted blindly).
4. `alembic upgrade head` against the compose Postgres; `alembic downgrade base`
   then `upgrade head` again to prove reversibility.
**Verify:** tables exist (`\dt` in psql); round-trip up/down clean. Commit.

### Task 2.9: Storage-key bridge service (TDD)

**Files:**
- Create: `backend/src/novelai/services/catalog_service.py`
- Test: `backend/tests/test_catalog_service.py`

**Step:** Service that writes chapter text to file/object storage and persists
`{raw,translated}_storage_key` + checksum in Postgres. Keeps storage-path
knowledge inside the storage boundary (arch.md §8). TDD with a temp dir + SQLite.
Commit.

---

## Phase 3 — Background Workers (Redis + RQ)

**Objective:** Move crawl + translation work off request/response routes onto RQ
workers, with retry, provider-usage recording, and job state in Postgres.

**Outline (expand to tasks when Phase 2 merges):**
- Add `rq>=1.16` to the `db`/new `worker` extra.
- Create `backend/src/novelai/worker/queue.py` (RQ queue factory bound to `REDIS_URL`).
- Create `backend/src/novelai/worker/tasks.py` — enqueueable functions: crawl
  metadata, crawl chapter list, fetch raw chapter, segment, translate chapter,
  retry failed, record provider usage, scheduled refresh.
- Job lifecycle: enqueue → `CrawlJob`/`TranslationJob` row updated by worker →
  `ProviderRequest` rows written per attempt. Reuse existing translation
  pipeline + scheduler (arch.md §5/§6) — do NOT reimplement.
- Add a `worker` service to `deploy/compose.yml` (`rq worker`).
- Tests: enqueue→execute with a fake/inline RQ connection; assert job-state
  transitions and provider-usage rows.
- **Pitfall:** the existing in-process scheduler/activity worker must be
  parallel-run, then cut over — not deleted up front.

**Recommendation from notes:** RQ first, Celery only if complexity demands it.

---

## Phase 4 — Authentication & Authorization (guest / user / owner)

**Objective:** Backend-enforced role boundary. Owner-only operations rejected at
the API layer, never relying on frontend route hiding.

**Outline (expand when Phase 2 stable; can parallel Phase 3):**
- Add `user` role plumbing on the `User` model (already created Task 2.7).
- Session strategy: secure HTTP-only cookie session OR JWT — decide in Phase 1
  doc; default to HTTP-only server session for owner safety.
- Create `backend/src/novelai/api/auth/` — login, logout, session dependency,
  `require_role(...)` FastAPI dependency.
- Apply `require_role("owner")` to every dangerous router (crawler, translation
  start, provider config, usage, logs, edit/delete, settings, user mgmt).
- Guest = unauthenticated read of public catalog/chapters only.
- Google OAuth: **design now, implement last** (notes §7/§9 — do not add before
  schema design; it's an optional login method, not the foundation).
- Tests (mandatory, from notes): prove user A cannot reach owner endpoints, and
  unauthenticated calls to owner API return 401/403 — not 200.
- **Pitfall:** seed exactly one owner via env/CLI bootstrap, not via a public
  signup path.

---

## Phase 5 — Public Reader Features

**Objective:** WTR-LAB-like public browsing over the Postgres catalog.

**Outline (Phase 2 + 4):**
- Backend read endpoints: catalog list (paginated), novel detail, chapter
  reader, search/filter (title/author/tag/status/language/recent/popular).
- Frontend public routes already exist under `frontend/app/(public)/*` — wire
  them to the new endpoints via `frontend/lib/api.ts` only (arch.md §9/§10).
- Search: PostgreSQL full-text/trigram first. No Meilisearch/Typesense yet.
- Tests: endpoint contract tests + frontend `npm run typecheck`/`build`.

---

## Phase 6 — User Library / Progress / Ratings / Requests

**Objective:** Logged-in user features over models from Task 2.7.

**Outline (Phase 4 + 5):**
- Endpoints: save/remove library item, upsert reading progress, post rating/
  review, create novel/chapter request (rate-limited).
- Requests are **requests only** — they never auto-trigger paid translation;
  the owner approves/runs (permission matrix).
- Frontend: library, continue-reading, rating UI, request form.
- Tests: per-endpoint authz (user-owned objects only) + rate-limit behavior.

---

## Phase 7 — Owner Dashboard Hardening

**Objective:** Owner-only operational control surface.

**Outline (Phase 3 + 4):**
- Owner dashboard endpoints + pages (extend existing `frontend/app/(admin)/admin/*`):
  running jobs, failed jobs, provider usage/cost, recent errors, queue size,
  storage status, user management, unpublish/delete with reason, system settings.
- All backed by `require_role("owner")` and writing `AuditLog` rows for
  dangerous actions.
- Tests: every owner action emits an audit-log row; non-owner is rejected.

---

## Phase 8 — Hosting / Deployment

**Objective:** First public deployment without exposing the owner boundary.

**Outline (Phase 2–4 stable):**
- Local: Docker Compose (backend, frontend, postgres, redis, worker).
- First public: VPS + Docker Compose + Postgres + Redis + worker + reverse proxy
  (Caddy) with HTTPS + Cloudflare DNS/proxy.
- Object storage (R2/B2/MinIO) for covers/chapters/logs/exports at scale;
  store keys/checksums in Postgres.
- **Hard gate:** do NOT deploy publicly until Phase 4 owner boundary is verified
  by tests. No Kubernetes (notes §9).

---

## Phase 9 — Monitoring, Backups, Rate Limiting

**Outline (Phase 8):**
- Structured backend + worker logs; failed-job table surfaced to owner.
- Scheduled Postgres backups + storage backups; secrets backed up separately.
- Rate limiting on: login, search, request endpoints, job creation, any
  provider-backed action. **Public users must not burn translation quota.**
- Owner-visible system health page.

---

## Phase 10 — Search / Recommendation Upgrades (optional, last)

**Outline (Phase 5 stable):**
- Only if Postgres search proves insufficient: evaluate Meilisearch/Typesense.
- No Elasticsearch, no recommendation AI yet (notes §9).

---

## Single-Owner Permission Matrix (authoritative)

| Capability | Guest | User | Owner |
|---|---|---|---|
| View public catalog | Yes | Yes | Yes |
| Read public chapters | Yes | Yes | Yes |
| Search/filter novels | Yes | Yes | Yes |
| Save to library | No | Yes | Yes |
| Track reading progress | No | Yes | Yes |
| Rate/review | No | Yes | Yes |
| Request novel/chapter | Limited | Yes (rate-limited) | Yes |
| Start crawler | No | No | Yes |
| Start translation | No | Request only | Yes |
| Edit metadata | No | No | Yes |
| Delete/unpublish content | No | No | Yes |
| View logs/errors | No | No | Yes |
| Configure providers | No | No | Yes |
| View provider/API usage | No | No | Yes |
| Manage users | No | No | Yes |
| Change system settings | No | No | Yes |

**Core rule:** Owner does dangerous operations. Users request things. Guests read
public content. Enforced in the backend.

---

## Risks, Tradeoffs, Open Questions

- **Biggest risk — dual source of truth.** This plan is meaningless until
  architecture.md is updated (Phase 1). Building DB/auth while the canonical doc
  forbids them violates the project's own rules. Phase 1 is non-negotiable first.
- **File→DB migration risk.** Existing novels/chapters/jobs live in
  `storage/novel_library`. Phase 2 must parallel-run (DB alongside files), with a
  one-time backfill script, before any file-backed code is removed. Do not
  big-bang delete file storage.
- **Paid-quota abuse.** Until rate limiting (Phase 9) and the owner boundary
  (Phase 4) exist, no public exposure (Phase 8). Hard ordering.
- **Auth method undecided.** HTTP-only session vs JWT, and whether Google OAuth
  ships at all — needs an owner decision in Phase 1.
- **Scope creep vs blocked features.** Contribution credentials, billing,
  multi-admin, batch mode stay blocked. This plan must not quietly reintroduce them.

## Open Questions for the Owner (answer before Phase 2 code)
1. Approve the architecture.md direction change (Phase 1)? Without this, stop.
2. Session cookies or JWT for owner/user auth?
3. Ship Google OAuth in v1, or email/password only with OAuth later?
4. Target first-deploy host (VPS provider) — affects compose/proxy specifics?
5. Keep file-backed chapter storage long-term (DB stores keys), or migrate
   content into object storage immediately at deploy time?

## Validation / Missing Repo Evidence
- Confirm current job/activity worker is in-process (arch.md §6 implies yes) so
  Phase 3 cutover is parallel-run, not rewrite.
- Confirm `deploy/compose.yml` current services before adding postgres/redis/worker.
- Confirm `frontend/lib/api.ts` is still the sole client (arch.md §9) before
  wiring public endpoints.
- No existing Alembic/SQLAlchemy usage found — Phase 2 is greenfield DB work.

---

## Execution Handoff

Phase 1 (architecture.md update) needs **owner approval of direction first** — it
changes the project's highest-authority document. Once approved, Phases 1–2 are
task-level and ready for `subagent-driven-development` (fresh subagent per task,
spec-compliance review then code-quality review). Phases 3–10 each need a
detailed task-level plan written when their prerequisites land.
