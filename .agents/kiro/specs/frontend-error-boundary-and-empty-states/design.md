# design.md

# Design: Frontend Error Boundary and Empty States

## Overview

`frontend-error-boundary-and-empty-states` adds a consistent frontend resilience layer for user-facing and admin pages.

The app should not collapse into blank screens when a component throws, an API request fails, data is missing, a route is unavailable, or a list is empty. This spec defines reusable error boundaries, loading states, empty states, unavailable states, retry actions, and safe error messaging across the frontend.

This is public-readiness and operator-readiness work. It improves reliability, trust, and debuggability without changing backend business logic.

## Goals

* Add route-level error boundaries.
* Add component-level error boundaries for high-risk areas.
* Add consistent loading, empty, error, unavailable, and degraded states.
* Add retry actions for recoverable failures.
* Add safe error messages that do not expose internals.
* Add frontend logging hooks for unexpected UI errors.
* Add typed API error normalization.
* Prevent blank screens in public reader, admin pages, auth pages, exports, notifications, analytics, and settings.
* Add tests for error boundaries, empty states, retry flows, and redaction.

## Non-goals

* No backend error contract redesign.
* No full observability platform.
* No crash reporting vendor requirement.
* No automatic bug-report submission unless already supported.
* No global redesign of all pages.
* No replacement for accessibility work.
* No replacement for rate limits or abuse protection.
* No user-facing stack traces.

## Target surfaces

Required public surfaces:

```text id="oofkdk"
public novel list
public novel detail
public chapter reader
public search
contact/support/error report pages
legal/support static pages
```

Required authenticated/admin surfaces if present:

```text id="onh9cm"
dashboard
activity pages
novel management pages
glossary pages
translation job pages
export pages
admin users
admin backups
admin health
admin metrics
admin analytics
admin settings
notifications
```

## State taxonomy

Use consistent page states:

```text id="uzcgz9"
loading
empty
error
unavailable
not_found
unauthorized
forbidden
degraded
partial
success
```

Meanings:

```text id="4zirc4"
loading: data is being fetched
empty: request succeeded but there is no data
error: request or rendering failed
unavailable: dependency/service temporarily unavailable
not_found: requested resource does not exist or is not visible
unauthorized: user is not logged in
forbidden: user lacks permission
degraded: page is usable with reduced functionality
partial: some sections failed, but page can still render
success: normal content
```

## Error boundary hierarchy

Recommended hierarchy:

```text id="xi52i8"
AppRootErrorBoundary
RouteErrorBoundary
SectionErrorBoundary
WidgetErrorBoundary
```

### App root boundary

Catches fatal frontend crashes.

Use for:

```text id="c2g0uh"
uncaught rendering failures
route shell failures
layout-level crashes
```

Display:

```text id="yx63hj"
Something went wrong.
Refresh the page or return home.
```

### Route boundary

Catches page-level failures.

Use for:

```text id="wlr6ge"
public reader route
admin route
settings route
export route
analytics route
```

Display route-specific recovery actions:

```text id="ucl63i"
Retry
Back
Home
Open dashboard
```

### Section/widget boundary

Catches partial failures in optional sections.

Use for:

```text id="9sh0m8"
summary cards
charts
notification badge
glossary annotation tooltip
export freshness panel
admin status widgets
```

Display compact section fallback instead of taking down the whole page.

## API error normalization

Add frontend API error normalizer.

Recommended normalized shape:

```ts id="qcekyc"
type NormalizedApiError = {
  code: string;
  message: string;
  status?: number;
  requestId?: string;
  retryable: boolean;
  category:
    | "network"
    | "timeout"
    | "unauthorized"
    | "forbidden"
    | "not_found"
    | "rate_limited"
    | "validation"
    | "server"
    | "unavailable"
    | "unknown";
};
```

Rules:

```text id="tazfku"
never display raw stack traces
never display raw HTML from backend errors
prefer backend safe error.message if trusted
fallback to generic safe messages
preserve request_id for support/debugging
detect retryable categories
```

## Safe user-facing messages

Recommended messages:

```text id="2fj0hx"
network: Could not connect. Check your connection and try again.
timeout: This took too long. Please try again.
unauthorized: Please sign in to continue.
forbidden: You do not have permission to view this page.
not_found: We could not find that page or it is no longer available.
rate_limited: Too many requests. Please try again later.
validation: Check the highlighted fields and try again.
server: Something went wrong. Please try again.
unavailable: This service is temporarily unavailable.
unknown: Something went wrong.
```

Do not show:

```text id="hqulvn"
stack traces
SQL errors
file paths
provider API errors
raw storage paths
signed URLs
tokens
request body
raw prompt text
private chapter text
```

