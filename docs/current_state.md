# NovelAI Current State

**Last updated**: 2026-06-15 (doc audit refresh)
**Source of truth**: `docs/architecture/architecture.md`

## Verdict

**PASS** — Core platform operational. Database migrated to PostgreSQL 16. Google OAuth public login implemented. Public user features (library, progress, history, reviews, requests) re-enabled with CSRF and rate-limit hardening.

---

## Implementation Status

### Fully Implemented

| Component | Status | Notes |
|-----------|--------|-------|
| Translation pipeline | ✅ | Smart segmentation, deterministic IDs, QA stage, chunk traceability |
| Multi-model scheduler | ✅ | Admin-owned provider/model routing, RPM/RPD tracking, pause/resume |
| Source ingestion | ✅ | FetchService, SSRF protection, per-domain throttle, fetch cache |
| Source adapters | ✅ | Syosetu, Novel18, Kakuyomu, Generic with offline fixtures |
| Storage layer | ✅ | File-backed, chapter-based, runtime contracts |
| Provider errors | ✅ | `ProviderError` / `ProviderErrorCode` classification, API error mapping |
|| PostgreSQL database | ✅ | Supabase PostgreSQL 16, 12 ORM models, Alembic migrations applied |
|| Redis/RQ workers | ✅ | Background crawl and translation jobs |
| Authentication | ✅ | HTTP-only sessions, guest/user/owner roles, `require_role()` dependency |
| Public catalog API | ✅ | `/api/public/*` — browse, search, read published chapters |
| User data API | ✅ | `/api/user/*` — library, progress, history, reviews, requests |
| Admin frontend | ✅ | Dashboard, crawler, translation, library, editor, activity, requests, settings |
| Public frontend | ✅ | Novel catalog, chapter reader |
| Security hardening | ✅ | Path traversal protection, secret redaction, SSRF, structured errors |
|| Row Level Security | ✅ | Supabase RLS policies applied (14 tables) |

### Partially Implemented / In Progress

| Component | Status | Notes |
|-----------|--------|-------|
|| Alembic migrations | ✅ | Applied — `bb48b53baff5_initial_schema` on Supabase |
|| Data migration script | ✅ | `backend/src/novelai/scripts/migrate_file_to_db.py` — 1 novel, 12 chapters migrated |
|| Object storage boundary | ⚠️ | Authorized for v1, not yet implemented |
|| Google OAuth | ✅ | Backend routes (`/api/auth/google/start`, `/api/auth/google/callback`), frontend login view, and auth hooks implemented |
| Public user features | ✅ | Library, progress, history, reviews/ratings, requests frontend hooks re-enabled |
| Security hardening | ✅ | CSRF enforcement, public rate limits, production session secret fail-closed |

### Not Implemented (Blocked / Later Phase)

| Component | Status | Reason |
|-----------|--------|--------|
| Public contribution credentials | 🚫 | Later gated phase (architecture.md §13) |
| Encrypted credential storage | 🚫 | Depends on contribution phase |
| Batch mode | 🚫 | Not prioritized |
| Billing, organizations, multi-admin | 🚫 | Out of scope for v1 |

---

## Test Baseline

```
713 passed, 7 skipped (2026-06-09)
```

**CI gates**: pytest + pyright on Python 3.13 only
**Local-only**: ruff lint, frontend typecheck/build

---

## Key Files

| Path | Purpose |
|------|---------|
| `docs/architecture/architecture.md` | Canonical architecture authority |
| `docs/sql/rls_policies.sql` | Supabase RLS policies (338 lines) |
| `backend/src/novelai/api/` | FastAPI app, routers, auth |
| `backend/src/novelai/db/models/` | 12 ORM models |
| `backend/src/novelai/scripts/migrate_file_to_db.py` | Data migration script |
| `backend/src/novelai/storage/` | File-backed persistence |
| `backend/src/novelai/translation/` | Pipeline stages, scheduler |
| `backend/src/novelai/sources/` | Source adapters (Syosetu, Kakuyomu, etc.) |
| `backend/alembic/versions/` | Alembic migrations |
| `frontend/app/(admin)/admin/` | Admin UI pages |
| `frontend/app/(public)/` | Public reader pages |
| `frontend/lib/api.ts` | API client (only frontend/backend contract) |

---

## ORM Models (12 total)

**User domain**:
- `User` — email, role (guest/user/owner), auth_provider, auth_provider_subject
- `LibraryItem` — user_id + novel_id composite key
- `ReadingProgress` — user_id + novel_id composite key
- `ReadingHistory` — read log per chapter
- `Review` — rating + body per user/novel
- `NovelRequest` — user requests for novels/chapters

**Catalog domain**:
- `Novel` — slug, title, author, status, storage keys
- `Chapter` — novel_id, chapter_number, storage keys, checksums

**Job domain**:
- `CrawlJob` — source_url, status, progress
- `TranslationJob` — novel_id, status, provider/model, progress
- `ProviderRequest` — request/response log (no secrets)

