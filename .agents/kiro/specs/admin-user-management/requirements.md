# requirements.md

# Requirements: Admin User Management

## Introduction

The application needs a secure admin user-management feature before V1 launch. Admins must be able to find users, inspect account state, disable or enable accounts, promote or demote roles, revoke sessions, and audit sensitive admin actions.

This feature reduces operational risk by removing the need for direct database edits during support, abuse response, account compromise response, or launch operations.

## Requirement 1: Admin-only access

### User story

As a site operator, I want user-management tools to be restricted to admins so that regular users cannot inspect or modify other accounts.

### Acceptance criteria

1. WHEN an unauthenticated request calls an admin user-management endpoint THEN the system SHALL return `401 Unauthorized`.
2. WHEN an authenticated non-admin calls an admin user-management endpoint THEN the system SHALL return `403 Forbidden`.
3. WHEN a disabled admin account calls an admin user-management endpoint THEN the system SHALL reject the request.
4. WHEN the frontend renders navigation for a non-admin user THEN the system SHALL NOT show admin user-management navigation.
5. WHEN the frontend route is manually opened by a non-admin user THEN the system SHALL show an access-denied state or redirect according to existing app conventions.
6. WHEN authorization is checked THEN the backend SHALL be the source of truth, regardless of frontend visibility.

## Requirement 2: User list, search, filter, and pagination

### User story

As an admin, I want to list and search users so that I can quickly find accounts that need support or moderation.

### Acceptance criteria

1. WHEN an admin opens the user-management page THEN the system SHALL display a paginated list of users.
2. WHEN an admin searches by email, username, or display name THEN the system SHALL return matching users.
3. WHEN an admin filters by role THEN the system SHALL return users with that role.
4. WHEN an admin filters by account status THEN the system SHALL return users with that status.
5. WHEN the result set is larger than the page size THEN the system SHALL return pagination metadata.
6. WHEN no users match the query THEN the system SHALL return an empty result set without an error.
7. WHEN invalid pagination values are supplied THEN the system SHALL return a validation error.
8. WHEN users are listed THEN sensitive data such as password hashes, tokens, secrets, and internal credentials SHALL NOT be returned.

## Requirement 3: User detail view

### User story

As an admin, I want to view user details so that I can understand the account state before taking action.

### Acceptance criteria

1. WHEN an admin opens a user detail page THEN the system SHALL return the selected user’s profile summary, role, status, timestamps, and relevant admin metadata.
2. WHEN the user does not exist THEN the system SHALL return `404 Not Found`.
3. WHEN a user is disabled THEN the detail response SHALL include disabled timestamp, disabled reason when available, and disabling actor when available.
4. WHEN sessions were revoked THEN the detail response SHALL include the latest session revocation timestamp.
5. WHEN audit events exist for the user THEN the detail response SHALL include recent audit events or provide an endpoint to fetch them.
6. WHEN user detail is returned THEN sensitive secrets SHALL NOT be included.

## Requirement 4: Disable account

### User story

As an admin, I want to disable a user account so that compromised or abusive accounts can be blocked from using the system.

### Acceptance criteria

1. WHEN an admin disables an active user with a valid reason THEN the system SHALL mark the account as disabled.
2. WHEN an account is disabled THEN the system SHALL record `disabled_at`, `disabled_by`, and `disabled_reason` or equivalent fields.
3. WHEN an account is disabled THEN the system SHALL revoke active sessions for that user.
4. WHEN a disabled user tries to authenticate THEN the system SHALL reject authentication.
5. WHEN a disabled user uses an existing session THEN the system SHALL reject protected API access.
6. WHEN an admin tries to disable themselves THEN the system SHALL reject the request.
7. WHEN an admin tries to disable the last remaining admin THEN the system SHALL reject the request.
8. WHEN the target account is already disabled THEN the system SHALL return a safe no-op response or a clear validation error according to project conventions.
9. WHEN disable succeeds THEN the system SHALL create an audit log entry.

## Requirement 5: Enable account

### User story

As an admin, I want to re-enable a disabled account so that users can regain access after review.

### Acceptance criteria

1. WHEN an admin enables a disabled user with a valid reason THEN the system SHALL mark the account as active.
2. WHEN an account is enabled THEN the system SHALL preserve historical audit records.
3. WHEN an account is enabled THEN the system SHALL clear or supersede disabled state according to the existing user model.
4. WHEN the target account is already active THEN the system SHALL return a safe no-op response or a clear validation error according to project conventions.
5. WHEN enable succeeds THEN the system SHALL create an audit log entry.
6. WHEN enable fails THEN the system SHALL NOT create a misleading success audit entry.

## Requirement 6: Promote and demote roles

### User story

As an admin, I want to promote or demote user roles so that trusted operators can be granted admin access and unneeded privileges can be removed.

### Acceptance criteria

1. WHEN an admin changes a user role with a valid target role and reason THEN the system SHALL update the user role.
2. WHEN an invalid role is supplied THEN the system SHALL return a validation error.
3. WHEN a role change succeeds THEN the system SHALL create an audit log entry with the previous role and new role.
4. WHEN a role change affects permissions encoded in sessions or tokens THEN the system SHALL revoke sessions or otherwise force permission refresh.
5. WHEN an admin tries to demote themselves in a way that removes their current admin access THEN the system SHALL reject the request.
6. WHEN an admin tries to demote the last remaining admin THEN the system SHALL reject the request.
7. WHEN the requested role is already assigned THEN the system SHALL return a safe no-op response or clear validation error according to project conventions.

