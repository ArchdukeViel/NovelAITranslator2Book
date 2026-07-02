# Tasks: Authentication and Authorization

## Task List

- [ ] 1. Create `User` model and migration
  - [ ] 1.1 Create `backend/src/novelai/db/models/user.py` with `User` SQLAlchemy model (REQ-1.1)
  - [ ] 1.2 Generate Alembic migration for `users` table (REQ-1.3)
  - [ ] 1.3 Run migration and verify table creation

- [ ] 2. Implement auth dependencies
  - [ ] 2.1 Create `backend/src/novelai/api/auth/__init__.py` (REQ-2)
  - [ ] 2.2 Implement `dependencies.py` with `hash_password`, `create_access_token`, `decode_token`, `get_current_user`, `require_role` (REQ-2.4, REQ-2.5, REQ-3.1)
  - [ ] 2.3 Implement `TokenPayload` Pydantic model (REQ-2.4)
  - [ ] 2.4 Configure JWT via `JWT_SECRET_KEY` and `JWT_EXPIRY_HOURS` env vars (REQ-2.2, REQ-2.3)
  - [ ] 2.5 Add OAuth2 password bearer scheme for Swagger docs (REQ-4.1)

- [ ] 3. Implement login endpoint
  - [ ] 3.1 Create `backend/src/novelai/api/auth/router.py` with `POST /api/auth/login` (REQ-2.1)
  - [ ] 3.2 Define `LoginRequest` and `TokenResponse` Pydantic schemas (REQ-2.1, REQ-4.3)
  - [ ] 3.3 Add rate limiting (5 attempts/min per IP) (REQ-5.2)
  - [ ] 3.4 Register auth router in `main.py`

- [ ] 4. Protect owner endpoints
  - [ ] 4.1 Update `library.py` — add `Depends(require_role("owner"))` to admin endpoints (REQ-3.2)
  - [ ] 4.2 Update `operations.py` — add to scrape/import/translate endpoints (REQ-3.2, REQ-3.3)
  - [ ] 4.3 Update `admin_glossary.py` — add to glossary mutation endpoints (REQ-3.2)
  - [ ] 4.4 Update `health.py` — add to `/health/errors` (REQ-3.2)

- [ ] 5. Add startup validation and CLI
  - [ ] 5.1 Validate `JWT_SECRET_KEY` at startup in `main.py` (REQ-5.1)
  - [ ] 5.2 Add `novelai create-user` CLI command (REQ-1.4)

- [ ] 6. Write tests
  - [ ] 6.1 Test `POST /api/auth/login` with valid credentials returns token
  - [ ] 6.2 Test login with invalid credentials returns 401 with generic message (REQ-5.3)
  - [ ] 6.3 Test unauthenticated access to owner endpoints returns 401 (REQ-3.2)
  - [ ] 6.4 Test `password_hash` never appears in API responses (REQ-5.4)
  - [ ] 6.5 Test rate limiting blocks after 5 failed attempts
  - [ ] 6.6 Test token expiration

- [ ] 7. Verify, lint, and type-check
  - [ ] 7.1 Run `pytest backend/tests/ --tb=short -q` and confirm all pass
  - [ ] 7.2 Run `ruff check backend/src/novelai/api/auth/` and fix issues
  - [ ] 7.3 Run `pyright` and fix type errors