**System domain**:
- `AuditLog` — security audit records
- `SystemSetting` — key/value config

---

## API Surface

### Public (guest-accessible)
- `GET /api/public/catalog` — paginated novel list with search/filter
- `GET /api/public/novels/{slug}` — novel detail
- `GET /api/public/novels/{slug}/chapters` — chapter list
- `GET /api/public/novels/{slug}/chapters/{chapter_id}` — translated chapter reader

### User (authenticated, role="user")
- `GET/POST/DELETE /api/user/library/{slug}` — saved novels
- `GET/PUT /api/user/progress/{slug}` — reading progress
- `GET/POST /api/user/history` — reading history
- `POST /api/user/reviews/{slug}` — ratings/reviews
- `GET/POST /api/user/requests` — novel/chapter requests

### Admin (role="owner")
- All `/api/admin/*` routes for crawl, translation, providers, settings, activity

### Auth
- `POST /api/auth/login` — owner login (secret-based bootstrap)
- `GET /api/auth/google/start` — start public Google OAuth login
- `GET /api/auth/google/callback` — complete public Google OAuth login
- `POST /api/auth/logout` — clear session
- `GET /api/auth/me` — current user info

---

## Backend Modules

```
backend/src/novelai/
├── activity/         Background activity queue, runner, worker
├── api/              FastAPI app, routers, dependencies
│   ├── auth/         Session management, role enforcement
│   └── routers/      public, user_data, auth, activity, requests
├── config/           Settings and workflow profiles
├── core/             Shared domain errors, primitive types
├── db/               SQLAlchemy engine, session, models
│   └── models/       12 ORM models
├── export/           Exporter interfaces and output formats
├── glossary/         Glossary and term memory
├── infrastructure/   HTTP fetching, throttle, cache
├── inputs/           Non-web input adapters
├── prompts/          Prompt builders, templates, parsing
├── providers/        LLM provider interfaces (Gemini, OpenAI)
├── runtime/          CLI, bootstrap, container
├── services/         Application use cases, orchestration
├── shared/           Cross-domain protocols, pipeline contracts
├── sources/          Web source parsers (Syosetu, Kakuyomu, Generic)
├── storage/          File-backed persistence boundary
├── translation/      Pipeline stages, QA, scheduler
├── utils/            Pure utilities
└── worker/           RQ tasks and queue management
```

---

## Frontend Routes

**Admin** (`/admin/*`):
- `/admin/dashboard` — overview
- `/admin/crawler` — crawl jobs
- `/admin/translation` — translation jobs
- `/admin/library` — novel library
- `/admin/editor` — chapter editor
- `/admin/activity` — activity log
- `/admin/requests` — user requests
- `/admin/settings` — provider/settings config

**Public** (`/novel/*`):
- `/novel/[slug]` — novel detail
- `/novel/[slug]/chapter/[chapterId]` — chapter reader

---

## Debt Summary

**P0 (correctness/security)**:
- Scheduler runtime persistence hardening
- Private storage isolation verification

**P1 (maintainability)**:
- Router thinning (operations.py, admin.py)
- Kakuyomu/Generic FetchService migration verification
- Legacy alias migration plan

**P2 (cosmetic)**:
- Frontend lint configuration
- Documentation examples

---

## Next Milestones

1. ~~Create Alembic migrations folder and initial migration~~ ✅ Done
2. ~~Run data migration (file-backed → Postgres)~~ ✅ Done (1 novel, 12 chapters)
3. ~~Wire Google OAuth for public user login~~ ✅ Done
4. ~~Public user features re-enable (library, progress, history, reviews, requests)~~ ✅ Done
5. ~~CSRF, rate-limit, and security hardening~~ ✅ Done
6. Implement object storage boundary (S3/R2/B2)
7. Scheduler resume hardening
8. Production deployment (DEP1)

---

## Run Commands

```bash
# Backend (from repo root, using venv python)
./.venv/Scripts/python -m novelaibook web --reload   # API server
./.venv/Scripts/python -m novelaibook worker         # Background worker

# Frontend
cd frontend && npm run dev                           # Admin UI

# Tests
./.venv/Scripts/python -m pytest backend/tests -q
./.venv/Scripts/python -m pyright
```

---

## Security Checklist

- [x] Path traversal protection
- [x] Secret redaction in logs/responses
- [x] SSRF protection in FetchService
- [x] Runtime storage isolation
- [x] Structured error envelopes (no raw tracebacks)
- [x] HTTP-only session cookies
- [x] Role-based authorization (`require_role()`)
- [x] Object-level authorization on user-owned endpoints
- [x] Row Level Security (Supabase RLS policies applied)
- [x] CSRF token enforcement for cookie-auth mutations
- [x] Basic public rate limits (auth, user data, engagement)
- [x] Production session secret fail-closed
- [x] Google OAuth public login (separate from owner bootstrap)
- [ ] Encrypted credential storage (later phase)
- [ ] Security audit logging (schema ready, not wired)
