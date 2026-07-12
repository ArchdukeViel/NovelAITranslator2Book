# requirements.md

# Requirements: Frontend Error Boundary and Empty States

## Introduction

The frontend must handle rendering errors, API failures, missing data, empty lists, unavailable services, and partial failures gracefully. Users should see safe, actionable states instead of blank screens or raw technical errors.

## Requirement 1: Root error boundary

### User story

As a user, I want the app to show a safe recovery screen when a fatal frontend error occurs.

### Acceptance criteria

1. WHEN an uncaught rendering error reaches the app root THEN the root error boundary SHALL render a safe fallback.
2. WHEN the root fallback renders THEN it SHALL include a generic safe message.
3. WHEN the root fallback renders THEN it SHOULD include a refresh action.
4. WHEN the root fallback renders THEN it SHOULD include a return-home action where appropriate.
5. WHEN the root fallback renders THEN it SHALL not show stack traces.
6. WHEN the root fallback renders THEN it SHALL not expose source text, translated text, prompts, tokens, or private data.
7. WHEN the root boundary catches an error THEN a safe frontend error log SHOULD be emitted.

## Requirement 2: Route-level error boundaries

### User story

As a user, I want page-level errors to be contained so the rest of the app shell remains usable.

### Acceptance criteria

1. WHEN a public route throws during rendering THEN a route-level fallback SHALL be shown.
2. WHEN an admin route throws during rendering THEN a route-level fallback SHALL be shown.
3. WHEN route-level fallback is shown THEN it SHALL include a safe title and description.
4. WHEN route-level fallback is shown THEN it SHOULD include a retry or navigation action where useful.
5. WHEN route-level fallback is shown THEN focus SHOULD move to the fallback heading.
6. WHEN route error details exist THEN raw technical details SHALL not be shown to normal users.
7. WHEN tests simulate route rendering failure THEN route fallback SHALL render instead of a blank screen.

## Requirement 3: Section/widget error boundaries

### User story

As a user, I want one broken widget to not crash the whole page.

### Acceptance criteria

1. WHEN an optional dashboard widget throws THEN only that widget SHALL show a fallback where practical.
2. WHEN a reader optional feature throws THEN core reader content SHALL remain visible where practical.
3. WHEN an admin summary card throws THEN other cards SHALL remain visible where practical.
4. WHEN a section fallback is shown THEN it SHALL explain that the section could not load.
5. WHEN a section fallback is shown THEN it MAY include retry.
6. WHEN section error is logged THEN logs SHALL use safe fields only.
7. WHEN tests simulate widget failure THEN the parent page SHALL remain rendered.

## Requirement 4: API error normalization

### User story

As a developer, I want API errors normalized so UI states behave consistently.

### Acceptance criteria

1. WHEN an API request fails due to network error THEN it SHALL normalize to `network`.
2. WHEN an API request times out THEN it SHALL normalize to `timeout`.
3. WHEN an API response is `401` THEN it SHALL normalize to `unauthorized`.
4. WHEN an API response is `403` THEN it SHALL normalize to `forbidden`.
5. WHEN an API response is `404` THEN it SHALL normalize to `not_found`.
6. WHEN an API response is `429` THEN it SHALL normalize to `rate_limited`.
7. WHEN an API response is `422` or validation-shaped THEN it SHALL normalize to `validation`.
8. WHEN an API response is `5xx` THEN it SHALL normalize to `server` or `unavailable`.
9. WHEN a backend request ID exists THEN normalized error SHOULD preserve it.
10. WHEN backend error text is unsafe THEN normalized error SHALL replace it with a safe message.

## Requirement 5: Safe user-facing error messages

### User story

As a user, I want understandable error messages that do not expose private internals.

### Acceptance criteria

1. WHEN a network error occurs THEN UI SHALL show a safe connection message.
2. WHEN a timeout occurs THEN UI SHALL show a safe timeout message.
3. WHEN a user is unauthorized THEN UI SHALL guide the user to sign in.
4. WHEN a user is forbidden THEN UI SHALL explain they lack permission.
5. WHEN a resource is not found THEN UI SHALL show a not-found message.
6. WHEN a user is rate-limited THEN UI SHALL show a safe retry-later message.
7. WHEN a validation error occurs THEN UI SHALL show field or form-level guidance.
8. WHEN a server error occurs THEN UI SHALL show a generic safe error.
9. WHEN displaying errors THEN UI SHALL not show stack traces, SQL errors, file paths, provider errors, signed URLs, tokens, or private text.
10. WHEN request ID exists THEN UI MAY show it for support.

## Requirement 6: Consistent loading states

### User story

As a user, I want pages to show clear loading states while data is being fetched.

### Acceptance criteria

