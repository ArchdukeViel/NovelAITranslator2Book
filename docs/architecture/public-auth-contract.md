# Public Auth and User Data Contract

## 0. Status

**Status**: design contract, largely implemented
**Last reviewed**: 2026-06-15 (doc audit refresh)
**Authority**: subordinate to `docs/architecture/architecture.md`

This document defines the target contract for public user authentication and
user-owned public reader features. The Google OAuth backend, public auth
frontend plumbing, `/api/user/*` contract alignment, library/progress/history
UI, reviews/ratings and requests UI, CSRF enforcement, and rate limiting have
been implemented. Contribution credentials remain gated and unavailable.

## 1. Current Repository State

| Area | Repository evidence | Current state |
|---|---|---|
| Owner bootstrap auth | `backend/src/novelai/api/routers/auth.py` | `POST /api/auth/login` accepts an owner bootstrap secret only. It is not public login. |
| Session cookie behavior | `backend/src/novelai/api/app.py`, `backend/src/novelai/api/auth/session.py` | `SessionMiddleware` stores `novelai_session` with `same_site="lax"` and `https_only` in production. Session stores `user_id`, `email`, and `role`. |
| Role support | `backend/src/novelai/api/auth/roles.py` | `guest < user < owner`; `require_role("user")` allows users and owner, guests receive 401. |
| User DB model | `backend/src/novelai/db/models/users.py` | `User` has `email`, `display_name`, `role`, `auth_provider`, `auth_provider_subject`, `is_active`, timestamps. |
| OAuth model support | `backend/src/novelai/db/models/users.py`, `backend/src/novelai/api/auth/google_oauth.py` | Provider and subject fields exist. Google OAuth client and routes (`/api/auth/google/start`, `/api/auth/google/callback`) are implemented. |
| User data endpoints | `backend/src/novelai/api/routers/user_data.py` | `/api/user/library`, `/progress`, `/history`, `/reviews`, and `/requests` exist behind `require_role("user")`. |
| Backend tests | `backend/tests/test_auth.py`, `backend/tests/test_user_data_router.py` | Owner session, role guards, no public signup/JWT route, and basic user-data endpoint behavior are tested. |
| Public auth frontend | `frontend/lib/public-api.ts`, `frontend/hooks/public/use-auth.ts` | Public client exposes `authApi.me`, `authApi.logout`, and `authApi.startGoogleLogin`. No `/api/auth/login` call from public UI. |
| Public user frontend | `frontend/hooks/public/index.ts`, `frontend/lib/public-api.ts` | Guest reader hooks and `/api/user/*` public client methods for library, progress, history, reviews, and requests are re-exported and active. |
| Public UI gates | `frontend/components/public/*`, `frontend/app/(public)/account/*` | Login uses Google OAuth. Library, progress, history, reviews, and requests UI are active for authenticated users. Contribution UI remains gated/unavailable. |

## 2. Public Auth Model

**Decision for v1**: Google OAuth first; email/password later.

Rules:

- Public users use the same HTTP-only session mechanism as the owner session.
- Public OAuth creates or resumes `role="user"` sessions only.
- The owner remains separate. Public OAuth must never create or promote an
  owner account.
- No public self-register password flow in v1.
- `/api/auth/login` remains owner bootstrap login only. Public UI must never
  call it.
- Public auth uses separate OAuth endpoints.

### Endpoint Contract

| Endpoint | Method | Auth | Request | Response | Notes |
|---|---|---|---|---|---|
| `/api/auth/google/start` | GET | Guest | Query: optional `next` relative path | `302` to Google OAuth consent | Sets signed `oauth_state`, nonce, and optional safe return path in session. |
| `/api/auth/google/callback` | GET | Guest | Query: `code`, `state` | `302` to safe frontend path | Validates state/nonce, exchanges code server-side, upserts/resumes user, sets session. |
| `/api/auth/logout` | POST | Any | Empty body | `{ "status": "logged_out" }` | Clears any guest/user/owner session. Existing endpoint may be reused. |
| `/api/auth/me` | GET | Any | None | `AuthUser` | Existing endpoint returns guest, user, or owner session. |
| `/api/auth/login` | POST | Owner bootstrap only | `{ "secret": string }` | `AuthUser` owner on success | Must remain hidden from public UI; consider renaming later only in a dedicated owner-auth migration. |

`AuthUser` response:

