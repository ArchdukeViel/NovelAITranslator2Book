# requirements.md

# Requirements: Admin Audit Log Viewer

## Introduction

Admins need a secure audit log viewer for investigating sensitive actions. The viewer must show who performed what action, when, on which target, and with what safe metadata. It must support filtering, pagination, detail views, redaction, and admin-only access.

## Requirement 1: Admin audit page

### User story

As an admin, I want an audit log page so I can review sensitive system actions.

### Acceptance criteria

1. WHEN an admin opens `/admin/audit` THEN the system SHALL display an audit log page.
2. WHEN audit events exist THEN the page SHALL show them in reverse chronological order by default.
3. WHEN no audit events exist THEN the page SHALL show an empty state.
4. WHEN audit events are loading THEN the page SHALL show a loading state.
5. WHEN audit events fail to load THEN the page SHALL show a safe error state.
6. WHEN the page renders THEN it SHALL include filters, event list/table, and pagination where available.
7. WHEN the admin layout has navigation THEN audit log page SHOULD be reachable from admin navigation.

## Requirement 2: Admin-only access

### User story

As an operator, I want audit logs restricted to admins because they contain sensitive operational metadata.

### Acceptance criteria

1. WHEN an unauthenticated user opens the audit page THEN access SHALL be blocked.
2. WHEN a non-admin authenticated user opens the audit page THEN access SHALL be blocked.
3. WHEN an admin opens the audit page THEN access SHALL be allowed.
4. WHEN unauthenticated user calls audit APIs THEN the API SHALL return `401 Unauthorized`.
5. WHEN non-admin calls audit APIs THEN the API SHALL return `403 Forbidden`.
6. WHEN scoped permissions exist THEN audit viewing SHALL require `audit:read` or equivalent.
7. WHEN access is denied THEN audit data SHALL not be included in the response.

## Requirement 3: Audit list API

### User story

As an admin, I want audit events loaded from an API so the viewer reflects real recorded actions.

### Acceptance criteria

1. WHEN the audit page loads THEN it SHALL call an admin audit list API.
2. WHEN the API returns events THEN the UI SHALL render them.
3. WHEN the API returns pagination metadata THEN the UI SHALL use it.
4. WHEN the API returns event fields THEN they SHALL include created time, actor, action, target, status, and severity where available.
5. WHEN legacy events are missing optional fields THEN the UI SHALL render safe fallbacks.
6. WHEN the API fails THEN the UI SHALL show a safe error.
7. WHEN API response includes unsafe fields THEN they SHALL be redacted or omitted before display.

## Requirement 4: Audit detail API

### User story

As an admin, I want to open an audit event detail view so I can inspect the safe context for an action.

### Acceptance criteria

1. WHEN an admin selects an audit event THEN the UI SHALL show a detail view, drawer, modal, or page.
2. WHEN detail view opens THEN it SHALL load or use full audit event details.
3. WHEN details exist THEN the UI SHALL show overview, actor, target, request context, metadata, and changes where available.
4. WHEN the audit event does not exist THEN the UI SHALL show not-found state.
5. WHEN detail loading fails THEN the UI SHALL show a safe error.
6. WHEN legacy event has incomplete fields THEN detail view SHALL render safe fallbacks.
7. WHEN detail is shown THEN unsafe fields SHALL be redacted.

## Requirement 5: Pagination

### User story

As an admin, I want audit events paginated so large audit tables remain usable.

### Acceptance criteria

1. WHEN more events exist than page size THEN pagination controls SHALL be available.
2. WHEN admin changes page THEN the UI SHALL request the selected page.
3. WHEN page size selector exists THEN it SHALL enforce maximum page size.
4. WHEN filters change THEN pagination SHALL reset to a valid page.
5. WHEN requested page is empty due to changed data THEN UI SHALL recover to valid state or show empty state.
6. WHEN pagination metadata is unavailable THEN UI SHALL not pretend full pagination exists.
7. WHEN tests run THEN pagination behavior SHALL be covered.

## Requirement 6: Filtering

### User story

As an admin, I want to filter audit logs so I can investigate specific events quickly.

### Acceptance criteria

1. WHEN admin filters by date range THEN only events in that range SHALL be shown.
2. WHEN admin filters by action THEN matching action events SHALL be shown.
3. WHEN admin filters by target type THEN matching target type events SHALL be shown.
4. WHEN admin filters by actor THEN matching actor events SHALL be shown where supported.
5. WHEN admin filters by status THEN matching status events SHALL be shown.
6. WHEN admin filters by severity THEN matching severity events SHALL be shown.
7. WHEN admin filters by request ID or correlation ID THEN matching events SHALL be shown where supported.
8. WHEN filters produce no results THEN filtered empty state SHALL be shown.
9. WHEN invalid filters are submitted THEN UI SHALL show validation error or API SHALL return validation error.
10. WHEN filters are cleared THEN default audit list SHALL be restored.

