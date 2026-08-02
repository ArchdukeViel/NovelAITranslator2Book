# Admin Operations — Dashboard Page

## Contract Metadata

| Field | Value |
|---|---|
| Surface | admin |
| Domain | operations |
| Routes | `/admin`, `/admin/dashboard` |
| Design status | approved |
| Implementation status | implemented |
| Active work | none |
| Implementation | `frontend/app/(admin)/admin/dashboard/page.tsx`, `frontend/app/(admin)/admin/page.tsx` |

## Purpose
System overview landing page providing quick health metrics, job status cards, and recent activity feeds.

## User Goal
Inspect overall platform health, active translation jobs, pending requests, and system status at a glance.

## Audience and Permissions
- **Owners (`role="owner"`):** Authorized access.

## Primary Action
Inspect system metrics and navigate to active operational queues.

## Information Hierarchy
1. Page Header ("Operator Dashboard", System Health Badge)
2. Metrics Grid Cards (Total Novels, Active Translation Jobs, Pending Requests, Pending Reviews, Database Storage Usage)
3. Recent Activity Stream
4. Quick Action Buttons (Launch Crawl, Dispatch Translation, Review Requests)

## Page Anatomy
- 4-column metric cards grid + recent activity log pane.

## Desktop Layout
4-column card grid + 2-column lower section (activity log + quick actions).

## Mobile Layout
Single column stacked card flow.

## Interaction Flow
- Clicking metric card navigates to corresponding admin queue (e.g. Pending Requests -> `/admin/requests`).

## Authentication or Authorization Behavior
- Requires owner role (`require_role("owner")`).

## States

### Initial
Loading metric skeletons.

### Loading
Pulse loading on status cards.

### Empty
Not applicable.

### Pending
Not applicable.

### Settled
Populated dashboard metrics.

### Recoverable Error
"Failed to load dashboard metrics." with Retry button.

### Unavailable
Backend offline.

### Unauthorized or Forbidden
403 Forbidden.

### Success
Not applicable.

## Components
- `Panel`
- `Badge`
- `Button`

## Content and Copy
- Header: "Dokushodo Operator Dashboard"

## Accessibility
- Metric cards use proper headings and accessible text summaries.

## Responsive Behavior
- Reflows from 4 columns on desktop to 1 column on mobile.

## Data Requirements
- System health probe data, aggregate database counts.

## Privacy, Safety, and Security
- Exposes no credentials, secret tokens, or private paths.

## Acceptance Criteria
- System health status badge reflects live `/health/ready` probe.

## Implementation Mapping
- `frontend/app/(admin)/admin/dashboard/page.tsx`
