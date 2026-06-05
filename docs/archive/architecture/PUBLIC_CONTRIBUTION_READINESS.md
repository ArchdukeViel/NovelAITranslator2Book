# Archived Architecture Note

This historical document was consolidated into `docs/architecture/architecture.md`. It may contain stale implementation status and should not be used as current architecture guidance.

# Public Contribution Readiness

## Verdict

Not Ready.

Prompt 12 public contribution credentials should be delayed. The hard gate fails because the current project has neither authenticated registered users nor an `owner_admin` authorization boundary. The current system is still a single-owner/admin deployment protected by an optional shared bearer token.

Required question answers:

| Question | Answer | Evidence |
|---|---:|---|
| Does the project have authenticated registered users? | No | `backend/src/novelai/api/routers/dependencies.py` exposes `verify_api_key`, which checks one configured `WEB_API_KEY` bearer token and does not identify a user. No `auth/` or `accounts/` implementation exists. |
| Does the project have an `owner_admin` authorization boundary? | No | Admin routes use the same `verify_api_key` dependency as other protected routes; there is no role or permission object. |
| Does every user-owned object have backend ownership checks? | No | There are no authenticated user-owned objects. Request fields like `requested_by`, `reviewed_by`, `voter`, and `submitted_by` in `backend/src/novelai/api/routers/requests.py` are caller-provided strings. |
| Does request approval exist? | Partial | `NovelRequestService.update_request_status` can set statuses and `reviewed_by`, but approval is not tied to an authenticated owner/admin and does not gate contributed credential use. |
| Are provider credentials encrypted at rest? | Not applicable / No | There is no persisted provider credential store. `PreferencesService.set_api_key` stores runtime `SecretStr` values only in process settings and explicitly does not persist keys. |
| Is there credential revoke/delete flow? | Admin runtime only | `backend/src/novelai/api/routers/admin.py` has `DELETE /admin/provider-api-key/{provider}` to clear the runtime provider key. There is no stored credential lifecycle, `credential_id`, owner, revoke timestamp, or user deletion flow. |
| Is there security audit logging? | No | Activity/job logs exist, but no `security_audit_service`, credential lifecycle audit schema, or security audit storage exists. |
| Are usage limits represented? | Partially for models, not credentials | Scheduler model state has `rpm_limit`, `rpd_limit`, `requests_this_minute`, and `requests_today`; no per-credential daily/monthly contribution limits exist. |
| Can admin view sanitized credential metadata without raw keys? | Only runtime status | `ProviderApiKeyStatus` returns `configured`, provider/model choices, fallback models, and validation status. It does not return raw keys, but it is not a credential metadata list. |
| Can raw keys ever be returned after creation? | Not by current admin key status endpoints | Admin key endpoints return provider status, not raw keys. Raw keys are accepted in request bodies and can exist in frontend/admin local state before submission. |
| Can frontend API types represent `requesting_user_id`, `credential_owner_user_id`, `credential_id`, `contribution_scope` separately? | No | `frontend/lib/api-types.ts` includes scheduler/job fields but no credential contribution type with these four fields. |
| Can scheduler exclude revoked/disabled credentials? | No | `SchedulerModelStatus.DISABLED` exists, but scheduler state is per provider/model, not per credential, and has no `credential_id` or `revoked_at`. |
| Can scheduler guarantee contributed credentials are used only for approved public-library jobs? | No | There are no contributed credentials, no authenticated requester identity, no approved-public-library eligibility contract, and no credential scope enforcement. |
| Can private user jobs be protected from contributed credentials? | No | There are no private user jobs or object-level user authorization rules in code. |
| Is there clear contribution consent copy? | Architecture only | Consent copy exists in `docs/architecture/architecture.md`, but there is no public credential UI or consent capture. |

## Current Auth Model

The backend has a shared bearer-token gate:

```text
backend/src/novelai/api/routers/dependencies.py
  verify_api_key(credentials)
  -> settings.WEB_API_KEY
  -> allowed shared token list
```