1. WHEN a full page is loading THEN a page loading state SHALL be shown.
2. WHEN a table/list is loading THEN a list/table loading state SHALL be shown.
3. WHEN a section/widget is loading THEN a section loading state SHALL be shown.
4. WHEN an action is pending THEN the triggering control SHALL show pending or disabled state where appropriate.
5. WHEN loading state is shown THEN it SHALL include accessible text or semantics.
6. WHEN loading exceeds expected timeout or API fails THEN UI SHALL transition to an error state.
7. WHEN tests inspect loading states THEN they SHALL be identifiable.

## Requirement 7: Consistent empty states

### User story

As a user, I want empty pages and lists to explain what happened and what I can do next.

### Acceptance criteria

1. WHEN a list request succeeds with zero items THEN an empty state SHALL be shown.
2. WHEN search returns zero results THEN a search-specific empty state SHALL be shown.
3. WHEN exports list is empty THEN an export-specific empty state SHALL be shown.
4. WHEN notifications list is empty THEN a notification-specific empty state SHALL be shown.
5. WHEN admin summary has no data THEN a time-range-specific empty state SHOULD be shown.
6. WHEN filters cause empty results THEN UI SHALL distinguish filtered empty from truly empty where practical.
7. WHEN an empty state has a useful next action THEN it SHOULD show a primary action.
8. WHEN tests simulate empty data THEN empty state SHALL render.

## Requirement 8: Public reader fallback states

### User story

As a reader, I want the public reader to show safe states for missing, unavailable, degraded, or partially loaded chapters.

### Acceptance criteria

1. WHEN chapter data is loading THEN reader SHALL show an accessible loading state.
2. WHEN chapter is not found THEN reader SHALL show a safe not-found state.
3. WHEN chapter is unpublished/private/unavailable THEN reader SHALL show safe unavailable or not-found state according to policy.
4. WHEN public reader is degraded but content is available THEN reader SHALL show content and a safe degraded notice where appropriate.
5. WHEN optional annotation loading fails THEN chapter content SHALL remain visible.
6. WHEN reader settings fail to load THEN reader SHALL use safe defaults.
7. WHEN public reader API fails with retryable error THEN retry SHALL be available.
8. WHEN reader fallback renders THEN it SHALL not expose private publication details.

## Requirement 9: Admin page fallback states

### User story

As an admin, I want admin pages to fail gracefully so I can still diagnose or retry.

### Acceptance criteria

1. WHEN admin list data fails to load THEN UI SHALL show safe error and retry where useful.
2. WHEN admin detail data is not found THEN UI SHALL show not-found state.
3. WHEN admin user lacks permission THEN UI SHALL show forbidden state.
4. WHEN admin metrics/analytics widget fails THEN page SHOULD render other widgets where practical.
5. WHEN admin action fails THEN UI SHALL show safe action error.
6. WHEN admin action succeeds THEN UI SHALL show success or refreshed state where appropriate.
7. WHEN request ID exists for admin errors THEN UI SHOULD show it.
8. WHEN admin fallback renders THEN raw backend errors SHALL not be exposed.

## Requirement 10: Form error states

### User story

As a user, I want form errors to be clear and not destroy my input.

### Acceptance criteria

1. WHEN form validation fails THEN field-level errors SHALL be shown near related fields where possible.
2. WHEN form submission fails due to non-field error THEN a form-level error SHALL be shown.
3. WHEN form submission is pending THEN submit control SHALL show pending/disabled state where appropriate.
4. WHEN form submission fails recoverably THEN user input SHALL be preserved.
5. WHEN form is rate-limited THEN safe retry-later message SHALL be shown.
6. WHEN form succeeds THEN success state or navigation SHALL be shown.
7. WHEN form errors are displayed THEN they SHALL be accessible to screen readers.
8. WHEN tests simulate validation and submit errors THEN states SHALL render correctly.

## Requirement 11: Retry actions

### User story

As a user, I want to retry recoverable failures without refreshing the whole app.

### Acceptance criteria

1. WHEN a network error occurs THEN retry SHOULD be available.
2. WHEN a timeout occurs THEN retry SHOULD be available.
3. WHEN a temporary unavailable/server error occurs THEN retry SHOULD be available where operation is safe.
4. WHEN a rate-limited error includes retry timing THEN UI MAY indicate when to retry.
5. WHEN an unauthorized error occurs THEN sign-in action SHOULD be shown instead of retry.
6. WHEN a forbidden error occurs THEN retry SHALL not be the primary action unless permission may change.
7. WHEN a not-found error occurs THEN navigation action SHOULD be shown instead of retry.
8. WHEN retry is clicked THEN the relevant request SHALL be attempted again.
9. WHEN retry is clicked for non-idempotent actions THEN duplicate operation SHALL be avoided unless backend supports idempotency.

## Requirement 12: Partial/degraded states

### User story

As a user, I want usable parts of a page to remain available when optional sections fail.

### Acceptance criteria

