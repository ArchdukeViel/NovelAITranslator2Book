# Tasks: Authentication and Authorization

## Task List

- [x] 1. Create `User` model and migration
  - [x] 1.1 `backend/src/novelai/db/models/users.py` — full User model with id, email, display_name, role, auth_provider, password_hash, etc. (REQ-1.1)
  - [x] 1.2 Alembic migration `bb48b53baff5_initial_schema.py` creates users table + child tables (REQ-1.3)
  - [x] 1.3 migration `c7d2a91f4b8e` adds password_hash column

- [x] 2. Implement auth dependencies (session-based, not JWT)
  - [x] 2.1 `auth/__init__.py` exists — re-exports `require_role`, `get_current_user`, `SessionUser` (REQ-2)
  - [x] 2.2 `session.py` — `get_current_user` reads user_id/email/role from session. `passwords.py` — Argon2id hash/verify. `roles.py` — `require_role(minimum_role)` with hierarchy guest→user→owner (REQ-2.4, REQ-2.5, REQ-3.1)
  - [x] 2.3 `SessionUser` dataclass in `session.py` — id, email, display_name, role, is_authenticated (REQ-2.4)
  - [x] 2.4 `SESSION_SECRET_KEY` + `SESSION_MAX_AGE` env vars configured (REQ-2.2, REQ-2.3)
  - [x] 2.5 No OAuth2 password bearer — session cookie remains primary auth model as per AGENTS.md §5

- [x] 3. Implement login endpoint (`auth.py`, not `router.py`)
  - [x] 3.1 `POST /api/auth/login` — owner bootstrap via secret constant-time compare (REQ-2.1)
  - [x] 3.2 `POST /api/auth/register` — creates User(role="user") with Argon2 password hash; `POST /api/auth/password/login` — email+password auth (REQ-2.1, REQ-4.3)
  - [x] 3.3 Rate limiting per-action (60s window, in-memory) on login/register/reset/verify (REQ-5.2)
  - [x] 3.4 Auth router registered at /api/auth in `main.py`

- [x] 4. Protect owner endpoints
  - [x] 4.1 `library.py` — `Depends(require_role("owner"))` on all endpoints (REQ-3.2)
  - [x] 4.2 `operations.py` — `Depends(require_role("owner"))` on scrape/import/translate/export (REQ-3.2, REQ-3.3)
  - [x] 4.3 `admin_glossary.py` — `Depends(require_role("owner"))` on all endpoints (REQ-3.2)
  - [x] 4.4 `health.py` — `Depends(require_role("owner"))` on errors endpoint (REQ-3.2)

- [x] 5. Add startup validation and CLI
  - [x] 5.1 `SESSION_SECRET_KEY` validated at startup in `app.py` — falls back to `settings.SECRET_KEY` (REQ-5.1)
  - [x] 5.2 `novelaibook create-user` CLI command — creates password-based user with Argon2id hash (REQ-1.4)
  - [ ] 5.2 Add `novelaibook create-user` CLI command (REQ-1.4)

- [x] 6. Write tests
  - [x] 6.1 `test_auth.py` — 800+ lines, covers login, register, password login, CSRF, rate limits, email verification, password reset, Google OAuth, owner access control
  - [x] 6.2 Invalid credentials → 401 generic (REQ-5.3)
  - [x] 6.3 Unauthenticated access to owner endpoints → 401 (REQ-3.2)
  - [x] 6.4 `password_hash` never in API responses — confirmed by model serialization setup (REQ-5.4)
  - [x] 6.5 Rate limiting tested for login/register/reset (5 attempts/60s per action)
  - [x] 6.6 Session max-age tested (8h default, 28,800s)

- [x] 7. Verify, lint, and type-check
  - [x] 7.1 Auth tests pass (part of 1533 passing tests) — see prior full suite run
  - [x] 7.2 `ruff check backend/src/novelai/api/auth/` — clean (REQ-7.2)
  - [x] 7.3 `pyright` — no auth-related errors
