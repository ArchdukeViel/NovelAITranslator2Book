# design.md

# Design: Admin User Management

## Overview

`admin-user-management` adds a secure admin workflow for managing users before V1 launch. The feature gives trusted admins the ability to list and search users, inspect user details, disable or re-enable accounts, promote or demote roles, revoke active sessions, and review an audit trail of admin actions.

This is a V1 launch blocker because production operations need a safe way to respond to abuse, compromised accounts, support requests, and mistaken role assignments without direct database access.

## Goals

* Add an admin-only user management backend API.
* Add an admin frontend page for user list/search and user detail actions.
* Support account disable/enable.
* Support role promotion/demotion.
* Support session revocation for a selected user.
* Persist audit records for all sensitive admin actions.
* Prevent dangerous admin lockout cases.
* Add tests for authorization, action behavior, session invalidation, and audit logging.

## Non-goals

* No public self-service account deletion.
* No billing, subscription, or plan management.
* No password reset flow unless already present.
* No organization/team management.
* No permanent user deletion in V1.
* No full support-ticket system.
* No fine-grained custom permission editor unless roles already support it.

## Actors

### Regular user

A normal authenticated user. They must not access admin user-management APIs or frontend pages.

### Admin user

A trusted user with admin privileges. They can view users and perform admin actions, subject to safety rules.

### System

The backend service that validates permissions, mutates user state, revokes sessions, and writes audit records.

## Role model

The implementation should use the existing role model if one already exists. If the project currently has only a basic `is_admin` flag, this spec can be implemented with that flag first, while keeping the API shape compatible with future role expansion.

Recommended V1 role values:

* `user`
* `admin`

Optional future role values:

* `moderator`
* `owner`
* `support`

For V1, only `admin` can access admin user-management APIs.

## Account status model

The user record should expose a normalized account status.

Recommended statuses:

* `active`
* `disabled`

If the existing schema uses `is_disabled`, `disabled_at`, or similar fields, the API should map those fields into the normalized response.

A disabled account must not be able to authenticate, refresh sessions, access protected APIs, or continue using existing sessions after revocation takes effect.

## Data model

### User fields used by this feature

The feature should use the existing user table/model and add only missing fields required for safe operation.

Recommended fields:

```text
id
email
username or display_name
role
is_disabled
disabled_at
disabled_reason
disabled_by_user_id
created_at
updated_at
last_login_at
session_revoked_at
```

If the project already has equivalent names, prefer existing names and adapt serializers.

### Admin audit log

Add a persistent audit log table/model for admin actions.

Recommended table: `admin_audit_logs`

Recommended fields:

```text
id
actor_user_id
target_user_id
action
reason
before_state_json
after_state_json
metadata_json
request_id
ip_address_hash
user_agent
created_at
```

Recommended action values:

```text
user.disabled
user.enabled
user.role_promoted
user.role_demoted
user.sessions_revoked
```

Audit records should be append-only. Normal admin APIs should not update or delete audit rows.

## Backend architecture

### Components

Recommended backend components:

```text
AdminUserRouter
AdminUserService
AdminAuditService
SessionRevocationService
AdminAuthGuard / require_admin dependency
UserRepository
```

The router should handle HTTP concerns only: auth dependency, request parsing, response models, and error mapping.

The service layer should own business rules:

* Check admin permissions.
* Prevent self-disable.
* Prevent self-demotion where it would remove the current admin’s access.
* Prevent disabling or demoting the last remaining admin.
* Apply user status and role changes.
* Revoke sessions when needed.
* Write audit records atomically with mutations.

The repository layer should encapsulate database queries and pagination.

## API design

All endpoints should be admin-only.

Base path:

```text
/admin/users
```

### List and search users

```http
GET /admin/users
```

Query params:

```text
q?: string
role?: string
status?: active | disabled
page?: number
page_size?: number
sort?: created_at | email | role | status | last_login_at
order?: asc | desc
```

Response:

```json
{
  "items": [
    {
      "id": "user-id",
      "email": "user@example.com",
      "display_name": "User Name",
      "role": "user",
      "status": "active",
      "created_at": "2026-07-10T00:00:00Z",
      "last_login_at": "2026-07-10T00:00:00Z"
    }
  ],
  "page": 1,
  "page_size": 25,
  "total": 1
}
```

### Get user detail

```http
GET /admin/users/{user_id}
```

Response should include:

```text
profile summary
role
status
created_at
updated_at
last_login_at
disabled metadata
session_revoked_at
recent admin audit entries for this user
```

### Disable user

```http
POST /admin/users/{user_id}/disable
```

Request:

```json
{
  "reason": "Compromised account report"
}
```

Behavior:

* Set user as disabled.
* Store disabled timestamp, reason, and actor.
* Revoke active sessions.
* Write audit log.

### Enable user

```http
POST /admin/users/{user_id}/enable
```

Request:

```json
{
  "reason": "Support review completed"
}
```

Behavior:

* Clear disabled state.
* Keep historical audit logs.
* Write audit log.

### Change user role

```http
PATCH /admin/users/{user_id}/role
```

Request:

```json
{
  "role": "admin",
  "reason": "Trusted operator for launch support"
}
```