## Requirement 7: Search

### User story

As an admin, I want basic search or lookup so I can find events by known identifiers.

### Acceptance criteria

1. WHEN request ID search is supported THEN exact request ID lookup SHALL return matching events.
2. WHEN correlation ID search is supported THEN exact correlation ID lookup SHALL return matching events.
3. WHEN target ID search is supported THEN matching target events SHALL be returned.
4. WHEN action text search is supported THEN matching action events MAY be returned.
5. WHEN search is unsupported THEN UI SHALL not show broken search controls.
6. WHEN search is performed THEN raw metadata full-text search SHALL not expose unsafe data.
7. WHEN tests run THEN supported search behavior SHALL be covered.

## Requirement 8: Redaction

### User story

As an operator, I want audit logs redacted so sensitive values are never displayed.

### Acceptance criteria

1. WHEN audit metadata contains password values THEN they SHALL be redacted.
2. WHEN audit metadata contains tokens, API keys, or credentials THEN they SHALL be redacted.
3. WHEN audit metadata contains signed URLs THEN they SHALL be redacted.
4. WHEN audit metadata contains prompts THEN they SHALL be redacted.
5. WHEN audit metadata contains source or translated chapter text THEN they SHALL be redacted.
6. WHEN audit metadata contains private glossary definitions THEN they SHALL be redacted.
7. WHEN audit metadata contains private filesystem paths or storage credentials THEN they SHALL be redacted.
8. WHEN redaction occurs THEN UI SHALL display a safe redaction marker or omit the field.
9. WHEN tests provide unsafe audit payloads THEN unsafe values SHALL not appear in rendered UI or API response.

## Requirement 9: Before/after changes

### User story

As an admin, I want safe before/after changes so I can understand what changed.

### Acceptance criteria

1. WHEN audit event includes safe change data THEN detail view SHALL show before and after values.
2. WHEN a changed field is safe THEN UI SHALL show field name, previous value, and new value.
3. WHEN a changed field is sensitive THEN previous and new values SHALL be redacted.
4. WHEN change data is unavailable THEN UI SHALL show that field-level changes were not recorded.
5. WHEN change data is malformed THEN UI SHALL show safe fallback.
6. WHEN tests render change data THEN safe diffs and redacted diffs SHALL be covered.

## Requirement 10: Status and severity display

### User story

As an admin, I want status and severity to be clear so I can identify failed or critical actions.

### Acceptance criteria

1. WHEN status is `succeeded` THEN UI SHALL show succeeded state.
2. WHEN status is `failed` THEN UI SHALL show failed state.
3. WHEN status is `denied` THEN UI SHALL show denied state.
4. WHEN status is `partial` THEN UI SHALL show partial state.
5. WHEN status is missing/unknown THEN UI SHALL show unknown state.
6. WHEN severity is critical THEN UI SHALL make it distinguishable without relying only on color.
7. WHEN severity/status badges are rendered THEN they SHALL be accessible.
8. WHEN tests render statuses and severities THEN labels SHALL be discoverable by text or accessible name.

## Requirement 11: Audit event action support

### User story

As an admin, I want all audit event types to render even if the UI does not know a custom label.

### Acceptance criteria

1. WHEN action is known THEN UI SHOULD show a human-readable label.
2. WHEN action is unknown THEN UI SHALL show the raw safe action name.
3. WHEN action has a known target type THEN UI SHOULD show target label.
4. WHEN target label is missing THEN UI SHALL show safe target type and ID where allowed.
5. WHEN legacy audit event uses older action naming THEN UI SHALL still render it.
6. WHEN tests include unknown action THEN UI SHALL not crash.

## Requirement 12: Request context

### User story

As an admin investigating an issue, I want request context such as request ID and correlation ID.

### Acceptance criteria

1. WHEN request ID exists THEN audit list or detail SHALL display it.
2. WHEN correlation ID exists THEN detail view SHOULD display it.
3. WHEN IP hash exists THEN detail view MAY display the hash.
4. WHEN user agent family exists THEN detail view MAY display it.
5. WHEN full raw IP exists THEN it SHALL not be displayed unless policy explicitly allows it.
6. WHEN request context fields are missing THEN UI SHALL render safe fallbacks.
7. WHEN tests render request context THEN safe display and redaction SHALL be covered.

## Requirement 13: Summary cards

### User story

As an admin, I want quick summary counts for the current audit range.

### Acceptance criteria

1. WHEN summary data is available THEN UI SHALL show total events in selected range.
2. WHEN summary data is available THEN UI SHOULD show failed/denied event count.
3. WHEN summary data is available THEN UI SHOULD show critical event count.
4. WHEN summary data is available THEN UI MAY show most recent event time.
5. WHEN summary data fails to load THEN audit event list SHOULD still render where possible.
6. WHEN only page-level counts are available THEN UI SHALL not label them as global range counts.
7. WHEN tests run THEN summary states SHALL be covered where implemented.

