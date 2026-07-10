# tasks.md

# Tasks: Admin User Management

## Task List

* [ ] 0. Preflight review

  * [ ] 0.1 Inspect existing user model, auth dependencies, role fields, disabled-account handling, and session/token validation.
  * [ ] 0.2 Inspect existing admin routes, router registration pattern, Pydantic/schema pattern, and API error format.
  * [ ] 0.3 Inspect existing database migration tooling and model conventions.
  * [ ] 0.4 Inspect existing frontend routing, auth guard, admin layout, table component, modal component, and API client pattern.
  * [ ] 0.5 Inspect existing tests for auth, users, sessions, and frontend route protection.
  * [ ] 0.6 Record exact existing field names before adding new fields to avoid duplicate concepts.

* [ ] 1. Define admin user-management contract

  * [ ] 1.1 Define normalized user summary response for admin list. (REQ-2)
  * [ ] 1.2 Define admin user detail response. (REQ-3)
  * [ ] 1.3 Define disable account request/response. (REQ-4, REQ-10)
  * [ ] 1.4 Define enable account request/response. (REQ-5, REQ-10)
  * [ ] 1.5 Define role change request/response. (REQ-6, REQ-10)
  * [ ] 1.6 Define session revocation request/response. (REQ-7, REQ-10)
  * [ ] 1.7 Define admin audit log response. (REQ-8)
  * [ ] 1.8 Define stable error codes for admin safety failures. (REQ-10)

* [ ] 2. Add or adapt database fields

  * [ ] 2.1 Add missing user disabled-state fields, or map existing fields into the admin API contract. (REQ-4, REQ-5)
  * [ ] 2.2 Add `session_revoked_at` or equivalent session invalidation timestamp if missing. (REQ-7)
  * [ ] 2.3 Ensure user role is persisted in a normalized way or mapped from the existing role/is-admin field. (REQ-6)
  * [ ] 2.4 Add indexes for admin search fields where appropriate, such as email, username/display name, role, status, and created time. (REQ-2)
  * [ ] 2.5 Add migration tests or migration verification according to existing project conventions. (REQ-12)

* [ ] 3. Add admin audit log persistence

  * [ ] 3.1 Create `admin_audit_logs` table/model or equivalent persistent audit store. (REQ-8)
  * [ ] 3.2 Include actor user ID, target user ID, action, reason, before state, after state, metadata, request ID, and timestamp. (REQ-8)
  * [ ] 3.3 Add safe request metadata capture without storing secrets or raw tokens. (REQ-8, REQ-10)
  * [ ] 3.4 Add repository methods to create audit records and query audit history by target user. (REQ-8)
  * [ ] 3.5 Ensure audit records are append-only through normal application APIs. (REQ-8)

* [ ] 4. Add admin authorization guard

  * [ ] 4.1 Implement or reuse a `require_admin` backend dependency. (REQ-1)
  * [ ] 4.2 Ensure unauthenticated requests return `401`. (REQ-1)
  * [ ] 4.3 Ensure authenticated non-admin requests return `403`. (REQ-1)
  * [ ] 4.4 Ensure disabled users cannot use admin endpoints. (REQ-1, REQ-4)
  * [ ] 4.5 Add backend tests for admin-only access. (REQ-1, REQ-12)

* [ ] 5. Implement admin user query service

  * [ ] 5.1 Add user list query with pagination. (REQ-2)
  * [ ] 5.2 Add search by email, username, and display name where those fields exist. (REQ-2)
  * [ ] 5.3 Add role filter. (REQ-2)
  * [ ] 5.4 Add account status filter. (REQ-2)
  * [ ] 5.5 Add safe sorting with an allowlist. (REQ-2, REQ-10)
  * [ ] 5.6 Ensure list responses exclude password hashes, tokens, secrets, and internal credentials. (REQ-2, REQ-10)
  * [ ] 5.7 Add tests for list, search, filters, pagination, sorting, and empty results. (REQ-2, REQ-12)

* [ ] 6. Implement admin user detail service

  * [ ] 6.1 Add lookup by user ID. (REQ-3)
  * [ ] 6.2 Return profile summary, role, status, created/updated timestamps, last login when available, disabled metadata, and session revocation timestamp. (REQ-3)
  * [ ] 6.3 Include recent audit entries or a linked audit endpoint for the selected user. (REQ-3, REQ-8)
  * [ ] 6.4 Return `404` for missing users. (REQ-3, REQ-10)
  * [ ] 6.5 Add tests for detail response, missing user, disabled metadata, and audit metadata. (REQ-3, REQ-12)

