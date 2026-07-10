# requirements.md

# Requirements: Export Manifest Admin UI

## Introduction

Admins need a UI for export history, freshness status, manifest details, and re-export actions. The UI must be admin-only, safe, paginated, filterable, and compatible with existing export manifest and scheduled freshness systems.

## Requirement 1: Admin export manifest list page

### User story

As an admin, I want to view export manifests in one place so I can inspect generated exports.

### Acceptance criteria

1. WHEN an admin opens `/admin/exports` THEN the system SHALL display an export manifest list page.
2. WHEN export manifests exist THEN the page SHALL show them in a table or list.
3. WHEN no export manifests exist THEN the page SHALL show an empty state.
4. WHEN export manifests are loading THEN the page SHALL show a loading state.
5. WHEN export manifest loading fails THEN the page SHALL show a safe error state.
6. WHEN the list renders THEN it SHALL include format, export status, freshness status, generated time, and actions.
7. WHEN existing admin layout/navigation exists THEN the page SHOULD be reachable from admin navigation.

## Requirement 2: Admin-only access

### User story

As an operator, I want export manifest management restricted to admins so export metadata and actions are not exposed publicly.

### Acceptance criteria

1. WHEN an unauthenticated user opens the admin export page THEN access SHALL be blocked.
2. WHEN a non-admin authenticated user opens the admin export page THEN access SHALL be blocked.
3. WHEN an admin opens the admin export page THEN access SHALL be allowed.
4. WHEN an unauthenticated user calls admin export APIs THEN the system SHALL return `401 Unauthorized`.
5. WHEN a non-admin calls admin export APIs THEN the system SHALL return `403 Forbidden`.
6. WHEN a disabled admin is blocked by existing auth policy THEN export admin APIs SHALL follow the same policy.
7. WHEN scoped permissions exist THEN export read and re-export actions SHALL use appropriate permissions.

## Requirement 3: Export manifest list API integration

### User story

As an admin, I want the UI to load export manifest data from backend APIs so it reflects real export state.

### Acceptance criteria

1. WHEN the export page loads THEN it SHALL call an admin export manifest list API.
2. WHEN the API returns items THEN the UI SHALL render those items.
3. WHEN the API returns pagination metadata THEN the UI SHALL use it.
4. WHEN the API returns freshness metadata THEN the UI SHALL render it.
5. WHEN old export records lack freshness metadata THEN the UI SHALL render unknown or unavailable state safely.
6. WHEN the API request fails THEN the UI SHALL show a safe error state.
7. WHEN API response fields are missing unexpectedly THEN the UI SHALL fail gracefully.

## Requirement 4: Filtering and sorting

### User story

As an admin, I want to filter and sort export manifests so I can find stale or problematic exports quickly.

### Acceptance criteria

1. WHEN an admin filters by format THEN the list SHALL show matching export formats.
2. WHEN an admin filters by freshness status THEN the list SHALL show matching freshness statuses.
3. WHEN an admin filters by export status THEN the list SHALL show matching export statuses where supported.
4. WHEN an admin filters by novel/search query THEN the list SHALL show matching export records.
5. WHEN an admin filters by date range THEN the list SHALL show exports generated within that range.
6. WHEN an admin changes sorting THEN the list SHALL reload or reorder according to selected sort.
7. WHEN filters are cleared THEN the list SHALL return to default query.
8. WHEN filters are active and no results match THEN the UI SHALL show a filtered empty state.
9. WHEN unsupported filters are not available in backend APIs THEN the UI SHALL not show broken filter controls.

## Requirement 5: Pagination

### User story

As an admin, I want export manifests paginated so the UI remains usable with many exports.

### Acceptance criteria

1. WHEN the export list has more records than page size THEN pagination controls SHALL be available.
2. WHEN an admin changes page THEN the UI SHALL load the selected page.
3. WHEN an admin changes page size and page size control exists THEN the UI SHALL reload with the selected page size.
4. WHEN pagination metadata is returned by the API THEN the UI SHALL display current page and total where practical.
5. WHEN a page returns no items due to changed filters or deletion THEN the UI SHALL recover to a valid page or show a clear empty state.
6. WHEN pagination is not supported by backend APIs THEN the UI SHALL avoid pretending full pagination exists.

## Requirement 6: Freshness and stale badges

### User story

As an admin, I want clear freshness badges so I can quickly see which exports need attention.

### Acceptance criteria

1. WHEN an export is fresh THEN the UI SHALL show a Fresh badge.
2. WHEN an export is stale THEN the UI SHALL show a Stale badge.
3. WHEN an export artifact is missing THEN the UI SHALL show a Missing badge.
4. WHEN freshness is unknown THEN the UI SHALL show an Unknown badge.
5. WHEN freshness check is in progress THEN the UI SHALL show a Checking badge if that state exists.
6. WHEN freshness check errored THEN the UI SHALL show an Error badge.
7. WHEN a stale reason exists THEN the UI SHALL show a human-readable stale reason.
8. WHEN stale reason is unknown or missing THEN the UI SHALL show a safe unknown reason.
9. WHEN old exports lack freshness data THEN the UI SHALL not incorrectly label them fresh.

