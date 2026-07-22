# Requirements: Authentication and Authorization

## Introduction

All owner API endpoints (`/scrape`, `/import`, `/translate`, and other admin routes) currently accept unauthenticated requests. There is no user model, no token-based authentication, and no role-based access control. Any client can trigger expensive operations like translation or scraping, which risks abuse, quota exhaustion, and exposure of unpublished content.

This spec adds a user model with secure credential storage, JWT-based authentication for owner endpoints, role-based access control, and a login endpoint for token issuance.

## Requirements

### REQ-1: User Model and Credential Storage

A user model must be created for authentication.

- REQ-1.1: Create a `User` SQLAlchemy model in `backend/src/novelai/db/models/user.py` with fields: `id` (int PK), `username` (str, unique), `email` (str, unique), `password_hash` (str), `role` (str, default `"owner"`), `is_active` (bool, default True), `created_at` (datetime), `updated_at` (datetime).
- REQ-1.2: Passwords must be hashed using `bcrypt` via `passlib` before storage. Plaintext passwords must never be stored or logged.
- REQ-1.3: An Alembic migration must be created for the `users` table.
- REQ-1.4: A CLI command `novelai create-user <username> <email>` must exist to create the initial owner account interactively (prompts for password securely).

### REQ-2: Token-Based Authentication

JWT access tokens must be used to authenticate API requests.

- REQ-2.1: Implement `POST /api/auth/login` accepting `username` and `password` in the request body. On success, return an access token (`access_token`) and token type (`"bearer"`). On failure, return HTTP 401 with `"Invalid credentials"`.
- REQ-2.2: The access token must be a JWT signed with `HS256` using a secret key from the environment variable `JWT_SECRET_KEY`.
- REQ-2.3: The token must include claims: `sub` (user id), `username`, `role`, `exp` (expiration). Default expiration: 24 hours, configurable via `JWT_EXPIRY_HOURS`.
- REQ-2.4: Implement `TokenPayload` Pydantic model for decoding and validating JWT tokens.
- REQ-2.5: Implement a `get_current_user` FastAPI dependency that extracts and validates the JWT from the `Authorization: Bearer <token>` header, queries the user from the database, and raises HTTP 401 if the token is missing, expired, or invalid.
- REQ-2.6: If a user's `is_active` is `False`, authentication must fail with HTTP 403.

### REQ-3: Role-Based Access Control

Protected endpoints must require specific roles.

- REQ-3.1: Implement `require_role(role: str)` FastAPI dependency that calls `get_current_user` and checks the user's role. Raises HTTP 403 if the role does not match.
- REQ-3.2: All existing owner endpoints must use `Depends(require_role("owner"))` to enforce authentication.
- REQ-3.3: Existing endpoints must be individually audited and updated:
  - `POST /{novel_id}/scrape` — owner only
  - `POST /{novel_id}/import` — owner only
  - `POST /{novel_id}/translate` — owner only
  - `POST /api/admin/novels` — owner only
  - `GET /api/admin/novels/{id}` — owner only
  - `POST /{novel_id}/glossary` — owner only
  - `GET /api/admin/health/errors` — owner only

### REQ-4: Swagger/OpenAPI Documentation

The auth scheme must be documented in the API.

- REQ-4.1: The FastAPI app must include an OAuth2 password bearer scheme in the OpenAPI docs so the "Authorize" button appears in `/docs`.
- REQ-4.2: Protected endpoints must show a lock icon in Swagger UI.
- REQ-4.3: The login endpoint must be documented with request/response schemas.

### REQ-5: Security Hardening

- REQ-5.1: The `JWT_SECRET_KEY` must be required at startup. If not set, the application must refuse to start with a clear error message.
- REQ-5.2: Login attempts must be rate-limited (max 5 failed attempts per minute per IP) to prevent brute-force attacks.
- REQ-5.3: Auth-related errors must never leak whether a username exists vs. password is wrong. Return the same message: `"Invalid credentials"`.
- REQ-5.4: The `password_hash` field must never be included in API responses or serialized output.

## Non-Goals

- This spec does not add public user registration or Google OAuth (already exists for public users).
- This spec does not change the existing public endpoints or their auth behavior.
- This spec does not add multi-factor authentication.
- This spec does not add API key-based authentication (only JWT for now).
- This spec does not change the frontend login flow.
