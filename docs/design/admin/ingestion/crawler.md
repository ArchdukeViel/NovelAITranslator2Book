# Admin Ingestion — Crawler Control Page

## Contract Metadata

| Field | Value |
|---|---|
| Surface | admin |
| Domain | ingestion |
| Routes | `/admin/crawler` |
| Design status | approved |
| Implementation status | implemented |
| Active work | none |
| Implementation | `frontend/app/(admin)/admin/crawler/page.tsx` |

## Purpose
Operator interface for triggering automated novel web crawls from supported source platforms.

## User Goal
Ingest a new web novel from Syosetu, Kakuyomu, or Novel18 by providing a source URL or novel ID.

## Audience and Permissions
- **Owners (`role="owner"`):** Authorized access.
- **Others:** 403 Forbidden.

## Primary Action
"Start Crawl Job" button.

## Information Hierarchy
1. Page Header ("Novel Crawler", Subtitle)
2. Source Input Form (Source platform select, URL/ID input field, chapter range limit)
3. Advanced Options (Rate limit delay, overwrite existing chapters checkbox)
4. Trigger Button

## Page Anatomy
- Admin panel form container (`Panel`).

## Desktop Layout
Form container (720px max width).

## Mobile Layout
Full width panel container.

## Interaction Flow
- Submitting form validates source URL, triggers crawl background job, and redirects operator to `/admin/activity`.

## Authentication or Authorization Behavior
- Requires owner role (`require_role("owner")`).

## States

### Initial
Empty crawl form ready for input.

### Loading
Form submitting state.

### Empty
Not applicable.

### Pending
Crawl trigger API request in flight.

### Settled
Crawl job queued.

### Recoverable Error
"Failed to trigger crawl job. Check source URL format."

### Unavailable
Backend crawler worker offline.

### Unauthorized or Forbidden
Displays "403 Forbidden - Owner access required."

### Success
Toast notification and redirect to Activity monitor.

## Components
- `Panel`
- `Button`
- `Input`
- `Select`

## Content and Copy
- Header: "Web Novel Ingestion"
- Action: "Queue Crawl Job"

## Accessibility
- Form inputs labeled; clear high contrast focus boundaries.

## Responsive Behavior
- Reflows cleanly across desktop and mobile.

## Data Requirements
- Source key, target novel URL/ID.

## Privacy, Safety, and Security
- Owner-only mutation. Exposes no credentials.

## Acceptance Criteria
- Validates URL hostname against supported source list before dispatching job.

## Implementation Mapping
- `frontend/app/(admin)/admin/crawler/page.tsx`