1. WHEN a non-critical section fails THEN the page SHOULD render remaining sections.
2. WHEN public reader annotations fail THEN reader content SHALL still render.
3. WHEN export freshness summary fails THEN export list SHOULD still render if available.
4. WHEN admin dashboard widget fails THEN other widgets SHOULD still render.
5. WHEN partial state is shown THEN UI SHALL indicate which section is unavailable.
6. WHEN retry is useful for the failed section THEN section retry SHOULD be available.
7. WHEN tests simulate partial failure THEN available content SHALL remain visible.

## Requirement 13: Frontend error logging

### User story

As a maintainer, I want safe frontend error logs so UI crashes can be diagnosed.

### Acceptance criteria

1. WHEN an error boundary catches an error THEN a safe log SHOULD be emitted.
2. WHEN an unhandled promise rejection occurs THEN a safe log SHOULD be emitted where practical.
3. WHEN an API error occurs THEN a safe log MAY be emitted according to policy.
4. WHEN logs are emitted THEN they MAY include route template, component name, error category, request ID, and build version.
5. WHEN logs are emitted THEN they SHALL not include raw source text, translated text, prompts, tokens, API keys, signed URLs, full request bodies, passwords, or private content.
6. WHEN logging fails THEN UI behavior SHALL not fail.
7. WHEN frontend logging is disabled THEN logging SHALL be no-op.

## Requirement 14: Accessibility of states

### User story

As a keyboard or screen-reader user, I want loading, empty, and error states to be accessible.

### Acceptance criteria

1. WHEN a route-level error appears THEN focus SHOULD move to the error heading.
2. WHEN loading state appears THEN it SHALL include accessible text or status semantics.
3. WHEN critical error appears after user action THEN it SHOULD be announced.
4. WHEN empty state appears THEN it SHALL be real readable text.
5. WHEN retry action appears THEN it SHALL be keyboard accessible.
6. WHEN form errors appear THEN they SHALL be associated with fields where possible.
7. WHEN tests inspect state components THEN accessible names/text SHALL be discoverable.

## Requirement 15: Redaction and privacy

### User story

As an operator, I want frontend fallbacks to never expose sensitive internals.

### Acceptance criteria

1. WHEN an error object contains stack trace THEN UI SHALL not display it.
2. WHEN an error object contains SQL or file path details THEN UI SHALL not display them.
3. WHEN an error object contains provider API error details THEN UI SHALL not display raw details.
4. WHEN an error object contains signed URL or storage path THEN UI SHALL not display it.
5. WHEN an error object contains prompt, source text, or translated text THEN UI SHALL not display it.
6. WHEN an error object contains token, API key, password, or credential THEN UI SHALL not display it.
7. WHEN logs are emitted THEN the same redaction rules SHALL apply.
8. WHEN tests provide unsafe error payloads THEN UI SHALL show safe messages only.

## Requirement 16: Test coverage

### User story

As a maintainer, I want tests for frontend fallback states so regressions do not produce blank screens.

### Acceptance criteria

1. WHEN tests run THEN they SHALL cover root error boundary.
2. WHEN tests run THEN they SHALL cover route-level error boundary.
3. WHEN tests run THEN they SHALL cover section/widget error boundary.
4. WHEN tests run THEN they SHALL cover API error normalization.
5. WHEN tests run THEN they SHALL cover safe message mapping.
6. WHEN tests run THEN they SHALL cover loading states.
7. WHEN tests run THEN they SHALL cover empty states.
8. WHEN tests run THEN they SHALL cover public reader fallback states.
9. WHEN tests run THEN they SHALL cover admin fallback states where admin UI exists.
10. WHEN tests run THEN they SHALL cover form error states.
11. WHEN tests run THEN they SHALL cover retry actions.
12. WHEN tests run THEN they SHALL cover partial/degraded states.
13. WHEN tests run THEN they SHALL cover redaction/privacy rules.
14. WHEN tests run THEN they SHALL cover accessibility of state components where practical.

## Requirement 17: Completion verification

### User story

As a maintainer, I want a clear verification path so this spec is complete only when blank screens and unsafe errors are eliminated from major flows.

### Acceptance criteria

1. WHEN a route component throws in a test fixture THEN route fallback SHALL render.
2. WHEN a widget throws in a test fixture THEN page SHALL remain visible with widget fallback.
3. WHEN public reader API returns not found THEN reader SHALL show safe not-found state.
4. WHEN public reader API returns unavailable/server error THEN reader SHALL show safe retryable error.
5. WHEN list APIs return empty arrays THEN empty states SHALL render.
6. WHEN a form returns validation errors THEN field/form errors SHALL render and input SHALL be preserved.
7. WHEN an unsafe backend error payload is returned THEN UI SHALL not display secrets or stack traces.
8. WHEN retry is clicked for retryable fetch failure THEN request SHALL run again.
9. WHEN frontend fallback states are inspected with keyboard/screen-reader queries THEN they SHALL be accessible.