## Requirement 7: Revoke user sessions

### User story

As an admin, I want to revoke a user’s sessions so that compromised sessions can be invalidated immediately.

### Acceptance criteria

1. WHEN an admin revokes sessions for a user with a valid reason THEN the system SHALL invalidate existing sessions for that user.
2. WHEN the app uses server-side sessions THEN the system SHALL remove or invalidate stored sessions for the target user.
3. WHEN the app uses JWTs THEN the system SHALL reject tokens issued before the user’s latest session revocation timestamp.
4. WHEN sessions are revoked THEN the system SHALL persist a `session_revoked_at` timestamp or equivalent.
5. WHEN sessions are revoked THEN the system SHALL create an audit log entry.
6. WHEN session revocation partially fails THEN the system SHALL return a clear error unless persisted revocation state guarantees old sessions are rejected.
7. WHEN a revoked session calls a protected API THEN the system SHALL reject it.
8. WHEN a user logs in after revocation and the account is active THEN the system SHALL allow a new valid session.

## Requirement 8: Admin audit logging

### User story

As a site operator, I want sensitive admin actions to be audited so that account changes are accountable and reviewable.

### Acceptance criteria

1. WHEN an admin disables a user THEN the system SHALL create an audit log entry.
2. WHEN an admin enables a user THEN the system SHALL create an audit log entry.
3. WHEN an admin changes a user role THEN the system SHALL create an audit log entry.
4. WHEN an admin revokes sessions THEN the system SHALL create an audit log entry.
5. WHEN an audit log entry is created THEN it SHALL include actor, target, action, timestamp, reason, and before/after state where applicable.
6. WHEN request metadata is available THEN the audit entry SHOULD include request ID, user agent, and safe IP metadata.
7. WHEN a mutation cannot be audited THEN the system SHALL fail the mutation.
8. WHEN audit logs are queried THEN the system SHALL return paginated results.
9. WHEN audit logs are returned THEN the system SHALL NOT expose secrets or sensitive token data.
10. WHEN audit logs are stored THEN they SHALL be append-only through normal application APIs.

## Requirement 9: Admin frontend actions

### User story

As an admin, I want safe UI controls for user actions so that I can perform account operations without direct API calls.

### Acceptance criteria

1. WHEN an admin views the user list THEN the frontend SHALL show search, filters, pagination, role, status, and created/last-login metadata when available.
2. WHEN an admin views user detail THEN the frontend SHALL show account summary, current role, current status, session revocation timestamp, and recent audit history.
3. WHEN an admin disables a user THEN the frontend SHALL require confirmation and a reason.
4. WHEN an admin enables a user THEN the frontend SHALL require confirmation and a reason.
5. WHEN an admin changes a role THEN the frontend SHALL require confirmation and a reason.
6. WHEN an admin revokes sessions THEN the frontend SHALL require confirmation and a reason.
7. WHEN an action succeeds THEN the frontend SHALL refresh the displayed user state.
8. WHEN an action fails THEN the frontend SHALL show a clear error message.
9. WHEN a blocked safety rule is triggered THEN the frontend SHALL display the backend-provided reason where safe.

## Requirement 10: Validation and error handling

### User story

As a developer and operator, I want predictable validation and error responses so that admin actions are safe and debuggable.

### Acceptance criteria

1. WHEN a mutation request omits a required reason THEN the system SHALL reject the request.
2. WHEN a reason exceeds the maximum length THEN the system SHALL reject the request.
3. WHEN a user ID is malformed THEN the system SHALL return a validation error or `404` according to existing conventions.
4. WHEN a target user is missing THEN the system SHALL return `404 Not Found`.
5. WHEN an action violates a safety rule THEN the system SHALL return a stable structured error code.
6. WHEN an unexpected error occurs THEN the system SHALL return a safe error without exposing secrets or stack traces.
7. WHEN admin actions are logged by the application logger THEN secret fields SHALL be redacted.

## Requirement 11: First-admin and launch readiness

### User story

As a deployer, I need a reliable way to create or verify the first admin so that the admin panel is usable after deployment.

### Acceptance criteria

1. WHEN the app is deployed to a new environment THEN there SHALL be a documented way to create or promote the first admin.
2. WHEN no admin exists THEN the system SHALL expose this as a launch readiness problem through documentation, startup check, or admin bootstrap command.
3. WHEN at least one admin exists THEN last-admin protection SHALL prevent removing all admin access.
4. WHEN release verification is performed THEN the checklist SHALL include admin login, user search, disable/enable, role change, session revocation, and audit review.

## Requirement 12: Test coverage

### User story

As a maintainer, I want automated tests for admin user management so that future auth changes do not silently break launch-critical operations.

### Acceptance criteria

1. WHEN backend tests run THEN they SHALL cover admin authorization.
2. WHEN backend tests run THEN they SHALL cover user list/search/filter/pagination.
3. WHEN backend tests run THEN they SHALL cover user detail.
4. WHEN backend tests run THEN they SHALL cover disable and enable behavior.
5. WHEN backend tests run THEN they SHALL cover role promotion and demotion.
6. WHEN backend tests run THEN they SHALL cover session revocation enforcement.
7. WHEN backend tests run THEN they SHALL cover audit log creation.
8. WHEN backend tests run THEN they SHALL cover self-protection and last-admin protection.
9. WHEN frontend tests run THEN they SHOULD cover admin list/detail rendering and sensitive action confirmation.
10. WHEN end-to-end tests are available THEN they SHOULD cover the core admin action path.