## Empty state design

Every important list should have an empty state.

Recommended empty state fields:

```text id="fbryrz"
title
description
primary action
secondary action optional
icon/illustration optional
```

Examples:

### Public novel list

```text id="zrzzxr"
No novels available yet.
Check back later.
```

### Search results

```text id="czhxes"
No results found.
Try a different search or clear filters.
```

### User activity list

```text id="brmcql"
No activity yet.
Start by adding a novel.
```

### Export list

```text id="08jm5k"
No exports yet.
Generate an export to see it here.
```

### Notifications

```text id="8docyu"
No notifications.
You’re all caught up.
```

### Admin metrics/analytics

```text id="cxh6sl"
No data for this period.
Try another time range.
```

## Loading states

Use consistent loading states.

Recommended:

```text id="5h5mxv"
page skeleton for full page data
section skeleton for cards/tables
button spinner or disabled pending state for actions
status text for accessibility
```

Rules:

```text id="l5thza"
do not show infinite loading forever without timeout/error path
loading state must not shift layout excessively
loading state must be accessible
actions should show pending state to avoid double submit
```

## Retry behavior

Retry should be available for recoverable failures.

Retryable:

```text id="l8lfqf"
network
timeout
rate_limited after retry-after
temporary unavailable
server error where idempotent
```

Not retryable without user changes:

```text id="045jej"
validation error
forbidden
unauthorized unless sign-in changes
not_found
```

Recommended retry UI:

```text id="jd1rox"
Retry
Refresh
Sign in
Go back
Return home
Clear filters
```

Retry actions should not duplicate non-idempotent operations unless the backend supports idempotency.

## Route-specific behavior

### Public reader

States:

```text id="gjm9q4"
loading chapter
chapter not found
chapter unavailable
degraded/fallback served
annotation failure partial state
reader settings failure fallback
```

Behavior:

```text id="a96xft"
chapter text should remain visible even if optional features fail
glossary annotation failure should not break reader
settings load failure should use defaults
```

### Admin pages

States:

```text id="74v3v4"
unauthorized
forbidden
empty data
partial widget failure
backend unavailable
action failure
```

Behavior:

```text id="ld2zk2"
section-level failures should not crash entire admin page where possible
admin actions should show safe errors and request IDs
```

### Forms

States:

```text id="3q8rh2"
field validation error
submit pending
submit success
submit failure
rate limited
```

Behavior:

```text id="9lxdpd"
field errors should be attached to controls
non-field errors should appear near submit area
do not lose user input on recoverable errors
```

## Degraded and partial states

A page can be usable even when optional features fail.

Examples:

```text id="w8k2ta"
reader loads but annotations fail -> show reader without annotations
admin dashboard loads but metrics widget fails -> show widget error only
export list loads but freshness summary fails -> show list and unavailable summary
analytics summary partially fails -> show available groups
```

Use `PartialErrorState` for widgets.

## Frontend logging

Add a safe frontend error logging hook.

Recommended event:

```text id="fck9lw"
frontend.error_boundary_triggered
frontend.api_error
frontend.unhandled_rejection
frontend.route_error
```

Safe fields:

```text id="9eu171"
route_template
component_name
error_code
error_category
request_id
status
build_version
```

Do not log:

```text id="3f30zy"
raw source text
translated text
prompts
tokens
API keys
signed URLs
full request body
passwords
private user content
```

If no logging backend exists, use console in development and no-op in production, or integrate with existing logging.

## Accessibility

Error and empty states must be accessible.

Rules:

```text id="qzwkjj"
state messages are real text
critical errors use appropriate alert/status semantics
retry buttons are keyboard accessible
focus moves to route-level error heading when route fails
form errors are associated with fields
loading states include accessible text
```

## Testing strategy

Tests should cover:

```text id="4zwgp0"
route boundary catches thrown error
section boundary catches widget error
API error normalization
safe message redaction
public reader not found state
public reader unavailable state
empty search state
empty list state
form validation state
retry action calls refetch
partial dashboard failure
unauthorized/forbidden states
loading state accessibility
request ID displayed where available
no stack traces displayed
```

## Rollout plan

1. Audit pages for blank-screen risk.
2. Add API error normalizer.
3. Add shared state components.
4. Add root and route error boundaries.
5. Add section/widget boundaries.
6. Replace ad-hoc loading/error/empty states.
7. Add route-specific fallback states.
8. Add frontend safe logging.
9. Add tests.
10. Verify:

    * errors do not produce blank screens.
    * empty lists have useful guidance.
    * retry works for recoverable failures.
    * raw internals are never shown to users.
