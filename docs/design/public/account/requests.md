# Account — Requests History Page

## Contract Metadata

| Field | Value |
|---|---|
| Surface | public |
| Domain | account |
| Routes | `/account/requests` |
| Design status | approved |
| Implementation status | implemented |
| Active work | none |
| Implementation | `frontend/app/(public)/account/requests/page.tsx`, `frontend/components/public/request-control.tsx` |

## Purpose
View and track novel and chapter translation requests submitted by the user.

## User Goal
Submit a new request or check approval/completion status of past requests.

## Audience and Permissions
- **Guests:** Displays `LoginPrompt`.
- **Authenticated Users:** Submit requests and view history log.

## Primary Action
Submit request or check request status.

## Information Hierarchy
1. Page Header ("My Requests", Subtitle)
2. Inline Submission Form (`RequestControl`)
3. Filter Bar (Status filter buttons: All, Pending, Approved, Rejected, Completed)
4. Requests Table / List (Request type, novel/source URL, status badge, submission date)

## Page Anatomy
- Form block + Data table container.

## Desktop Layout
Form card + full width requests table.

## Mobile Layout
Form card + stacked mobile list rows.

## Interaction Flow
- Submitting form adds new pending item to history table.
- Filter buttons filter table items by status.

## Authentication or Authorization Behavior
- Requires authenticated user session (`useRequests`).

## States

### Initial
Loading skeletons.

### Loading
Table loading indicator.

### Empty
"No matching requests found."

### Pending
Submitting request mutation in flight.

### Settled
Populated request history list.

### Recoverable Error
"Failed to load requests." with Retry button.

### Unavailable
Backend offline.

### Unauthorized or Forbidden
`LoginPrompt` displayed.

### Success
Toast confirmation on submission.

## Components
- `RequestControl`
- `Badge`
- `Button`

## Content and Copy
- Header: "My Requests"

## Accessibility
- Data table accessible with table headings and keyboard filter buttons.

## Responsive Behavior
- Table transforms into stacked card rows on narrow viewports.

## Data Requirements
- Authenticated user requests list (`useRequests`).

## Privacy, Safety, and Security
- Scoped to authenticated session owner.

## Acceptance Criteria
- Status badges use clear semantic colors (Pending amber, Approved green, Rejected red).

## Implementation Mapping
- `frontend/app/(public)/account/requests/page.tsx`
- `frontend/components/public/request-control.tsx`