## Requirement 14: Optional audit export

### User story

As an admin, I may want to export filtered audit logs for offline review.

### Acceptance criteria

1. WHEN audit export is not implemented THEN UI SHALL not show a broken export action.
2. WHEN audit export is implemented THEN it SHALL be admin-only.
3. WHEN audit export is implemented THEN it SHALL use the same redaction rules as the viewer.
4. WHEN audit export is implemented THEN it SHALL enforce maximum rows/date range.
5. WHEN audit export is requested THEN the request itself SHALL be audited.
6. WHEN audit export fails THEN UI SHALL show safe error.
7. WHEN tests run THEN export authorization and redaction SHALL be covered if implemented.

## Requirement 15: Audit-of-audit behavior

### User story

As a security-conscious operator, I want sensitive audit viewing actions to be recorded.

### Acceptance criteria

1. WHEN an admin opens an audit event detail THEN the system SHOULD record a safe audit/detail-view event where policy requires it.
2. WHEN an admin exports audit logs THEN the system SHALL record an audit/export event if export is implemented.
3. WHEN list view auditing is enabled THEN it SHOULD avoid excessive noisy records or use sampling/policy.
4. WHEN audit-view event is recorded THEN it SHALL not include raw metadata payloads.
5. WHEN audit-view logging fails THEN normal viewer behavior SHALL follow existing audit failure policy.
6. WHEN tests run THEN audit-of-audit behavior SHALL be covered where implemented.

## Requirement 16: Accessibility

### User story

As an admin using keyboard or assistive technology, I want the audit viewer to be accessible.

### Acceptance criteria

1. WHEN audit table renders THEN column headers SHALL be available.
2. WHEN filters render THEN each filter SHALL have an accessible label.
3. WHEN status/severity appears THEN meaning SHALL not rely only on color.
4. WHEN detail drawer/modal opens THEN focus SHALL move into it where appropriate.
5. WHEN detail drawer/modal closes THEN focus SHOULD return to triggering control.
6. WHEN pagination controls render THEN they SHALL be keyboard accessible.
7. WHEN error/empty states render THEN they SHALL use readable text.
8. WHEN tests inspect accessibility labels THEN core controls SHALL be discoverable.

## Requirement 17: Error handling

### User story

As an admin, I want audit viewer failures to be safe and recoverable.

### Acceptance criteria

1. WHEN audit list fails to load THEN UI SHALL show safe error and retry where useful.
2. WHEN audit detail fails to load THEN UI SHALL show safe error and retry where useful.
3. WHEN audit API returns unauthorized THEN UI SHALL show sign-in or unauthorized state.
4. WHEN audit API returns forbidden THEN UI SHALL show forbidden state.
5. WHEN invalid filters are used THEN UI SHALL show validation guidance.
6. WHEN backend returns unsafe error details THEN UI SHALL not display them.
7. WHEN tests simulate API failures THEN safe states SHALL render.

## Requirement 18: Test coverage

### User story

As a maintainer, I want tests for audit viewer behavior so security-sensitive UI does not regress.

### Acceptance criteria

1. WHEN tests run THEN they SHALL cover admin-only access.
2. WHEN tests run THEN they SHALL cover audit list rendering.
3. WHEN tests run THEN they SHALL cover pagination.
4. WHEN tests run THEN they SHALL cover filters.
5. WHEN tests run THEN they SHALL cover detail view rendering.
6. WHEN tests run THEN they SHALL cover redaction.
7. WHEN tests run THEN they SHALL cover safe before/after diffs.
8. WHEN tests run THEN they SHALL cover unknown action rendering.
9. WHEN tests run THEN they SHALL cover request ID/correlation ID display.
10. WHEN tests run THEN they SHALL cover status/severity labels.
11. WHEN tests run THEN they SHALL cover empty/error states.
12. WHEN tests run THEN they SHALL cover accessibility labels.
13. WHEN export is implemented THEN tests SHALL cover export authorization and redaction.

## Requirement 19: Completion verification

### User story

As an operator, I want a clear verification path so audit log viewer is complete only when sensitive changes can be reviewed safely.

### Acceptance criteria

1. WHEN admin opens audit page THEN audit events SHALL be visible.
2. WHEN admin filters by action/date/status THEN matching events SHALL be shown.
3. WHEN admin opens event detail THEN actor, action, target, request context, metadata, and changes SHALL be visible where available.
4. WHEN unsafe audit values exist THEN they SHALL be redacted.
5. WHEN non-admin attempts to access audit page or APIs THEN access SHALL be blocked.
6. WHEN unknown/legacy audit event exists THEN UI SHALL render it safely.
7. WHEN audit API fails THEN UI SHALL show safe recoverable error.
8. WHEN detail view or export is audited by policy THEN safe audit-of-audit records SHALL be created.
