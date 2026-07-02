# NovelAI Current State

**Last updated**: 2026-07-02 (post-OPS-SAFETY-1)
**Source of truth**: `docs/architecture/architecture.md`

## Verdict

**PASS** — Core platform operational. Database migrated to PostgreSQL 16. Public auth supports Google OAuth plus email/password sign-up, sign-in, and sign-out. Owner bootstrap login is admin-only and separate from public auth. Public user features (library, progress, history, reviews, requests) remain enabled with CSRF and rate-limit hardening.

---

## Auth State

- Email/password backend auth is complete for public sign-up and sign-in.
- Email/password public UI is complete alongside Google OAuth.
- Public auth supports Google OAuth plus email/password; Google OAuth requires Dokushodo OAuth configuration.
- Public sign-up/sign-in creates and uses normal public user sessions only (`role="user"`), never owner sessions.
- Owner bootstrap login is admin-only at `POST /api/auth/login` and is separate from public sign-in/sign-up.
- Public auth UI must not expose owner, admin, secret, or bootstrap wording.
- Password reset is not implemented yet.
- Email verification is not implemented yet.
- Auth smoke passed after the backend, public frontend, and admin-owner-login auth phases.

---

## Implementation Status

### Fully Implemented

| Component | Status | Notes |
|-----------|--------|-------|
| Translation pipeline | ✅ | Smart segmentation, deterministic IDs, QA stage, chunk traceability |
| Translation optimization stack | ✅ | Request estimator, retry ceiling, metadata batching, adaptive chunking, conditional overlap, paragraph hash lineage, delta window estimator, conservative delta retranslation, structured provider JSON hardening |
| Multi-model scheduler | ✅ | Admin-owned provider/model routing, RPM/RPD tracking, pause/resume |
| Source ingestion | ✅ | FetchService, SSRF protection, per-domain throttle, fetch cache |
| Source adapters | ✅ | Syosetu, Novel18, Kakuyomu, Generic with offline fixtures; Syosetu live smoke confirmed; Kakuyomu trailing-slash URL canonicalization fixed |
| Source pipeline hardening | ✅ | GenericSource ruby/preflight/confidence, KakuyomuSource preflight/UTF-8/UA/Kakuyomu URL canonicalization, per-chapter partial failure, in-process crawl lock, block-page regex refined |
| Storage layer | ✅ | File-backed, chapter-based, runtime contracts |
| Provider errors | ✅ | `ProviderError` / `ProviderErrorCode` classification, API error mapping |
|| PostgreSQL database | ✅ | Supabase PostgreSQL 16, 12 ORM models, Alembic migrations applied |
|| Redis/RQ workers | ✅ | Background crawl and translation jobs |
| Authentication | ✅ | HTTP-only sessions, guest/user/owner roles, `require_role()` dependency; public Google OAuth plus email/password auth implemented |
|| Public catalog API | ✅ | `/api/public/*` — browse, search, read published chapters; `PublicNovelSummary` includes `source_title` and `synopsis` |
|| Public taxonomy contract | ✅ | Genre/tag display labels, adult filtering internal via ORM, `is_adult` stripped from public API responses |
| Public frontend polish | ✅ | Loading/error/empty states, SEO, trust pages, auth UX, account honesty, de-AI copy; catalog summary enrichment (source_title, synopsis) |
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
|| Public auth | ✅ | Google OAuth plus email/password backend routes, frontend login/sign-up UI, and auth hooks implemented |
| Public user features | ✅ | Library, progress, history, reviews/ratings, requests frontend hooks re-enabled |
| Security hardening | ✅ | CSRF enforcement, public rate limits, production session secret fail-closed |

### Not Implemented (Blocked / Later Phase)

| Component | Status | Reason |
|-----------|--------|--------|
| Public contribution credentials | 🚫 | Later gated phase (architecture.md §13) |
| Encrypted credential storage | 🚫 | Depends on contribution phase |
| Password reset | 🚫 | Not implemented yet |
| Email verification | 🚫 | Not implemented yet |
| Batch mode | 🚫 | Not prioritized |
| Billing, organizations, multi-admin | 🚫 | Out of scope for v1 |