Behavior:

* Validate target role.
* Prevent lockout or unsafe demotion.
* Update role.
* Write audit log.
* Optionally revoke sessions so role claims refresh immediately.

### Revoke user sessions

```http
POST /admin/users/{user_id}/sessions/revoke
```

Request:

```json
{
  "reason": "Security review"
}
```

Behavior:

* Set `session_revoked_at` to current server time.
* Delete server-side sessions if the app uses Redis/session storage.
* Ensure JWT/session validation rejects tokens issued before `session_revoked_at`.
* Write audit log.

### Admin audit list

Recommended endpoint:

```http
GET /admin/audit
```

Query params:

```text
target_user_id?: string
actor_user_id?: string
action?: string
page?: number
page_size?: number
```

This can be implemented in the same spec or as part of the admin user detail page. At minimum, user detail should show recent audit events for the selected user.

## Authorization and security rules

The backend must enforce authorization even if the frontend hides admin routes.

Required rules:

* Non-admin users receive `403 Forbidden`.
* Unauthenticated users receive `401 Unauthorized`.
* Disabled users cannot use admin APIs.
* Admins cannot disable themselves.
* Admins cannot revoke their own session through the target-user action unless explicitly supported by a separate “sign out everywhere” flow.
* Admins cannot demote themselves if that removes their current admin access.
* The system must prevent disabling or demoting the last remaining admin.
* All sensitive mutations require a non-empty reason.
* All sensitive mutations write an audit log.

## Session revocation design

Use the existing authentication/session mechanism if available.

Recommended approaches:

### Server-side sessions

If sessions are stored in Redis/database:

* Delete all sessions for the target user.
* Set `session_revoked_at` on the user record as a fallback.
* Reject any stale session that still appears after revocation.

### JWT access tokens

If JWTs are stateless:

* Add or use an issued-at claim.
* Store `session_revoked_at` on the user record.
* During auth validation, reject tokens with `iat` earlier than `session_revoked_at`.
* If role is encoded in JWT, revoke sessions on role change so new tokens pick up the new role.

## Frontend design

Add an admin-only page.

Recommended routes:

```text
/admin/users
/admin/users/:userId
```

### User list page

Features:

* Search by email, username, or display name.
* Filter by role.
* Filter by status.
* Paginated table.
* User status badge.
* Role badge.
* Link to user detail.

### User detail page

Features:

* Profile summary.
* Role and status section.
* Disable/enable action.
* Promote/demote role action.
* Revoke sessions action.
* Recent admin audit timeline.
* Confirmation modal for sensitive actions.
* Required reason input for sensitive actions.

### Frontend safety

The UI should:

* Hide admin navigation for non-admin users.
* Still rely on backend authorization.
* Show clear error messages for blocked actions.
* Require confirmation before disable, role change, or session revocation.
* Display audit history after successful mutations.

## Error contract

Use the project’s existing structured error format if one already exists.

Recommended error codes:

```text
admin_required
user_not_found
invalid_role
invalid_status
reason_required
cannot_modify_self
cannot_remove_last_admin
user_already_disabled
user_already_active
session_revocation_failed
audit_log_failed
```

For mutation endpoints, if audit logging fails, the mutation should fail too. Admin-sensitive state changes should not happen without auditability.

## Transaction behavior

For disable, enable, role change, and session revocation:

* Validate actor and target.
* Validate safety rules.
* Apply mutation.
* Write audit record.
* Commit transaction.

If the project uses external Redis/session deletion, the database should still persist `session_revoked_at`. Redis cleanup failure should be surfaced if sessions might remain usable. If `session_revoked_at` is enough to invalidate sessions during auth validation, Redis cleanup can be best-effort and recorded in audit metadata.

## Observability

Log admin mutations with safe metadata:

```text
actor_user_id
target_user_id
action
request_id
success/failure
```

Do not log secrets, raw tokens, passwords, or full personal data.

Metrics can be added later under `metrics-dashboard-baseline`, but this spec should be compatible with future metrics such as:

```text
admin_user_action_total
admin_user_action_failed_total
admin_session_revocation_total
```

## Testing strategy

Backend tests should cover:

* Admin-only access.
* User list/search/filter/pagination.
* User detail.
* Disable user.
* Enable user.
* Promote user.
* Demote user.
* Revoke sessions.
* Audit log creation.
* Self-protection rules.
* Last-admin protection.
* Disabled users cannot authenticate or call protected APIs.
* Revoked sessions are rejected.

Frontend tests should cover:

* Admin users can view admin user pages.
* Non-admin users cannot access admin pages.
* Sensitive actions require confirmation and reason.
* Successful mutations refresh user detail state.
* API errors are displayed clearly.

## Rollout plan

1. Add database fields and audit table.
2. Add backend service and admin API.
3. Add session revocation enforcement to auth validation.
4. Add frontend admin pages.
5. Add tests.
6. Seed or document how to create the first admin.
7. Verify launch checklist:

   * At least one admin exists.
   * Last-admin protection works.
   * Disabled users are blocked.
   * Session revocation invalidates active sessions.
   * Audit records are created for every admin mutation.