```json
{
  "user_id": 123,
  "email": "reader@example.com",
  "role": "user",
  "is_authenticated": true,
  "is_owner": false
}
```

Guest response remains:

```json
{
  "user_id": null,
  "email": null,
  "role": "guest",
  "is_authenticated": false,
  "is_owner": false
}
```

## 3. Identity and Ownership Rules

- Users are identified internally by immutable integer `users.id`.
- Public responses may include `user_id`; user-owned mutation requests must not
  accept `user_id` from the client.
- `email` must be unique case-insensitively after normalization.
- `(auth_provider, auth_provider_subject)` must be unique when present.
- Google OAuth login links to an existing account only when the provider subject
  already matches or when a verified email matches an existing non-owner user
  without another provider link.
- Public OAuth must not link to or create the owner account.
- Public users cannot become owner/admin through OAuth, request payloads, or
  frontend flags.
- Anonymous guests have no server-side saved user data. Guest reading remains
  available without login.
- Library items, progress, history, reviews, and public requests belong to the
  authenticated session user.
- Deactivation sets `is_active=false`, blocks login/session use, and keeps
  content for moderation/audit unless a later deletion policy says otherwise.
- Account deletion should delete or anonymize user-owned saved data according to
  the final privacy policy. Until then, implement deactivation before deletion.

## 4. Public User Feature Contracts

All endpoints require `role >= user` unless explicitly stated. Guests receive
`401 Authentication required`. Authenticated users may only access their own
records. Owner may pass role checks but public UI must not depend on owner
behavior for user features.

### Library

| Operation | Contract |
|---|---|
| List library | `GET /api/user/library` |
| Add novel | `POST /api/user/library/{slug}` |
| Remove novel | `DELETE /api/user/library/{slug}` |
| Auth | `require_role("user")` |
| Add request | No body for v1; optional later `{ "status": "reading" }` |
| Response | `LibraryItem[]` for list; `LibraryItem` for add; `204` for delete |
| Shape | `{ "slug": string, "status": "reading" \| "completed" \| "paused", "added_at": string }` |
| Errors | `401`, `403`, `404 Novel not found`, `409` only if future status conflicts require it |
| Ownership | `user_id` comes only from session |
| Idempotency | Add existing item returns existing item with 200 or 201-compatible message; delete missing item is 204 |
| Future frontend | `userApi.listLibrary`, `userApi.addToLibrary`, `userApi.removeFromLibrary`; hooks `useLibrary`, `useAddToLibrary`, `useRemoveFromLibrary` |
| Required tests | Guest blocked; user A cannot see/remove user B item; add duplicate idempotent; delete missing no-op; unknown slug 404 |

### Reading Progress

| Operation | Contract |
|---|---|
| Get progress | `GET /api/user/progress/{slug}` |
| Upsert progress | `PUT /api/user/progress/{slug}` |
| Auth | `require_role("user")` |
| Request | `{ "chapter_id": string \| null, "progress_percent": number }` |
| Response | `{ "slug": string, "chapter_id": string \| null, "progress_percent": number, "updated_at": string }` |
| Errors | `400` invalid percent/chapter, `401`, `403`, `404 Novel or chapter not found` |
| Ownership | One progress row per `(user_id, novel_id)` |
| Idempotency | `PUT` upserts and may be repeated safely |
| Future frontend | `userApi.getProgress`, `userApi.updateProgress`; hooks `useProgress`, `useUpdateProgress` |
| Required tests | Guest blocked; user A/B isolation; invalid percent rejected; chapter must belong to novel; repeated update overwrites same row |

### Reading History

| Operation | Contract |
|---|---|
| List history | `GET /api/user/history?limit=50&cursor=...` |
| Record history | `POST /api/user/history` |
| Auth | `require_role("user")` |
| Request | `{ "slug": string, "chapter_id": string \| null }` |
| Response | List: `{ "items": HistoryEntry[], "next_cursor": string \| null }`; record: `HistoryEntry` |
| Shape | `{ "id": number, "slug": string, "chapter_id": string \| null, "read_at": string }` |
| Errors | `400`, `401`, `403`, `404 Novel or chapter not found` |
| Ownership | Entries are scoped to session user |
| Idempotency | Recording may create multiple events; later compaction/dedup is a separate policy |
| Future frontend | `userApi.listHistory`, `userApi.recordHistory`; hooks `useHistory`, `useRecordHistory` |
| Required tests | Guest blocked; user A/B isolation; limit cap; newest first; chapter belongs to novel |