---

## Test Baseline

```
Backend: 150+ tests pass (pytest, 2026-06-18)
  - test_crawl_resilience_contracts.py: 21 passed (contract tests for crawl behavior)
  - test_novel_orchestration_service.py: 56 passed
  - test_taxonomy.py: 37 passed
  - test_public_router.py: 83 passed (incl. source_title, synopsis, is_adult contract)
  - test_gemini_provider.py: 12 passed
  - test_translation_qa.py: 21 passed
  - test_source_quality.py: 8 passed
  - test_storage_service.py: 31 passed
  - (full suite: 730+ total)

Frontend: 411 tests pass (vitest, 2026-06-17) — unchanged
  - 40 test files
  - taxonomy-contract.test.tsx: 9 passed
  - browse-page.test.tsx: 42 passed

Auth smoke: PASS (2026-06-18) after email/password backend, public auth UI, and admin-owner-login phases. Public auth smoke confirmed sign-up/sign-in/sign-out, safe failures, duplicate-email handling, Google unavailable messaging, admin-only owner login, and the public auth boundary.
```

**CI gates**: pytest + pyright on Python 3.13 only
**Local-only**: ruff lint, frontend typecheck/build

---

## Current Spec Burndown (`.kiro/specs/`)

All 8 specs are 100% complete:

| Spec | Tasks | Status |
|------|-------|--------|
| create-novel-lifecycle | 28/28 | ✅ Done |
| glossary-apply-safety | 55/55 | ✅ Done |
| glossary-first-onboarding | 53/53 | ✅ Done |
| glossary-sync-bridge | 49/49 | ✅ Done |
| operational-safety-observability | 53/53 | ✅ Done |
| prompt-translation-hardening | 57/57 | ✅ Done |
| public-path-performance | 49/49 | ✅ Done |
| translation-qa-hardening | 52/52 | ✅ Done |
| translation-resume-hardening | 46/46 | ✅ Done |

---

## Key Files

| Path | Purpose |
|------|---------|
| `docs/architecture/architecture.md` | Canonical architecture authority |
| `docs/current_state.md` | This file — project state tracking |
| `docs/sql/rls_policies.sql` | Supabase RLS policies (338 lines) |
| `backend/src/novelai/api/` | FastAPI app, routers, auth |
| `backend/src/novelai/db/models/` | 14 ORM models (incl. Genre, Tag) |
| `backend/src/novelai/scripts/migrate_file_to_db.py` | Data migration script |
| `backend/src/novelai/storage/` | File-backed persistence |
| `backend/src/novelai/translation/` | Pipeline stages, QA, scheduler |
| `backend/src/novelai/sources/` | Source adapters (Syosetu, Kakuyomu, etc.) |
| `backend/alembic/versions/` | Alembic migrations |
| `frontend/app/(admin)/admin/` | Admin UI pages |
| `frontend/app/(public)/` | Public reader pages |
| `frontend/lib/api.ts` | Admin API client |
| `frontend/lib/public-api.ts` | Public API client (guest/user) |
| `frontend/lib/public-types.ts` | Public API TypeScript types |

---

## ORM Models (14 total)

**User domain**:
- `User` — email, password_hash, role (guest/user/owner), auth_provider, auth_provider_subject
- `LibraryItem` — user_id + novel_id composite key
- `ReadingProgress` — user_id + novel_id composite key
- `ReadingHistory` — read log per chapter
- `Review` — rating + body per user/novel
- `NovelRequest` — user requests for novels/chapters

**Catalog domain**:
- `Novel` — slug, title, author, status, storage keys
- `Chapter` — novel_id, chapter_number, storage keys, checksums
- `Genre` — slug, name_ja, name_en, is_adult, display_order, is_active
- `Tag` — name, name_ja, is_adult
- `novel_genres` — novel/genre association table
- `novel_tags` — novel/tag association table

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
- `GET /api/public/genres` — genre list (no `is_adult` field)
- `GET /api/public/tags/search` — tag search (no `is_adult` field)