* [ ] 7. Implement account disable action

  * [ ] 7.1 Add service method to disable an active target user. (REQ-4)
  * [ ] 7.2 Require a non-empty reason. (REQ-4, REQ-10)
  * [ ] 7.3 Persist disabled timestamp, actor, and reason or equivalent fields. (REQ-4)
  * [ ] 7.4 Revoke the target user’s sessions as part of disable. (REQ-4, REQ-7)
  * [ ] 7.5 Prevent self-disable. (REQ-4)
  * [ ] 7.6 Prevent disabling the last remaining admin. (REQ-4, REQ-11)
  * [ ] 7.7 Write audit log in the same transaction where possible. (REQ-4, REQ-8)
  * [ ] 7.8 Add tests for success, already disabled behavior, self-disable block, last-admin block, session revocation, and audit creation. (REQ-4, REQ-12)

* [ ] 8. Implement account enable action

  * [ ] 8.1 Add service method to enable a disabled target user. (REQ-5)
  * [ ] 8.2 Require a non-empty reason. (REQ-5, REQ-10)
  * [ ] 8.3 Clear or supersede disabled state according to the existing user model. (REQ-5)
  * [ ] 8.4 Preserve historical audit records. (REQ-5, REQ-8)
  * [ ] 8.5 Write audit log in the same transaction where possible. (REQ-5, REQ-8)
  * [ ] 8.6 Add tests for success, already active behavior, audit preservation, and audit creation. (REQ-5, REQ-12)

* [ ] 9. Implement role promotion and demotion

  * [ ] 9.1 Add role validation against allowed V1 roles. (REQ-6, REQ-10)
  * [ ] 9.2 Add service method to change target user role. (REQ-6)
  * [ ] 9.3 Require a non-empty reason. (REQ-6, REQ-10)
  * [ ] 9.4 Prevent unsafe self-demotion. (REQ-6)
  * [ ] 9.5 Prevent demoting the last remaining admin. (REQ-6, REQ-11)
  * [ ] 9.6 Revoke sessions or force permission refresh when role changes affect token/session claims. (REQ-6, REQ-7)
  * [ ] 9.7 Write audit log with before/after role values. (REQ-6, REQ-8)
  * [ ] 9.8 Add tests for promote, demote, invalid role, same-role behavior, self-demotion block, last-admin block, session refresh, and audit creation. (REQ-6, REQ-12)

* [ ] 10. Implement session revocation enforcement

  * [ ] 10.1 Add service method to revoke all sessions for a target user. (REQ-7)
  * [ ] 10.2 Persist `session_revoked_at` or equivalent timestamp. (REQ-7)
  * [ ] 10.3 If server-side sessions exist, delete or invalidate stored sessions for the target user. (REQ-7)
  * [ ] 10.4 If JWTs are used, reject tokens issued before `session_revoked_at`. (REQ-7)
  * [ ] 10.5 Ensure disabled accounts are rejected during auth validation. (REQ-4, REQ-7)
  * [ ] 10.6 Require a non-empty reason for manual session revocation. (REQ-7, REQ-10)
  * [ ] 10.7 Write audit log for manual session revocation. (REQ-7, REQ-8)
  * [ ] 10.8 Add tests proving revoked sessions cannot access protected APIs and new login works for active users. (REQ-7, REQ-12)

* [ ] 11. Add admin API routes

  * [ ] 11.1 Add `GET /admin/users`. (REQ-2)
  * [ ] 11.2 Add `GET /admin/users/{user_id}`. (REQ-3)
  * [ ] 11.3 Add `POST /admin/users/{user_id}/disable`. (REQ-4)
  * [ ] 11.4 Add `POST /admin/users/{user_id}/enable`. (REQ-5)
  * [ ] 11.5 Add `PATCH /admin/users/{user_id}/role`. (REQ-6)
  * [ ] 11.6 Add `POST /admin/users/{user_id}/sessions/revoke`. (REQ-7)
  * [ ] 11.7 Add `GET /admin/audit` or user-scoped audit retrieval if not already included in detail. (REQ-8)
  * [ ] 11.8 Register router with the app using existing route registration conventions. (REQ-1)
  * [ ] 11.9 Add OpenAPI/schema coverage if the project validates generated schemas. (REQ-10)

* [ ] 12. Add frontend admin user-management pages

  * [ ] 12.1 Add admin user list route/page. (REQ-2, REQ-9)
  * [ ] 12.2 Add admin user detail route/page. (REQ-3, REQ-9)
  * [ ] 12.3 Add frontend API client methods for admin user endpoints. (REQ-2 through REQ-8)
  * [ ] 12.4 Add search, role filter, status filter, and pagination controls. (REQ-2, REQ-9)
  * [ ] 12.5 Add status and role badges. (REQ-2, REQ-9)
  * [ ] 12.6 Add action buttons for disable, enable, role change, and session revocation. (REQ-4 through REQ-7, REQ-9)
  * [ ] 12.7 Add confirmation modal with required reason input for sensitive actions. (REQ-9, REQ-10)
  * [ ] 12.8 Refresh user detail state after successful mutations. (REQ-9)
  * [ ] 12.9 Display backend validation and safety errors clearly. (REQ-9, REQ-10)