## Requirement 7: Manifest detail view

### User story

As an admin, I want to inspect manifest details so I can understand why an export is stale or missing.

### Acceptance criteria

1. WHEN an admin selects an export record THEN the UI SHALL show a detail view, drawer, modal, or page.
2. WHEN detail data loads THEN it SHALL show export identity, novel, format, generated time, and status.
3. WHEN artifact metadata exists THEN it SHALL show safe size, checksum, storage backend, and artifact-exists status.
4. WHEN freshness metadata exists THEN it SHALL show freshness status, checked time, and stale reason.
5. WHEN revision comparison data exists THEN it SHALL show export-time and current revisions where safe.
6. WHEN manifest metadata exists THEN it SHALL show a safe manifest summary or redacted JSON.
7. WHEN detail loading fails THEN the UI SHALL show a safe error state.
8. WHEN an export record is old or incomplete THEN the detail view SHALL show unavailable fields gracefully.

## Requirement 8: Manifest redaction

### User story

As an operator, I want manifest details redacted so the admin UI does not expose secrets or unsafe internals.

### Acceptance criteria

1. WHEN manifest details are displayed THEN raw signed URLs SHALL NOT be shown.
2. WHEN manifest details are displayed THEN storage credentials SHALL NOT be shown.
3. WHEN manifest details are displayed THEN private absolute filesystem paths SHALL NOT be shown.
4. WHEN manifest details are displayed THEN raw prompts SHALL NOT be shown.
5. WHEN manifest details are displayed THEN full source chapter text SHALL NOT be shown.
6. WHEN manifest details are displayed THEN full translated chapter text SHALL NOT be shown.
7. WHEN manifest JSON contains unsafe keys THEN they SHALL be redacted or omitted.
8. WHEN redaction occurs THEN the UI MAY indicate that some values were redacted.

## Requirement 9: Download/open artifact action

### User story

As an admin, I want to open or download an export artifact when it exists so I can verify the generated file.

### Acceptance criteria

1. WHEN an artifact exists and download is allowed THEN the UI SHALL show a download/open action.
2. WHEN an artifact is missing THEN the download/open action SHALL be disabled or hidden.
3. WHEN an artifact is stale and download is allowed THEN the UI SHOULD warn that the artifact may be stale.
4. WHEN an artifact is unavailable due to storage error THEN the UI SHALL show a safe unavailable state.
5. WHEN download/open action is used THEN it SHALL use existing authorized download routes.
6. WHEN download/open action is used THEN it SHALL not expose raw storage keys, signed URLs, credentials, or private paths directly in the UI.
7. WHEN download fails THEN the UI SHALL show a safe error message.

## Requirement 10: Re-export action

### User story

As an admin, I want to re-export stale or missing artifacts so I can regenerate current files.

### Acceptance criteria

1. WHEN an admin views an export record THEN a re-export action SHALL be available where supported.
2. WHEN an admin clicks re-export THEN the UI SHALL ask for confirmation.
3. WHEN the admin confirms THEN the UI SHALL call the re-export API.
4. WHEN re-export is accepted THEN the UI SHALL show success and activity/job link if available.
5. WHEN re-export fails validation THEN the UI SHALL show a safe validation error.
6. WHEN re-export fails due to server error THEN the UI SHALL show a safe error.
7. WHEN re-export is started THEN it SHALL use current source/export inputs, not stale manifest inputs.
8. WHEN re-export creates a new artifact/version THEN existing artifacts SHALL not be overwritten unless existing export policy explicitly allows it.
9. WHEN non-admin users attempt re-export through API THEN access SHALL be blocked.

## Requirement 11: Re-export backend behavior

### User story

As a maintainer, I want re-export requests to use existing export services so behavior stays consistent.

### Acceptance criteria

1. WHEN re-export is requested THEN the backend SHALL validate admin authorization.
2. WHEN re-export is requested THEN the backend SHALL validate the export record exists.
3. WHEN re-export is requested THEN the backend SHALL resolve current novel/chapter/export inputs.
4. WHEN re-export is requested THEN the backend SHALL enqueue an export job or call the existing export service according to project architecture.
5. WHEN an export is already running for the same target and format THEN the backend SHOULD dedupe, reject, or return existing job according to policy.
6. WHEN re-export is accepted THEN the backend SHALL return job/activity/export identifier where available.
7. WHEN re-export cannot be started THEN the backend SHALL return a structured safe error.
8. WHEN re-export is logged THEN logs SHALL not include raw manifest JSON or secrets.

## Requirement 12: Summary cards

### User story

As an admin, I want summary counts so I can quickly understand export health.