### Reviews and Ratings

| Operation | Contract |
|---|---|
| Create/update own review | `PUT /api/user/reviews/{slug}` |
| Delete own review | `DELETE /api/user/reviews/{slug}` |
| Optional public list | `GET /api/public/novels/{slug}/reviews` after moderation design |
| Auth | Mutations require `require_role("user")` |
| Request | `{ "rating": 1..5 \| null, "body": string \| null }` |
| Response | `{ "slug": string, "rating": number \| null, "body": string \| null, "status": "pending" \| "published" \| "rejected", "updated_at": string }` |
| Errors | `400` invalid rating/body, `401`, `403`, `404 Novel not found`, `429` spam limit |
| Ownership | One active review per `(user_id, novel_id)` |
| Idempotency | `PUT` upserts own review; `DELETE` missing own review is 204 |
| Future frontend | `userApi.getMyReview`, `userApi.upsertReview`, `userApi.deleteReview`; hooks `useMyReview`, `useUpsertReview` |
| Required tests | Guest blocked; user A/B isolation; rating bounds; one review per user/novel; spam/rate limit; moderation status not client-controlled |

### Novel and Chapter Requests

| Operation | Contract |
|---|---|
| List own requests | `GET /api/user/requests?limit=50&cursor=...` |
| Create request | `POST /api/user/requests` |
| Auth | `require_role("user")` |
| Request | `{ "request_type": "novel" \| "chapter", "source_url": string \| null, "slug": string \| null, "chapter_id": string \| null, "details": string \| null }` |
| Response | `{ "id": number, "request_type": string, "status": "pending" \| "approved" \| "rejected" \| "completed", "source_url": string \| null, "slug": string \| null, "chapter_id": string \| null, "created_at": string }` |
| Errors | `400` invalid type/body, `401`, `403`, `404 referenced novel/chapter not found`, `429` request limit |
| Ownership | Users list only their own requests; owner moderation uses separate admin endpoints |
| Idempotency | Exact duplicate pending request from same user may return existing request instead of creating another |
| Future frontend | `userApi.listRequests`, `userApi.createRequest`; hooks `useRequests`, `useCreateRequest` |
| Required tests | Guest blocked; user A/B isolation; requests never auto-trigger jobs; duplicate/rate-limit behavior; URL validation; status not client-controlled |

Current backend schema note: `NovelRequest` stores `request_type`, `novel_id`,
`source_url`, `status`, and timestamps. `chapter_id` and `details` may be
validated at request time, but persistence for those fields requires a later
schema migration and must not be faked.

## 5. Frontend Re-enable Plan

The following plan has been largely followed through phases B1–B6. Remaining
items are noted inline.

1. Add public auth methods to `frontend/lib/public-api.ts` only after OAuth
   endpoints exist: `authApi.startGoogleLogin`, `authApi.me`, `authApi.logout`.
2. Add public user methods to `frontend/lib/public-api.ts` only after
   `/api/user/*` response shapes are tested.
3. Re-export hooks from `frontend/hooks/public/index.ts` only when their
   corresponding API contracts are live.
4. Replace unavailable login dialogs with Google login entry points only after
   `/api/auth/google/start` and callback tests pass.
5. Preserve guest catalog, novel detail, and reader behavior when unauthenticated.
6. Account pages should show unavailable or guest-safe states until the relevant
   user feature phase lands.
7. Reader progress tracking must be opt-in for authenticated users and must not
   call `/api/user/*` for guests.

## 6. Security Requirements

- Session cookie: HTTP-only, same-site `lax`, secure in production, scoped to
  the app domain, reasonable max age.
- CSRF: require CSRF protection for cookie-authenticated state-changing
  endpoints. At minimum, use same-site cookies plus a signed CSRF token header
  for POST/PUT/PATCH/DELETE.
- OAuth state/nonce: generate signed unpredictable state and nonce per login
  attempt; validate and clear after callback.
- Redirect URIs: allow only configured backend callback URLs and safe relative
  frontend return paths. Reject open redirects.
- Account takeover: never link OAuth accounts on unverified email; never link a
  public OAuth identity to the owner account.
- Rate limits: login start/callback, review creation/update, request creation,
  and history writes need limits.
- Login abuse: log failed OAuth callbacks without raw tokens; cap repeated
  attempts per IP/session.
- Privacy: reading history is private to the owning user and owner only through
  deliberate admin/audit surfaces, not public endpoints.