* [ ] 13. Add frontend route protection

  * [ ] 13.1 Hide admin navigation for non-admin users. (REQ-1, REQ-9)
  * [ ] 13.2 Block or redirect non-admin users who manually open admin routes. (REQ-1, REQ-9)
  * [ ] 13.3 Ensure frontend protection does not replace backend authorization. (REQ-1)
  * [ ] 13.4 Add frontend tests for admin visibility and non-admin blocked state. (REQ-1, REQ-12)

* [ ] 14. Add audit UI

  * [ ] 14.1 Show recent audit events on user detail. (REQ-3, REQ-8, REQ-9)
  * [ ] 14.2 Show action, actor, timestamp, reason, and safe before/after summary. (REQ-8, REQ-9)
  * [ ] 14.3 Add empty state when no audit entries exist. (REQ-8, REQ-9)
  * [ ] 14.4 Add pagination or “view more” if the audit list can grow large. (REQ-8)
  * [ ] 14.5 Add tests for audit timeline rendering. (REQ-8, REQ-12)

* [ ] 15. Add first-admin bootstrap and launch documentation

  * [ ] 15.1 Document how to create or promote the first admin in a new environment. (REQ-11)
  * [ ] 15.2 Add a management command, script, seed path, or documented database-safe process if none exists. (REQ-11)
  * [ ] 15.3 Add a startup/readiness warning or release checklist item when no admin exists. (REQ-11)
  * [ ] 15.4 Verify last-admin protection with tests. (REQ-11, REQ-12)

* [ ] 16. Backend test coverage

  * [ ] 16.1 Add authorization tests for unauthenticated, non-admin, disabled admin, and admin users. (REQ-1, REQ-12)
  * [ ] 16.2 Add user list/search/filter/pagination tests. (REQ-2, REQ-12)
  * [ ] 16.3 Add user detail tests. (REQ-3, REQ-12)
  * [ ] 16.4 Add disable/enable tests. (REQ-4, REQ-5, REQ-12)
  * [ ] 16.5 Add role promotion/demotion tests. (REQ-6, REQ-12)
  * [ ] 16.6 Add session revocation tests for active sessions and new login behavior. (REQ-7, REQ-12)
  * [ ] 16.7 Add audit log tests for every sensitive mutation. (REQ-8, REQ-12)
  * [ ] 16.8 Add validation/error contract tests. (REQ-10, REQ-12)

* [ ] 17. Frontend and integration test coverage

  * [ ] 17.1 Add admin user list rendering test. (REQ-2, REQ-9, REQ-12)
  * [ ] 17.2 Add admin user detail rendering test. (REQ-3, REQ-9, REQ-12)
  * [ ] 17.3 Add confirmation modal/reason-required tests. (REQ-9, REQ-10, REQ-12)
  * [ ] 17.4 Add success-state refresh tests for disable, enable, role change, and revoke sessions. (REQ-4 through REQ-9, REQ-12)
  * [ ] 17.5 Add error display tests for safety-rule failures. (REQ-9, REQ-10, REQ-12)
  * [ ] 17.6 Add E2E smoke test if the project has E2E infrastructure. (REQ-12)

* [ ] 18. Security and observability review

  * [ ] 18.1 Verify admin responses never expose password hashes, tokens, secrets, or internal credentials. (REQ-2, REQ-3, REQ-10)
  * [ ] 18.2 Verify logs redact secrets and do not include raw tokens. (REQ-10)
  * [ ] 18.3 Verify audit records contain enough information for operational review. (REQ-8)
  * [ ] 18.4 Verify all sensitive mutations require a reason. (REQ-4 through REQ-10)
  * [ ] 18.5 Verify database mutations and audit writes are atomic where possible. (REQ-8, REQ-10)
  * [ ] 18.6 Verify rate limiting or abuse protection is inherited from existing admin/API protections, or document follow-up if missing. (REQ-10)

* [ ] 19. Release verification

  * [ ] 19.1 Run database migrations from a clean database. (REQ-11)
  * [ ] 19.2 Create or promote the first admin using the documented path. (REQ-11)
  * [ ] 19.3 Log in as admin and verify user list/search. (REQ-2, REQ-11)
  * [ ] 19.4 Disable a test user and verify login/API access is blocked. (REQ-4, REQ-11)
  * [ ] 19.5 Enable the test user and verify login works again. (REQ-5, REQ-11)
  * [ ] 19.6 Promote and demote a test user and verify permissions refresh correctly. (REQ-6, REQ-11)
  * [ ] 19.7 Revoke sessions and verify old sessions fail. (REQ-7, REQ-11)
  * [ ] 19.8 Verify audit entries exist for each action. (REQ-8, REQ-11)
  * [ ] 19.9 Verify self-protection and last-admin protection. (REQ-4, REQ-6, REQ-11)
  * [ ] 19.10 Mark `admin-user-management` launch blocker complete only after tests and manual verification pass.