If `WEB_API_KEY` is unset or empty, `verify_api_key` allows the request. If it is set, any valid token receives the same access. The dependency returns `None`, not a user identity, role, or session.

There is no:

- registered user model
- login/logout/session flow
- `current_user` dependency
- `owner_admin` role
- object-level authorization service
- user-owned storage contract

The frontend stores the admin API token in UI state and sends it as `Authorization: Bearer ...` through `frontend/lib/api.ts`. This is appropriate for current owner/admin mode, but it is not public-user authentication.

## Current Request Approval Model

Request storage is file-backed through:

```text
backend/src/novelai/services/novel_request_service.py
```

Routes live in:

```text
backend/src/novelai/api/routers/requests.py
```

The request model supports:

- `requested_by`
- `reviewed_by`
- `status`
- `vote_count`
- `voters`
- source candidates with `submitted_by`

These are plain strings supplied by the caller or admin UI. They are not bound to authenticated users. Status updates can represent an approval-like workflow, but there is no backend guarantee that:

- only an owner admin can approve
- the requester owns the request
- an approved request is public-library eligible
- scheduler credential selection is gated by approval

## Current Credential Model

The current provider key model is runtime/admin-only.

Relevant files:

```text
backend/src/novelai/services/preferences_service.py
backend/src/novelai/api/routers/admin.py
frontend/lib/api-types.ts
frontend/lib/api.ts
```

Current behavior:

- Admin API accepts `api_key` in `ProviderApiKeyRequest`.
- `PreferencesService.set_api_key` writes the key into runtime `settings.PROVIDER_GEMINI_API_KEY` or `settings.PROVIDER_OPENAI_API_KEY` as `SecretStr`.
- `PreferencesService` comments state keys are not persisted to preferences or environment.
- Admin status endpoints return configured status and provider/model metadata, not raw key material.

Missing for Prompt 12:

- `credential_id`
- `user_id` / owner identity
- encrypted API key persistence
- key fingerprint
- contribution enabled flag
- contribution scope
- allowed models
- daily/monthly limits
- revoked/deleted lifecycle
- credential audit events
- sanitized admin credential list
- public user own-credential list

## Missing Product Boundaries

Prompt 12 needs product boundaries that do not exist yet:

- registered public users
- owner/admin role separation
- public-library request semantics
- private user job semantics
- approval queue tied to an authenticated admin
- contribution consent capture
- user-facing credential management
- admin-facing sanitized credential management

Do not fake these boundaries with localStorage IDs, request-provided `requested_by` strings, unsigned cookies, frontend-only flags, or hidden form fields.

## Missing Security Boundaries

Prompt 12 is blocked by missing security foundations:

- no authenticated user identity in backend dependencies
- no `owner_admin` permission check
- no object-level authorization for `credential_id`, `request_id`, `novel_id`, `job_id`, or `activity_id`
- no encrypted credential-at-rest store
- no credential revocation/deletion persistence
- no credential lifecycle audit log
- no contribution usage limits
- no scheduler enforcement of credential scope
- no private-user-job isolation from contributed credentials

Baseline single-owner hardening exists in `docs/architecture/SECURITY_PROTECTION_PLAN.md`, but that document explicitly defers public contribution security until these boundaries are introduced.

## Required Backend Work Before Prompt 12

Implement these before contributed credentials:

1. Authentication/account boundary:
   - registered users
   - secure sessions or token auth
   - backend `current_user` dependency
   - password/OAuth/session lifecycle as chosen by product scope

2. Authorization boundary:
   - `owner_admin` role
   - public reader vs registered user vs owner admin
   - object-level access checks for requests, credentials, jobs, activities, novels, and exports

3. Request approval workflow:
   - authenticated requester
   - authenticated reviewer/admin
   - approval/rejection audit events
   - approved public-library eligibility flag
   - explicit separation from private jobs/uploads

4. Credential service:
   - `provider_credentials_service.py`
   - raw key accepted only on create/rotate
   - encryption/decryption behind service boundary
   - sanitized views only
   - owner and scope enforcement