### User (authenticated, role="user")
- `GET/POST/DELETE /api/user/library/{slug}` — saved novels
- `GET/PUT /api/user/progress/{slug}` — reading progress
- `GET/POST /api/user/history` — reading history
- `POST /api/user/reviews/{slug}` — ratings/reviews
- `GET/POST /api/user/requests` — novel/chapter requests

### Admin (role="owner")
- All `/api/admin/*` routes for crawl, translation, providers, settings, activity

### Auth
- `POST /api/auth/login` — admin-only owner login (secret-based bootstrap)
- `POST /api/auth/register` — public email/password sign-up; creates normal `role="user"` sessions only
- `POST /api/auth/password/login` — public email/password sign-in; uses normal public user sessions only
- `GET /api/auth/google/start` — start public Google OAuth login; requires Dokushodo OAuth configuration
- `GET /api/auth/google/callback` — complete public Google OAuth login; requires Dokushodo OAuth configuration
- `POST /api/auth/logout` — clear session
- `GET /api/auth/me` — current user info

Public sign-up/sign-in must never create or expose owner/admin access and must not show owner, admin, secret, or bootstrap wording. Owner bootstrap remains separate from public sign-in/sign-up.

---

## Backend Modules

```
backend/src/novelai/
├── activity/         Background activity queue, runner, worker
├── api/              FastAPI app, routers, dependencies
│   ├── auth/         Session management, role enforcement
│   └── routers/      public, user_data, auth, activity, requests, admin_taxonomy
├── config/           Settings and workflow profiles
├── core/             Shared domain errors, primitive types
├── db/               SQLAlchemy engine, session, models
│   └── models/       14 ORM models (incl. Genre, Tag, association tables)
├── export/           Exporter interfaces and output formats
├── glossary/         Glossary and term memory
├── infrastructure/   HTTP fetching, throttle, cache
├── inputs/           Non-web input adapters
├── prompts/          Prompt builders, templates, parsing
├── providers/        LLM provider interfaces (Gemini, NVIDIA)
├── runtime/          CLI, bootstrap, container
├── services/         Application use cases, orchestration
├── shared/           Cross-domain protocols, pipeline contracts
├── sources/          Web source parsers (Syosetu, Kakuyomu, Generic)
├── storage/          File-backed persistence boundary
├── translation/      Pipeline stages, QA, scheduler, delta estimator
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

**Public** (`/*`):
- `/home` — homepage with latest novels, updates
- `/browse-novels` — catalog browse with genre/tag filters
- `/novel/[slug]` — novel detail
- `/novel/[slug]/chapter/[chapterId]` — chapter reader
- `/ranking` — ranking page
- `/request-novel` — novel request form
- `/contribute` — contribution page
- `/account/*` — account settings, contributions, library
- `/login`, `/register`, `/logout` — auth flows
- Static trust pages: `/about`, `/privacy`, `/terms`, `/dmca`, `/contact`, `/cookie-policy`

---

## Debt Summary

**P0 (correctness/security)**:
- ~~Scheduler runtime persistence hardening~~ ✅ Done (TR-OPT stack)
- ~~Private storage isolation verification~~ ✅ Done (public API contract tests)
- Object storage boundary (S3/R2/B2) — not yet implemented
- Broader real-provider smoke on slightly larger input — monitor Gemini metadata batch

**P1 (maintainability)**:
- Router thinning (operations.py, admin.py)
- GenericSource FetchService migration verification
- Legacy alias migration plan
- ~~Source pipeline audit / ingestion fixes~~ ✅ Done (AUDIT-1, FIX-1, FIX-2A/B/C, FIX-3)
- ~~Kakuyomu work URL canonicalization~~ ✅ Done (trailing-slash URL pattern fixed in FIX-3B)

**P2 (cosmetic)**:
- Frontend lint configuration
- Documentation examples
- TAXONOMY-5C: tag `name_ja` display
- TAXONOMY-5D: public genre enrichment / label payload decision
- Admin provider credential UI (currently env-based only)

---

## Next Milestones

### Completed (2026-07-02)

**Translation optimization stack (TR-OPT-1 through TR-OPT-6C)**:
1. ✅ Request estimator / dry run
2. ✅ Max attempts per chunk (retry ceiling)
3. ✅ Metadata batching (title/author/synopsis/chapter titles)
4. ✅ Adaptive balanced chunking
5. ✅ Conditional chunk overlap
6. ✅ Paragraph hash lineage
7. ✅ Delta window estimator
8. ✅ Conservative delta retranslation execution
9. ✅ Backend full suite restored (dependency/test isolation fix)
10. ✅ Tiny Gemini body smoke passed
11. ✅ Structured provider JSON handling hardened

**Taxonomy contract (TAXONOMY-2E, TAXONOMY-5B)**:
1. ✅ Public taxonomy contract aligned (genre label display)
2. ✅ `is_adult` removed from public `/api/public/genres` and `/api/public/tags/search` responses
3. ✅ Frontend public taxonomy types updated (no `is_adult`)
4. ✅ Admin taxonomy dialog still works via `include_adult=true` query parameter

**Public frontend polish (PUBLIC-* phases)**:
1. ✅ Public information architecture
2. ✅ Real catalog data wiring
3. ✅ Loading/error/empty states
4. ✅ Section duplication reduction
5. ✅ Copy polish (de-AI, de-scaffold)
6. ✅ SEO metadata
7. ✅ CTA consistency
8. ✅ Novel detail audit
9. ✅ Reader audit
10. ✅ Account audit + honesty
11. ✅ Auth UX flows
12. ✅ Static trust pages (about, privacy, terms, DMCA, contact, cookie policy)

**Source pipeline hardening (SOURCE-PIPELINE-* phases)**:
1. ✅ SOURCE-PIPELINE-AUDIT-1: full ingestion pipeline audit (4 adapters, storage, orchestration, 197 existing tests reviewed)
2. ✅ SOURCE-PIPELINE-FIX-1: GenericSource hardening — ruby annotation stripping, block-page/age-gate preflight, conservative confidence failure
3. ✅ SOURCE-PIPELINE-FIX-3: KakuyomuSource hardening — block-page/age-gate preflight, UTF-8 force-decode, browser-like User-Agent
4. ✅ SOURCE-PIPELINE-FIX-2A: crawl resilience contract tests (12 tests documenting admin taxonomy preservation, update-mode behavior, failure semantics)
5. ✅ SOURCE-PIPELINE-FIX-2B: per-chapter partial failure handling — failed chapters recorded, remaining chapters continue, summary dict returned
6. ✅ SOURCE-PIPELINE-FIX-2C: per-novel in-process crawl lock — concurrent same-novel scrapes rejected, different-novel scrapes independent

**Source smoke and live compatibility (SOURCE-SMOKE-1, SOURCE-PIPELINE-FIX-3B)**:
1. ✅ Syosetu live smoke: metadata + 1 chapter fetch, temp storage roundtrip, update-mode dedup (n6656lw, 20/20 checks passed)
2. ✅ Kakuyomu work URL canonicalization fixed (trailing slash removed from `_normalize_url`)
3. ✅ Block-page regex false positive fixed (`(?<!re)captcha` excludes "recaptcha" in JSON metadata)
4. ✅ Kakuyomu live smoke: metadata + 1 chapter fetch after fix (822139845959461179)
5. ✅ GenericSource live smoke deferred (no known safe public disposable URL)

**Public homepage data states (PUBLIC-HOME-DATA-* phases)**:
1. ✅ PUBLIC-HOME-DATA-1: real catalog data wiring (useCatalog with sort/limit)
2. ✅ PUBLIC-HOME-DATA-2: polish loading/error/empty states, duplicate section reduction, copy polish

**Public catalog summary enrichment (PUBLIC-SEARCH-1)**:
1. ✅ Backend `PublicNovelSummary` exposes `source_title` (original title when translation differs) and `synopsis`
2. ✅ `source_title` is null when no translation exists (no distinct original)
3. ✅ `synopsis` populated from description field in file-backed metadata
4. ✅ Frontend `PublicNovelSummary` type aligned; homepage uses real `source_title` instead of fallback
5. ✅ NovelCard `DiscoveryNovel` simplified (source_title/synopsis now in base type)
6. ✅ Adult/R18 safety preserved: no `is_adult` in public responses, no `include_adult=true` calls

**Translation resume hardening (TR-RESUME-*)**:
1. ✅ Scheduler resume hardening — paused/resumed translation jobs survive process restart
2. ✅ Runtime state persistence for in-flight translation chunks
3. ✅ Chunk attempt tracking across scheduler cycles
4. ✅ Chunk attempt tracking across scheduler cycles (46/46 tasks)

**Public path performance (PUBLIC-PATH-PERF-*)**:
1. ✅ Frontend bundle size audit & reduction
2. ✅ Image optimization pipeline
3. ✅ Chapter reader lazy loading
4. ✅ Catalog page pagination / virtualisation
5. ✅ Backend response caching for public endpoints (49/49 tasks)

**Glossary system (GLOSSARY-FIRST-*, GLOSSARY-SYNC-*, GLOSSARY-APPLY-*)**:
1. ✅ Glossary-first onboarding — glossary readiness gate on Novel model + API + frontend
2. ✅ Glossary sync bridge — background glossary sync between storage and DB
3. ✅ Glossary apply safety — preview, validation, rollback for glossary application
4. ✅ 3 specs fully implemented (157/157 tasks)

**Operational safety & observability (OPS-SAFETY-*)**:
1. ✅ atomic_write for BackupManager manifest
2. ✅ Logging on parse failure in runtime contracts
3. ✅ Catalog refresh hook after backup restore
4. ✅ request_id correlation in TranslateStage
5. ✅ Runtime state definitions expandable via AdminService
6. ✅ Malformed artifact recovery tests (16 tests)
7. ✅ Backup restore catalog refresh tests (3 tests)
8. ✅ 53/53 tasks complete

**Create-novel-lifecycle**:
1. ✅ End-to-end novel creation flow through all layers (28/28 tasks)

**Prompt translation hardening**:
1. ✅ Prompt structure hardening, injection resistance, test coverage (57/57 tasks)

**Translation QA hardening**:
1. ✅ QA stage hardening, quality metrics, threshold enforcement (52/52 tasks)

### Next

1. Implement object storage boundary (S3/R2/B2)
2. Production deployment (DEP1)
3. Monitor Gemini metadata batch structured output on broader real inputs
4. TAXONOMY-5C: tag `name_ja` display (frontend-only)
5. TAXONOMY-5D: public genre enrichment / label payload decision
6. PUBLIC-LATEST-1: latest updates time grouping
7. PUBLIC-COPY-1: de-AI public copy polish
8. SOURCE-PIPELINE-FIX-4: novel status extraction (ongoing/completed/hiatus)
9. SOURCE-PIPELINE-FIX-5: storage safety (cache TTL, metadata backup, event pruning)
10. GenericSource live smoke (once a safe public disposable URL is identified)
11. Admin provider credential UI (currently env-based only)
12. Broader real-source smoke / manual verification

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
- [x] Email/password public sign-up and sign-in (separate from owner bootstrap)
- [x] Admin-only owner bootstrap login surface
- [x] Public auth UI boundary: no owner/admin/secret/bootstrap wording
- [x] Public taxonomy contract hardened (no `is_adult` leakage)
- [x] Adult taxonomy filtering internal-only (ORM `Genre.is_adult`, `Tag.is_adult`)
- [x] Public catalog summary enrichment preserves adult safety (`source_title`/`synopsis` added, no `is_adult` reintroduced)
- [x] Per-novel in-process crawl lock (prevents concurrent same-novel scrapes; not distributed)
- [x] Block-page detection refined (`(?<!re)captcha` avoids false positives on "recaptcha" in page metadata)
- [ ] Encrypted credential storage (later phase)
- [ ] Security audit logging (schema ready, not wired)
