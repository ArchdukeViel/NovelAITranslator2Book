# Admin Moderation — Requests Queue Page

## Contract Metadata

| Field | Value |
|---|---|
| Surface | admin |
| Domain | moderation |
| Routes | `/admin/requests` |
| Design status | approved |
| Implementation status | implemented |
| Active work | none |
| Implementation | `frontend/app/(admin)/admin/requests/page.tsx` |

## Purpose
Operator moderation queue for reviewing novel and chapter requests submitted by public users.

## User Goal
Review pending requests, approve valid novel requests to queue crawl jobs, or reject invalid requests.

## Audience and Permissions
- **Owners (`role="owner"`):** Authorized access.

## Primary Action
"Approve Request" / "Reject Request" actions.

## Information Hierarchy
1. Page Header ("Request Moderation Queue", Status Filter Tabs)
2. Requests Data Table (Request ID, requesting user, source URL/slug, request type, status badge, submission date, actions)

## Page Anatomy
- High-density moderation data table with inline Approve/Reject action buttons.

## Desktop Layout
Full width data table.

## Mobile Layout
Horizontal scrolling table container.

## Interaction Flow
- Clicking "Approve" sets status to approved and optionally triggers crawl.
- Clicking "Reject" opens modal to input rejection reason note.

## Authentication or Authorization Behavior
- Requires owner role (`require_role("owner")`).

## States

### Initial
Loading table skeletons.

### Loading
Table pulse loading.

### Empty
"No pending requests to review."

### Pending
Approve/Reject mutation in flight.

### Settled
Populated moderation table.

### Recoverable Error
"Failed to load requests queue."

### Unavailable
Backend offline.

### Unauthorized or Forbidden
403 Forbidden.

### Success
Toast confirmation on request approval/rejection.

## Components
- `Table`
- `Button`
- `Badge`

## Content and Copy
- Header: "Public Request Moderation"

## Accessibility
- Data table headers bound; action buttons labeled.

## Responsive Behavior
- Table scrolls horizontally on narrow viewports.

## Data Requirements
- Paginated requests list with status filter.

## Privacy, Safety, and Security
- Owner-only access. Emits audit log events.

## Acceptance Criteria
- Approving a request updates status immediately and emits audit event.

## Implementation Mapping
- `frontend/app/(admin)/admin/requests/page.tsx`