### Acceptance criteria

1. WHEN summary data is available THEN the UI SHALL show total export count.
2. WHEN summary data is available THEN the UI SHALL show fresh export count.
3. WHEN summary data is available THEN the UI SHALL show stale export count.
4. WHEN summary data is available THEN the UI SHALL show missing export count.
5. WHEN summary data is available THEN the UI SHALL show unknown/error export count.
6. WHEN freshness run metadata is available THEN the UI SHOULD show last freshness check time.
7. WHEN only current page data is available THEN the UI SHALL not present page-only counts as global counts without labeling them clearly.
8. WHEN summary data fails to load THEN the page SHALL still show the manifest list if available.

## Requirement 13: Compatibility with scheduled freshness

### User story

As an operator, I want the admin UI to display persisted freshness from the scheduled checker when it exists.

### Acceptance criteria

1. WHEN scheduled freshness metadata exists THEN the UI SHALL use it.
2. WHEN freshness status is stale THEN the UI SHALL show the persisted stale reason.
3. WHEN freshness status is missing THEN the UI SHALL show missing artifact state.
4. WHEN freshness status is unknown/error THEN the UI SHALL show safe unknown/error state.
5. WHEN scheduled freshness has never run THEN the UI SHALL show no-run or unknown state where applicable.
6. WHEN scheduled freshness is not implemented yet THEN the UI SHALL still render manifests and avoid claiming scheduled freshness is active.
7. WHEN freshness status updates after a scan THEN refreshing the page SHALL show updated status.

## Requirement 14: Error handling

### User story

As an admin, I want safe and useful errors when export manifest data cannot be loaded or actions fail.

### Acceptance criteria

1. WHEN list loading fails THEN the UI SHALL show a safe error message.
2. WHEN detail loading fails THEN the UI SHALL show a safe error message.
3. WHEN re-export fails THEN the UI SHALL show a safe error message.
4. WHEN download fails THEN the UI SHALL show a safe error message.
5. WHEN backend errors include stack traces or storage errors THEN the UI SHALL not expose them.
6. WHEN a retry action is practical THEN the UI SHOULD provide a retry button.
7. WHEN partial data is available THEN the UI SHOULD display available data with clear unavailable sections.

## Requirement 15: Observability

### User story

As an operator, I want safe logs for admin export actions so I can audit operational activity.

### Acceptance criteria

1. WHEN an admin views the export list THEN the system MAY log a safe list-view event.
2. WHEN an admin views export details THEN the system MAY log a safe detail-view event.
3. WHEN an admin requests re-export THEN the system SHALL log a safe re-export request event.
4. WHEN re-export fails THEN the system SHALL log a safe failure event.
5. WHEN logs are emitted THEN they SHALL include admin user, export ID, format, and safe status where available.
6. WHEN logs are emitted THEN they SHALL not include raw signed URLs, credentials, raw manifest JSON, prompts, or full content.

## Requirement 16: Test coverage

### User story

As a maintainer, I want tests for the export manifest admin UI so admins can safely inspect and regenerate exports.

### Acceptance criteria

1. WHEN tests run THEN they SHALL cover admin export page rendering.
2. WHEN tests run THEN they SHALL cover non-admin access blocked.
3. WHEN tests run THEN they SHALL cover loading, empty, and error states.
4. WHEN tests run THEN they SHALL cover list rendering.
5. WHEN tests run THEN they SHALL cover filters and pagination where implemented.
6. WHEN tests run THEN they SHALL cover freshness badges.
7. WHEN tests run THEN they SHALL cover stale reason labels.
8. WHEN tests run THEN they SHALL cover detail view rendering.
9. WHEN tests run THEN they SHALL cover manifest redaction.
10. WHEN tests run THEN they SHALL cover download/open action states.
11. WHEN tests run THEN they SHALL cover re-export confirmation and success.
12. WHEN tests run THEN they SHALL cover re-export failure.
13. WHEN backend endpoints are added or changed THEN tests SHALL cover API authorization, filtering, detail, redaction, and re-export behavior.

## Requirement 17: Completion verification

### User story

As an operator, I want a clear verification path so the admin export UI is complete only when it can manage stale exports safely.

### Acceptance criteria

1. WHEN admin opens export page THEN export history SHALL be visible.
2. WHEN stale exports exist THEN stale badges and reasons SHALL be visible.
3. WHEN missing exports exist THEN missing badges SHALL be visible.
4. WHEN admin opens manifest detail THEN safe manifest metadata SHALL be visible.
5. WHEN unsafe manifest fields exist THEN they SHALL be redacted.
6. WHEN admin clicks re-export and confirms THEN a re-export job/activity SHALL start or a controlled error SHALL be returned.
7. WHEN non-admin attempts to access the page or APIs THEN access SHALL be blocked.
8. WHEN old manifests without freshness metadata exist THEN the UI SHALL handle them gracefully.