5. Security audit service:
   - login failures
   - credential created/rotated/revoked/deleted
   - request approved/rejected
   - credential selected for job
   - admin security actions

6. Scheduler integration contract:
   - scheduler-visible sanitized credential state
   - exclude revoked/disabled credentials
   - enforce contribution scope
   - enforce usage caps
   - record both `requesting_user_id` and `credential_owner_user_id`

## Required Frontend Work Before Prompt 12

Add public and admin surfaces only after backend auth/authorization exists:

- public account credential page for a user's own Gemini credentials
- public contribution consent page/control
- admin sanitized credential management page
- admin request approval queue that uses backend authority, not frontend-only flags
- API client methods in `frontend/lib/api.ts`
- typed credential/request ownership models in `frontend/lib/api-types.ts`

Frontend types must represent:

```text
requesting_user_id
credential_owner_user_id
credential_id
contribution_scope
credential status
key_fingerprint
allowed_models
daily/monthly limits
cooldown_until
exhausted_until
revoked_at
```

## Required Storage/Data Model

Add storage contracts for:

- users/accounts
- sessions or auth tokens if file-backed auth is chosen
- roles / owner-admin grants
- provider credentials with encrypted key material
- credential usage counters and history
- security audit events
- request approval events
- scheduler credential state

Credential record requirements:

```text
credential_id
user_id
provider_key
encrypted_api_key
key_fingerprint
label
allowed_models
contribution_enabled
contribution_scope
allowed_novel_ids
daily_request_limit
monthly_request_limit
requests_today
requests_this_month
cooldown_until
exhausted_until
revoked_at
created_at
updated_at
last_used_at
```

Provider request records must include:

```text
requesting_user_id
credential_id
credential_owner_user_id
credential_scope
```

## Required API Routes

Do not add these until auth exists:

```text
POST   /api/me/provider-credentials
GET    /api/me/provider-credentials
PATCH  /api/me/provider-credentials/{credential_id}
DELETE /api/me/provider-credentials/{credential_id}
GET    /api/me/provider-credential-usage

GET    /api/admin/provider-credentials
POST   /api/admin/provider-credentials
PATCH  /api/admin/provider-credentials/{credential_id}
DELETE /api/admin/provider-credentials/{credential_id}
GET    /api/admin/provider-credential-usage

GET    /api/admin/requests
PATCH  /api/admin/requests/{request_id}
```

Backend route rules:

- `/me/*` routes operate only on the authenticated user's own objects.
- `/admin/*` routes require `owner_admin`.
- no route returns raw API keys after creation.
- every route accepting an object ID checks access scope.

## Required Tests

Prompt 12 is not safe without tests for:

- registered user login/session behavior
- admin role enforcement
- user A cannot read/update/delete user B's credentials
- user A cannot approve requests
- admin can approve/reject requests
- raw key is never returned after creation
- raw key is encrypted at rest
- raw key is not logged or returned in error payloads
- credential revoke/delete makes the credential unselectable
- scheduler excludes revoked/disabled credentials
- scheduler uses contributed keys only for approved public-library jobs
- scheduler never uses public contribution keys for private jobs
- usage limits stop selection
- audit events are written for credential and approval actions
- frontend API client uses the correct paths and types

## Do Not Implement Yet

Do not implement public contribution credentials while the current auth model is only `WEB_API_KEY`.

Do not implement:

- public credential UI
- public credential API routes
- admin contributed credential management
- credential pooling
- request-provided user ownership
- localStorage user IDs
- scheduler credential selection
- private/public job routing

These would create a false security boundary.

## Historical Recommended Next Step

At the time, this note recommended delaying Prompt 12. Use `docs/architecture/architecture.md` for the current public-contribution readiness gate.

Recommended sequence:

1. Finish Prompt 11 scheduler for admin-owned provider/model routing only.
2. Design and implement real authentication plus `owner_admin` authorization.
3. Add backend object-level authorization and request approval semantics.
4. Add encrypted credential storage and security audit logging.
5. Re-run this gate.
6. Only then run Prompt 12 public contribution credentials.