- Review spam: cap write frequency, length, duplicate content, and moderation
  status changes.
- Request spam: cap request creation per user/IP and validate source URLs.
- IDOR: every user-owned endpoint must have tests proving user A cannot read,
  update, or delete user B data.
- Secrets: never log OAuth tokens, provider API keys, cookies, authorization
  headers, raw tracebacks, or contributed credentials.

## 7. Implementation Phases

> **Status update (doc audit 2026-06-15)**: Phases B1–B6 have been implemented.
> Google OAuth backend, public auth frontend, `/api/user/*` contract alignment,
> library/progress/history/reviews/requests UI re-enable, and security
> hardening (CSRF, rate limits, session secret fail-closed) are complete.

### Phase B1 - Backend OAuth Foundation ✅

Scope:

- Add Google OAuth settings and provider exchange service.
- Add `GET /api/auth/google/start` and `GET /api/auth/google/callback`.
- Set `role="user"` sessions for public users.

Forbidden:

- Do not alter owner bootstrap semantics.
- Do not add frontend user actions.
- Do not implement email/password login.

Validation:

```bash
./.venv/Scripts/python -m pytest backend/tests/test_auth.py -q
./.venv/Scripts/python -m pytest backend/tests -q
git diff --check
```

### Phase B2 - Backend Public-User Contract Tests ✅

Scope:

- Lock `/api/user/*` request/response shapes.
- Add ownership/IDOR/rate-limit tests.
- Adjust backend implementation only to satisfy the documented contract.

Forbidden:

- Do not change frontend UI.
- Do not implement contributed credentials.

Validation:

```bash
./.venv/Scripts/python -m pytest backend/tests/test_user_data_router.py -q
./.venv/Scripts/python -m pytest backend/tests -q
git diff --check
```

### Phase B3 - Frontend Public Auth API/Hook Reintroduction ✅

Scope:

- Add OAuth start/logout/me methods through `frontend/lib/public-api.ts`.
- Add public auth hooks.
- Replace unavailable login dialog with Google login only after backend tests pass.

Forbidden:

- Do not add `/api/user/*` methods yet.
- Do not call `/api/auth/login` from public UI.

Validation:

```bash
cd frontend && npm run typecheck
cd frontend && npm run build
cd frontend && npm test -- --run
python -m pytest backend/tests/test_frontend_api_contract.py -q
git diff --check
```

### Phase B4 - Library, Progress, and History UI Re-enable ✅

Scope:

- Reintroduce library/progress/history public API methods and hooks.
- Enable save-to-library, continue-reading, and authenticated reader progress.

Forbidden:

- Do not enable reviews/requests in this phase.
- Do not call user endpoints for guests.

Validation:

```bash
cd frontend && npm run typecheck
cd frontend && npm run build
cd frontend && npm test -- --run
./.venv/Scripts/python -m pytest backend/tests/test_user_data_router.py -q
git diff --check
```

### Phase B5 - Reviews and Requests UI Re-enable ✅

Scope:

- Reintroduce review/rating and novel/chapter request methods and hooks.
- Add unavailable-to-authenticated transitions only after backend moderation and
  rate-limit contracts exist.

Forbidden:

- Do not auto-trigger crawl/translation from public requests.
- Do not expose moderation controls on public pages.

Validation:

```bash
cd frontend && npm run typecheck
cd frontend && npm run build
cd frontend && npm test -- --run
./.venv/Scripts/python -m pytest backend/tests/test_user_data_router.py -q
git diff --check
```

### Phase B6 - Security and Rate-Limit Hardening ✅

Scope:

- Add CSRF enforcement for session-authenticated mutations.
- Harden rate limits, login abuse logging, privacy behavior, and audit trails.

Forbidden:

- Do not implement contribution credentials.
- Do not add community folders/lists before moderation exists.

Validation:

```bash
./.venv/Scripts/python -m pytest backend/tests -q
./.venv/Scripts/python -m pyright
cd frontend && npm run typecheck
cd frontend && npm run build
git diff --check
```

## 8. Remaining Guardrails

- Do not route public login through owner bootstrap `/api/auth/login`. Public
  login must use Google OAuth only.
- Do not implement contributed credentials in the public-auth phase.
- Do not build community features before moderation exists.
- Do not add fake endpoints to satisfy UI.
- Do not accept client-supplied `user_id` for user-owned data.
- Do not create or promote owner accounts through public OAuth.
- Do not add email/password self-registration in v1.
